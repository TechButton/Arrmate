# Publishing Arrmate to GitHub - Complete Guide

This guide walks you through publishing Arrmate to GitHub, setting up GitHub Pages, adding your Buy Me a Coffee link, and getting testers.

## Part 1: Prepare the Repository

### Step 1: Rename the Directory

Since you're on WSL and the automatic rename failed, do this manually:

```bash
# Navigate to parent directory
cd /mnt/c/tools

# Rename the directory
mv mediatools arrmate

# Navigate into the new directory
cd arrmate
```

### Step 2: Verify All Files Are Updated

```bash
# Check that all references are updated
grep -r "mediatools" . --exclude-dir=.git --exclude-dir=venv --exclude-dir=__pycache__ || echo "✓ All updated!"
```

If you see any remaining "mediatools" references, they need to be updated.

### Step 3: Update Your Information

Edit these files with your actual information:

**`.github/FUNDING.yml`:**
```yaml
custom: ['https://buymeacoffee.com/YOURUSERNAME']
```

**`pyproject.toml`:**
```toml
[project.urls]
Homepage = "https://github.com/YOURUSERNAME/arrmate"
Repository = "https://github.com/YOURUSERNAME/arrmate"
Issues = "https://github.com/YOURUSERNAME/arrmate/issues"
```

## Part 2: Initialize Git Repository

```bash
# Navigate to your project
cd /mnt/c/tools/arrmate

# Initialize git
git init

# Add all files
git add .

# Create initial commit
git commit -m "Initial commit: Arrmate v0.1.0

🤝 Your AI companion for Sonarr, Radarr, and Lidarr

Features:
- Natural language command interface
- Multi-provider LLM support (Ollama, OpenAI, Anthropic)
- CLI and REST API interfaces
- Docker deployment ready
- Sonarr and Radarr integration
"
```

## Part 3: Create GitHub Repository

### Option A: Via GitHub Web Interface

1. Go to https://github.com/new
2. **Repository name**: `arrmate`
3. **Description**: `🤝 Your AI companion for Sonarr, Radarr, and Lidarr - manage your media library with natural language`
4. **Visibility**: Public
5. **DO NOT** initialize with README (we already have one)
6. Click **Create repository**

### Option B: Via GitHub CLI

```bash
# Install GitHub CLI if you haven't
# https://cli.github.com/

# Login
gh auth login

# Create repository
gh repo create arrmate --public --description "🤝 Your AI companion for Sonarr, Radarr, and Lidarr" --source=.
```

## Part 4: Push to GitHub

```bash
# Add remote (replace YOURUSERNAME)
git remote add origin https://github.com/YOURUSERNAME/arrmate.git

# Push to GitHub
git branch -M main
git push -u origin main
```

## Part 5: Configure Repository Settings

### 5.1: Add Topics

On GitHub:
1. Go to your repository page
2. Click the ⚙️ settings icon next to "About"
3. Add topics:
   - `sonarr`
   - `radarr`
   - `lidarr`
   - `media-management`
   - `natural-language`
   - `llm`
   - `ai`
   - `docker`
   - `python`
   - `ollama`

### 5.2: Enable Issues and Discussions

1. Go to Settings → General
2. Check ✓ Issues
3. Check ✓ Discussions (optional, good for Q&A)

### 5.3: Set Up Branch Protection (Optional)

1. Go to Settings → Branches
2. Add rule for `main` branch
3. Require pull request reviews before merging
4. Require status checks to pass

## Part 6: Set Up Buy Me a Coffee

### 6.1: Create Buy Me a Coffee Account

1. Go to https://www.buymeacoffee.com/
2. Sign up / Create account
3. Set up your page with:
   - Profile picture
   - Description: "Supporting Arrmate development"
   - Link to GitHub repo

### 6.2: Update FUNDING.yml

Edit `.github/FUNDING.yml`:

```yaml
custom: ['https://buymeacoffee.com/YOURACTUALUSERNAME']
```

Commit and push:

```bash
git add .github/FUNDING.yml
git commit -m "Add Buy Me a Coffee sponsorship link"
git push
```

GitHub will automatically show the "Sponsor" button on your repo!

## Part 7: Create GitHub Pages (Project Website)

### 7.1: Create docs directory

```bash
mkdir -p docs
```

### 7.2: Create index.html

Create `docs/index.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Arrmate - Your AI Companion for Media Management</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            line-height: 1.6;
            color: #333;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }
        header {
            text-align: center;
            padding: 60px 20px;
            color: white;
        }
        header h1 {
            font-size: 3em;
            margin-bottom: 20px;
        }
        .emoji { font-size: 1.2em; }
        .tagline {
            font-size: 1.5em;
            margin-bottom: 30px;
            opacity: 0.9;
        }
        .buttons {
            display: flex;
            gap: 20px;
            justify-content: center;
            flex-wrap: wrap;
            margin-top: 30px;
        }
        .btn {
            padding: 15px 30px;
            border-radius: 8px;
            text-decoration: none;
            font-weight: bold;
            transition: transform 0.2s;
            display: inline-block;
        }
        .btn:hover { transform: translateY(-2px); }
        .btn-primary {
            background: white;
            color: #667eea;
        }
        .btn-secondary {
            background: rgba(255,255,255,0.2);
            color: white;
            border: 2px solid white;
        }
        .features {
            background: white;
            border-radius: 12px;
            padding: 60px 40px;
            margin-top: -30px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
        }
        .features h2 {
            text-align: center;
            font-size: 2em;
            margin-bottom: 40px;
            color: #667eea;
        }
        .feature-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 30px;
            margin-top: 40px;
        }
        .feature {
            text-align: center;
            padding: 20px;
        }
        .feature h3 {
            margin: 15px 0;
            color: #764ba2;
        }
        .example {
            background: #f7f7f7;
            padding: 40px;
            border-radius: 12px;
            margin: 40px 0;
        }
        .example h3 {
            margin-bottom: 20px;
            color: #667eea;
        }
        .code {
            background: #2d2d2d;
            color: #f8f8f2;
            padding: 20px;
            border-radius: 8px;
            overflow-x: auto;
            font-family: 'Courier New', monospace;
        }
        footer {
            text-align: center;
            padding: 40px 20px;
            color: white;
        }
        .sponsor-btn {
            background: #FFDD00;
            color: #000;
            padding: 12px 24px;
            border-radius: 8px;
            text-decoration: none;
            font-weight: bold;
            display: inline-block;
            margin: 20px;
        }
    </style>
</head>
<body>
    <header>
        <div class="container">
            <h1><span class="emoji">🤝</span> Arrmate</h1>
            <p class="tagline">Your AI companion for Sonarr, Radarr, and Lidarr</p>
            <p>Manage your media library with natural language - no more clicking through UIs!</p>

            <div class="buttons">
                <a href="https://github.com/YOURUSERNAME/arrmate" class="btn btn-primary">
                    View on GitHub
                </a>
                <a href="https://github.com/YOURUSERNAME/arrmate#quick-start" class="btn btn-secondary">
                    Get Started
                </a>
            </div>
        </div>
    </header>

    <div class="container">
        <div class="features">
            <h2>✨ Features</h2>

            <div class="feature-grid">
                <div class="feature">
                    <div style="font-size: 3em;">💬</div>
                    <h3>Natural Language</h3>
                    <p>Just say what you want - no complex commands to remember</p>
                </div>

                <div class="feature">
                    <div style="font-size: 3em;">🤖</div>
                    <h3>Multiple LLMs</h3>
                    <p>Ollama (free), OpenAI, or Anthropic - your choice</p>
                </div>

                <div class="feature">
                    <div style="font-size: 3em;">🎬</div>
                    <h3>Multi-Service</h3>
                    <p>Works with Sonarr, Radarr, and Lidarr</p>
                </div>

                <div class="feature">
                    <div style="font-size: 3em;">🐳</div>
                    <h3>Docker Ready</h3>
                    <p>One command to deploy everything</p>
                </div>

                <div class="feature">
                    <div style="font-size: 3em;">⌨️</div>
                    <h3>CLI & API</h3>
                    <p>Command line interface and REST API</p>
                </div>

                <div class="feature">
                    <div style="font-size: 3em;">🔓</div>
                    <h3>Open Source</h3>
                    <p>MIT licensed, contributions welcome</p>
                </div>
            </div>

            <div class="example">
                <h3>Example Commands</h3>
                <div class="code">
# List your library<br>
arrmate execute "show me all my TV shows"<br>
<br>
# Add new content<br>
arrmate execute "add Breaking Bad to my library"<br>
<br>
# Remove episodes<br>
arrmate execute "remove episode 1 and 2 of Angel season 1"<br>
<br>
# Search for upgrades<br>
arrmate execute "search for 4K version of Blade Runner"
                </div>
            </div>

            <div style="text-align: center; margin-top: 40px;">
                <h3>Support Development</h3>
                <p>If Arrmate makes your life easier, consider buying me a coffee!</p>
                <a href="https://buymeacoffee.com/YOURUSERNAME" class="sponsor-btn">
                    ☕ Buy Me a Coffee
                </a>
            </div>
        </div>
    </div>

    <footer>
        <div class="container">
            <p>Made with ❤️ by the Arrmate community</p>
            <p style="margin-top: 10px;">
                <a href="https://github.com/YOURUSERNAME/arrmate" style="color: white;">GitHub</a> •
                <a href="https://github.com/YOURUSERNAME/arrmate/issues" style="color: white;">Issues</a> •
                <a href="https://github.com/YOURUSERNAME/arrmate/blob/main/CONTRIBUTING.md" style="color: white;">Contributing</a>
            </p>
        </div>
    </footer>
</body>
</html>
```

**Remember to replace `YOURUSERNAME` with your GitHub username!**

### 7.3: Enable GitHub Pages

1. Go to Settings → Pages
2. Source: Deploy from a branch
3. Branch: `main` / `docs`
4. Click Save

Your site will be live at: `https://yourusername.github.io/arrmate/`

### 7.4: Commit and Push

```bash
git add docs/
git commit -m "Add GitHub Pages website"
git push
```

## Part 8: Getting Testers

### 8.1: Create a Beta Testing Discussion

1. Go to your repo → Discussions
2. Create new discussion in "General" category
3. Title: "🧪 Beta Testers Wanted!"

**Template:**

```markdown
# 🧪 Beta Testers Wanted!

Arrmate is ready for testing! I'm looking for people to help test the natural language interface for Sonarr/Radarr.

## What Arrmate Does

Manage your media library with natural language:
- "add Breaking Bad to my library"
- "remove episode 1 of Angel season 1"
- "search for 4K version of Blade Runner"

## What I Need From Testers

- [ ] Test with your existing Sonarr/Radarr setup
- [ ] Try different command formats
- [ ] Report bugs and unexpected behavior
- [ ] Suggest improvements

## Requirements

- Sonarr and/or Radarr already set up
- Docker OR Python 3.11+
- Willingness to report issues

## How to Get Started

See [QUICKSTART.md](QUICKSTART.md) for setup instructions.

## Feedback

Please create issues for bugs or join the discussion here with your experience!

Thanks for helping make Arrmate better! 🚀
```

### 8.2: Share on Social Media / Forums

**Reddit:**
- r/selfhosted
- r/sonarr
- r/radarr
- r/homelab

**Example Post:**
```
[Project] Arrmate - Natural language interface for Sonarr/Radarr

I built a tool that lets you manage your Sonarr/Radarr library
with natural language instead of clicking through UIs.

Examples:
- "add Breaking Bad to my library"
- "remove episode 1 of Angel season 1"
- "search for 4K version of Blade Runner"

Uses LLMs (Ollama/OpenAI/Claude) to parse commands and execute
via Sonarr/Radarr APIs. Docker deployment included.

GitHub: https://github.com/yourusername/arrmate

Looking for beta testers! Feedback welcome.
```

**Discord:**
- TRaSH Guides Discord
- Servarr Discord
- r/Selfhosted Discord

### 8.3: Create a v0.1.0 Release

1. Go to Releases → Create a new release
2. Tag: `v0.1.0`
3. Title: `Arrmate v0.1.0 - Initial Release`
4. Description:

```markdown
# 🎉 Arrmate v0.1.0 - Initial Release

First public release of Arrmate!

## Features

- 🗣️ Natural language command interface
- 🤖 Multi-provider LLM support (Ollama, OpenAI, Anthropic)
- 📺 Sonarr integration (TV shows)
- 🎬 Radarr integration (Movies)
- ⌨️ CLI interface with rich formatting
- 🔌 REST API with OpenAPI docs
- 🐳 Docker deployment ready

## Quick Start

See [QUICKSTART.md](QUICKSTART.md) for setup instructions.

## Known Limitations

- Lidarr not yet implemented
- No web UI (CLI and API only)
- Single-turn commands only (no conversation memory)

## What's Next

- Web UI
- Lidarr support
- Better fuzzy matching
- Conversation memory

## Feedback

Please report bugs via [Issues](https://github.com/yourusername/arrmate/issues)!

---

If you find Arrmate useful, consider [buying me a coffee](https://buymeacoffee.com/yourusername)! ☕
```

4. Attach any assets (optional)
5. Click "Publish release"

## Part 9: Update README with Badges

Add badges to the top of README.md:

```markdown
# Arrmate

[![GitHub release](https://img.shields.io/github/v/release/YOURUSERNAME/arrmate)](https://github.com/YOURUSERNAME/arrmate/releases)
[![License](https://img.shields.io/github/license/YOURUSERNAME/arrmate)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://hub.docker.com/r/YOURUSERNAME/arrmate)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-support-yellow.svg)](https://buymeacoffee.com/YOURUSERNAME)

🤝 Your AI companion for Sonarr, Radarr, and Lidarr
```

## Checklist

Before announcing publicly:

- [ ] Directory renamed to `arrmate`
- [ ] Git repository initialized
- [ ] GitHub repository created
- [ ] All files pushed to GitHub
- [ ] Topics added to repository
- [ ] Buy Me a Coffee account created
- [ ] FUNDING.yml updated with your username
- [ ] GitHub Pages enabled and working
- [ ] GitHub Pages HTML updated with your info
- [ ] Beta testing discussion created
- [ ] v0.1.0 release published
- [ ] README badges added
- [ ] Tested locally (Docker and/or Python)
- [ ] All documentation reviewed

## Next: Docker Hub (Optional)

See next section for Docker Hub publishing.
