# Arrmate

Arrmate turns plain English into media server commands. Type what you want — it figures out what to do.

```
"can you add Yellowstone for me?"
"the sound is off on Breaking Bad, can you fix it?"
"what movies do I have?"
"add the Dune audiobook"
"what's downloading right now?"
```

**Built for families.** The admin sets it up once. Everyone else — parents, grandparents, partners, kids — just types what they need in plain language, the same way they'd send a text message. No need to know what Sonarr or Radarr is. No menus to navigate, no API keys to deal with. Just ask.

Works with Sonarr, Radarr, Lidarr, Bazarr, Plex, AudioBookshelf, ReadMeABook, SABnzbd, qBittorrent, and more. Powered by your choice of local (Ollama, LM Studio, LocalAI) or cloud AI (OpenAI, Anthropic, Groq, OpenRouter, Mistral, and any OpenAI-compatible API).

---

## How It Works

1. A family member types a plain English message — exactly how they'd text you
2. Arrmate's AI reads it and figures out what they mean
3. It calls the right service (Sonarr, Radarr, Plex, etc.) automatically
4. They see a plain English result — no technical jargon

The admin never needs to get involved for day-to-day requests. Family members self-serve.

---

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

---

## Who It's For

### The Admin (you)
You run the media server — Sonarr, Radarr, Plex, etc. You set up Arrmate once, connect it to your services, and invite your family. After that, most requests take care of themselves.

### Family Members
They just type. A few real-world examples of what they might send:

| What they type | What Arrmate does |
|----------------|-------------------|
| "can you add Yellowstone?" | Searches Sonarr, adds the show |
| "the sound is weird on Interstellar" | Triggers a quality upgrade in Radarr |
| "I can't hear what they're saying in Succession S2" | Searches for a better copy |
| "can you get me the Harry Potter audiobook?" | Submits a request to AudioBookshelf |
| "what shows do I have?" | Lists the library |
| "I finished Ozark, you can delete it" | Removes the series (if they have permission) |
| "put Silo on my list" | Adds it to the library |
| "what's downloading?" | Shows the current download queue |
| "the picture on The Bear is all green" | Upgrades the file |
| "fix Mandalorian season 2, it keeps stopping" | Triggers a search for a better version |

They don't need to know what Sonarr is. They don't need an account on each service. They just need access to Arrmate.

---

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

---

## Setup Guide

### Step 1 — Pick your LLM

Arrmate needs an AI model to understand natural language. You have two main options:

**Option A: Ollama (local, free, no data leaves your server)**

Recommended if you already run Ollama, or want full privacy. Pull a model that supports tool calling:

```bash
ollama pull qwen2.5:7b        # recommended, fast, good quality
# or
ollama pull llama3.1:8b       # larger, slightly better
```

**Option B: Cloud AI (easiest to start)**

Sign up for a free account at one of these — no credit card required for the free tiers:

- **Groq** — [console.groq.com](https://console.groq.com) → API Keys → Create key. Use model `llama-3.3-70b-versatile`. Very fast, generous free tier.
- **Google Gemini** — [aistudio.google.com](https://aistudio.google.com/app/apikey) → Get API key. Use model `gemini-2.0-flash`. Free tier available.
- **OpenRouter** — [openrouter.ai](https://openrouter.ai/settings/keys) → Create key. Many free models available (look for `:free` suffix).

See the full [LLM Providers](#llm-providers) section for all options.

---

### Step 2 — Install Arrmate

```bash
# Download the compose file and example config
curl -O https://raw.githubusercontent.com/TechButton/Arrmate/main/docker-compose.prod.yml
curl -O https://raw.githubusercontent.com/TechButton/Arrmate/main/.env.example
cp .env.example .env
```

Edit `.env` with your details (see Step 3), then start:

```bash
docker compose -f docker-compose.prod.yml up -d
```

Open `http://your-server-ip:8000` in a browser.

---

### Step 3 — Configure your `.env`

Open `.env` in a text editor. The key settings:

**LLM (choose one):**

```bash
# Option A: Ollama
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://ollama:11434    # or http://localhost:11434 if Ollama is on the host
OLLAMA_MODEL=qwen2.5:7b

# Option B: Groq (cloud, free tier)
LLM_PROVIDER=openai
OPENAI_API_KEY=gsk_your-key-from-console.groq.com
OPENAI_BASE_URL=https://api.groq.com/openai/v1
OPENAI_MODEL=llama-3.3-70b-versatile

# Option C: OpenAI
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-key-from-platform.openai.com

# Option D: Anthropic
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-your-key-from-console.anthropic.com
```

**Media services (add whichever you run):**

```bash
SONARR_URL=http://sonarr:8989          # or http://your-server-ip:8989
SONARR_API_KEY=your-sonarr-api-key

RADARR_URL=http://radarr:7878
RADARR_API_KEY=your-radarr-api-key

PLEX_URL=http://plex:32400
PLEX_TOKEN=your-plex-token

LIDARR_URL=http://lidarr:8686
LIDARR_API_KEY=your-lidarr-api-key

BAZARR_URL=http://bazarr:6767
BAZARR_API_KEY=your-bazarr-api-key

AUDIOBOOKSHELF_URL=http://audiobookshelf:13378
AUDIOBOOKSHELF_API_KEY=your-abs-token

READMEABOOK_URL=http://readmeabook:3030
READMEABOOK_API_KEY=your-readmeabook-token
```

> **Tip:** If Arrmate and your services are on the same Docker network, use the container name as the hostname (e.g. `http://sonarr:8989`). If they're on different machines or not in Docker, use the IP address or hostname instead.

**How to find your API keys:**

| Service | Where to find the key |
|---------|----------------------|
| Sonarr | Settings → General → API Key |
| Radarr | Settings → General → API Key |
| Lidarr | Settings → General → API Key |
| Bazarr | Settings → General → API Key |
| AudioBookshelf | Settings → Users → your user → API Token |
| ReadMeABook | Profile → API Tokens |
| Plex | Visit `https://plex.tv/claim` or open any item in Plex → ··· → Get Info → View XML → look for `X-Plex-Token` in the URL |

---

### Step 4 — Log in and change the default password

Open `http://your-server-ip:8000`. The default credentials are:

```
Username: admin
Password: changeme123
```

You'll be prompted to set a new password immediately. Do this before sharing the URL with anyone.

---

### Step 5 — Invite your family

Go to **Admin Panel** (`/web/admin`) → **Invite Links** → create a link.

Pick a role for the family member:

| Role | What they can do |
|------|-----------------|
| **user** | Type commands, browse library, submit requests for new content — can't delete anything |
| **power_user** | Everything a user can do, plus approve requests and execute commands directly |
| **admin** | Full access — settings, user management, everything |

Send them the invite link. They register their own account and can start typing immediately.

---

### Step 6 — Optional: set up notifications

If you want to be notified when a family member submits a media request, add a Slack or Discord webhook to your `.env`:

```bash
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
# or
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

You can also use the Settings → Notifications tab in the web UI.

---

## LLM Providers

Arrmate supports three built-in providers, plus any OpenAI-compatible API via the `openai` provider with a custom base URL.

### Built-in providers

| Provider | Set in .env | Notes |
|----------|-------------|-------|
| Ollama | `LLM_PROVIDER=ollama` | Runs locally, free, private. `qwen2.5:7b` recommended. |
| OpenAI | `LLM_PROVIDER=openai` | Requires `OPENAI_API_KEY`. Defaults to `gpt-4o`. |
| Anthropic | `LLM_PROVIDER=anthropic` | Requires `ANTHROPIC_API_KEY`. Defaults to `claude-sonnet-4-6`. |

### OpenAI-compatible providers

Any service with an OpenAI-compatible API works by setting `LLM_PROVIDER=openai`, a custom `OPENAI_BASE_URL`, and the matching `OPENAI_MODEL`. The model must support tool/function calling.

| Provider | `OPENAI_BASE_URL` | Good models | Free tier |
|----------|-------------------|-------------|-----------|
| **[Groq](https://console.groq.com)** | `https://api.groq.com/openai/v1` | `llama-3.3-70b-versatile` | ✅ Yes |
| **[OpenRouter](https://openrouter.ai)** | `https://openrouter.ai/api/v1` | `meta-llama/llama-3.3-70b-instruct:free` | ✅ Yes |
| **[Google Gemini](https://aistudio.google.com)** | `https://generativelanguage.googleapis.com/v1beta/openai/` | `gemini-2.0-flash` | ✅ Yes |
| **[Mistral AI](https://console.mistral.ai)** | `https://api.mistral.ai/v1` | `mistral-small-latest` | ❌ Paid |
| **[Together AI](https://api.together.ai)** | `https://api.together.xyz/v1` | `meta-llama/Llama-3.3-70B-Instruct-Turbo` | ❌ Paid |
| **[xAI / Grok](https://console.x.ai)** | `https://api.x.ai/v1` | `grok-2-latest` | ❌ Paid |
| **[LM Studio](https://lmstudio.ai)** | `http://host.docker.internal:1234/v1` | *(any tool-calling model)* | ✅ Local |
| **[LocalAI](https://localai.io)** | `http://host.docker.internal:8080/v1` | *(any tool-calling model)* | ✅ Local |
| **[Jan](https://jan.ai)** | `http://host.docker.internal:1337/v1` | *(any tool-calling model)* | ✅ Local |

You can also configure all of this through the **Settings → AI / LLM tab** in the web UI — it has a provider preset picker that auto-fills the base URL and suggests a good model for each service.

> **Important:** The model must support **tool/function calling**. Not all models do. If commands aren't working, this is usually why — switch to one of the recommended models above.

---

## What's New

### v0.9.2
- **Discover tab — "In Library" badge for TV shows**: Shows already in Sonarr now correctly display the green ✓ In Library badge and hide the add button, matching the existing movie behaviour.
- **Discover tab — fixed HTTP 400 on add**: Adding TV shows from Discover now uses the full Sonarr lookup result as the POST body, so all required fields (`titleSlug`, `seriesType`, `languageProfileId`, seasons, etc.) are always present.
- **Better error messages on add**: If a show or movie is already in your library and the add is rejected, the UI now correctly reads the response body and shows "already in your library" instead of a raw HTTP error.

### v0.9.1
- **EST air times on Upcoming calendar**: Each scheduled episode now shows its air time in Eastern time, with a note that new episodes usually take 10–60 minutes to appear after airing.
- **Improved error handling on commands**: Errors are now categorised (not found, already exists, connection issue, etc.) with friendly messages, a pre-filled retry input, and contextual quick-action buttons.

### v0.9.0
- **OpenAI-compatible provider preset picker**: The Settings → AI/LLM tab now has a dropdown to auto-fill the base URL and model for Groq, OpenRouter, LM Studio, Google Gemini, and more.
- Expanded LLM provider support — any OpenAI-compatible API works.

---

## Features

### Natural Language Commands

Arrmate understands plain English — including the way real people talk:

- **Add content:** "put Yellowstone on my list", "can you get me Dune?", "add the Breaking Bad audiobook"
- **Fix problems:** "the sound is off on Interstellar", "Succession keeps freezing", "the picture on The Bear is all green"
- **Browse:** "what shows do I have?", "what can I watch tonight?", "what movies are downloading?"
- **Subtitles:** "get English subtitles for Parasite", "the subtitles are out of sync on The Wire"
- **Quality:** "get a better copy of Inception", "upgrade The Matrix to 4K"
- **Maintenance:** "clean up Plex", "backup the Plex database", "rescan Breaking Bad"

### Multi-User System

Three roles keep everything safe:

- **admin** — full access to everything including settings and user management
- **power_user** — can execute commands and approve media requests; no settings access
- **user** — browse library and submit requests; nothing gets deleted without admin approval

Family members get `user` role by default. They can request content, and you'll get notified. No one can accidentally wipe your library.

### Media Request Workflow

1. Family member submits a request: "can you add Outlander?"
2. Admin/power_user gets notified (Slack/Discord/in-app)
3. They approve it — Arrmate adds it automatically
4. The family member sees it appear in their library

### Download Queue & History

```
"what's downloading right now?"       → shows active downloads with progress
"what was downloaded recently?"       → shows recent import history
"what episodes am I missing?"         → shows monitored but undownloaded content
```

### Plex Integration

```
"what's playing on Plex?"             → active streams
"rate The Matrix 5 stars"             → rate items
"mark Succession as watched"          → update watch status
"refresh Plex metadata for The Wire"  → refresh artwork/info
"clean up Plex"                       → run Butler maintenance
"empty Plex trash"                    → clear deleted items
```

### H.265 Transcoding

Arrmate can scan your library for files not already in H.265 and convert them in the background to save disk space:

```
"convert all my movies to H265"
"transcode Breaking Bad to save space"
"convert all TV shows to HEVC"
```

Track progress at `/web/transcode`. Requires media files to be accessible inside the container — see volume mount comments in the compose file.

### Subtitle Management (Bazarr)

```
"download English subtitles for Parasite"
"sync subtitles for Breaking Bad season 3"
"what shows are missing subtitles?"
```

### Monitor / Unmonitor

```
"stop monitoring The Office"          → won't download new episodes
"monitor Breaking Bad season 3"       → re-enable a specific season
"unmonitor Inception"                 → pause movie monitoring
```

### Tags, Rename & Rescan

```
"rename Breaking Bad files"           → rename to match your naming convention
"rescan disk for The Sopranos"        → pick up manually added files
```

---

## Multi-User Authentication

Fresh installs create a default admin account:

```
Username: admin
Password: changeme123
```

You'll be prompted to change this on first login.

Invite additional users from the **Admin Panel** (`/web/admin`) → Invite Links. Send them the link — they register themselves with the role you chose.

Sessions persist across restarts when `SECRET_KEY` is set in `.env`. To generate one:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Locked out? Delete `/data/users.db` and restart — the default admin account will be recreated.

---

## Notifications

Set up Slack or Discord webhooks to get notified when family members submit media requests:

```bash
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/T.../B.../...
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/.../...
```

Or configure them in **Settings → Notifications** in the web UI.

---

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

---

## Documentation

- [Quick Start](docs/quickstart.md)
- [Docker Deployment](docs/docker.md)
- [Service Reference](docs/services.md)
- [Web UI](docs/web-ui.md)
- [Authentication](docs/authentication.md)
- [SimpleHomelab / Traefik](docs/simplehomelab-traefik.md)

---

## Development

```bash
git clone https://github.com/TechButton/Arrmate.git
cd Arrmate
pip install -e ".[dev]"
cp .env.example .env
# edit .env
python -m arrmate.interfaces.api.app
```

Full local stack with Sonarr + Radarr + Ollama:

```bash
docker compose -f docker-compose.full.yml up -d
```

---

## Links

- [Docker Hub](https://hub.docker.com/r/techbutton/arrmate)
- [GitHub](https://github.com/TechButton/Arrmate)
- [Issues](https://github.com/TechButton/Arrmate/issues)
- [Buy Me a Coffee](https://buymeacoffee.com/techbutton) — if Arrmate saves you time, consider supporting development

---

## License

MIT
