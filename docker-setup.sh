#!/bin/bash
# Arrmate — docker-setup.sh
# Interactive setup helper. Checks dependencies, creates .env, and starts services.

set -e

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║              Arrmate Docker Setup                            ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# ─── Dependency checks ─────────────────────────────────────────────────────

if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    echo "   https://docs.docker.com/engine/install/"
    exit 1
fi

if ! docker compose version &> /dev/null && ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed."
    echo "   https://docs.docker.com/compose/install/"
    exit 1
fi

# ─── .env setup ────────────────────────────────────────────────────────────

if [ ! -f .env ]; then
    echo "📝 Creating .env from .env.example..."
    cp .env.example .env
    echo ""
    echo "⚠️  IMPORTANT: Edit .env before continuing!"
    echo "   nano .env"
    echo ""
    echo "   Key things to configure:"
    echo "   • LLM_PROVIDER and model settings"
    echo "   • Media service URLs and API keys"
    echo "   • GPU option in COMPOSE_FILE (if applicable)"
    echo ""
    read -p "Press Enter once you have edited .env, or Ctrl+C to exit..." _
fi

# ─── GPU detection hint ─────────────────────────────────────────────────────

echo ""
echo "🖥️  GPU Acceleration (Ollama):"
if command -v nvidia-smi &> /dev/null; then
    GPU=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1)
    echo "   ✅ NVIDIA GPU detected: ${GPU}"
    echo "   To enable GPU acceleration, set in .env:"
    echo "   COMPOSE_FILE=docker-compose.yml:docker-compose.ollama-nvidia.yml"
elif ls /dev/kfd &> /dev/null 2>&1; then
    echo "   ✅ AMD GPU device detected (/dev/kfd)"
    echo "   To enable GPU acceleration, set in .env:"
    echo "   COMPOSE_FILE=docker-compose.yml:docker-compose.ollama-amd.yml"
else
    echo "   ℹ️  No GPU detected — will run Ollama on CPU (slower but works)"
    echo "   If you have a GPU, install the appropriate drivers first."
fi

# ─── External Ollama hint ───────────────────────────────────────────────────

echo ""
echo "🌐 External Ollama:"
echo "   If Ollama is already running on another machine, set in .env:"
echo "   OLLAMA_BASE_URL=http://<ip-address>:11434"
echo "   Then comment out the 'ollama' service in docker-compose.yml."

# ─── Build and start ────────────────────────────────────────────────────────

echo ""
echo "🐳 Building and starting Arrmate..."
docker compose up -d --build

echo ""
echo "⏳ Waiting for services to start..."
sleep 8

# ─── Model pull hint ────────────────────────────────────────────────────────

OLLAMA_MODEL=$(grep -E "^OLLAMA_MODEL=" .env 2>/dev/null | cut -d= -f2 | tr -d '"' || echo "qwen2.5:7b")
if docker compose ps ollama &>/dev/null 2>&1; then
    echo ""
    echo "📥 Pull your Ollama model (run this after Ollama is healthy):"
    echo "   docker compose exec ollama ollama pull ${OLLAMA_MODEL}"
fi

# ─── Status ─────────────────────────────────────────────────────────────────

echo ""
echo "📊 Service Status:"
docker compose ps

API_PORT=$(grep -E "^API_PORT=" .env 2>/dev/null | cut -d= -f2 || echo "8000")

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║              Setup Complete!                                 ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "🌐 Arrmate URLs:"
echo "   • Web UI:   http://localhost:${API_PORT}/web/"
echo "   • API docs: http://localhost:${API_PORT}/docs"
echo "   • Services: http://localhost:${API_PORT}/api/v1/services"
echo ""
echo "📝 Next Steps:"
echo "   1. Pull your Ollama model (see above) if using local Ollama"
echo "   2. Confirm services show 'available: true' at /api/v1/services"
echo "   3. Try a command in the Web UI: 'show me all my TV shows'"
echo ""
echo "🔍 Useful Commands:"
echo "   View logs:       docker compose logs -f"
echo "   View logs (app): docker compose logs -f arrmate"
echo "   Stop:            docker compose down"
echo "   Restart app:     docker compose restart arrmate"
echo "   Status:          docker compose ps"
echo ""
