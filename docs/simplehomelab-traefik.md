# Arrmate with SimpleHomelab Docker-Traefik

This guide explains how to add Arrmate to an existing [SimpleHomelab Docker-Traefik](https://github.com/SimpleHomelab/Docker-Traefik) setup.

## Quick Setup

### 1. Copy the compose snippet

Copy `compose/arrmate.yml` into your Docker-Traefik `compose/$HOSTNAME/` directory:

```bash
cp compose/arrmate.yml $DOCKERDIR/../compose/$HOSTNAME/arrmate.yml
```

Or download it directly:

```bash
curl -o compose/$HOSTNAME/arrmate.yml \
  https://raw.githubusercontent.com/techbutton/arrmate/main/compose/arrmate.yml
```

### 2. Add environment variables to your `.env`

Add these to your existing `.env` file:

```bash
# ===== Arrmate =====
ARRMATE_PORT=8000

# LLM Provider (ollama | openai | anthropic)
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=qwen2.5:7b

# OpenAI (leave empty if using Ollama)
# OPENAI_API_KEY=sk-your-key-here
# OPENAI_MODEL=gpt-4o

# Anthropic (leave empty if using Ollama)
# ANTHROPIC_API_KEY=sk-ant-your-key-here
# ANTHROPIC_MODEL=claude-3-5-sonnet-20241022

# Media service API keys — Arrmate reads these to connect.
# URLs default to Docker service names if your *arr containers
# are on the same network (e.g. http://sonarr:8989).
SONARR_URL=http://sonarr:8989
SONARR_API_KEY=your-sonarr-api-key
RADARR_URL=http://radarr:7878
RADARR_API_KEY=your-radarr-api-key
# LIDARR_URL=http://lidarr:8686
# LIDARR_API_KEY=your-lidarr-api-key
# BAZARR_URL=http://bazarr:6767
# BAZARR_API_KEY=your-bazarr-api-key
# PLEX_URL=http://plex:32400
# PLEX_TOKEN=your-plex-token

# Authentication (optional — set up via web UI Settings page)
# SECRET_KEY=your-random-secret-key
```

### 3. Include Arrmate in docker-compose

Add this line to the `include:` section of your `docker-compose-$HOSTNAME.yml`:

```yaml
include:
  # ... existing services ...
  - compose/$HOSTNAME/arrmate.yml
```

### 4. Start Arrmate

```bash
docker compose -f docker-compose-$HOSTNAME.yml --profile starr up -d arrmate
```

Or if you use the `all` profile:

```bash
docker compose -f docker-compose-$HOSTNAME.yml --profile all up -d
```

### 5. Access the web UI

Open `http://your-server-ip:$ARRMATE_PORT/web/` in your browser.

## Traefik Labels

The compose snippet includes a `# DOCKER-LABELS-PLACEHOLDER` comment compatible with the SimpleHomelab label automation. If you manage labels manually, replace the placeholder with:

```yaml
    labels:
      - "traefik.enable=true"
      # HTTP router
      - "traefik.http.routers.arrmate-rtr.entrypoints=websecure"
      - "traefik.http.routers.arrmate-rtr.rule=Host(`arrmate.$DOMAINNAME_1`)"
      # Middlewares (adjust chain as needed)
      - "traefik.http.routers.arrmate-rtr.middlewares=chain-no-auth@file"
      # Service
      - "traefik.http.routers.arrmate-rtr.service=arrmate-svc"
      - "traefik.http.services.arrmate-svc.loadbalancer.server.port=8000"
```

If using Arrmate's built-in authentication, use `chain-no-auth@file`. If you prefer Traefik-level OAuth/Authelia instead, use `chain-oauth@file` or `chain-authelia@file` and leave Arrmate's auth disabled.

When using Traefik labels, also add `t3_proxy` to the networks:

```yaml
    networks:
      - default
      - t3_proxy
```

## How It Fits Together

Arrmate connects to your existing *arr services over the shared Docker network. It does **not** need its own Sonarr/Radarr instances — it talks to the ones you already run.

```
┌─────────────────────────────────────────────┐
│         Your Docker-Traefik Stack           │
│                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │  Sonarr  │  │  Radarr  │  │   Plex   │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  │
│       └──────┬──────┘──────────────┘        │
│              │                              │
│        ┌─────▼──────┐                       │
│        │  Arrmate   │ ← this service        │
│        │   :8000    │                       │
│        └─────┬──────┘                       │
│              │                              │
│        ┌─────▼──────┐                       │
│        │   Ollama   │ (or OpenAI/Anthropic) │
│        └────────────┘                       │
│                                             │
│  ┌──────────┐                               │
│  │ Traefik  │──→ arrmate.yourdomain.com     │
│  └──────────┘                               │
└─────────────────────────────────────────────┘
```

## LLM Provider

Arrmate needs an LLM to understand natural language commands. If you already run Ollama in your stack, just point `OLLAMA_BASE_URL` to it. Otherwise, add an Ollama service or use OpenAI/Anthropic.

If your Ollama is on the same Docker network:

```bash
OLLAMA_BASE_URL=http://ollama:11434
```

If it's on a separate machine:

```bash
OLLAMA_BASE_URL=http://192.168.1.x:11434
```

## Data Persistence

Arrmate stores authentication credentials in `/data` inside the container. The compose snippet maps this to `$DOCKERDIR/appdata/arrmate`, following the SimpleHomelab convention. This persists across container restarts.

## Profiles

The compose snippet registers under the `media`, `starr`, and `all` profiles, matching how Sonarr/Radarr/Lidarr are grouped in the SimpleHomelab stack.

---

Back to [Documentation](README.md) | [README](../README.md)
