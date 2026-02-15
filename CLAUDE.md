# Arrmate - AI Media Library Companion

## Project Overview

Arrmate is a natural language interface for managing media services (Sonarr, Radarr, Lidarr, Plex, and more). Users type plain English commands, an LLM parses them into structured intents, and Arrmate executes them against the configured services.

- **Language**: Python 3.11+
- **Web framework**: FastAPI + HTMX + Tailwind CSS + Alpine.js
- **Templates**: Jinja2 (server-rendered)
- **Package manager**: pip / setuptools (pyproject.toml)
- **Version**: 0.2.5

## Project Structure

```
src/arrmate/
├── auth/              # Optional authentication system
│   ├── manager.py     # AuthManager — credential CRUD, bcrypt hashing
│   ├── session.py     # Signed cookie sessions (itsdangerous)
│   └── dependencies.py # FastAPI Depends() for route protection
├── clients/           # Service API clients
│   ├── base.py        # Base Arr client (Sonarr/Radarr/Lidarr pattern)
│   ├── base_companion.py   # Base for companion services (Bazarr, etc.)
│   ├── base_external.py    # Base for non-Arr services (Plex, etc.)
│   ├── discovery.py   # Auto-discovery of configured services
│   ├── sonarr.py      # Sonarr client (TV)
│   ├── radarr.py      # Radarr client (Movies)
│   ├── lidarr.py      # Lidarr client (Music)
│   ├── plex.py        # Plex Media Server client
│   ├── bazarr.py      # Bazarr client (Subtitles)
│   ├── audiobookshelf.py   # AudioBookshelf client
│   ├── lazylibrarian.py    # LazyLibrarian client
│   ├── huntarr.py     # huntarr.io client
│   ├── whisparr.py    # Whisparr client
│   └── readarr.py     # Readarr client (deprecated)
├── config/
│   └── settings.py    # Pydantic Settings (env vars)
├── core/
│   ├── models.py      # Pydantic models (Intent, ExecutionResult, etc.)
│   ├── command_parser.py   # LLM-powered NL → Intent parsing
│   ├── intent_engine.py    # Intent enrichment + validation
│   └── executor.py    # Intent → API call execution
├── interfaces/
│   ├── api/
│   │   └── app.py     # FastAPI app, API routes, router inclusion
│   ├── cli/
│   │   └── main.py    # Typer CLI (arrmate command)
│   └── web/
│       ├── routes.py  # Web routes (HTMX pages + partials)
│       ├── static/    # CSS
│       └── templates/ # Jinja2 templates
│           ├── base.html
│           ├── components/  # Reusable: navbar, toast, cards
│           ├── pages/       # Full pages: index, command, settings, login, etc.
│           └── partials/    # HTMX swap targets: results, lists, auth_settings
└── llm/               # LLM provider abstraction
```

## Key Files

| File | Purpose |
|------|---------|
| `src/arrmate/interfaces/api/app.py` | FastAPI app entry point, all routers mounted here |
| `src/arrmate/interfaces/web/routes.py` | All web routes (protected + auth), Jinja2 template globals |
| `src/arrmate/config/settings.py` | All env var configuration (Settings class) |
| `src/arrmate/clients/discovery.py` | Service auto-discovery logic |
| `src/arrmate/auth/manager.py` | Auth credential management |
| `pyproject.toml` | Dependencies and project metadata |

## Docker & Deployment

| File | Purpose |
|------|---------|
| `Dockerfile` | Main Dockerfile (builds from source) |
| `docker-compose.yml` | Dev/self-hosted compose (build from source) |
| `docker-compose.prod.yml` | Production compose (Docker Hub image) |
| `docker-compose.full.yml` | Full stack with Sonarr + Radarr + Ollama |
| `compose/arrmate.yml` | SimpleHomelab Docker-Traefik drop-in snippet |
| `.env.example` | Full env var reference with documentation |

## Documentation

All docs live in `docs/`:
- `quickstart.md` — Getting started
- `docker.md` — Docker deployment guide
- `web-ui.md` — Web interface guide
- `services.md` — Supported services reference
- `authentication.md` — Optional login system
- `simplehomelab-traefik.md` — SimpleHomelab Docker-Traefik integration

## Architecture Notes

- **Auth is optional**: Disabled by default. `require_auth` dependency passes through when no credentials exist. Settings page is always reachable for initial setup.
- **HTMX pattern**: Pages load full HTML, interactive sections swap via HTMX partials. Auth redirect uses `HX-Redirect` header for HTMX requests.
- **Service discovery**: Clients are instantiated based on which env vars are set. No service configured = not shown in UI.
- **LLM flow**: User command → CommandParser (LLM) → Intent model → IntentEngine (enrich/validate) → Executor (API calls) → Result
- **Template globals**: `auth_manager` is registered as a Jinja2 global so navbar can conditionally show Sign Out.

## Common Commands

```bash
# Run locally
pip install -e .
python -m arrmate.interfaces.api.app

# Run with Docker (build from source)
docker compose up -d

# Run with Docker (pre-built image)
docker compose -f docker-compose.prod.yml up -d

# View logs
docker compose logs -f arrmate

# Pull Ollama model
docker compose exec ollama ollama pull qwen2.5:7b
```

## Git Workflow

Always commit and push after making changes:

```bash
git add -A
git commit -m "Description of changes"
git push
```

Commit message style: imperative, concise summary. Examples from history:
- `Add optional authentication and update docs`
- `Add SimpleHomelab Docker-Traefik compose snippet and fix Docker configs`
- `Improve LLM prompts, fix schema bugs, add service-aware parsing`

## Conventions

- **Line length**: 100 chars (configured in pyproject.toml for black/ruff)
- **Python version**: 3.11+ (uses `str | None` union syntax)
- **Imports**: Relative imports within the package (`from ...config.settings import settings`)
- **Settings**: All config via environment variables through Pydantic Settings
- **Templates**: Tailwind CSS utility classes, dark mode only, `card` CSS class for sections
- **Compose env vars**: Use `${VAR:-}` pattern (empty default) so missing vars don't error
