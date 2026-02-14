#!/bin/bash

set -e

# Configuration
DOCKER_USER="techbutton"
IMAGE_NAME="arrmate"
REGISTRY="docker.io"

# Get version from pyproject.toml
VERSION=$(grep '^version = ' pyproject.toml | sed 's/version = "\(.*\)"/\1/')

if [ -z "$VERSION" ]; then
    echo "❌ Could not determine version from pyproject.toml"
    exit 1
fi

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║           Publishing Arrmate to Docker Hub                   ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "📦 Image: ${DOCKER_USER}/${IMAGE_NAME}"
echo "🏷️  Version: ${VERSION}"
echo ""

# Check if logged in to Docker Hub
echo "🔐 Checking Docker Hub authentication..."
if ! docker info | grep -q "Username: ${DOCKER_USER}"; then
    echo "⚠️  Not logged in to Docker Hub as ${DOCKER_USER}"
    echo "   Please run: docker login"
    echo ""
    read -p "Press Enter after logging in, or Ctrl+C to cancel..."
fi

# Build the image
echo ""
echo "🔨 Building Docker image..."
docker build -t ${DOCKER_USER}/${IMAGE_NAME}:${VERSION} .
docker build -t ${DOCKER_USER}/${IMAGE_NAME}:latest .

echo ""
echo "✅ Build complete!"
echo ""

# Show image size
echo "📊 Image Information:"
docker images ${DOCKER_USER}/${IMAGE_NAME}:${VERSION} --format "table {{.Repository}}:{{.Tag}}\t{{.Size}}"
echo ""

# Confirm before pushing
read -p "🚀 Push to Docker Hub? (y/N) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Push cancelled"
    exit 0
fi

# Push to Docker Hub
echo ""
echo "📤 Pushing to Docker Hub..."
docker push ${DOCKER_USER}/${IMAGE_NAME}:${VERSION}
docker push ${DOCKER_USER}/${IMAGE_NAME}:latest

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║              ✅ Published Successfully! ✅                    ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "🌐 Docker Hub URL:"
echo "   https://hub.docker.com/r/${DOCKER_USER}/${IMAGE_NAME}"
echo ""
echo "📦 Pull Commands:"
echo "   docker pull ${DOCKER_USER}/${IMAGE_NAME}:${VERSION}"
echo "   docker pull ${DOCKER_USER}/${IMAGE_NAME}:latest"
echo ""
echo "🚀 Next Steps:"
echo "   1. Verify on Docker Hub: https://hub.docker.com/r/${DOCKER_USER}/${IMAGE_NAME}"
echo "   2. Test with: docker run -p 8000:8000 ${DOCKER_USER}/${IMAGE_NAME}:latest"
echo "   3. Use in docker-compose.prod.yml for production deployments"
echo ""
