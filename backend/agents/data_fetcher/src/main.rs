use std::{env, process, sync::Arc, time::Duration};
use anyhow::{Context, Result};
use tokio::{sync::RwLock, time};
use tracing::{info, error, Level};
use tracing_subscriber::FmtSubscriber;
use serde::{Deserialize, Serialize};
use reqwest::Client;
use chrono::{DateTime, Utc};
use rskafka::{
    client::{
        ClientBuilder,
        partition::{Compression, PartitionClient},
    },
    record::Record,
};
use async_trait::async_trait;

#[derive(Debug, Deserialize)]
struct Config {
    kafka_bootstrap_servers: String,
    kafka_topic_in: String,
    kafka_topic_out: String,
    kafka_group_id: String,
    api_request_timeout: u64,
    poll_interval: u64,
}

impl Config {
    fn from_env() -> Result<Self> {
        Ok(Self {
            kafka_bootstrap_servers: env::var("KAFKA_BOOTSTRAP_SERVERS").unwrap_or_else(|_| "localhost:9092".to_string()),
            kafka_topic_in: env::var("KAFKA_TOPIC_IN").unwrap_or_else(|_| "data_fetch_requests".to_string()),
            kafka_topic_out: env::var("KAFKA_TOPIC_OUT").unwrap_or_else(|_| "data_fetch_results".to_string()),
            kafka_group_id: env::var("KAFKA_GROUP_ID").unwrap_or_else(|_| "data_fetcher_group".to_string()),
            api_request_timeout: env::var("API_REQUEST_TIMEOUT")
                .ok()
                .and_then(|v| v.parse().ok())
                .unwrap_or(30),
            poll_interval: env::var("POLL_INTERVAL")
                .ok()
                .and_then(|v| v.parse().ok())
                .unwrap_or(1000),
        })
    }
}

#[derive(Debug, Deserialize)]
struct FetchRequest {
    task_id: String,
    url: String,
    method: Option<String>,
    headers: Option<serde_json::Value>,
    params: Option<serde_json::Value>,
    body: Option<serde_json::Value>,
    timeout: Option<u64>,
    retry_count: Option<u8>,
}

#[derive(Debug, Serialize)]
struct FetchResult {
    task_id: String,
    url: String,
    status: String,
    status_code: Option<u16>,
    headers: Option<serde_json::Value>,
    data: Option<serde_json::Value>,
    error: Option<String>,
    fetched_at: DateTime<Utc>,
    elapsed_time: u128,
}

#[async_trait]
trait DataFetcher {
    async fn fetch(&self, request: FetchRequest) -> FetchResult;
}

struct HttpFetcher {
    client: Client,
    timeout: Duration,
}

impl HttpFetcher {
    fn new(timeout: u64) -> Self {
        let client = Client::builder()
            .timeout(Duration::from_secs(timeout))
            .build()
            .expect("Failed to create HTTP client");

        Self {
            client,
            timeout: Duration::from_secs(timeout),
        }
    }
}

#[async_trait]
impl DataFetcher for HttpFetcher {
    async fn fetch(&self, request: FetchRequest) -> FetchResult {
        let start = std::time::Instant::now();
        let now = Utc::now();

        let mut result = FetchResult {
            task_id: request.task_id.clone(),
            url: request.url.clone(),
            status: "completed".to_string(),
            status_code: None,
            headers: None,
            data: None,
            error: None,
            fetched_at: now,
            elapsed_time: 0,
        };

        let method = request.method.unwrap_or_else(|| "GET".to_string());
        let timeout = request.timeout.unwrap_or(self.timeout.as_secs());
        let retry_count = request.retry_count.unwrap_or(3);

        let mut req_builder = match method.to_uppercase().as_str() {
            "GET" => self.client.get(&request.url),
            "POST" => self.client.post(&request.url),
            "PUT" => self.client.put(&request.url),
            "DELETE" => self.client.delete(&request.url),
            "PATCH" => self.client.patch(&request.url),
            _ => {
                result.status = "failed".to_string();
                result.error = Some(format!("Unsupported HTTP method: {}", method));
                result.elapsed_time = start.elapsed().as_millis();
                return result;
            }
        };

        // Add headers if provided
        if let Some(headers) = request.headers {
            if let Ok(headers_map) = serde_json::from_value::<std::collections::HashMap<String, String>>(headers) {
                for (key, value) in headers_map {
                    req_builder = req_builder.header(key, value);
                }
            }
        }

        // Add query parameters if provided
        if let Some(params) = request.params {
            if let Ok(params_map) = serde_json::from_value::<std::collections::HashMap<String, String>>(params) {
                req_builder = req_builder.query(&params_map);
            }
        }

        // Add body if provided
        if let Some(body) = request.body {
            req_builder = req_builder.json(&body);
        }

        // Set request timeout
        req_builder = req_builder.timeout(Duration::from_secs(timeout));

        // Execute request with retries
        let mut attempt = 0;
        let mut last_err = None;

        while attempt < retry_count {
            match req_builder.try_clone().unwrap().send().await {
                Ok(response) => {
                    result.status_code = Some(response.status().as_u16());

                    // Convert response headers to JSON
                    let headers_map: std::collections::HashMap<String, String> = response
                        .headers()
                        .iter()
                        .map(|(k, v)| (k.to_string(), v.to_str().unwrap_or("").to_string()))
                        .collect();
                    result.headers = Some(serde_json::to_value(headers_map).unwrap_or_default());

                    // Check if response is successful
                    if response.status().is_success() {
                        match response.json::<serde_json::Value>().await {
                            Ok(data) => {
                                result.data = Some(data);
                            }
                            Err(e) => {
                                result.status = "partial".to_string();
                                result.error = Some(format!("Failed to parse response JSON: {}", e));
                            }
                        }
                    } else {
                        result.status = "failed".to_string();
                        result.error = Some(format!("HTTP error: {}", response.status()));
                    }

                    break;
                }
                Err(e) => {
                    last_err = Some(e);
                    attempt += 1;
                    if attempt < retry_count {
                        time::sleep(Duration::from_millis(500 * 2u64.pow(attempt as u32))).await;
                    }
                }
            }
        }

        if result.status_code.is_none() {
            result.status = "failed".to_string();
            result.error = last_err.map(|e| format!("Request failed: {}", e));
        }

        result.elapsed_time = start.elapsed().as_millis();
        result
    }
}

struct DataFetcherAgent {
    config: Config,
    fetcher: Arc<dyn DataFetcher + Send + Sync>,
    input_topic: String,
    output_topic: String,
    running: Arc<RwLock<bool>>,
}

impl DataFetcherAgent {
    fn new(config: Config, fetcher: Arc<dyn DataFetcher + Send + Sync>) -> Self {
        Self {
            input_topic: config.kafka_topic_in.clone(),
            output_topic: config.kafka_topic_out.clone(),
            config,
            fetcher,
            running: Arc::new(RwLock::new(true)),
        }
    }

    async fn start(&self) -> Result<()> {
        info!("Starting Data Fetcher Agent");

        // Connect to Kafka
        let connection = ClientBuilder::new(vec![self.config.kafka_bootstrap_servers.clone()])
            .build()
            .await
            .context("Failed to connect to Kafka")?;

        let controller_client = connection.controller_client().await.context("Failed to create controller client")?;

        // Ensure topics exist or create them
        for topic in &[&self.input_topic, &self.output_topic] {
            match controller_client.create_topic(topic, 1, 1, 5000).await {
                Ok(_) => info!("Created topic: {}", topic),
                Err(e) => info!("Topic already exists or creation failed: {}: {}", topic, e),
            }
        }

        // Get partition clients for input and output topics
        let input_partition = connection
            .partition_client(self.input_topic.clone(), 0)
            .await
            .context("Failed to create input partition client")?;

        let output_partition = connection
            .partition_client(self.output_topic.clone(), 0)
            .await
            .context("Failed to create output partition client")?;

        // Start consumer loop
        self.consume_loop(input_partition, output_partition).await
    }

    async fn consume_loop(
        &self,
        input_partition: PartitionClient,
        output_partition: PartitionClient,
    ) -> Result<()> {
        let poll_interval = Duration::from_millis(self.config.poll_interval);
        let mut offset = 0;

        while *self.running.read().await {
            match input_partition.fetch_records(offset, 1024 * 1024, 1000).await {
                Ok(fetch_response) => {
                    for record in fetch_response.records {
                        if let Some(value) = record.value {
                            offset = record.offset + 1;

                            match serde_json::from_slice::<FetchRequest>(&value) {
                                Ok(request) => {
                                    info!("Processing fetch request for task: {}", request.task_id);
                                    let result = self.fetcher.fetch(request).await;

                                    let result_json = serde_json::to_vec(&result).unwrap_or_default();

                                    // Send result to output topic
                                    if let Err(e) = output_partition
                                        .produce(vec![Record {
                                            key: Some(result.task_id.as_bytes().to_vec()),
                                            value: Some(result_json),
                                            headers: vec![],
                                            timestamp: chrono::Utc::now().timestamp_millis(),
                                        }], Compression::default())
                                        .await
                                    {
                                        error!("Failed to send result to Kafka: {}", e);
                                    }
                                }
                                Err(e) => {
                                    error!("Failed to deserialize fetch request: {}", e);
                                }
                            }
                        }
                    }
                }
                Err(e) => {
                    error!("Error fetching records: {}", e);
                    time::sleep(Duration::from_secs(1)).await;
                }
            }

            time::sleep(poll_interval).await;
        }

        Ok(())
    }

    async fn stop(&self) {
        let mut running = self.running.write().await;
        *running = false;
    }
}

#[tokio::main]
async fn main() -> Result<()> {
    // Initialize tracing
    let subscriber = FmtSubscriber::builder()
        .with_max_level(Level::INFO)
        .finish();
    tracing::subscriber::set_global_default(subscriber)
        .expect("Failed to set tracing subscriber");

    // Load configuration
    let config = match Config::from_env() {
        Ok(config) => config,
        Err(e) => {
            error!("Failed to load configuration: {}", e);
            process::exit(1);
        }
    };

    // Create HTTP fetcher
    let fetcher = Arc::new(HttpFetcher::new(config.api_request_timeout));

    // Create agent
    let agent = DataFetcherAgent::new(config, fetcher);

    // Set up signal handling for graceful shutdown
    let agent_runner = Arc::new(agent);
    let agent_clone = agent_runner.clone();

    tokio::spawn(async move {
        if let Err(e) = agent_clone.start().await {
            error!("Agent error: {}", e);
        }
    });

    // Wait for Ctrl+C signal
    tokio::signal::ctrl_c().await?;
    info!("Shutting down...");

    // Stop the agent
    agent_runner.stop().await;
    time::sleep(Duration::from_secs(1)).await;

    Ok(())
}