#!/bin/bash
set -e

echo "?? Bootstrapping AI Reel Studio environment..."

# Create necessary directories
mkdir -p apps/worker/tmp
mkdir -p data/postgres
mkdir -p data/redis
mkdir -p data/minio

# Check dependencies
command -v docker >/dev/null 2>&1 || { echo >&2 "Docker is required but not installed. Aborting."; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo >&2 "Python 3 is required but not installed. Aborting."; exit 1; }

# Install Python dependencies (for local dev/scripts)
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
fi

# Copy .env.example if .env doesn't exist
if [ ! -f .env ]; then
    cp .env.example .env
    echo "??  Created .env from .env.example. Please fill in your secrets."
fi

echo "? Bootstrap complete! You can now run: docker compose up -d"
