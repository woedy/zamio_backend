# Local Development Dockerfile for ZamIO Django
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    libpq-dev \
    libsndfile1 \
    ffmpeg \
    git \
    curl \
    postgresql-client \
    nano \
    vim \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create app directory
WORKDIR /zamio_django

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip setuptools wheel \
    && pip install -r requirements.txt

# Copy application code
COPY . .

# Copy and set permissions for entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Create necessary directories
RUN mkdir -p /zamio_django/static_cdn /zamio_django/media

# Set matplotlib environment variable for local development
ENV MPLCONFIGDIR=/tmp/matplotlib

EXPOSE 8000

# Health check for local development
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

# Use the entrypoint script
ENTRYPOINT ["/entrypoint.sh"]