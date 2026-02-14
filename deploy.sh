#!/bin/bash

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║        Arrmate Docker Stack Deployment                       ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Check Docker permissions
if ! docker ps > /dev/null 2>&1; then
    echo "⚠️  Docker requires elevated permissions."
    echo "   You may need to run with sudo or add your user to docker group:"
    echo "   sudo usermod -aG docker $USER"
    echo "   Then log out and back in."
    echo ""
    USE_SUDO="sudo "
else
    USE_SUDO=""
fi

# Create .env if needed
if [ ! -f .env ]; then
    echo "📝 Creating .env file..."
    cp .env.example .env
fi

echo "🔨 Building Arrmate image..."
${USE_SUDO}docker compose build arrmate

echo ""
echo "🚀 Starting all services..."
${USE_SUDO}docker compose up -d

echo ""
echo "⏳ Waiting for services to start..."
sleep 15

echo ""
echo "📊 Service Status:"
${USE_SUDO}docker compose ps

echo ""
echo "🎯 Pulling Ollama model (this may take a few minutes)..."
${USE_SUDO}docker compose exec ollama ollama pull llama3.2

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║              🎉 Deployment Complete!                         ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "🌐 Access URLs:"
echo "   ✓ Arrmate Web UI:  http://localhost:8000/web/"
echo "   ✓ Arrmate API:     http://localhost:8000/docs"
echo "   ✓ Sonarr:          http://localhost:8989"
echo "   ✓ Radarr:          http://localhost:7878"
echo "   ✓ Ollama:          http://localhost:11434"
echo ""
echo "📝 Next Steps:"
echo "   1. Configure Sonarr → http://localhost:8989"
echo "   2. Configure Radarr → http://localhost:7878"
echo "   3. Get API keys from each service (Settings > General)"
echo "   4. Update .env with API keys"
echo "   5. Restart Arrmate: ${USE_SUDO}docker compose restart arrmate"
echo ""
echo "📖 Full documentation: DOCKER.md"
echo ""
