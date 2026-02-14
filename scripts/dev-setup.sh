#!/bin/bash
# Development setup script

set -e

echo "MediaTools Development Setup"
echo "============================"
echo ""

# Check Python version
echo "Checking Python version..."
python3 --version || { echo "Python 3.11+ required"; exit 1; }

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
pip install -e .

# Create .env if it doesn't exist
if [ ! -f ".env" ]; then
    echo "Creating .env from example..."
    cp .env.example .env
    echo ""
    echo "⚠️  Please edit .env with your API keys and URLs"
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env with your Sonarr/Radarr API keys"
echo "2. If using Ollama, start it: ollama serve"
echo "3. If using Ollama, pull a model: ollama pull llama3.1"
echo "4. Test CLI: arrmate services"
echo "5. Start API: python -m arrmate.interfaces.api.app"
echo ""
echo "To activate venv in future sessions:"
echo "  source venv/bin/activate"
