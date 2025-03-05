# Atheon AI - Rust Data Fetcher Agent Dockerfile
# Multi-stage build for optimized asynchronous data fetching

# ====== Build Stage ======
FROM rust:1.72-slim AS builder

# Set work directory
WORKDIR /usr/src/app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    pkg-config \
    libssl-dev \
    build-essential \
    git \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create a new empty project
RUN cargo init --bin

# Copy only Cargo.toml and Cargo.lock files to cache dependencies
COPY Cargo.toml Cargo.lock* ./

# Build the project with fake main.rs to cache dependencies
RUN cargo build --release && \
    rm -f target/release/deps/data_fetcher_agent*

# Copy source code
COPY src ./src

# Rebuild application with actual source code
RUN cargo build --release

# ====== Runtime Stage ======
FROM debian:bookworm-slim AS runtime

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    libssl3 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -g 1001 atheon && \
    useradd -u 1001 -g atheon -s /bin/bash -m atheon

# Set work directory
WORKDIR /app

# Copy the binary from builder
COPY --from=builder /usr/src/app/target/release/rust_agent_template /app/data-fetcher-agent

# Set ownership
RUN chown -R atheon:atheon /app

# Switch to non-root user
USER atheon

# Expose port
EXPOSE 8081

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8081/health || exit 1

# Run the application
ENTRYPOINT ["/app/data-fetcher-agent"]