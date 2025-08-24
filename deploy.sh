#!/bin/bash

# ZamIO Django Deployment Script for Coolify
# This script helps prepare your project for deployment

set -e

echo "🚀 ZamIO Django Deployment Preparation Script"
echo "=============================================="

# Check if we're in the right directory
if [ ! -f "manage.py" ]; then
    echo "❌ Error: This script must be run from the Django project root directory"
    exit 1
fi

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Error: Docker is not running. Please start Docker and try again."
    exit 1
fi

echo "✅ Docker is running"

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Error: docker-compose is not installed. Please install it and try again."
    exit 1
fi

echo "✅ docker-compose is available"

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "📝 Creating .env file from template..."
    if [ -f "env.production.example" ]; then
        cp env.production.example .env
        echo "✅ .env file created from env.production.example"
        echo "⚠️  Please edit .env file with your actual production values"
    else
        echo "❌ env.production.example not found. Please create .env manually."
    fi
else
    echo "✅ .env file already exists"
fi

# Check if .env has been customized
if [ -f ".env" ]; then
    if grep -q "your-super-secret-key-here" .env; then
        echo "⚠️  Warning: .env file contains default values. Please customize them for production."
    fi
fi

# Build Docker images
echo "🔨 Building Docker images..."
docker-compose build

echo "✅ Docker images built successfully"

# Check if all required files exist
echo "🔍 Checking required files..."
required_files=("docker-compose.yml" "Dockerfile" "entrypoint.sh" "requirements.txt")
for file in "${required_files[@]}"; do
    if [ -f "$file" ]; then
        echo "✅ $file exists"
    else
        echo "❌ $file missing"
        exit 1
    fi
done

echo ""
echo "🎉 Deployment preparation completed successfully!"
echo ""
echo "📋 Next steps:"
echo "1. Edit .env file with your production values"
echo "2. Commit and push your changes to Git"
echo "3. Deploy to Coolify using the deployment guide"
echo ""
echo "📚 See COOLIFY_DEPLOYMENT.md for detailed deployment instructions"
echo ""
echo "🔧 To test locally: docker-compose up --build"
