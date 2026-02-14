#!/bin/bash

set -e

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║           Arrmate Docker Setup                                ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Create .env if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file from .env.example..."
    cp .env.example .env
    echo "⚠️  Please edit .env file and add your API keys!"
    echo ""
fi

# Build and start services
echo "🐳 Building and starting Docker containers..."
docker compose up -d --build

echo ""
echo "⏳ Waiting for services to be healthy..."
sleep 10

# Check service status
echo ""
echo "📊 Service Status:"
docker compose ps

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║           Setup Complete!                                     ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "🌐 Access URLs:"
echo "   • Arrmate Web UI:  http://localhost:8000/web/"
echo "   • Arrmate API:     http://localhost:8000/docs"
echo "   • Sonarr:          http://localhost:8989"
echo "   • Radarr:          http://localhost:7878"
echo "   • Ollama:          http://localhost:11434"
echo ""
echo "📝 Next Steps:"
echo "   1. Configure Sonarr at http://localhost:8989"
echo "   2. Configure Radarr at http://localhost:7878"
echo "   3. Get API keys from Settings > General in each service"
echo "   4. Update .env file with the API keys"
echo "   5. Restart Arrmate: docker compose restart arrmate"
echo "   6. Pull Ollama model: docker compose exec ollama ollama pull llama3.2"
echo ""
echo "🔍 Useful Commands:"
echo "   • View logs:       docker compose logs -f"
echo "   • Stop services:   docker compose down"
echo "   • Restart:         docker compose restart"
echo "   • View status:     docker compose ps"
echo ""
