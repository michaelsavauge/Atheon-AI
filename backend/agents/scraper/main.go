package main

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"os/signal"
	"sync"
	"syscall"
	"time"

	"github.com/Shopify/sarama"
	"github.com/gocolly/colly/v2"
	"github.com/sirupsen/logrus"
)

// ScraperConfig holds configuration parameters for the scraper
type ScraperConfig struct {
	KafkaBootstrapServers string
	KafkaTopicIn          string
	KafkaTopicOut         string
	KafkaGroupID          string
	MaxConcurrency        int
	UserAgent             string
}

// ScrapeRequest represents a request to scrape a website
type ScrapeRequest struct {
	TaskID         string   `json:"task_id"`
	URL            string   `json:"url"`
	Selectors      []string `json:"selectors,omitempty"`
	MaxDepth       int      `json:"max_depth,omitempty"`
	Timeout        int      `json:"timeout,omitempty"`
	WaitTime       int      `json:"wait_time,omitempty"`
	ForceJS        bool     `json:"force_js,omitempty"`
	AllowedDomains []string `json:"allowed_domains,omitempty"`
}

// ScrapeResult represents the result of a scraping operation
type ScrapeResult struct {
	TaskID      string            `json:"task_id"`
	URL         string            `json:"url"`
	Status      string            `json:"status"`
	Data        map[string]string `json:"data,omitempty"`
	Error       string            `json:"error,omitempty"`
	ScrapedAt   time.Time         `json:"scraped_at"`
	ElapsedTime int64             `json:"elapsed_time"`
}

// Scraper represents the web scraper agent
type Scraper struct {
	config   ScraperConfig
	log      *logrus.Logger
	consumer sarama.ConsumerGroup
	producer sarama.SyncProducer
	wg       sync.WaitGroup
}

// NewScraper creates a new scraper instance
func NewScraper(config ScraperConfig) (*Scraper, error) {
	logger := logrus.New()
	logger.SetFormatter(&logrus.JSONFormatter{})

	return &Scraper{
		config: config,
		log:    logger,
	}, nil
}

// Start initializes Kafka connections and starts consuming messages
func (s *Scraper) Start(ctx context.Context) error {
	var err error

	// Setup producer
	producerConfig := sarama.NewConfig()
	producerConfig.Producer.RequiredAcks = sarama.WaitForAll
	producerConfig.Producer.Retry.Max = 5
	producerConfig.Producer.Return.Successes = true

	s.producer, err = sarama.NewSyncProducer([]string{s.config.KafkaBootstrapServers}, producerConfig)
	if err != nil {
		return fmt.Errorf("failed to setup producer: %w", err)
	}

	// Setup consumer
	consumerConfig := sarama.NewConfig()
	consumerConfig.Consumer.Group.Rebalance.Strategy = sarama.BalanceStrategyRoundRobin
	consumerConfig.Consumer.Offsets.Initial = sarama.OffsetOldest

	s.consumer, err = sarama.NewConsumerGroup([]string{s.config.KafkaBootstrapServers}, s.config.KafkaGroupID, consumerConfig)
	if err != nil {
		return fmt.Errorf("failed to setup consumer: %w", err)
	}

	s.log.Info("Connected to Kafka")

	// Start consuming in a goroutine
	s.wg.Add(1)
	go func() {
		defer s.wg.Done()
		for {
			if err := s.consumer.Consume(ctx, []string{s.config.KafkaTopicIn}, s); err != nil {
				s.log.Errorf("Error from consumer: %v", err)
				time.Sleep(5 * time.Second)
			}

			if ctx.Err() != nil {
				return
			}
		}
	}()

	return nil
}

// Cleanup closes Kafka connections
func (s *Scraper) Cleanup() error {
	if s.producer != nil {
		if err := s.producer.Close(); err != nil {
			s.log.Errorf("Failed to close producer: %v", err)
		}
	}

	if s.consumer != nil {
		if err := s.consumer.Close(); err != nil {
			s.log.Errorf("Failed to close consumer: %v", err)
		}
	}

	s.wg.Wait()
	return nil
}

// Setup is called before consuming starts
func (s *Scraper) Setup(_ sarama.ConsumerGroupSession) error {
	return nil
}

// Cleanup is called after consuming stops
func (s *Scraper) Cleanup(_ sarama.ConsumerGroupSession) error {
	return nil
}

// ConsumeClaim processes messages from Kafka
func (s *Scraper) ConsumeClaim(session sarama.ConsumerGroupSession, claim sarama.ConsumerGroupClaim) error {
	for {
		select {
		case msg := <-claim.Messages():
			if msg == nil {
				return nil
			}

			s.log.Infof("Received message: %s", string(msg.Value))

			var req ScrapeRequest
			if err := json.Unmarshal(msg.Value, &req); err != nil {
				s.log.Errorf("Failed to unmarshal message: %v", err)
				session.MarkMessage(msg, "")
				continue
			}

			// Process the scrape request in a goroutine
			go func(r ScrapeRequest) {
				result := s.processScrapeRequest(r)

				// Send result back to Kafka
				resultBytes, err := json.Marshal(result)
				if err != nil {
					s.log.Errorf("Failed to marshal result: %v", err)
					return
				}

				_, _, err = s.producer.SendMessage(&sarama.ProducerMessage{
					Topic: s.config.KafkaTopicOut,
					Value: sarama.StringEncoder(resultBytes),
					Key:   sarama.StringEncoder(r.TaskID),
				})

				if err != nil {
					s.log.Errorf("Failed to send result to Kafka: %v", err)
				}
			}(req)

			session.MarkMessage(msg, "")

		case <-session.Context().Done():
			return nil
		}
	}
}

// processScrapeRequest handles the actual web scraping
func (s *Scraper) processScrapeRequest(req ScrapeRequest) ScrapeResult {
	startTime := time.Now()

	result := ScrapeResult{
		TaskID:    req.TaskID,
		URL:       req.URL,
		ScrapedAt: startTime,
		Status:    "completed",
		Data:      make(map[string]string),
	}

	c := colly.NewCollector(
		colly.UserAgent(s.config.UserAgent),
		colly.MaxDepth(req.MaxDepth),
	)

	if len(req.AllowedDomains) > 0 {
		c.AllowedDomains = req.AllowedDomains
	}

	// Set timeout if specified
	if req.Timeout > 0 {
		c.SetRequestTimeout(time.Duration(req.Timeout) * time.Second)
	}

	// Configure wait time between requests
	if req.WaitTime > 0 {
		c.Limit(&colly.LimitRule{
			DomainGlob:  "*",
			RandomDelay: time.Duration(req.WaitTime) * time.Second,
		})
	}

	// Process HTML content based on selectors
	for _, selector := range req.Selectors {
		c.OnHTML(selector, func(e *colly.HTMLElement) {
			result.Data[selector] = e.Text
		})
	}

	// Handle errors
	c.OnError(func(r *colly.Response, err error) {
		result.Status = "failed"
		result.Error = err.Error()
		s.log.Errorf("Scraping error for %s: %v", req.URL, err)
	})

	// Visit the URL
	err := c.Visit(req.URL)
	if err != nil {
		result.Status = "failed"
		result.Error = err.Error()
	}

	// Wait until scraping is complete
	c.Wait()

	result.ElapsedTime = time.Since(startTime).Milliseconds()
	return result
}

func main() {
	// Load configuration from environment
	config := ScraperConfig{
		KafkaBootstrapServers: getEnv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
		KafkaTopicIn:          getEnv("KAFKA_TOPIC_IN", "scrape_requests"),
		KafkaTopicOut:         getEnv("KAFKA_TOPIC_OUT", "scrape_results"),
		KafkaGroupID:          getEnv("KAFKA_GROUP_ID", "scraper_group"),
		MaxConcurrency:        getIntEnv("MAX_CONCURRENCY", 10),
		UserAgent:             getEnv("USER_AGENT", "Atheon-AI Web Scraper"),
	}

	scraper, err := NewScraper(config)
	if err != nil {
		panic(fmt.Sprintf("Failed to create scraper: %v", err))
	}

	ctx, cancel := context.WithCancel(context.Background())

	// Handle graceful shutdown
	signals := make(chan os.Signal, 1)
	signal.Notify(signals, syscall.SIGINT, syscall.SIGTERM)

	go func() {
		<-signals
		cancel()
	}()

	if err := scraper.Start(ctx); err != nil {
		panic(fmt.Sprintf("Failed to start scraper: %v", err))
	}

	<-ctx.Done()

	fmt.Println("Shutting down...")
	if err := scraper.Cleanup(); err != nil {
		fmt.Printf("Error during cleanup: %v\n", err)
	}
}

// Helper functions for environment variables
func getEnv(key, fallback string) string {
	if value, ok := os.LookupEnv(key); ok {
		return value
	}
	return fallback
}

func getIntEnv(key string, fallback int) int {
	if value, ok := os.LookupEnv(key); ok {
		var result int
		_, err := fmt.Sscanf(value, "%d", &result)
		if err == nil {
			return result
		}
	}
	return fallback
}
