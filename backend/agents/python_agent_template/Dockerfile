# Atheon AI - Python Agent Template Dockerfile
# Multi-stage build for optimized production image

# ====== Build Stage ======
FROM python:3.11-slim AS builder

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="${PATH}:/root/.local/bin"

# Copy poetry configuration files
COPY pyproject.toml poetry.lock* /app/

# Configure poetry to create a venv inside the project directory
RUN poetry config virtualenvs.in-project true

# Install dependencies only (without development dependencies)
RUN poetry install --no-dev --no-interaction --no-ansi

# Copy source code
COPY src/ /app/src/

# ====== Development Stage ======
FROM python:3.11-slim AS development

# Set work directory
WORKDIR /app

# Set Python to run in unbuffered mode
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Install development dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="${PATH}:/root/.local/bin"

# Configure poetry to create a venv inside the project directory
RUN poetry config virtualenvs.in-project true

# Expose port
EXPOSE 8082

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8082}/health || exit 1

# Default command to run development server
CMD ["poetry", "run", "python", "-m", "src.agent"]

# ====== Runtime Stage ======
FROM python:3.11-slim AS runtime

# Set work directory
WORKDIR /app

# Set Python to run in unbuffered mode
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Install runtime system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    tini \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd -g 1001 atheon && \
    useradd -u 1001 -g atheon -s /bin/bash -m atheon

# Copy the venv from the builder stage
COPY --from=builder /app/.venv /app/.venv

# Copy only the necessary application files
COPY --from=builder /app/src /app/src
COPY --from=builder --chown=atheon:atheon /app/poetry.lock /app/pyproject.toml /app/

# Create directory for logs
RUN mkdir -p /app/logs && chown -R atheon:atheon /app/logs

# Add venv to PATH
ENV PATH="/app/.venv/bin:$PATH"

# Switch to non-root user
USER atheon

# Expose port
EXPOSE 8082

# Use tini as entrypoint
ENTRYPOINT ["/usr/bin/tini", "--"]

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8082}/health || exit 1

# Run the agent
CMD ["python", "-m", "src.agent"]