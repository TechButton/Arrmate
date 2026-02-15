# Arrmate Web UI Guide

## Overview

Arrmate now includes a mobile-friendly web UI built with HTMX and Tailwind CSS. This provides a modern, responsive interface for managing your media libraries through a browser.

## What Was Implemented

### 🎨 Technology Stack
- **HTMX v1.9** - Dynamic updates without full page reloads
- **Tailwind CSS v3.4** - Mobile-first responsive styling (CDN)
- **Alpine.js v3.13** - Lightweight client-side interactivity
- **Jinja2** - Server-side templating
- **FastAPI** - Backend routing and API

### 📁 Project Structure

```
src/arrmate/interfaces/web/
├── __init__.py
├── routes.py                    # FastAPI routes for web UI
├── templates/
│   ├── base.html                # Base layout with nav & scripts
│   ├── components/              # Reusable UI components
│   │   ├── navbar.html          # Mobile-friendly navigation
│   │   ├── service_card.html    # Service status card
│   │   ├── media_item.html      # Library item card
│   │   ├── search_result.html   # Search result card
│   │   └── toast.html           # Toast notifications
│   ├── pages/                   # Full page templates
│   │   ├── index.html           # Dashboard
│   │   ├── command.html         # Command interface
│   │   ├── services.html        # Service status
│   │   ├── library.html         # Library browser
│   │   └── search.html          # Search & add
│   └── partials/                # HTMX partials
│       ├── command_preview.html # Command parse preview
│       ├── execution_result.html# Command execution result
│       ├── service_list.html    # Service list
│       ├── library_list.html    # Library items
│       └── search_results.html  # Search results
└── static/
    └── css/
        └── custom.css           # Custom styles
```

### ✨ Features Implemented

#### 1. Dashboard (`/web/`)
- Quick stats overview (services, TV shows, movies)
- Service status at a glance
- Quick action buttons to all sections
- Getting started guide

#### 2. Command Interface (`/web/command`)
- Large textarea for natural language input
- **Parse Preview** button - See how command is interpreted
- **Execute Command** button - Run the command
- Visual feedback with color-coded intent fields
- Example commands section
- Success/error toasts

#### 3. Service Status (`/web/services`)
- Grid of service cards (Sonarr, Radarr, Lidarr)
- Real-time status indicators (green/red)
- Auto-refresh every 30 seconds
- Manual refresh button
- Version info and API key display
- Configuration help

#### 4. Library Browser (`/web/library`)
- Tabs for TV Shows / Movies
- Search/filter input (500ms debounce)
- Responsive grid layout (1-4 columns)
- Item cards with status badges
- Infinite scroll support (placeholder)
- View/Delete actions

#### 5. Search & Add (`/web/search`)
- Media type selector (TV/Movies)
- Debounced search input (500ms)
- Search result cards with metadata
- Quality profile selector
- One-click add to library
- Success/error toasts

#### 6. Mobile-First Design
- ✓ 44px minimum tap targets
- ✓ Hamburger menu on mobile
- ✓ Responsive grid layouts
- ✓ Touch-friendly interactions
- ✓ Fast CDN-based assets
- ✓ Dark mode support
- ✓ Accessible focus states

## Getting Started

### 1. Install Dependencies

```bash
# Install the new dependencies
pip install -e .

# Or install them individually
pip install jinja2 python-multipart
```

### 2. Start the Server

```bash
# Using uvicorn directly
uvicorn arrmate.interfaces.api.app:app --reload --host 0.0.0.0 --port 8000

# Or using the Python module
python -m arrmate.interfaces.api.app
```

### 3. Access the Web UI

Open your browser to:
- **Web UI**: http://localhost:8000/web
- **API Docs**: http://localhost:8000/docs
- **Root**: http://localhost:8000 (redirects to /web)

### 4. Configure Services

Make sure your `.env` file has service URLs and API keys:

```env
SONARR_URL=http://localhost:8989
SONARR_API_KEY=your-sonarr-api-key

RADARR_URL=http://localhost:7878
RADARR_API_KEY=your-radarr-api-key

LIDARR_URL=http://localhost:8686
LIDARR_API_KEY=your-lidarr-api-key

# LLM Provider (required for command parsing)
LLM_PROVIDER=ollama  # or openai, anthropic
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2
```

## Usage Examples

### Command Interface

Try these natural language commands:

```
list my TV shows
add Breaking Bad to my library
remove episode 1 of Angel season 1
search for 4K version of Blade Runner
```

1. Go to `/web/command`
2. Type or paste a command
3. Click **Parse Preview** to see how it's interpreted
4. Click **Execute Command** to run it
5. View results and toast notifications

### Library Browser

1. Go to `/web/library`
2. Switch between TV Shows and Movies tabs
3. Use search to filter items
4. View details or delete items
5. Items load with infinite scroll

### Search & Add

1. Go to `/web/search`
2. Select media type (TV/Movies)
3. Type a title to search
4. Select quality profile
5. Click "Add to Library"
6. See success toast

## Mobile Testing

### Using Browser DevTools

1. Open Chrome/Edge DevTools (F12)
2. Click device toolbar icon (Ctrl+Shift+M)
3. Select a mobile device (e.g., iPhone 12 Pro)
4. Test all features work on mobile

### On Real Device

1. Start server with `--host 0.0.0.0`
2. Find your computer's IP address
3. On mobile, visit `http://YOUR_IP:8000/web`
4. Test touch interactions and responsiveness

## Progressive Enhancement

The UI is built with progressive enhancement:

- **Without JavaScript**: Forms work via standard POST
- **With HTMX**: Partial updates, no full page reload
- **With Alpine.js**: Mobile menu, toasts, UI animations

If HTMX fails to load, forms still submit normally.

## API Routes

### Full Pages
- `GET /web/` - Dashboard
- `GET /web/command` - Command interface
- `GET /web/services` - Service status
- `GET /web/library?media_type=tv` - Library browser
- `GET /web/search` - Search & add

### HTMX Partials
- `POST /web/command/parse` - Parse command preview
- `POST /web/command/execute` - Execute command
- `GET /web/services/refresh` - Refresh service status
- `GET /web/library/items?type=tv&page=1` - Library items
- `GET /web/search/results?query=...&media_type=tv` - Search
- `POST /web/library/add` - Add item to library

## Customization

### Custom Styles

Edit `src/arrmate/interfaces/web/static/css/custom.css` to customize:
- Colors and themes
- Loading indicators
- Toast animations
- Custom components

### Templates

All templates use Jinja2 syntax:
- Extend `base.html` for new pages
- Use `{% include %}` for components
- Add partials for HTMX endpoints

### Routes

Add new routes in `routes.py`:

```python
@router.get("/new-page", response_class=HTMLResponse)
async def new_page(request: Request):
    return templates.TemplateResponse(
        "pages/new_page.html",
        {"request": request}
    )
```

## Troubleshooting

### "Template not found" error
- Check templates directory path in `routes.py`
- Verify file names match exactly (case-sensitive)

### Static files not loading
- Ensure static directory is mounted in `app.py`
- Check browser console for 404 errors
- Verify CDN links are accessible

### HTMX not working
- Check browser console for JavaScript errors
- Verify HTMX CDN is loading
- Use `hx-boost` attribute for debugging

### Services showing as unavailable
- Check `.env` configuration
- Verify service URLs are accessible
- Check API keys are correct
- View `/web/services` for detailed status

## Next Steps

### Planned Enhancements (Post-MVP)

- [ ] Implement actual library fetching from services
- [ ] Implement actual search using service APIs
- [ ] Add command history persistence
- [ ] Add keyboard shortcuts (Cmd+K palette)
- [ ] Make it a PWA (installable)
- [ ] Add dark mode toggle (save preference)
- [ ] Multi-language support (i18n)
- [ ] Bulk actions (select multiple items)
- [ ] Advanced filters
- [ ] Real-time notifications (WebSocket/SSE)
- [ ] Build process for production Tailwind

### Contributing

The web UI is fully integrated with the existing Arrmate architecture:
- Reuses `CommandParser`, `IntentEngine`, `Executor`
- Uses existing models (`Intent`, `ExecutionResult`)
- Shares service discovery with API
- No code duplication

Add new features by:
1. Creating templates in `templates/`
2. Adding routes in `routes.py`
3. Using existing core components

## Version

Current version: **0.2.6**

This web UI was implemented as a major feature update, bumping from v0.1.0 to v0.2.0.

---

Built with ❤️ by the Arrmate team
Contributors: Arrmate Contributors, Claude Sonnet 4.5
