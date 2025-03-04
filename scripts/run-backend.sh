#!/bin/bash

# This script runs just the backend services with Doppler for environment variables

# Check if Doppler CLI is installed
if ! command -v doppler &> /dev/null; then
    echo "Error: Doppler CLI is not installed or not in PATH"
    echo "Install Doppler CLI following instructions at: https://docs.doppler.com/docs/cli"
    exit 1
fi

# Check if doppler is configured for this project
if ! doppler configure verify --no-read-env &> /dev/null; then
    echo "Doppler is not configured for this project."
    echo "Please run: doppler setup --project atheon-ai --config dev"
    exit 1
fi

echo "Starting backend services with Doppler for secrets management..."

# Start backend services with Doppler injecting environment variables
doppler run -- docker-compose -f docker-compose.backend.yml up -d

# Check if services started successfully
echo "Checking service status..."
sleep 5
doppler run -- docker-compose -f docker-compose.backend.yml ps

echo ""
echo "Backend services are now running with Doppler-managed secrets"
echo ""
echo "To view logs for a specific service:"
echo "doppler run -- docker-compose -f docker-compose.backend.yml logs -f <service-name>"
echo ""
echo "To stop all services:"
echo "doppler run -- docker-compose -f docker-compose.backend.yml down"