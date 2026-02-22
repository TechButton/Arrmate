# Quick Start

## Docker (recommended)

```bash
curl -O https://raw.githubusercontent.com/techbutton/arrmate/main/docker-compose.prod.yml
curl -O https://raw.githubusercontent.com/techbutton/arrmate/main/.env.example
cp .env.example .env
```

Open `.env` and fill in at minimum:

- `LLM_PROVIDER` and the corresponding model/key settings
- URLs and API keys for any services you want to connect

```bash
docker compose -f docker-compose.prod.yml up -d
```

Then open `http://localhost:8000`.

If you're using Ollama, pull a model:

```bash
docker compose -f docker-compose.prod.yml exec ollama ollama pull qwen2.5:7b
```

`qwen2.5:7b` works well for tool-calling. Larger models will be more accurate with complex commands.

## Local Python

```bash
git clone https://github.com/techbutton/arrmate.git
cd arrmate
python3 -m venv venv && source venv/bin/activate
pip install -e .
cp .env.example .env
# edit .env
python -m arrmate.interfaces.api.app
```

## Finding API keys

**Sonarr / Radarr / Lidarr / Bazarr:** Settings → General → Security → API Key

**Plex token:** Sign in at app.plex.tv, open any item, click `···` → Get Info → View XML — the token is in the URL as `X-Plex-Token`.

**AudioBookshelf:** Settings → Security → API Tokens

## Troubleshooting

**Services show as unavailable** — verify the URL is reachable from inside the container. Use Docker service names (e.g. `http://sonarr:8989`), not `localhost`, when services are on the same Docker network.

**Commands aren't parsed correctly** — your Ollama model may not support tool-calling reliably. `qwen2.5:7b` or `llama3.1` are good options. For OpenAI/Anthropic the defaults work fine.

**Can't reach Sonarr/Radarr** — test from inside the container:

```bash
docker exec arrmate curl http://sonarr:8989/api/v3/system/status?apikey=YOUR_KEY
```

**Locked out** — delete `auth.json` from your data volume and restart.
