# Atheon AI - Go Scraper Agent Dockerfile
# Multi-stage build for optimized web scraping with concurrent operations

# ====== Build Stage ======
FROM golang:1.21-alpine AS builder

# Set work directory
WORKDIR /app

# Install build dependencies
RUN apk add --no-cache git ca-certificates tzdata build-base

# Install Colly and other dependencies
COPY go.mod go.sum* ./
RUN go mod download

# Copy source code
COPY . .

# Build the application with optimization flags
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build \
    -ldflags="-w -s -X main.version=$(git describe --tags --always --dirty)" \
    -o scraper-agent \
    ./main.go

# ====== Runtime Stage ======
FROM alpine:3.18 AS runtime

# Add security updates and CA certificates
RUN apk --no-cache add ca-certificates tzdata curl

# Create non-root user
RUN addgroup -g 1001 atheon && \
    adduser -u 1001 -G atheon -s /bin/sh -D atheon

# Create app directory
WORKDIR /app

# Copy the binary from builder
COPY --from=builder /app/scraper-agent /app/scraper-agent

# Set ownership
RUN chown -R atheon:atheon /app

# Switch to non-root user
USER atheon

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Run the application
ENTRYPOINT ["/app/scraper-agent"]