#!/bin/bash

# This script runs just the backend services with Doppler for environment variables

# Check if doppler is installed
if ! command -v doppler &> /dev/null; then
    echo "Doppler CLI is not installed. Please install it first:"
    echo "https://docs.doppler.com/docs/install"
    exit 1
fi

# Run the docker-compose command with Doppler
echo "Starting backend services with Doppler..."
doppler run -- docker-compose -f docker-compose.backend.yml up -d

echo "Checking service status..."
docker-compose -f docker-compose.backend.yml ps

echo "Backend services started. Use the following commands for logs:"
echo "  docker-compose -f docker-compose.backend.yml logs -f orchestrator"
echo "  docker-compose -f docker-compose.backend.yml logs -f postgres"
echo "  docker-compose -f docker-compose.backend.yml logs -f kafka"