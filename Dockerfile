FROM python:3.8-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/root/.local/bin:$PATH"

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libffi-dev \
    libpq-dev \
    libsndfile1 \
    ffmpeg \
    bash \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /zamio_django

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip setuptools wheel && \
    pip install -r requirements.txt

# Copy project
COPY . .

# Run with Daphne (ASGI, recommended for channels)
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "core.asgi:application"]
