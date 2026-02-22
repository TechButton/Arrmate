# Service Reference

## Configuration

Every service is opt-in. Set its URL and API key in your `.env` — if either is missing, the service is silently skipped and won't appear in the UI.

```bash
# Sonarr
SONARR_URL=http://sonarr:8989
SONARR_API_KEY=

# Radarr
RADARR_URL=http://radarr:7878
RADARR_API_KEY=

# Lidarr
LIDARR_URL=http://lidarr:8686
LIDARR_API_KEY=

# Bazarr
BAZARR_URL=http://bazarr:6767
BAZARR_API_KEY=

# Plex
PLEX_URL=http://plex:32400
PLEX_TOKEN=

# AudioBookshelf
AUDIOBOOKSHELF_URL=http://audiobookshelf:13378
AUDIOBOOKSHELF_API_KEY=

# LazyLibrarian
LAZYLIBRARIAN_URL=http://lazylibrarian:5299
LAZYLIBRARIAN_API_KEY=

# huntarr.io
HUNTARR_URL=http://huntarr:3000
HUNTARR_API_KEY=

# Download managers
SABNZBD_URL=http://sabnzbd:8080
SABNZBD_API_KEY=

NZBGET_URL=http://nzbget:6789
NZBGET_USERNAME=
NZBGET_PASSWORD=

QBITTORRENT_URL=http://qbittorrent:8080
QBITTORRENT_USERNAME=
QBITTORRENT_PASSWORD=

TRANSMISSION_URL=http://transmission:9091
TRANSMISSION_USERNAME=
TRANSMISSION_PASSWORD=
```

When services are on the same Docker network, use the container/service name as the hostname.

---

## Sonarr (TV shows)

API v3. Full support: search, add, remove, upgrade, season/episode-level control, monitoring toggle.

Commands like `"remove episodes 1 and 2 of Angel season 1"` or `"add Breaking Bad"` route through Sonarr automatically when `SONARR_URL` is set.

---

## Radarr (Movies)

API v3. Full support: search, add, remove, upgrade, monitoring toggle.

---

## Lidarr (Music)

API v3. Supports search, add, remove, and listing artists and albums.

---

## Bazarr (Subtitles)

Companion to Sonarr/Radarr. Handles subtitle downloading and syncing.

```
"download missing subtitles for The Wire"
"get English subtitles for Inception"
"sync subtitles for Breaking Bad season 3"
```

Bazarr doesn't manage media files — it only handles subtitle files for content already in your Sonarr/Radarr libraries.

---

## Plex

Plex is a media server, not a content manager — it doesn't download anything. Arrmate connects to it for browsing and control.

**Finding your Plex token:** Sign in at [app.plex.tv](https://app.plex.tv), open any item, click `···` → Get Info → View XML. The token appears in the URL as `X-Plex-Token`.

### Web UI (`/web/plex`)

The Plex hub has five tabs:

**Continue Watching** — items you've started but not finished, with progress bars. Hover over a card to rate it or queue intro/credit detection.

**On Deck** — next episodes to watch based on your viewing history.

**Recently Added** — latest additions across all your libraries.

**Watch History** — full playback history. Filter by user to see what a specific household member has watched. Hover a row to trigger intro or credit detection on that item.

**Maintenance** — Butler tasks (database backup, cache cleanup, deep media analysis, subtitle search, etc.) with run-now buttons. You can also trigger these by voice: `"backup Plex database"`, `"clean Plex"`.

### Now-playing strip

When anything is playing, a strip appears across the top of every page showing title, user, player, and progress. Click the × to terminate a session — you'll get an inline confirmation first.

### Natural language commands

```
"what's playing on Plex"
"mark The Sopranos as watched"
"rate The Matrix 5 stars"
"clean Plex"
"backup Plex database"
"run deep media analysis on Plex"
```

Ratings use a 1–5 star scale. Butler task names are inferred from the command — "clean" maps to `CleanOldBundles`, "backup" maps to `BackupDatabase`, and so on.

### Intro and credit detection

Intro and credit skip markers can be queued from any card in the Continue Watching, On Deck, Recently Added, or History views. Calling detection on a series processes all its episodes.

---

## AudioBookshelf

Browse and search audiobook and podcast libraries. AudioBookshelf manages its own downloads — Arrmate provides a read-only view and basic search.

```
"list my audiobooks"
"search for Dune audiobook"
```

---

## LazyLibrarian

Book and audiobook management with automated downloading. Similar to Sonarr/Radarr but for books — monitors authors and downloads new releases.

```
"add Terry Pratchett books"
"search for Dune audiobook"
```

---

## huntarr.io

Dashboard statistics across connected services. Arrmate pulls metrics from huntarr's API to surface them in the services overview.

---

## Download managers

All four managers appear on the `/web/downloads` page when configured. You can monitor queue status, pause/resume downloads, and set speed limits from there.

Speed limits can also be set via the command page (natural language support for this is limited — use the Downloads UI for precise control).

**SABnzbd** — API key-based auth. Speed limit is set in KB/s; 0 removes the limit.

**NZBget** — HTTP Basic auth. JSON-RPC API.

**qBittorrent** — Cookie-based session auth. Speed limits in bytes/s (the UI converts from KB/s automatically).

**Transmission** — Optional HTTP Basic auth. Uses the X-Transmission-Session-Id CSRF token system internally.

---

## Readarr

Readarr shut down in 2024. Basic support remains for existing installs but won't be developed further. If you're setting up a new book management stack, use LazyLibrarian or AudioBookshelf instead.

---

## Feature matrix

| Service | Search | Add | Remove | List | Notes |
|---------|--------|-----|--------|------|-------|
| Sonarr | ✓ | ✓ | ✓ | ✓ | Season/episode level, monitoring |
| Radarr | ✓ | ✓ | ✓ | ✓ | Monitoring toggle |
| Lidarr | ✓ | ✓ | ✓ | ✓ | Artists and albums |
| Bazarr | — | — | — | ✓ | Subtitle download/sync only |
| Plex | ✓ | — | ✓ | ✓ | Rate, history, butler, terminate session |
| AudioBookshelf | ✓ | — | ✓ | ✓ | Library browse |
| LazyLibrarian | ✓ | ✓ | ✓ | ✓ | Author monitoring |
| huntarr.io | — | — | — | ✓ | Stats only |
| SABnzbd | — | — | ✓ | ✓ | Speed control |
| NZBget | — | — | ✓ | ✓ | Speed control |
| qBittorrent | — | — | ✓ | ✓ | Speed control |
| Transmission | — | — | ✓ | ✓ | Speed control |
