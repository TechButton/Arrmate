# Arrmate - Natural Language Media Management

Control your media library with natural language commands. Arrmate provides a unified interface to Sonarr, Radarr, Lidarr, and future services using LLMs to parse your intent.

## Features

- **Natural Language Interface**: Just say what you want
  - "remove episode 1 and 2 of Angel season 1"
  - "add Breaking Bad to my library"
  - "search for 4K version of Blade Runner"
  - "show me all my TV shows"

- **Multi-Provider LLM Support**: Choose your preferred LLM
  - Ollama (default, runs locally)
  - OpenAI (GPT-4, GPT-3.5)
  - Anthropic (Claude)

- **Multiple Interfaces**:
  - **CLI**: Quick commands from terminal
  - **REST API**: Integrate with other tools
  - **Web UI**: Coming soon

- **Service Integration**:
  - ✅ Sonarr (TV shows)
  - ✅ Radarr (Movies)
  - 🚧 Lidarr (Music) - planned
  - 🚧 Readarr (Audiobooks) - planned

## Quick Start

### Using Docker (Recommended)

1. **Clone and configure**:
```bash
git clone <repo-url>
cd arrmate
cp .env.example .env
```

2. **Edit `.env` with your settings**:
```bash
# Required: Your Sonarr/Radarr API keys
SONARR_URL=http://sonarr:8989
SONARR_API_KEY=your-api-key-here

RADARR_URL=http://radarr:7878
RADARR_API_KEY=your-api-key-here

# Optional: LLM provider (defaults to Ollama)
LLM_PROVIDER=ollama
```

3. **Start services**:
```bash
cd docker
docker-compose up -d
```

4. **Pull Ollama model** (if using Ollama):
```bash
docker exec -it arrmate-ollama ollama pull llama3.1
```

5. **Test it out**:
```bash
# Via CLI
docker exec -it arrmate arrmate execute "list my TV shows"

# Via API
curl -X POST http://localhost:8000/api/v1/execute \
  -H "Content-Type: application/json" \
  -d '{"command": "list my TV shows"}'
```

### Local Installation

1. **Install dependencies**:
```bash
pip install -r requirements.txt
pip install -e .
```

2. **Configure environment**:
```bash
cp .env.example .env
# Edit .env with your settings
```

3. **Run commands**:
```bash
# CLI
arrmate execute "add The Expanse to my library"

# Interactive mode
arrmate interactive

# Start API server
python -m arrmate.interfaces.api.app
```

## Usage Examples

### CLI Interface

```bash
# Remove episodes
arrmate execute "remove episode 1 and 2 of Angel season 1"

# Add to library
arrmate execute "add Breaking Bad to my library"

# Search for specific version
arrmate execute "search for 4K version of Blade Runner"

# List library
arrmate execute "show me all my TV shows"

# Interactive mode
arrmate interactive
> add The Expanse
> remove season 1 of Dexter
> quit

# Check service status
arrmate services

# View configuration
arrmate config

# Dry run (parse only)
arrmate execute --dry-run "remove episode 5 of The Office season 2"
```

### REST API

Start the API server:
```bash
# Local
python -m arrmate.interfaces.api.app

# Docker
docker-compose up -d
```

Execute commands:
```bash
# Execute command
curl -X POST http://localhost:8000/api/v1/execute \
  -H "Content-Type: application/json" \
  -d '{
    "command": "remove episode 1 of Angel season 1"
  }'

# Dry run (parse only)
curl -X POST http://localhost:8000/api/v1/execute \
  -H "Content-Type: application/json" \
  -d '{
    "command": "add Breaking Bad",
    "dry_run": true
  }'

# Check services
curl http://localhost:8000/api/v1/services

# Health check
curl http://localhost:8000/health
```

API documentation: http://localhost:8000/docs

## Configuration

### Environment Variables

See `.env.example` for all available options.

**Required**:
- `SONARR_URL` / `SONARR_API_KEY` - For TV shows
- `RADARR_URL` / `RADARR_API_KEY` - For movies

**LLM Provider** (choose one):

**Ollama (default)**:
```bash
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:latest
```

**OpenAI**:
```bash
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4-turbo-preview
```

**Anthropic**:
```bash
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
```

### Finding API Keys

Sonarr/Radarr/Lidarr API keys:
1. Open the web UI
2. Go to Settings → General → Security
3. Copy the API Key

## Docker Deployment

### Joining Existing Network

If you already have Sonarr/Radarr running in Docker:

1. Find your existing network:
```bash
docker network ls
```

2. Edit `docker-compose.yml`:
```yaml
networks:
  media-network:
    external: true
    name: your-existing-network-name
```

3. Update service URLs in `.env`:
```bash
SONARR_URL=http://sonarr:8989  # Use container name
RADARR_URL=http://radarr:7878
```

### Using Ollama

The docker-compose includes Ollama for local LLM:

```bash
# Pull a model
docker exec -it arrmate-ollama ollama pull llama3.1

# List available models
docker exec -it arrmate-ollama ollama list

# Try different models
docker exec -it arrmate-ollama ollama pull mistral
```

Recommended models:
- `llama3.1:latest` - Best balance of speed and accuracy
- `mistral:latest` - Faster, slightly less accurate
- `llama3.1:70b` - Most accurate (requires GPU)

## Architecture

```
User Command → Interface (CLI/API/Web)
    ↓
Command Parser (LLM) → Extract Intent
    ↓
Intent Engine → Validate & Enrich
    ↓
Executor → API Operations
    ↓
Media Client (Sonarr/Radarr/Lidarr)
    ↓
Result → User
```

### Components

- **Command Parser**: Uses LLM tool calling to extract structured intent
- **Intent Engine**: Validates intent and enriches with IDs via fuzzy matching
- **Executor**: Maps intent to specific API operations
- **Media Clients**: API clients for each service (Sonarr, Radarr, etc.)
- **LLM Providers**: Abstracted multi-provider support

## Development

### Setup

```bash
# Install dev dependencies
pip install -r requirements.txt
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black src/

# Lint
ruff src/

# Type check
mypy src/
```

### Project Structure

```
arrmate/
├── src/arrmate/
│   ├── core/           # Core logic (parser, intent, executor)
│   ├── llm/            # LLM provider abstraction
│   ├── clients/        # Media service API clients
│   ├── interfaces/     # CLI, API, Web UI
│   └── config/         # Configuration management
├── docker/             # Docker deployment
├── tests/              # Test suite
└── config/             # Runtime config (prompts, etc.)
```

### Adding a New LLM Provider

1. Create provider in `src/arrmate/llm/`:
```python
from .base import BaseLLMProvider

class MyProvider(BaseLLMProvider):
    async def parse_command(self, user_input, tools, system_prompt):
        # Implement tool calling
        pass
```

2. Register in `llm/factory.py`:
```python
from .myprovider import MyProvider

_PROVIDERS["myprovider"] = MyProvider
```

3. Add to settings in `config/settings.py`

### Adding a New Media Service

1. Create client in `src/arrmate/clients/`:
```python
from .base import BaseMediaClient

class MyServiceClient(BaseMediaClient):
    async def search(self, query):
        # Implement search
        pass
```

2. Update `clients/discovery.py` to include service

3. Add to `MediaType` enum in `core/models.py`

## Troubleshooting

### "Could not find series/movie"

The item must either:
- Already be in your Sonarr/Radarr library, OR
- Be searchable via TVDB/TMDB

Check your indexers are configured in Sonarr/Radarr.

### "LLM did not use the parse_media_command function"

Your LLM model may not support tool calling. Try:
- Ollama: Use `llama3.1` or `mistral`
- OpenAI: Use `gpt-4` or `gpt-3.5-turbo`
- Anthropic: Use any Claude 3+ model

### Service Discovery Issues

If services aren't found:
1. Check they're on the same Docker network
2. Verify URLs use container names (not localhost)
3. Test connection: `arrmate services`

## Roadmap

- [x] Core NL parsing with LLM
- [x] Sonarr integration
- [x] Radarr integration
- [x] CLI interface
- [x] REST API
- [x] Docker deployment
- [ ] Web UI (Streamlit or HTMX)
- [ ] Lidarr integration (music)
- [ ] Readarr integration (audiobooks)
- [ ] Conversation memory (multi-turn)
- [ ] Webhooks (react to events)
- [ ] Scheduling (cron-like)

## License

MIT

## Contributing

Contributions welcome! Please open an issue or PR.
