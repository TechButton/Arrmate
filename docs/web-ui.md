# Web UI

Open `http://localhost:8000` — it redirects to `/web/`.

## Pages

### Dashboard (`/web/`)
Overview of configured services with connection status. Each service shows its version and whether it's reachable.

### Command (`/web/command`)
The main interface. Type a natural language command, click **Parse** to preview how it's interpreted, then **Execute** to run it. Results and any errors appear below.

Voice input is supported in Chrome and Edge — click the microphone icon to dictate. The example commands at the bottom are clickable.

### Library (`/web/library`)
Browse your Sonarr and Radarr libraries as a poster grid. Switch between TV and Movies with the tabs at the top.

Each card shows the poster, monitoring status, and file size. Hover to reveal action buttons: upgrade quality, toggle monitoring, grab more seasons, or remove the item and its files. Posters load from TVDB/TMDB where available, with a server-side proxy fallback.

### Search (`/web/search`)
Find and add content. Results come from Sonarr or Radarr's indexer search — the same thing as searching inside those apps. Select a result and click Add.

### Services (`/web/services`)
Live status of all configured services — version, URL, API health. Auto-refreshes every 30 seconds.

### Plex (`/web/plex`)
Five tabs covering your Plex server activity. See [Service Reference → Plex](services.md#plex) for details.

### Downloads (`/web/downloads`)
Queue overview for all configured download managers (SABnzbd, NZBget, qBittorrent, Transmission). The speed control panel at the top lets you set a download limit on any client.

### Transcode (`/web/transcode`)
Status of active H.265 transcoding jobs. Jobs are started via natural language command or the Command page. Each job shows progress per file, estimated size savings, and a cancel button.

### Settings (`/web/settings`)
Configure authentication (username/password). Authentication is disabled by default — once credentials are created, all pages and API routes require login.

---

## API

FastAPI routes are at `/api/v1/`. Interactive docs: `/docs`.

### Full pages
- `GET /web/` — Dashboard
- `GET /web/command` — Command interface
- `GET /web/library` — Library browser
- `GET /web/search` — Search and add
- `GET /web/services` — Service status
- `GET /web/plex` — Plex hub
- `GET /web/downloads` — Download manager overview
- `GET /web/transcode` — Transcode job status
- `GET /web/settings` — Settings

### Key partials (HTMX)
- `POST /web/command/parse` — Parse preview
- `POST /web/command/execute` — Execute command
- `GET /web/library/items` — Library grid (paginated)
- `GET /web/plex/history` — Watch history (supports `?account_id=`)
- `GET /web/plex/continue` — Continue watching
- `GET /web/plex/ondeck` — On deck
- `GET /web/plex/recent` — Recently added
- `GET /web/plex/butler` — Butler task list
- `GET /web/downloads/status` — Live download queue
- `DELETE /web/plex/session/{key}` — Terminate Plex session

### REST API
- `POST /api/v1/execute` — Execute a natural language command
- `GET /api/v1/services` — Service status JSON
- `GET /api/v1/config` — Current configuration (sanitized)
- `GET /health` — Health check

---

## Technology

The UI is server-rendered Jinja2 with HTMX for partial updates and Alpine.js for client-side state (modals, tabs, the voice input component). Tailwind CSS via CDN. No build step.

Templates live in `src/arrmate/interfaces/web/templates/`. Extend `base.html` for new pages; add partials under `partials/` for HTMX endpoints.
