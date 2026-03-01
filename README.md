# Arrmate

Arrmate is a natural language interface for your media server stack. Type plain English — it figures out what you mean and calls the right API.

```
"remove episode 1 and 2 of Angel season 1"
"add Breaking Bad to my library"
"convert all my movies to H265"
"rate The Matrix 5 stars"
"backup Plex database"
```

Works with Sonarr, Radarr, Lidarr, Bazarr, Plex, AudioBookshelf, ReadMeABook, SABnzbd, qBittorrent, and more. Uses your choice of local (Ollama, LM Studio, LocalAI) or cloud LLM (OpenAI, Anthropic, Groq, OpenRouter, Mistral, and any OpenAI-compatible API).

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
| ReadMeABook | Audiobooks | Search, request, and manage audiobook acquisition |
| LazyLibrarian | Books | Search and manage book libraries |
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

Open `http://localhost:8000` and sign in with the default credentials:

```
Username: admin
Password: changeme123
```

You'll be prompted to set a new password on first login.

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

Arrmate supports three built-in providers, plus any OpenAI-compatible API via the `openai` provider with a custom base URL.

### Built-in providers

| Provider | Set in .env | Notes |
|----------|-------------|-------|
| Ollama | `LLM_PROVIDER=ollama` | Runs locally, free. `qwen2.5:7b` recommended. |
| OpenAI | `LLM_PROVIDER=openai` | Requires `OPENAI_API_KEY`. Defaults to `gpt-4o`. |
| Anthropic | `LLM_PROVIDER=anthropic` | Requires `ANTHROPIC_API_KEY`. Defaults to `claude-3-5-sonnet`. |

### OpenAI-compatible providers

Any service with an OpenAI-compatible API works by setting `LLM_PROVIDER=openai`, a custom `OPENAI_BASE_URL`, and the matching `OPENAI_MODEL`. **The model must support tool/function calling.**

| Provider | `OPENAI_BASE_URL` | Good models | Notes |
|----------|-------------------|-------------|-------|
| **[Groq](https://groq.com)** | `https://api.groq.com/openai/v1` | `llama-3.3-70b-versatile` | Very fast inference, free tier available |
| **[OpenRouter](https://openrouter.ai)** | `https://openrouter.ai/api/v1` | `meta-llama/llama-3.3-70b-instruct` | Routes to 200+ models; free tier on many |
| **[Mistral AI](https://mistral.ai)** | `https://api.mistral.ai/v1` | `mistral-large-latest`, `mistral-small-latest` | European provider, strong reasoning |
| **[Together AI](https://together.ai)** | `https://api.together.xyz/v1` | `meta-llama/Llama-3.3-70B-Instruct-Turbo` | Many open models, fast inference |
| **[LM Studio](https://lmstudio.ai)** | `http://localhost:1234/v1` | *(any tool-calling model you load)* | Local GUI app, Windows/Mac/Linux |
| **[LocalAI](https://localai.io)** | `http://localhost:8080/v1` | *(any tool-calling model you load)* | Self-hosted, Docker-friendly |
| **[Jan](https://jan.ai)** | `http://localhost:1337/v1` | *(any tool-calling model you load)* | Local GUI app, fully offline |
| **[xAI / Grok](https://x.ai)** | `https://api.x.ai/v1` | `grok-2-latest` | OpenAI-compatible API |
| **[Google Gemini](https://ai.google.dev)** | `https://generativelanguage.googleapis.com/v1beta/openai/` | `gemini-2.0-flash` | Requires Google AI Studio API key |

**Example — using Groq:**

```bash
LLM_PROVIDER=openai
OPENAI_API_KEY=gsk_your-groq-api-key
OPENAI_BASE_URL=https://api.groq.com/openai/v1
OPENAI_MODEL=llama-3.3-70b-versatile
```

**Example — using LM Studio locally:**

```bash
LLM_PROVIDER=openai
OPENAI_API_KEY=lm-studio  # any non-empty string
OPENAI_BASE_URL=http://host.docker.internal:1234/v1
OPENAI_MODEL=your-loaded-model-name
```

> **Important:** The model must support **tool/function calling**. For Ollama, `qwen2.5:7b` and `llama3.1:8b` are reliable choices. For local apps like LM Studio or Jan, look for models tagged with "tool use" or "function calling" support.

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

**Default credentials:** On a fresh install, a default admin account is created automatically:

```
Username: admin
Password: changeme123
```

The login page will display these credentials as a reminder until the password is changed. You'll be prompted to set a new password immediately after signing in.

After that, invite additional users from the Admin Panel (`/web/admin`) — share the generated link and they register with a role you pick.

Existing `auth.json` single-user setups are automatically migrated to the new system on first startup.

Locked out? Delete `/data/users.db` and restart — the default admin account will be recreated.

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
