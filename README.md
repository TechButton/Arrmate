# Arrmate

Arrmate is a natural language interface for your media server stack. Type plain English — it figures out what you mean and calls the right API.

```
"remove episode 1 and 2 of Angel season 1"
"add Breaking Bad to my library"
"convert all my movies to H265"
"rate The Matrix 5 stars"
"backup Plex database"
```

Works with Sonarr, Radarr, Lidarr, Bazarr, Plex, SABnzbd, qBittorrent, and more. Uses your choice of local (Ollama) or cloud LLM.

## Supported Services

| Service | Type | What you can do |
|---------|------|-----------------|
| Sonarr | TV | Search, add, remove, upgrade, monitor/unmonitor shows and episodes |
| Radarr | Movies | Search, add, remove, upgrade, monitor/unmonitor movies |
| Lidarr | Music | Search, add, remove artists and albums |
| Plex | Media server | History, continue watching, on deck, recently added, rate items, Butler maintenance, terminate sessions |
| Bazarr | Subtitles | Download and sync subtitles by language |
| AudioBookshelf | Audiobooks | Browse and search libraries |
| LazyLibrarian | Books | Search and manage book libraries |
| huntarr.io | Stats | Dashboard metrics across all services |
| SABnzbd | Downloads | Queue status, speed control, pause/resume |
| NZBget | Downloads | Queue status, speed control, pause/resume |
| qBittorrent | Torrents | Queue status, speed limits, pause/resume |
| Transmission | Torrents | Queue status, speed limits, pause/resume |

Services are optional — anything not configured simply doesn't appear in the UI.

## Quick Start

```bash
# Pull the compose file and create your env
curl -O https://raw.githubusercontent.com/techbutton/arrmate/main/docker-compose.prod.yml
curl -O https://raw.githubusercontent.com/techbutton/arrmate/main/.env.example
cp .env.example .env
```

Edit `.env` with your service URLs and API keys, then:

```bash
docker compose -f docker-compose.prod.yml up -d
```

Open `http://localhost:8000` — that's it.

### Minimum config

```bash
# Pick one LLM provider:
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=qwen2.5:7b

# Add whichever services you run (others stay hidden):
SONARR_URL=http://sonarr:8989
SONARR_API_KEY=your-key
RADARR_URL=http://radarr:7878
RADARR_API_KEY=your-key
```

Use Docker container names as hostnames when services are on the same Docker network. See [.env.example](.env.example) for the full list including Plex, download managers, and GPU acceleration.

## LLM Providers

| Provider | Set in .env | Notes |
|----------|-------------|-------|
| Ollama | `LLM_PROVIDER=ollama` | Runs locally, free. `qwen2.5:7b` recommended. |
| OpenAI | `LLM_PROVIDER=openai` | Requires `OPENAI_API_KEY`. Defaults to `gpt-4o`. |
| Anthropic | `LLM_PROVIDER=anthropic` | Requires `ANTHROPIC_API_KEY`. Defaults to `claude-3-5-sonnet`. |

## H.265 Transcoding

Arrmate can scan your Sonarr/Radarr libraries for files not already in H.265 and run ffmpeg on them in the background:

```
"convert all my movies to H265"
"transcode Breaking Bad to save space"
```

Track progress at `/web/transcode`. Requires media files to be accessible inside the container — see the volume mount comments in the compose file.

## Authentication

Off by default. Enable it from the Settings page — pick a username and password, and all routes (web and API) require login from that point on. Sessions persist across restarts when `SECRET_KEY` is set in your env.

Locked out? Delete `auth.json` from your data directory and restart.

## API

The REST API lives at `/api/v1/`. Interactive docs: `http://localhost:8000/docs`.

```bash
# Execute a command
curl -X POST http://localhost:8000/api/v1/execute \
  -H "Content-Type: application/json" \
  -d '{"command": "list my TV shows"}'

# With auth
curl -u username:password http://localhost:8000/api/v1/services
```

## Documentation

- [Quick Start](docs/quickstart.md)
- [Docker Deployment](docs/docker.md)
- [Service Reference](docs/services.md)
- [Web UI](docs/web-ui.md)
- [Authentication](docs/authentication.md)
- [SimpleHomelab / Traefik](docs/simplehomelab-traefik.md)

## Development

```bash
git clone https://github.com/techbutton/arrmate.git
cd arrmate
pip install -e ".[dev]"
cp .env.example .env
# edit .env
python -m arrmate.interfaces.api.app
```

Full local stack with Sonarr + Radarr + Ollama included:

```bash
docker compose -f docker-compose.full.yml up -d
```

## Links

- [Docker Hub](https://hub.docker.com/r/techbutton/arrmate)
- [GitHub](https://github.com/techbutton/arrmate)
- [Issues](https://github.com/techbutton/arrmate/issues)

## License

MIT
