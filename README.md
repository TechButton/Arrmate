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

## Screenshots

<p align="center">
  <img src="docs/screenshots/dashboard.png" alt="Dashboard — service overview and media counts" width="700">
</p>
<p align="center">
  <img src="docs/screenshots/command.png" alt="Command page — natural language input" width="700">
</p>
<p align="center">
  <img src="docs/screenshots/services.png" alt="Services status page" width="700">
</p>
<p align="center">
  <img src="docs/screenshots/settings.png" alt="Settings — service URLs and API keys" width="700">
</p>
<p align="center">
  <img src="docs/screenshots/transcode.png" alt="Transcode jobs — H.265 conversion progress" width="700">
</p>

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
| Prowlarr | Indexer aggregator | Search all indexers, send results to download managers |
| SABnzbd | Downloads | Queue, speed control, per-item priority/pause/resume, add by URL |
| NZBget | Downloads | Queue, speed control, per-item priority/pause/resume, add by URL |
| qBittorrent | Torrents | Queue, speed limits, priority reorder, add by URL/magnet |
| Transmission | Torrents | Queue, speed limits, bandwidth priority, add by URL/magnet |

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

## Multi-User Authentication

Arrmate includes a full multi-user system with three roles:

| Role | Access |
|------|--------|
| **admin** | Full access — settings, user management, execute commands, approve requests |
| **power_user** | Execute commands, approve/fulfill media requests |
| **user** | Browse library, submit media requests (no execute/delete) |

**First run:** navigate to `/web/register` to create the admin account. After that, invite additional users from the Admin Panel (`/web/admin`) — share the generated link and they register with a role you pick.

Existing `auth.json` single-user setups are automatically migrated to the new system on first startup.

Locked out? Delete `/data/users.db` and restart — you'll be prompted to create a new admin account.

Sessions persist across restarts when `SECRET_KEY` is set in your env.

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
- [Buy Me a Coffee](https://buymeacoffee.com/techbutton) — if Arrmate saves you time, consider supporting development

## License

MIT
