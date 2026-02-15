# Arrmate 🤝

Your AI companion for Sonarr, Radarr, and Lidarr - manage your media library with natural language.

## Features

- 🗣️ **Natural Language Interface** - Control your media with plain English
- 🌐 **Mobile-Friendly Web UI** - Built with HTMX and Tailwind CSS
- 🐳 **Docker Ready** - Deploy in minutes with your existing services
- 🤖 **Multiple LLM Providers** - Ollama (local), OpenAI, or Anthropic
- 📺 **Multi-Service Support** - Sonarr (TV), Radarr (Movies), Lidarr (Music), and more
- 🔒 **Optional Authentication** - Protect your instance with username/password login

## Supported Services

### Primary Media Services
| Service | Status | API | Media Type | Features |
|---------|--------|-----|------------|----------|
| **Sonarr v3** | ✅ Complete | v3 | TV Shows | Full Support |
| **Radarr v3** | ✅ Complete | v3 | Movies | Full Support |
| **Lidarr v3** | 🔜 Implemented | v3 | Music | Testing Required |
| **Whisparr v3** | 🔜 Implemented | v3 | Adult Content | Testing Required |

### Book & Audiobook Services
| Service | Status | API | Media Type | Notes |
|---------|--------|-----|------------|-------|
| **AudioBookshelf** | 🔜 Implemented | REST | Audiobooks/Podcasts | Modern player with apps |
| **LazyLibrarian** | 🔜 Implemented | Custom | Books/Audiobooks | Automated downloading |
| **Readarr** | ⚠️ Deprecated | v1 | Books/Audiobooks | Project Retired |

### Companion & Orchestration
| Service | Status | API | Purpose | Notes |
|---------|--------|-----|---------|-------|
| **Bazarr** | 🔜 Implemented | Custom | Subtitles | Sonarr/Radarr companion |
| **huntarr.io** | 🔜 Implemented | REST | Orchestration | Multi-service automation |
| **Plex** | 🔜 Implemented | REST | Media Server | Testing Required |

**Legend:** ✅ Complete | 🔜 Testing Required | ⚠️ Deprecated

See [docs/services.md](docs/services.md) for detailed service documentation, features, and configuration.

## Quick Start with Docker

The easiest way to run Arrmate is with Docker alongside your existing *arr services.

### Prerequisites

- Docker and Docker Compose installed
- Running instances of Sonarr, Radarr, or Lidarr
- LLM provider (Ollama, OpenAI, or Anthropic)

### Installation

```bash
# 1. Create docker-compose.yml
curl -O https://raw.githubusercontent.com/techbutton/arrmate/main/docker-compose.yml

# 2. Create .env file
curl -O https://raw.githubusercontent.com/techbutton/arrmate/main/.env.example
mv .env.example .env

# 3. Edit .env with your settings
nano .env
# Add your Sonarr/Radarr URLs and API keys
# Configure your LLM provider

# 4. Start Arrmate
docker compose up -d

# 5. Access the web UI
# http://localhost:8000/web/
```

### Environment Variables

Required in `.env`:

```bash
# LLM Provider (choose one)
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://ollama:11434   # use container name on same Docker host
OLLAMA_MODEL=qwen2.5:7b              # recommended model for tool calling

# Your *arr Services (comment out any you don't use — they won't appear in UI)
SONARR_URL=http://sonarr:8989
SONARR_API_KEY=your-api-key
RADARR_URL=http://radarr:7878
RADARR_API_KEY=your-api-key
```

> **Tip:** Use Docker service/container names as hostnames (e.g. `http://sonarr:8989`) when services run on the same Docker host. See [.env.example](.env.example) for all options including GPU acceleration and Traefik.

### Authentication (Optional)

Arrmate's web UI and API are open by default. To add login protection:

1. Open **Settings** in the web UI (`/web/settings`)
2. Create a username and password
3. Authentication is now active — all pages and API routes require login

You can disable or delete credentials at any time from the Settings page.

```bash
# Optional .env settings for auth
SECRET_KEY=your-secret-key-here    # For persistent sessions across restarts (auto-generated if empty)
AUTH_DATA_DIR=/data                # Where auth.json is stored (default: /data)
```

When authentication is enabled, API requests require HTTP Basic Auth:

```bash
curl -u username:password http://localhost:8000/api/v1/services
```

> **Locked out?** Delete the `auth.json` file from your data directory and restart.

## Usage Examples

Natural language commands:

```
list my TV shows
add Breaking Bad to my library
remove episode 1 of Angel season 1
search for 4K version of Blade Runner
upgrade all episodes of The Office
```

## Documentation

| Doc | Audience |
|-----|----------|
| [Quick Start](docs/quickstart.md) | New users |
| [Service Reference](docs/services.md) | All users — supported services, API details, config |
| [Docker Deployment](docs/docker.md) | Self-hosted Docker users |
| [Web UI Guide](docs/web-ui.md) | Web interface users |
| [Authentication](docs/authentication.md) | Users wanting login protection |
| [SimpleHomelab Traefik](docs/simplehomelab-traefik.md) | Users with SimpleHomelab Docker-Traefik stack |
| [Docker Hub Publishing](docs/dev/docker-hub.md) | Contributors / maintainers |
| [Publishing Guide](docs/dev/publishing.md) | Contributors / maintainers |

## Development

### Local Setup

```bash
# Clone the repository
git clone https://github.com/techbutton/arrmate.git
cd arrmate

# Install dependencies
pip install -e .

# Configure services
cp .env.example .env
nano .env

# Run the server
python -m arrmate.interfaces.api.app
```

### With Full Stack (for testing)

```bash
# Use the full stack docker-compose
docker compose -f docker-compose.full.yml up -d

# Includes: Arrmate + Ollama + Sonarr + Radarr
```

## Requirements

- Python 3.11+
- LLM Provider (Ollama/OpenAI/Anthropic)
- Sonarr/Radarr/Lidarr instances

## Architecture

```
┌─────────────────────────────────────────┐
│          Your Infrastructure            │
│  ┌──────────┐  ┌──────────┐            │
│  │  Sonarr  │  │  Radarr  │  ...       │
│  └────┬─────┘  └────┬─────┘            │
│       │             │                   │
│       └──────┬──────┘                   │
│              │                          │
│        ┌─────▼──────┐                   │
│        │  Arrmate   │ ← You add this   │
│        │   :8000    │                   │
│        └─────┬──────┘                   │
│              │                          │
│        ┌─────▼──────┐                   │
│        │   LLM      │ (Ollama/etc)     │
│        └────────────┘                   │
└─────────────────────────────────────────┘
```

## Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) and [docs/dev/publishing.md](docs/dev/publishing.md) for the release process.

## Version

Current: **0.2.5**

## License

MIT

## Contributors

- Arrmate Contributors
- Claude Sonnet 4.5

## Links

- 🐳 [Docker Hub](https://hub.docker.com/r/techbutton/arrmate)
- 🐙 [GitHub](https://github.com/techbutton/arrmate)
- 📚 [Documentation](https://github.com/techbutton/arrmate#readme)
