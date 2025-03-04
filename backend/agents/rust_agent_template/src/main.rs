use std::{env, sync::Arc, time::{Duration, SystemTime, UNIX_EPOCH}};

use anyhow::{Context, Result};
use clap::Parser;
use futures::StreamExt;
use rdkafka::{
    client::ClientContext,
    config::{ClientConfig, RDKafkaLogLevel},
    consumer::{stream_consumer::StreamConsumer, CommitMode, Consumer, ConsumerContext},
    error::KafkaError,
    message::{Headers, Message},
    producer::{FutureProducer, FutureRecord},
    util::get_rdkafka_version,
};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use tokio::signal;
use tracing::{debug, error, info, instrument, warn, Instrument};
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};
use uuid::Uuid;

/// Command line arguments for the agent
#[derive(Parser, Debug)]
#[command(author, version, about, long_about = None)]
struct Args {
    /// Kafka bootstrap servers
    #[arg(long, env = "KAFKA_BOOTSTRAP_SERVERS", default_value = "localhost:9092")]
    bootstrap_servers: String,

    /// Kafka consumer group ID
    #[arg(long, env = "KAFKA_CONSUMER_GROUP", default_value_t = String::from("rust-agent-group"))]
    consumer_group: String,

    /// Input topic to consume from
    #[arg(long, env = "KAFKA_INPUT_TOPIC", default_value = "requests")]
    input_topic: String,

    /// Output topic to produce to
    #[arg(long, env = "KAFKA_OUTPUT_TOPIC", default_value = "responses")]
    output_topic: String,

    /// Kafka topic prefix
    #[arg(long, env = "KAFKA_TOPIC_PREFIX", default_value = "atheon")]
    topic_prefix: String,

    /// Log level
    #[arg(long, env = "LOG_LEVEL", default_value = "info")]
    log_level: String,
}

/// Base model for task requests
#[derive(Debug, Serialize, Deserialize)]
struct TaskRequest {
    task_id: String,
    #[serde(default = "default_timestamp")]
    created_at: f64,
    #[serde(default)]
    parameters: Value,
    #[serde(default)]
    metadata: Value,
}

/// Base model for task responses
#[derive(Debug, Serialize, Deserialize)]
struct TaskResponse {
    task_id: String,
    status: String,
    #[serde(default = "default_timestamp")]
    created_at: f64,
    #[serde(skip_serializing_if = "Option::is_none")]
    result: Option<Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    error: Option<String>,
    #[serde(default)]
    metadata: Value,
}

/// Get current timestamp in seconds
fn default_timestamp() -> f64 {
    let start = SystemTime::now();
    let since_epoch = start
        .duration_since(UNIX_EPOCH)
        .expect("Time went backwards");
    since_epoch.as_secs_f64()
}

/// Struct to handle Kafka consumer logging
struct CustomContext;

impl ClientContext for CustomContext {}

impl ConsumerContext for CustomContext {}

type LoggingConsumer = StreamConsumer<CustomContext>;

/// A template for Rust agents within the Atheon AI system
struct RustAgent {
    agent_name: String,
    consumer: LoggingConsumer,
    producer: FutureProducer,
    input_topic: String,
    output_topic: String,
    topic_prefix: String,
}

impl RustAgent {
    #[instrument(skip(bootstrap_servers, consumer_group))]
    async fn new(
        agent_name: &str,
        bootstrap_servers: &str,
        consumer_group: &str,
        input_topic: &str,
        output_topic: &str,
        topic_prefix: &str,
    ) -> Result<Self> {
        info!("Initializing agent");

        // Create the consumer
        let consumer: LoggingConsumer = ClientConfig::new()
            .set("group.id", consumer_group)
            .set("bootstrap.servers", bootstrap_servers)
            .set("enable.partition.eof", "false")
            .set("session.timeout.ms", "6000")
            .set("enable.auto.commit", "false")
            .set_log_level(RDKafkaLogLevel::Debug)
            .create_with_context(CustomContext {})
            .context("Failed to create Kafka consumer")?;

        // Create the producer
        let producer: FutureProducer = ClientConfig::new()
            .set("bootstrap.servers", bootstrap_servers)
            .set("message.timeout.ms", "5000")
            .create()
            .context("Failed to create Kafka producer")?;

        info!(
            rdkafka_version = ?get_rdkafka_version(),
            "Agent initialized successfully"
        );

        Ok(Self {
            agent_name: agent_name.to_string(),
            consumer,
            producer,
            input_topic: input_topic.to_string(),
            output_topic: output_topic.to_string(),
            topic_prefix: topic_prefix.to_string(),
        })
    }

    /// Get the full topic name with prefix
    fn get_full_topic_name(&self, topic: &str) -> String {
        format!("{}.{}", self.topic_prefix, topic)
    }

    /// Start the agent and begin consuming messages
    #[instrument(skip(self))]
    async fn start(&self) -> Result<()> {
        let full_topic = self.get_full_topic_name(&self.input_topic);
        info!(topic = %full_topic, "Subscribing to topic");

        self.consumer
            .subscribe(&[&full_topic])
            .context("Failed to subscribe to topic")?;

        info!("Agent started successfully");

        Ok(())
    }

    /// Process incoming messages
    #[instrument(skip(self), fields(agent = %self.agent_name))]
    async fn process_messages(&self) -> Result<()> {
        info!("Waiting for messages...");

        let mut stream = self.consumer.stream();
        while let Some(message_result) = stream.next().await {
            match message_result {
                Ok(message) => {
                    let payload = match message.payload() {
                        Some(p) => p,
                        None => {
                            warn!("Empty message payload, skipping");
                            self.consumer.commit_message(&message, CommitMode::Async).unwrap_or_else(|e| {
                                error!(error = ?e, "Failed to commit message");
                            });
                            continue;
                        }
                    };

                    // Process the message
                    if let Err(e) = self.handle_message(payload).await {
                        error!(error = ?e, "Failed to process message");
                    }

                    // Commit the message
                    self.consumer.commit_message(&message, CommitMode::Async).unwrap_or_else(|e| {
                        error!(error = ?e, "Failed to commit message");
                    });
                }
                Err(e) => {
                    error!(error = ?e, "Error while receiving message");
                }
            }
        }

        Ok(())
    }

    /// Handle an individual message
    #[instrument(skip(self, payload), fields(agent = %self.agent_name))]
    async fn handle_message(&self, payload: &[u8]) -> Result<()> {
        // Deserialize the request
        let request: TaskRequest = match serde_json::from_slice(payload) {
            Ok(req) => req,
            Err(e) => {
                error!(error = ?e, "Failed to deserialize message");
                return Err(anyhow::anyhow!("Failed to deserialize message: {}", e));
            }
        };

        let task_id = request.task_id.clone();
        let span = tracing::info_span!("process_task", task_id = %task_id);

        // Process the task within the span
        self.process_task(request)
            .instrument(span)
            .await
            .map_err(|e| {
                // Send error response on failure
                let _ = self.send_error_response(&task_id, e.to_string().as_str());
                e
            })?;

        Ok(())
    }

    /// Process a single task
    #[instrument(skip(self), fields(agent = %self.agent_name))]
    async fn process_task(&self, request: TaskRequest) -> Result<()> {
        let task_id = request.task_id.clone();
        let start_time = SystemTime::now();

        info!(task_id = %task_id, "Processing task");

        // Extract and validate parameters
        // This is where agent-specific processing logic would go
        let text = request.parameters.get("text").and_then(|v| v.as_str()).unwrap_or("");

        // Example processing - in a real agent, this would be more complex
        tokio::time::sleep(Duration::from_secs(1)).await; // Simulate work

        let result = json!({
            "processed_text": text.to_uppercase(),
            "length": text.len(),
            "processing_time_ms": SystemTime::now().duration_since(start_time).unwrap().as_millis(),
        });

        // Send successful response
        self.send_success_response(&task_id, result).await?;

        info!(
            task_id = %task_id,
            elapsed_ms = ?SystemTime::now().duration_since(start_time).unwrap().as_millis(),
            "Task completed successfully"
        );

        Ok(())
    }

    /// Send a success response
    #[instrument(skip(self, result), fields(agent = %self.agent_name))]
    async fn send_success_response(&self, task_id: &str, result: Value) -> Result<()> {
        let response = TaskResponse {
            task_id: task_id.to_string(),
            status: "success".to_string(),
            created_at: default_timestamp(),
            result: Some(result),
            error: None,
            metadata: json!({
                "agent": self.agent_name,
                "processed_at": default_timestamp(),
            }),
        };

        self.send_response(response).await
    }

    /// Send an error response
    #[instrument(skip(self), fields(agent = %self.agent_name))]
    async fn send_error_response(&self, task_id: &str, error_message: &str) -> Result<()> {
        let response = TaskResponse {
            task_id: task_id.to_string(),
            status: "error".to_string(),
            created_at: default_timestamp(),
            result: None,
            error: Some(error_message.to_string()),
            metadata: json!({
                "agent": self.agent_name,
                "processed_at": default_timestamp(),
            }),
        };

        self.send_response(response).await
    }

    /// Send a response to the output topic
    #[instrument(skip(self, response), fields(agent = %self.agent_name))]
    async fn send_response(&self, response: TaskResponse) -> Result<()> {
        let task_id = response.task_id.clone();
        let payload = serde_json::to_string(&response).context("Failed to serialize response")?;
        let full_topic = self.get_full_topic_name(&self.output_topic);

        debug!(topic = %full_topic, task_id = %task_id, "Sending response");

        self.producer
            .send(
                FutureRecord::to(&full_topic)
                    .payload(&payload)
                    .key(&task_id),
                Duration::from_secs(5),
            )
            .await
            .map_err(|(e, _)| anyhow::anyhow!("Failed to send message: {}", e))?;

        info!(topic = %full_topic, task_id = %task_id, "Response sent successfully");
        Ok(())
    }
}

/// Example agent implementation
struct ExampleAgent {
    inner: Arc<RustAgent>,
}

impl ExampleAgent {
    /// Create a new example agent
    async fn new(args: &Args) -> Result<Self> {
        let agent = RustAgent::new(
            "example-agent",
            &args.bootstrap_servers,
            &args.consumer_group,
            &args.input_topic,
            &args.output_topic,
            &args.topic_prefix,
        ).await?;

        Ok(Self {
            inner: Arc::new(agent),
        })
    }

    /// Start the example agent
    async fn start(&self) -> Result<()> {
        self.inner.start().await?;
        self.inner.process_messages().await
    }
}

#[tokio::main]
async fn main() -> Result<()> {
    // Parse command line arguments
    let args = Args::parse();

    // Set up logging
    let log_level = match args.log_level.to_lowercase().as_str() {
        "trace" => tracing::Level::TRACE,
        "debug" => tracing::Level::DEBUG,
        "info" => tracing::Level::INFO,
        "warn" => tracing::Level::WARN,
        "error" => tracing::Level::ERROR,
        _ => tracing::Level::INFO,
    };

    // Initialize the tracing subscriber
    tracing_subscriber::registry()
        .with(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| format!("rust_agent_template={}", log_level).into()),
        )
        .with(tracing_subscriber::fmt::layer().json())
        .init();

    info!(
        version = env!("CARGO_PKG_VERSION"),
        "Starting rust-agent-template"
    );

    // Create and start the agent
    let agent = ExampleAgent::new(&args).await?;

    // Set up signal handler for graceful shutdown
    let agent_ref = Arc::clone(&agent.inner);
    tokio::spawn(async move {
        let _ = signal::ctrl_c().await;
        info!("Received shutdown signal, stopping agent...");
    });

    // Start processing messages
    agent.start().await
}