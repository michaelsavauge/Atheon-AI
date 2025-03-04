#!/bin/bash

# Script to build the frontend container
# Handles package-lock.json if it doesn't exist

# Check if Doppler CLI is installed
if ! command -v doppler &> /dev/null; then
    echo "Warning: Doppler CLI is not installed. Some build features may be limited."
    echo "Consider installing Doppler CLI: https://docs.doppler.com/docs/cli"
fi

echo "Building frontend container..."

# Change to frontend directory
cd frontend || { echo "Frontend directory not found"; exit 1; }

# Check if package-lock.json exists, if not generate it
if [ ! -f "package-lock.json" ]; then
    echo "package-lock.json not found, generating it..."
    npm install --package-lock-only
fi

# Return to original directory
cd ..

# Build using docker-compose
if command -v doppler &> /dev/null && doppler configure verify --no-read-env &> /dev/null; then
    echo "Using Doppler for build-time environment variables..."
    doppler run -- docker-compose build frontend
else
    echo "Building without Doppler..."
    docker-compose build frontend
fi

echo ""
echo "Frontend container built successfully."
echo ""
echo "To run the frontend container:"
echo "  doppler run -- docker-compose up -d frontend"