# Proof of Time Testnet Node
# Version: 2.0.0 Pantheon

FROM python:3.11-slim

LABEL maintainer="Proof of Time Team"
LABEL version="2.0.0"
LABEL description="Proof of Time Testnet Node"

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libgmp-dev \
    libsodium-dev \
    libssl-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -s /bin/bash pot

# Set working directory
WORKDIR /app

# Copy requirements first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create data directories
RUN mkdir -p /app/data /app/logs && \
    chown -R pot:pot /app

# Switch to non-root user
USER pot

# Expose ports
EXPOSE 9333 9334

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV POT_DATA_DIR=/app/data
ENV POT_LOG_LEVEL=INFO

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:9334/health')" || exit 1

# Default command
CMD ["python", "node.py", "--run", "--config", "/app/testnet/config.json"]
