# Dockerfile
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/root/.local/bin:$PATH"

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
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

# Python deps first (cache friendly)
COPY requirements.txt .
RUN pip install --upgrade pip setuptools wheel \
 && pip install -r requirements.txt

# App code
COPY . .

# Entrypoint will handle migrate/collectstatic/start
COPY entrypoint.sh /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
