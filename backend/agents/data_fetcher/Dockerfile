# Stage 1: Builder
FROM rust:1.71-alpine AS builder

WORKDIR /app

# Install build dependencies
RUN apk add --no-cache musl-dev openssl-dev pkgconfig

# Create empty project for caching dependencies
RUN mkdir -p src && \
    echo 'fn main() { println!("Dummy project"); }' > src/main.rs

# Copy manifests for dependency caching
COPY Cargo.toml Cargo.lock* ./

# Build dependencies - this is the key step that will be cached
RUN cargo build --release

# Remove the dummy project
RUN rm -rf src

# Copy the actual source code
COPY . .

# Do a clean rebuild of the application
RUN cargo build --release

# Stage 2: Runtime
FROM alpine:3.18

WORKDIR /app

# Add non-root user
RUN addgroup -S appgroup && adduser -S appuser -G appgroup

# Install runtime dependencies
RUN apk add --no-cache ca-certificates curl tzdata libgcc

# Copy the binary from the builder stage
COPY --from=builder /app/target/release/atheon-data-fetcher .

# Set proper permissions
RUN chown -R appuser:appgroup /app

# Switch to non-root user
USER appuser

# Expose the port the service runs on
EXPOSE 8081

# Health check (assuming the service has a health endpoint, adjust as needed)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8081/health || exit 1

# Run the application
CMD ["./atheon-data-fetcher"]