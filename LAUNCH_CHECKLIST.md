# 🚀 Arrmate Launch Checklist

Use this checklist to publish Arrmate to GitHub and get testers.

## Pre-Launch Preparation

### 1. Rename Directory
- [ ] Navigate to `/mnt/c/tools/`
- [ ] Manually rename `mediatools` to `arrmate`
- [ ] `cd arrmate`

### 2. Update Personal Information

Edit these files and replace placeholders with YOUR information:

#### `.github/FUNDING.yml`
```yaml
custom: ['https://buymeacoffee.com/YOURUSERNAME']  # ← Your Buy Me a Coffee username
```

#### `pyproject.toml`
```toml
[project.urls]
Homepage = "https://github.com/YOURUSERNAME/arrmate"  # ← Your GitHub username
Repository = "https://github.com/YOURUSERNAME/arrmate"
Issues = "https://github.com/YOURUSERNAME/arrmate/issues"
```

#### `docs/index.html`
Replace ALL occurrences of `YOURUSERNAME` with your GitHub username (5 places):
- View on GitHub button
- Get Started button
- Footer links (3 places)
- Buy Me a Coffee link

#### `README.md` (top section)
Add badges with your username:
```markdown
[![GitHub release](https://img.shields.io/github/v/release/YOURUSERNAME/arrmate)](https://github.com/YOURUSERNAME/arrmate/releases)
[![License](https://img.shields.io/github/license/YOURUSERNAME/arrmate)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-support-yellow.svg)](https://buymeacoffee.com/YOURUSERNAME)
```

### 3. Verify All Updates
```bash
# Check for any remaining 'mediatools' references
grep -r "mediatools" . --exclude-dir=.git --exclude-dir=venv --exclude-dir=__pycache__ --exclude-dir=.claude

# Should return no results (or only in this checklist file)
```

## Git & GitHub Setup

### 4. Initialize Git Repository
```bash
cd /mnt/c/tools/arrmate

# Initialize
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

### 5. Create GitHub Repository

**Option A - Web Interface:**
1. Go to https://github.com/new
2. Repository name: `arrmate`
3. Description: `🤝 Your AI companion for Sonarr, Radarr, and Lidarr - manage your media library with natural language`
4. Public repository
5. DO NOT initialize with README
6. Click "Create repository"

**Option B - GitHub CLI:**
```bash
gh auth login
gh repo create arrmate --public --description "🤝 Your AI companion for Sonarr, Radarr, and Lidarr" --source=.
```

### 6. Push to GitHub
```bash
# Add remote (replace YOURUSERNAME!)
git remote add origin https://github.com/YOURUSERNAME/arrmate.git

# Push to main
git branch -M main
git push -u origin main
```

## GitHub Configuration

### 7. Add Repository Topics
On GitHub:
1. Go to your repository
2. Click ⚙️ next to "About"
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
4. Save changes

### 8. Enable Features
Settings → General:
- [x] Issues
- [x] Discussions
- [x] Preserve this repository (optional)

### 9. Set Up GitHub Pages
Settings → Pages:
1. Source: "Deploy from a branch"
2. Branch: `main` / `docs`
3. Click Save
4. Wait 1-2 minutes
5. Visit: `https://yourusername.github.io/arrmate/`
6. Verify it works!

## Sponsorship Setup

### 10. Create Buy Me a Coffee Account
1. Go to https://www.buymeacoffee.com/
2. Sign up
3. Customize your page:
   - Add profile picture
   - Description: "Supporting Arrmate development - making media management easier!"
   - Link to your GitHub repo
4. Note your username

### 11. Verify Sponsor Button
- Go to your GitHub repo
- Look for "Sponsor" button near the top
- Should link to your Buy Me a Coffee
- If not visible, check `.github/FUNDING.yml` is committed

## Release & Testing

### 12. Create v0.1.0 Release
On GitHub:
1. Go to Releases → Create a new release
2. Tag: `v0.1.0`
3. Title: `Arrmate v0.1.0 - Initial Release`
4. Description:

```markdown
# 🎉 Arrmate v0.1.0 - Initial Release

First public release of Arrmate - your AI companion for managing Sonarr, Radarr, and Lidarr!

## ✨ Features

- 🗣️ Natural language command interface - just say what you want
- 🤖 Multi-provider LLM support (Ollama free & local, OpenAI, Anthropic)
- 📺 Full Sonarr integration (TV shows)
- 🎬 Full Radarr integration (Movies)
- ⌨️ Beautiful CLI interface with rich formatting
- 🔌 REST API with OpenAPI documentation
- 🐳 Docker deployment with docker-compose
- 🔄 Service auto-discovery

## 🚀 Quick Start

See [QUICKSTART.md](https://github.com/YOURUSERNAME/arrmate/blob/main/QUICKSTART.md) for 5-minute setup!

**Docker:**
```bash
git clone https://github.com/YOURUSERNAME/arrmate.git
cd arrmate
cp .env.example .env
# Edit .env with your API keys
cd docker
docker-compose up -d
```

## 📝 Example Commands

```bash
arrmate execute "show me all my TV shows"
arrmate execute "add Breaking Bad to my library"
arrmate execute "remove episode 1 of Angel season 1"
arrmate execute "search for 4K version of Blade Runner"
```

## ⚠️ Known Limitations

- Lidarr support not yet implemented
- No web UI (CLI and API only)
- Single-turn commands only (no conversation memory)
- Basic fuzzy matching

## 🔮 What's Next (v0.2)

- Web UI interface
- Lidarr integration (music)
- Improved fuzzy matching
- Conversation memory
- Better error messages

## 🐛 Feedback

Found a bug? Have a suggestion? Please [open an issue](https://github.com/YOURUSERNAME/arrmate/issues)!

## ☕ Support

If Arrmate saves you time, consider [buying me a coffee](https://buymeacoffee.com/YOURUSERNAME)!

---

**Full Documentation:** https://github.com/YOURUSERNAME/arrmate#readme
**Website:** https://yourusername.github.io/arrmate/
```

5. Check "Set as the latest release"
6. Click "Publish release"

### 13. Create Beta Testing Discussion
1. Go to Discussions
2. New Discussion → General
3. Title: "🧪 Beta Testers Wanted!"
4. Body:

```markdown
# 🧪 Beta Testers Wanted!

Arrmate v0.1.0 is ready for testing! Looking for people to help test the natural language interface for Sonarr/Radarr.

## What It Does

Manage your media with natural language:
- ✨ "add Breaking Bad to my library"
- 🗑️ "remove episode 1 of Angel season 1"
- 🔍 "search for 4K version of Blade Runner"
- 📋 "list my TV shows"

## What I Need

- [ ] Test with your existing Sonarr/Radarr setup
- [ ] Try different command formats
- [ ] Report bugs and unexpected behavior
- [ ] Suggest improvements

## Requirements

- Sonarr and/or Radarr already installed
- Docker OR Python 3.11+
- Willingness to report issues

## Setup

See [QUICKSTART.md](https://github.com/YOURUSERNAME/arrmate/blob/main/QUICKSTART.md)

## Feedback

Create [issues](https://github.com/YOURUSERNAME/arrmate/issues) for bugs or reply here with your experience!

Thanks! 🚀
```

## Spreading the Word

### 14. Share on Reddit

**r/selfhosted:**
```
Title: [Project] Arrmate - Natural language interface for *arr stack

I built a tool to manage Sonarr/Radarr with natural language instead of clicking through UIs.

Instead of navigating menus:
- "add Breaking Bad to my library"
- "remove episode 1 of Angel season 1"
- "search for 4K version of Blade Runner"

Uses LLMs (Ollama/OpenAI/Claude) to parse commands and execute via APIs. Docker deployment included. Supports Ollama for free local LLM.

GitHub: https://github.com/YOURUSERNAME/arrmate

Looking for beta testers! Feedback welcome.
```

Post to:
- [ ] r/selfhosted
- [ ] r/sonarr
- [ ] r/radarr
- [ ] r/homelab

**Discord Servers:**
- [ ] TRaSH Guides Discord
- [ ] Servarr Discord (if allowed)
- [ ] r/Selfhosted Discord

### 15. Social Media (Optional)
- [ ] Twitter/X with screenshot
- [ ] Hacker News "Show HN"
- [ ] Dev.to article

## Docker Hub (Optional but Recommended)

### 16. Set Up Automated Docker Publishing

See [DOCKER_HUB_GUIDE.md](DOCKER_HUB_GUIDE.md) for full instructions.

**Quick version:**
1. Create Docker Hub account
2. Create repository `arrmate`
3. Add GitHub secrets:
   - `DOCKERHUB_USERNAME`
   - `DOCKERHUB_TOKEN`
4. Commit `.github/workflows/docker-publish.yml` (already created)
5. Next release will auto-publish!

## Post-Launch

### 17. Monitor & Respond
- [ ] Watch for GitHub issues
- [ ] Respond to questions in Discussions
- [ ] Thank contributors
- [ ] Update documentation based on feedback

### 18. Prepare v0.2.0
Based on feedback:
- [ ] Fix critical bugs
- [ ] Add most-requested features
- [ ] Improve documentation
- [ ] Plan roadmap

## Quick Reference

**Your URLs:**
- GitHub: `https://github.com/YOURUSERNAME/arrmate`
- GitHub Pages: `https://yourusername.github.io/arrmate/`
- Docker Hub: `https://hub.docker.com/r/yourusername/arrmate`
- Buy Me a Coffee: `https://buymeacoffee.com/YOURUSERNAME`

**Commands:**
```bash
# Update README badges
# Edit README.md and replace YOURUSERNAME in badges section

# Test locally
arrmate services

# Create new release
git tag v0.2.0
git push origin v0.2.0
# Then create release on GitHub
```

## Checklist Summary

**Before launch:**
- [ ] Directory renamed
- [ ] Personal info updated (YOURUSERNAME)
- [ ] Git repository initialized
- [ ] GitHub repository created
- [ ] Code pushed to GitHub
- [ ] Topics added
- [ ] GitHub Pages enabled
- [ ] Buy Me a Coffee created
- [ ] v0.1.0 release published
- [ ] Beta testing discussion created

**After launch:**
- [ ] Shared on Reddit
- [ ] Shared on Discord
- [ ] Docker Hub set up (optional)
- [ ] Monitoring issues/discussions
- [ ] Responding to testers

**All done?** 🎉

You're ready to go! Share the link and start getting feedback.

Good luck! 🚀
