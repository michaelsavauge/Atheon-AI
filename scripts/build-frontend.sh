#!/bin/bash

# This script builds just the frontend container

echo "Building frontend container..."
cd frontend

# Create package-lock.json if it doesn't exist
if [ ! -f package-lock.json ]; then
    echo "Generating package-lock.json..."
    npm install --package-lock-only
fi

# Build the container
cd ..
docker-compose build frontend

echo "Frontend container built. To run the frontend, use:"
echo "  docker-compose up -d frontend"