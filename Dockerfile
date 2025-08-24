FROM python:3.8-slim

ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libffi-dev \
    libpq-dev \
    libsndfile1 \
    bash \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /zamio_django

# Copy requirements first for caching
COPY requirements.txt requirements.txt

# Upgrade pip & install dependencies
RUN pip install --upgrade pip setuptools wheel \
    && pip install -r requirements.txt

# Copy project files
COPY . .

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
