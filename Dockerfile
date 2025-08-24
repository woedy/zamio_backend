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

# Create static files directory
RUN mkdir -p /zamio_django/static_cdn/static_root

# Collect static files
RUN python manage.py collectstatic --noinput

# Expose port
EXPOSE 8000

# Use Gunicorn for production
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120", "core.wsgi:application"]
