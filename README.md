# Arrmate 🤝

Your AI companion for Sonarr, Radarr, and Lidarr - manage your media library with natural language.

## Features

- 🗣️ **Natural Language Interface** - Control your media with plain English
- 🌐 **Mobile-Friendly Web UI** - Built with HTMX and Tailwind CSS
- 🐳 **Docker Support** - Complete stack with Ollama, Sonarr, and Radarr
- 🤖 **Multiple LLM Providers** - Ollama (local), OpenAI, or Anthropic
- 📺 **Multi-Service Support** - Sonarr (TV), Radarr (Movies), Lidarr (Music)

## Quick Start

### Docker (Recommended)

```bash
# Deploy complete stack
sudo ./deploy.sh

# Or manually
sudo docker compose up -d
```

Access at: http://localhost:8000/web/

### Manual Installation

```bash
# Install dependencies
pip install -e .

# Configure services
cp .env.example .env
# Edit .env with your service URLs and API keys

# Start server
python -m arrmate.interfaces.api.app
```

## Usage Examples

```
list my TV shows
add Breaking Bad to my library
remove episode 1 of Angel season 1
search for 4K version of Blade Runner
```

## Documentation

- 📖 [Docker Deployment](DOCKER.md)
- 🌐 [Web UI Guide](WEB_UI_GUIDE.md)
- ⚙️ Configuration via `.env` file

## Requirements

- Python 3.11+
- LLM Provider (Ollama/OpenAI/Anthropic)
- Sonarr/Radarr/Lidarr instances

## Version

Current: **0.2.0**

## License

MIT

## Contributors

- Arrmate Contributors
- Claude Sonnet 4.5
