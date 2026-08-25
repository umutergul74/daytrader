FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY pyproject.toml README.md ./
RUN pip install --upgrade pip && pip install -e ".[dev]"

# Copy application source
COPY src/ ./src/
COPY docs/ ./docs/
COPY tests/ ./tests/

# Default command
CMD ["quant", "doctor"]
