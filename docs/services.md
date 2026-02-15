# Arrmate Service Support

This document provides detailed information about all media services supported by Arrmate, including implementation status, features, and configuration requirements.

## Table of Contents

- [Fully Supported Services](#fully-supported-services)
- [Planned Services](#planned-services)
- [Deprecated Services](#deprecated-services)
- [Book & Audiobook Services](#book--audiobook-services)
- [Companion Services](#companion-services)
- [Media Servers](#media-servers)
- [External Services](#external-services)
- [Configuration Guide](#configuration-guide)
- [Feature Matrix](#feature-matrix)
- [Adding New Services](#adding-new-services)

---

## Fully Supported Services

### Sonarr v3 (TV Shows) ✅

**Status:** Complete
**API Version:** v3
**Media Type:** TV Shows
**Default Port:** 8989

**Features:**
- ✅ Search external sources for TV shows
- ✅ Add shows to library
- ✅ Remove shows or specific episodes
- ✅ Trigger manual searches for missing episodes
- ✅ List all shows in library
- ✅ Get detailed show information
- ✅ Episode file management
- ✅ Quality profile support
- ✅ Season and episode-level control

**Configuration:**
```bash
SONARR_URL=http://sonarr:8989
SONARR_API_KEY=your_api_key_here
```

**API Endpoints Used:**
- `/api/v3/series` - Series management
- `/api/v3/episode` - Episode information
- `/api/v3/episodefile` - File management
- `/api/v3/command` - Trigger searches

---

### Radarr v3 (Movies) ✅

**Status:** Complete
**API Version:** v3
**Media Type:** Movies
**Default Port:** 7878

**Features:**
- ✅ Search external sources for movies
- ✅ Add movies to library
- ✅ Remove movies and files
- ✅ Trigger manual searches
- ✅ List all movies in library
- ✅ Get detailed movie information
- ✅ Movie file management
- ✅ Quality profile support

**Configuration:**
```bash
RADARR_URL=http://radarr:7878
RADARR_API_KEY=your_api_key_here
```

**API Endpoints Used:**
- `/api/v3/movie` - Movie management
- `/api/v3/moviefile` - File management
- `/api/v3/command` - Trigger searches

---

## Planned Services

### Lidarr v3 (Music) 🔜

**Status:** Implemented (Testing Required)
**API Version:** v3
**Media Type:** Music (Artists/Albums/Tracks)
**Default Port:** 8686

**Planned Features:**
- 🔜 Search for artists via MusicBrainz
- 🔜 Add artists and albums to library
- 🔜 Remove artists and files
- 🔜 Trigger album searches
- 🔜 List all artists in library
- 🔜 Track file management
- 🔜 Quality and metadata profile support

**Configuration:**
```bash
LIDARR_URL=http://lidarr:8686
LIDARR_API_KEY=your_api_key_here
```

**Implementation Notes:**
- Uses MusicBrainz for metadata
- Supports both quality profiles and metadata profiles
- Album and track-level management

---

### Whisparr v3 (Adult Content) 🔜

**Status:** Implemented (Testing Required)
**API Version:** v3
**Media Type:** Adult Videos
**Default Port:** 6969

**Planned Features:**
- 🔜 Search for adult content via TMDb
- 🔜 Add content to library
- 🔜 Remove content and files
- 🔜 Trigger manual searches
- 🔜 Quality profile support
- 🔞 Content filtering options (hide/show in UI)

**Configuration:**
```bash
WHISPARR_URL=http://whisparr:6969
WHISPARR_API_KEY=your_api_key_here
```

**UI Considerations:**
- Content can be hidden via settings for family-friendly deployments
- Uses 🔞 emoji for service identification
- Same API structure as Radarr (v3 movie endpoints)

---

## Deprecated Services

### Readarr (Books/Audiobooks) ⚠️

**Status:** Deprecated (Project Retired)
**API Version:** v1
**Media Type:** Books, eBooks, Audiobooks
**Default Port:** 8787

**⚠️ WARNING:** The Readarr project was officially retired in 2026. Support is provided for existing instances only. **Consider migrating to alternatives:**
- **Calibre-Web** - eBook management and OPDS server
- **LazyLibrarian** - Books and audiobook management
- **AudioBookshelf** - Audiobook-focused server

**Limited Features:**
- ⚠️ Search for books via GoodReads
- ⚠️ Add authors to library
- ⚠️ Remove authors and files
- ⚠️ Book file management
- ⚠️ Quality and metadata profiles

**Configuration:**
```bash
READARR_URL=http://readarr:8787
READARR_API_KEY=your_api_key_here
```

**Deprecation Details:**
- Last active development: 2024
- Uses older v1 API (different from Sonarr/Radarr v3)
- No future updates or bug fixes expected
- Logging warnings will appear when using this client

---

## Companion Services

Companion services supplement primary media managers rather than managing media directly.

### Bazarr (Subtitle Management) 🔜

**Status:** Implemented (Testing Required)
**API Version:** Custom
**Supplements:** Sonarr, Radarr
**Default Port:** 6767

**Planned Features:**
- 🔜 Detect missing subtitles for TV shows (Sonarr)
- 🔜 Detect missing subtitles for movies (Radarr)
- 🔜 Search for subtitles in multiple languages
- 🔜 Download and sync subtitles automatically
- 🔜 Subtitle history tracking
- 🔜 Integration with Sonarr/Radarr libraries

**Configuration:**
```bash
BAZARR_URL=http://bazarr:6767
BAZARR_API_KEY=your_api_key_here
```

**Integration Notes:**
- Requires Sonarr and/or Radarr to be configured
- Works with existing media in Sonarr/Radarr libraries
- Does not manage media files directly
- Monitors and downloads subtitles only

**Architecture Differences:**
- Extends `BaseCompanionClient` instead of `BaseMediaClient`
- Uses custom API endpoints (not v3 pattern)
- Depends on primary services for media information

---

## Book & Audiobook Services

### AudioBookshelf (Audiobooks/Podcasts) 🔜

**Status:** Implemented (Testing Required)
**API Version:** REST
**Media Type:** Audiobooks, Podcasts
**Default Port:** 13378

**Features:**
- 🔜 Browse audiobook libraries
- 🔜 Search across audiobooks
- 🔜 Track listening progress
- 🔜 Playback position sync
- 🔜 Multi-user support
- 🔜 Series and collection management
- 🔜 Personalized recommendations
- 🔜 Remove audiobooks from library

**Configuration:**
```bash
AUDIOBOOKSHELF_URL=http://audiobookshelf:13378
AUDIOBOOKSHELF_API_KEY=your_api_token_here
```

**Key Features:**
- **Modern UI**: Beautiful web interface with mobile apps (iOS/Android)
- **Progress Tracking**: Individual user progress and listening sessions
- **Podcast Support**: Manage both audiobooks and podcasts
- **Chapter Navigation**: Skip chapters, bookmarks, sleep timer
- **Metadata**: Automatic fetching from Audible, iTunes, etc.

**API Endpoints Used:**
- `/api/libraries` - Library management
- `/api/libraries/{id}/items` - Browse audiobooks
- `/api/me/progress` - Listening progress
- `/api/items/{id}` - Audiobook details

**Why Use Instead of Readarr:**
- Purpose-built for audiobooks (not adapted from book management)
- Active development with regular updates
- Superior playback experience
- Modern mobile apps

---

### LazyLibrarian (Books/Audiobooks) 🔜

**Status:** Implemented (Testing Required)
**API Version:** Custom
**Media Type:** Books, eBooks, Audiobooks, Magazines
**Default Port:** 5299

**Features:**
- 🔜 Search GoodReads/GoogleBooks for authors and books
- 🔜 Automated downloading via NZB/torrents
- 🔜 Add authors to monitor for new releases
- 🔜 Remove authors and books
- 🔜 Library scanning (books and audiobooks)
- 🔜 Calibre integration
- 🔜 Magazine management
- 🔜 Quality and metadata profiles

**Configuration:**
```bash
LAZYLIBRARIAN_URL=http://lazylibrarian:5299
LAZYLIBRARIAN_API_KEY=your_api_key_here
```

**Key Features:**
- **Automated Downloading**: Like Sonarr/Radarr but for books
- **Multi-Format**: Supports eBooks (EPUB, MOBI, PDF) and audiobooks
- **Metadata Integration**: GoodReads, GoogleBooks, Audible
- **Calibre Support**: Direct integration with Calibre library
- **Magazine Support**: Automatic magazine issue downloads

**API Commands:**
- `findAuthor`, `addAuthor` - Author management
- `findBook`, `searchBook` - Book search and download
- `getAllBooks`, `getIndex` - Library browsing
- `forceLibraryScan`, `forceAudioBookScan` - Library updates

**Use Case:**
Best for users who want *arr-style automation for books and audiobooks with automatic downloading capabilities.

---

## Media Servers

### Plex Media Server 🔜

**Status:** Implemented (Testing Required)
**API Version:** REST
**Media Type:** Media Server
**Default Port:** 32400

**Description:**
Plex is a media server and player that organizes and streams your existing media library. Unlike *arr services, Plex does **not** download or manage content — it serves files already on disk. This integration provides library browsing, search, metadata refresh, and active session monitoring.

**Features:**
- 🔜 List all library sections (movies, shows, music, photos)
- 🔜 Browse and search across libraries
- 🔜 Get active streaming sessions
- 🔜 Refresh metadata for items or libraries
- 🔜 Trigger library scans
- 🔜 Mark items as watched or unwatched
- 🔜 Delete items (sends to trash)
- 🔜 Empty library trash

**Configuration:**
```bash
PLEX_URL=http://plex:32400
PLEX_TOKEN=your-plex-token-here
```

**Finding Your Plex Token:**
1. Sign in at [app.plex.tv](https://app.plex.tv)
2. Open any media item and click the `...` menu → Get Info → View XML
3. The `X-Plex-Token` value appears in the URL
4. Alternatively: Settings → Troubleshooting → Download Logs (token appears in log header)

**API Endpoints Used:**
- `/identity` - Server identity and version
- `/library/sections` - Library sections
- `/library/sections/{id}/all` - Items in a section
- `/library/sections/{id}/refresh` - Scan a section
- `/library/sections/{id}/emptyTrash` - Empty trash
- `/hubs/search/` - Cross-library search
- `/library/metadata/{id}` - Item details
- `/library/metadata/{id}/refresh` - Refresh item metadata
- `/status/sessions` - Active streams
- `/:/scrobble` - Mark as watched
- `/:/unscrobble` - Mark as unwatched

**Key Differences from *arr Services:**
- Uses `X-Plex-Token` for auth (not `X-Api-Key`)
- Returns XML by default; Arrmate requests JSON via `Accept: application/json`
- Items identified by `ratingKey` (not a simple integer ID)
- No concept of quality profiles, indexers, or download clients
- Does NOT fit into the executor routing path (not a content manager)

**API Documentation:**
See [Plex Media Server API Reference](https://www.plexopedia.com/plex-media-server/api/) for additional endpoints.

---

## External Services

### huntarr.io (Orchestration) 🔜

**Status:** Implemented (Testing Required)
**API Version:** REST
**Type:** Orchestration Layer
**Default Port:** 3000

**Description:**
huntarr.io is an external automation and orchestration tool that coordinates actions across multiple *arr services, manages backups, and provides centralized monitoring.

**Features:**
- 🔜 Dashboard statistics across all connected services
- 🔜 Manage *arr service instances (Sonarr, Radarr, Lidarr, etc.)
- 🔜 Centralized logging with filtering
- 🔜 Automated backups and restore
- 🔜 Scheduling and notifications
- 🔜 Movie hunt coordination

**Configuration:**
```bash
HUNTARR_URL=http://huntarr:3000
HUNTARR_API_KEY=your_api_key_here
```

**API Endpoints Used:**
- `/api/stats` - Dashboard metrics
- `/api/instances/{app_type}` - Service instance management
- `/api/logs` - Centralized logging
- `/api/backup/*` - Backup operations
- `/api/schedules` - Task scheduling
- `/api/movie-hunt/*` - Movie hunt coordination

**Integration Benefits:**
- **Centralized Control**: Manage multiple *arr instances from one place
- **Backup Management**: Automated configuration backups
- **Monitoring**: Unified logging and statistics
- **Automation**: Cross-service scheduling and coordination

**Use Case:**
Perfect for advanced users managing multiple *arr instances who want centralized orchestration and backup capabilities.

**API Documentation:**
See https://plexguide.github.io/Huntarr.io/system/api.html for full API details.

---

## Configuration Guide

### Environment Variables

All services are configured via environment variables in `.env`:

```bash
# Sonarr (TV Shows)
SONARR_URL=http://sonarr:8989
SONARR_API_KEY=your_sonarr_api_key

# Radarr (Movies)
RADARR_URL=http://radarr:7878
RADARR_API_KEY=your_radarr_api_key

# Lidarr (Music)
LIDARR_URL=http://lidarr:8686
LIDARR_API_KEY=your_lidarr_api_key

# Readarr (Books) - DEPRECATED
READARR_URL=http://readarr:8787
READARR_API_KEY=your_readarr_api_key

# Whisparr (Adult Content)
WHISPARR_URL=http://whisparr:6969
WHISPARR_API_KEY=your_whisparr_api_key

# Bazarr (Subtitles)
BAZARR_URL=http://bazarr:6767
BAZARR_API_KEY=your_bazarr_api_key

# AudioBookshelf (Audiobooks/Podcasts)
AUDIOBOOKSHELF_URL=http://audiobookshelf:13378
AUDIOBOOKSHELF_API_KEY=your_audiobookshelf_api_token

# LazyLibrarian (Books/Audiobooks)
LAZYLIBRARIAN_URL=http://lazylibrarian:5299
LAZYLIBRARIAN_API_KEY=your_lazylibrarian_api_key

# huntarr.io (Orchestration)
HUNTARR_URL=http://huntarr:3000
HUNTARR_API_KEY=your_huntarr_api_key

# Plex Media Server
PLEX_URL=http://plex:32400
PLEX_TOKEN=your_plex_token
```

### Finding API Keys

Each service provides an API key in its settings:

1. **Sonarr/Radarr/Lidarr/Whisparr:**
   Settings → General → Security → API Key

2. **Readarr:**
   Settings → General → Security → API Key

3. **Bazarr:**
   Settings → General → Security → API Key

4. **AudioBookshelf:**
   Settings → Security → API Tokens → Generate

5. **LazyLibrarian:**
   Config → Web Interface → API Key (auto-generated)

6. **huntarr.io:**
   Settings → General → API Key

7. **Plex:**
   app.plex.tv → any item XML view → `X-Plex-Token` in URL

### Docker Service Discovery

When running in Docker Compose, Arrmate can auto-discover services by hostname:

```yaml
services:
  arrmate:
    environment:
      - SONARR_URL=http://sonarr:8989
      - RADARR_URL=http://radarr:7878
```

### Service Status API

Check service status via the API:

```bash
curl http://localhost:8000/api/v1/services
```

Returns implementation status, connection status, API version, and capabilities for each service.

---

## Feature Matrix

### Primary Media Services
| Service | Status | API | Search | Add | Remove | List | Upgrade |
|---------|--------|-----|--------|-----|--------|------|---------|
| Sonarr | ✅ Complete | v3 | ✅ | ✅ | ✅ | ✅ | ✅ |
| Radarr | ✅ Complete | v3 | ✅ | ✅ | ✅ | ✅ | ✅ |
| Lidarr | 🔜 Testing | v3 | 🔜 | 🔜 | 🔜 | 🔜 | ❌ |
| Readarr | ⚠️ Deprecated | v1 | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ❌ |
| Whisparr | 🔜 Testing | v3 | 🔜 | 🔜 | 🔜 | 🔜 | ❌ |

### Book & Audiobook Services
| Service | Status | API | Search | Add | Remove | List | Notes |
|---------|--------|-----|--------|-----|--------|------|-------|
| AudioBookshelf | 🔜 Testing | REST | 🔜 | N/A | 🔜 | 🔜 | Upload-based |
| LazyLibrarian | 🔜 Testing | Custom | 🔜 | 🔜 | 🔜 | 🔜 | Auto-download |

### Companion & Orchestration
| Service | Status | API | Stats | Manage | Logs | Backup | Notify |
|---------|--------|-----|-------|--------|------|--------|--------|
| Bazarr | 🔜 Testing | Custom | N/A | N/A | N/A | N/A | N/A |
| huntarr.io | 🔜 Testing | REST | 🔜 | 🔜 | 🔜 | 🔜 | 🔜 |

### Media Servers
| Service | Status | API | Search | List | Sessions | Refresh | Delete |
|---------|--------|-----|--------|------|----------|---------|--------|
| Plex | 🔜 Testing | REST | 🔜 | 🔜 | 🔜 | 🔜 | 🔜 |

**Legend:**
- ✅ Fully implemented and tested
- 🔜 Implemented, testing required
- ⚠️ Deprecated but functional
- ❌ Not supported
- N/A - Not applicable to this service

---

## Adding New Services

To add support for a new *arr service:

1. **Choose base class:**
   - `BaseMediaClient` - for standard media managers (Sonarr pattern)
   - `BaseCompanionClient` - for companion services (Bazarr pattern)
   - `BaseExternalService` - for orchestration tools (huntarr.io pattern)

2. **Create client class** implementing the abstract methods
3. **Implement required methods:** `test_connection()`, `search()`, `get_item()`, `delete_item()`
4. **Add configuration** to `settings.py`
5. **Update `DEFAULT_PORTS`** in `clients/discovery.py`
6. **Add helper entries** in `_get_implementation_status()`, `_get_api_version()`, `_get_media_type()`, `_get_capabilities()`
7. **Add discovery block** in `discover_services()`
8. **Update executor** to route media types to the new client (if applicable)
9. **Update this documentation** with service details

See existing clients (Sonarr, Radarr, Lidarr) for implementation examples.

---

## Support & Contributing

- **Issues:** Report bugs or request features at [GitHub Issues](https://github.com/your-repo/arrmate/issues)
- **Documentation:** See [README.md](../README.md) for general usage
- **API Docs:** See `/docs` endpoint when running the server

For questions about specific services, consult their official documentation:
- [Sonarr Docs](https://wiki.servarr.com/sonarr)
- [Radarr Docs](https://wiki.servarr.com/radarr)
- [Lidarr Docs](https://wiki.servarr.com/lidarr)
- [Readarr Docs](https://wiki.servarr.com/readarr) (archived)
- [Whisparr Docs](https://wiki.servarr.com/whisparr)
- [Bazarr Docs](https://wiki.bazarr.media/)
- [AudioBookshelf Docs](https://www.audiobookshelf.org/guides/)
- [AudioBookshelf API](https://api.audiobookshelf.org/)
- [LazyLibrarian Docs](https://lazylibrarian.gitlab.io/)
- [LazyLibrarian API](https://lazylibrarian.gitlab.io/api/)
- [huntarr.io API](https://plexguide.github.io/Huntarr.io/system/api.html)
- [Plex Media Server API](https://www.plexopedia.com/plex-media-server/api/)
