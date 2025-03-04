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
	"github.com/google/uuid"
	"github.com/sirupsen/logrus"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc"
	"go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	semconv "go.opentelemetry.io/otel/semconv/v1.4.0"
	"go.opentelemetry.io/otel/trace"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
)

// TaskRequest represents an incoming task request
type TaskRequest struct {
	TaskID     string                 `json:"task_id"`
	CreatedAt  float64                `json:"created_at"`
	Parameters map[string]interface{} `json:"parameters"`
	Metadata   map[string]interface{} `json:"metadata"`
}

// TaskResponse represents a task response
type TaskResponse struct {
	TaskID    string                 `json:"task_id"`
	Status    string                 `json:"status"`
	CreatedAt float64                `json:"created_at"`
	Result    map[string]interface{} `json:"result,omitempty"`
	Error     string                 `json:"error,omitempty"`
	Metadata  map[string]interface{} `json:"metadata"`
}

// Agent defines the interface for agent implementations
type Agent interface {
	ProcessTask(ctx context.Context, request TaskRequest) (map[string]interface{}, error)
	Start() error
	Stop()
}

// BaseAgent provides common functionality for Kafka integration and task processing
type BaseAgent struct {
	AgentName       string
	InputTopic      string
	OutputTopic     string
	TopicPrefix     string
	BootstrapServer string
	ConsumerGroup   string
	KafkaProducer   sarama.SyncProducer
	KafkaConsumer   sarama.ConsumerGroup
	ConsumerReady   chan bool
	WaitGroup       sync.WaitGroup
	Logger          *logrus.Logger
	Tracer          trace.Tracer
	ShutdownCh      chan os.Signal
	TasksProcessed  int
	SuccessfulTasks int
	FailedTasks     int
	ProcessFunc     func(ctx context.Context, request TaskRequest) (map[string]interface{}, error)
}

// ConsumerGroupHandler implements the sarama.ConsumerGroupHandler interface
type ConsumerGroupHandler struct {
	Agent      *BaseAgent
	Ready      chan bool
	Ctx        context.Context
	CancelFunc context.CancelFunc
}

// Setup is run at the beginning of a new session, before ConsumeClaim
func (h ConsumerGroupHandler) Setup(sarama.ConsumerGroupSession) error {
	// Mark the consumer as ready
	close(h.Ready)
	return nil
}

// Cleanup is run at the end of a session, once all ConsumeClaim goroutines have exited
func (h ConsumerGroupHandler) Cleanup(sarama.ConsumerGroupSession) error {
	return nil
}

// ConsumeClaim must start a consumer loop of ConsumerGroupClaim's Messages().
func (h ConsumerGroupHandler) ConsumeClaim(session sarama.ConsumerGroupSession, claim sarama.ConsumerGroupClaim) error {
	for {
		select {
		case msg, ok := <-claim.Messages():
			if !ok {
				h.Agent.Logger.Info("Message channel closed")
				return nil
			}

			// Process the message
			go h.Agent.handleMessage(h.Ctx, msg)

			// Mark the message as processed
			session.MarkMessage(msg, "")

		case <-h.Ctx.Done():
			return nil
		}
	}
}

// NewBaseAgent creates a new base agent
func NewBaseAgent(
	agentName string,
	inputTopic string,
	outputTopic string,
	bootstrapServer string,
	processFunc func(ctx context.Context, request TaskRequest) (map[string]interface{}, error),
) (*BaseAgent, error) {
	logger := logrus.New()
	logger.SetFormatter(&logrus.JSONFormatter{})
	logger.SetOutput(os.Stdout)

	// Set up tracing
	ctx := context.Background()
	tp, err := initTracer(ctx, agentName)
	if err != nil {
		logger.Errorf("Failed to initialize tracer: %v", err)
		// Continue without tracing
	}

	if tp != nil {
		otel.SetTracerProvider(tp)
	}

	tracer := otel.Tracer(agentName)

	topicPrefix := "atheon"
	if prefix := os.Getenv("KAFKA_TOPIC_PREFIX"); prefix != "" {
		topicPrefix = prefix
	}

	consumerGroup := fmt.Sprintf("%s-group", agentName)
	if group := os.Getenv("KAFKA_CONSUMER_GROUP"); group != "" {
		consumerGroup = group
	}

	// Initialize shutdown channel
	shutdownCh := make(chan os.Signal, 1)
	signal.Notify(shutdownCh, syscall.SIGINT, syscall.SIGTERM)

	agent := &BaseAgent{
		AgentName:       agentName,
		InputTopic:      inputTopic,
		OutputTopic:     outputTopic,
		TopicPrefix:     topicPrefix,
		BootstrapServer: bootstrapServer,
		ConsumerGroup:   consumerGroup,
		ConsumerReady:   make(chan bool),
		Logger:          logger,
		Tracer:          tracer,
		ShutdownCh:      shutdownCh,
		ProcessFunc:     processFunc,
	}

	return agent, nil
}

// initTracer initializes an OTLP exporter for tracing
func initTracer(ctx context.Context, serviceName string) (*sdktrace.TracerProvider, error) {
	otlpEndpoint := os.Getenv("OTLP_ENDPOINT")
	if otlpEndpoint == "" {
		otlpEndpoint = "localhost:4317"
	}

	conn, err := grpc.DialContext(ctx, otlpEndpoint, grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		return nil, fmt.Errorf("failed to create gRPC connection: %w", err)
	}

	exporter, err := otlptracegrpc.New(ctx, otlptracegrpc.WithGRPCConn(conn))
	if err != nil {
		return nil, fmt.Errorf("failed to create OTLP trace exporter: %w", err)
	}

	res := resource.NewWithAttributes(
		semconv.SchemaURL,
		semconv.ServiceNameKey.String(serviceName),
	)

	tp := sdktrace.NewTracerProvider(
		sdktrace.WithBatcher(exporter),
		sdktrace.WithResource(res),
	)

	return tp, nil
}

// connect initializes Kafka producer and consumer
func (a *BaseAgent) connect() error {
	// Configure Kafka producer
	producerConfig := sarama.NewConfig()
	producerConfig.Producer.RequiredAcks = sarama.WaitForAll
	producerConfig.Producer.Retry.Max = 5
	producerConfig.Producer.Return.Successes = true

	// Create sync producer
	producer, err := sarama.NewSyncProducer([]string{a.BootstrapServer}, producerConfig)
	if err != nil {
		return fmt.Errorf("failed to create Kafka producer: %w", err)
	}
	a.KafkaProducer = producer

	// Configure Kafka consumer
	consumerConfig := sarama.NewConfig()
	consumerConfig.Consumer.Group.Rebalance.Strategy = sarama.BalanceStrategyRoundRobin
	consumerConfig.Consumer.Offsets.Initial = sarama.OffsetOldest

	// Create consumer group
	consumer, err := sarama.NewConsumerGroup([]string{a.BootstrapServer}, a.ConsumerGroup, consumerConfig)
	if err != nil {
		return fmt.Errorf("failed to create Kafka consumer group: %w", err)
	}
	a.KafkaConsumer = consumer

	a.Logger.WithFields(logrus.Fields{
		"agent":            a.AgentName,
		"bootstrap_server": a.BootstrapServer,
		"input_topic":      getFullTopicName(a.TopicPrefix, a.InputTopic),
		"output_topic":     getFullTopicName(a.TopicPrefix, a.OutputTopic),
		"consumer_group":   a.ConsumerGroup,
	}).Info("Connected to Kafka")

	return nil
}

// getFullTopicName creates the full topic name with prefix
func getFullTopicName(prefix, topic string) string {
	return fmt.Sprintf("%s.%s", prefix, topic)
}

// Start initializes and starts the agent
func (a *BaseAgent) Start() error {
	a.Logger.WithField("agent", a.AgentName).Info("Starting agent")

	// Connect to Kafka
	if err := a.connect(); err != nil {
		return err
	}

	// Prepare the consumer handler context
	ctx, cancel := context.WithCancel(context.Background())
	handler := ConsumerGroupHandler{
		Agent:      a,
		Ready:      a.ConsumerReady,
		Ctx:        ctx,
		CancelFunc: cancel,
	}

	// Start consuming in a goroutine
	a.WaitGroup.Add(1)
	go func() {
		defer a.WaitGroup.Done()
		for {
			// Consume from the full topic name
			fullTopic := getFullTopicName(a.TopicPrefix, a.InputTopic)
			a.Logger.WithField("topic", fullTopic).Debug("Consuming from topic")

			// Start consuming
			if err := a.KafkaConsumer.Consume(ctx, []string{fullTopic}, handler); err != nil {
				a.Logger.Errorf("Error from consumer: %v", err)
			}

			// Check if context was cancelled, indicating a shutdown
			if ctx.Err() != nil {
				a.Logger.Info("Context cancelled, stopping consumer")
				return
			}

			// Restart consumer after a short delay
			a.Logger.Info("Consumer restarting in 5 seconds...")
			time.Sleep(5 * time.Second)
		}
	}()

	// Wait for consumer to be ready
	<-a.ConsumerReady
	a.Logger.Info("Consumer ready, agent started successfully")

	// Wait for shutdown signal
	go func() {
		<-a.ShutdownCh
		a.Logger.Info("Received shutdown signal")
		a.Stop()
	}()

	return nil
}

// Stop gracefully stops the agent
func (a *BaseAgent) Stop() {
	a.Logger.Info("Stopping agent")

	// Close Kafka connections
	if a.KafkaProducer != nil {
		if err := a.KafkaProducer.Close(); err != nil {
			a.Logger.Errorf("Error closing Kafka producer: %v", err)
		}
	}

	if a.KafkaConsumer != nil {
		if err := a.KafkaConsumer.Close(); err != nil {
			a.Logger.Errorf("Error closing Kafka consumer: %v", err)
		}
	}

	// Wait for goroutines to finish
	a.WaitGroup.Wait()

	a.Logger.WithFields(logrus.Fields{
		"tasks_processed":  a.TasksProcessed,
		"successful_tasks": a.SuccessfulTasks,
		"failed_tasks":     a.FailedTasks,
	}).Info("Agent stopped successfully")
}

// handleMessage processes a message from Kafka
func (a *BaseAgent) handleMessage(ctx context.Context, msg *sarama.ConsumerMessage) {
	// Create a new span for message processing
	ctx, span := a.Tracer.Start(ctx, fmt.Sprintf("%s_process_task", a.AgentName))
	defer span.End()

	startTime := time.Now()
	a.TasksProcessed++

	// Extract task ID from message
	var request TaskRequest
	if err := json.Unmarshal(msg.Value, &request); err != nil {
		a.Logger.WithError(err).Error("Failed to unmarshal message")
		a.FailedTasks++
		span.SetAttributes(attribute.Bool("error", true))
		return
	}

	taskID := request.TaskID
	if taskID == "" {
		taskID = uuid.New().String()
		request.TaskID = taskID
	}

	span.SetAttributes(attribute.String("task_id", taskID))
	logger := a.Logger.WithField("task_id", taskID)

	logger.WithFields(logrus.Fields{
		"topic":     msg.Topic,
		"partition": msg.Partition,
		"offset":    msg.Offset,
	}).Info("Received task")

	var response TaskResponse
	response.TaskID = taskID
	response.CreatedAt = float64(time.Now().Unix())
	response.Metadata = map[string]interface{}{
		"agent":        a.AgentName,
		"processed_at": float64(time.Now().Unix()),
	}

	// Process the task
	logger.Info("Processing task")
	result, err := a.ProcessFunc(ctx, request)

	if err != nil {
		a.FailedTasks++
		response.Status = "error"
		response.Error = err.Error()
		logger.WithError(err).Error("Error processing task")
		span.SetAttributes(attribute.Bool("error", true))
		span.RecordError(err)
	} else {
		a.SuccessfulTasks++
		response.Status = "success"
		response.Result = result
		logger.Info("Task processed successfully")
	}

	// Send the response
	responseJSON, err := json.Marshal(response)
	if err != nil {
		logger.WithError(err).Error("Failed to marshal response")
		return
	}

	// Send message to output topic
	fullOutputTopic := getFullTopicName(a.TopicPrefix, a.OutputTopic)
	_, _, err = a.KafkaProducer.SendMessage(&sarama.ProducerMessage{
		Topic: fullOutputTopic,
		Key:   sarama.StringEncoder(taskID),
		Value: sarama.ByteEncoder(responseJSON),
	})

	if err != nil {
		logger.WithError(err).Error("Failed to send response to Kafka")
		span.RecordError(err)
	} else {
		logger.WithField("topic", fullOutputTopic).Info("Response sent to Kafka")
	}

	// Record processing time
	processingTime := time.Since(startTime).Milliseconds()
	span.SetAttributes(attribute.Int64("processing_time_ms", processingTime))
	logger.WithField("processing_time_ms", processingTime).Info("Task handling completed")
}

// ProcessTask processes a task using the provided processing function
func (a *BaseAgent) ProcessTask(ctx context.Context, request TaskRequest) (map[string]interface{}, error) {
	return a.ProcessFunc(ctx, request)
}

// ExampleAgent is an example implementation of a specialized agent
type ExampleAgent struct {
	BaseAgent *BaseAgent
}

// NewExampleAgent creates a new example agent
func NewExampleAgent(bootstrapServer string) (*ExampleAgent, error) {
	processFunc := func(ctx context.Context, request TaskRequest) (map[string]interface{}, error) {
		// Extract parameters
		textParam, ok := request.Parameters["text"]
		if !ok {
			return nil, fmt.Errorf("text parameter is required")
		}

		text, ok := textParam.(string)
		if !ok {
			return nil, fmt.Errorf("text parameter must be a string")
		}

		// Simulate processing
		time.Sleep(1 * time.Second)

		// Return result
		return map[string]interface{}{
			"processed_text": text,
			"word_count":     len(text),
			"timestamp":      time.Now().Unix(),
		}, nil
	}

	baseAgent, err := NewBaseAgent(
		"example-agent",
		"example_requests",
		"example_results",
		bootstrapServer,
		processFunc,
	)

	if err != nil {
		return nil, err
	}

	return &ExampleAgent{BaseAgent: baseAgent}, nil
}

// Start starts the example agent
func (a *ExampleAgent) Start() error {
	return a.BaseAgent.Start()
}

// Stop stops the example agent
func (a *ExampleAgent) Stop() {
	a.BaseAgent.Stop()
}

// ProcessTask delegates processing to the base agent
func (a *ExampleAgent) ProcessTask(ctx context.Context, request TaskRequest) (map[string]interface{}, error) {
	return a.BaseAgent.ProcessTask(ctx, request)
}

func main() {
	// Get Kafka bootstrap servers from environment
	bootstrapServer := os.Getenv("KAFKA_BOOTSTRAP_SERVERS")
	if bootstrapServer == "" {
		bootstrapServer = "localhost:9092"
	}

	// Create and start the example agent
	agent, err := NewExampleAgent(bootstrapServer)
	if err != nil {
		logrus.Fatalf("Failed to create agent: %v", err)
	}

	// Start the agent
	if err := agent.Start(); err != nil {
		logrus.Fatalf("Failed to start agent: %v", err)
	}

	// Wait for a termination signal
	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)
	<-sigCh

	logrus.Info("Shutting down...")
}
