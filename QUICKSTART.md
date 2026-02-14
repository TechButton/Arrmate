# Arrmate Quick Start Guide

Get up and running with Arrmate in 5 minutes.

## Prerequisites

- Python 3.11+ OR Docker
- Sonarr and/or Radarr already running
- Sonarr/Radarr API keys (found in Settings → General → Security)

## Option 1: Docker (Easiest)

### Step 1: Configure

```bash
# Clone/download the project
cd arrmate

# Create .env file
cp .env.example .env

# Edit .env with your API keys
nano .env  # or use your favorite editor
```

Required in `.env`:
```bash
SONARR_URL=http://sonarr:8989  # Use container name if on same network
SONARR_API_KEY=your-actual-api-key

RADARR_URL=http://radarr:7878
RADARR_API_KEY=your-actual-api-key
```

### Step 2: Start Services

```bash
cd docker
docker-compose up -d
```

### Step 3: Pull LLM Model (if using Ollama)

```bash
docker exec -it arrmate-ollama ollama pull llama3.1
```

### Step 4: Test It!

```bash
# Check services are connected
docker exec -it arrmate arrmate services

# Try a command
docker exec -it arrmate arrmate execute "list my TV shows"

# Or use the API
curl -X POST http://localhost:8000/api/v1/execute \
  -H "Content-Type: application/json" \
  -d '{"command": "list my TV shows"}'
```

## Option 2: Local Python

### Step 1: Setup

```bash
# Run setup script
bash scripts/dev-setup.sh

# OR manually:
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

### Step 2: Configure

```bash
# Create .env
cp .env.example .env

# Edit with your settings
nano .env
```

For local setup, use localhost:
```bash
SONARR_URL=http://localhost:8989
SONARR_API_KEY=your-actual-api-key

RADARR_URL=http://localhost:7878
RADARR_API_KEY=your-actual-api-key

# LLM - choose one:
LLM_PROVIDER=ollama  # Free, runs locally
# LLM_PROVIDER=openai  # Requires API key
# LLM_PROVIDER=anthropic  # Requires API key
```

### Step 3: Install Ollama (if using local LLM)

```bash
# Install Ollama: https://ollama.ai
# Then pull a model:
ollama pull llama3.1
```

### Step 4: Test It!

```bash
# Activate venv
source venv/bin/activate

# Check services
arrmate services

# Try commands
arrmate execute "list my TV shows"

# Interactive mode
arrmate interactive
```

## Common Commands

```bash
# List library
arrmate execute "show me all my TV shows"
arrmate execute "list my movies"

# Add to library
arrmate execute "add Breaking Bad to my library"
arrmate execute "add The Matrix"

# Remove content
arrmate execute "remove episode 1 of Angel season 1"
arrmate execute "delete episodes 1 and 2 of The Office season 2"

# Search
arrmate execute "search for 4K version of Blade Runner"

# Dry run (see what would happen without doing it)
arrmate execute --dry-run "remove season 1 of Dexter"
```

## Troubleshooting

### "Could not connect to Sonarr/Radarr"

1. Check URLs are correct in `.env`
2. Check API keys are correct
3. Test manually:
   ```bash
   curl http://localhost:8989/api/v3/system/status?apikey=YOUR_KEY
   ```

### "LLM did not use the parse_media_command function"

Your model may not support tool calling. Use:
- Ollama: `llama3.1` or `mistral`
- OpenAI: `gpt-4` or `gpt-3.5-turbo`
- Anthropic: `claude-3-5-sonnet` or newer

### Docker: Services not found

If Sonarr/Radarr are on a different Docker network:

1. Find your network: `docker network ls`
2. Edit `docker/docker-compose.yml`:
   ```yaml
   networks:
     media-network:
       external: true
       name: your-actual-network-name
   ```
3. Restart: `docker-compose up -d`

## Next Steps

- Read the [full README](README.md) for advanced features
- Check API documentation: http://localhost:8000/docs
- Configure multiple LLM providers
- Set up webhooks for automation

## Getting Help

- Check `arrmate --help`
- View service status: `arrmate services`
- View config: `arrmate config`
- Check logs: `docker logs arrmate` (Docker) or see console output (local)
