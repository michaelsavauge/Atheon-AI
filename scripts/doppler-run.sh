#!/bin/bash

# This script runs commands with Doppler injected environment variables

# Check if doppler is installed
if ! command -v doppler &> /dev/null; then
    echo "Doppler CLI is not installed. Please install it first:"
    echo "https://docs.doppler.com/docs/install"
    exit 1
fi

# Ensure the script received arguments
if [ $# -eq 0 ]; then
    echo "Usage: $0 <command>"
    echo "Example: $0 docker-compose up -d"
    exit 1
fi

# Run the command with Doppler
echo "Running command with Doppler: $@"
doppler run -- "$@"