# Publishing Arrmate

Complete guide for releasing Arrmate to GitHub and Docker Hub.

## Quick Release Workflow

```bash
# 1. Update version in pyproject.toml
# 2. Commit changes
git add .
git commit -m "Release v0.2.0"

# 3. Create and push git tag
git tag v0.2.0
git push origin main
git push origin v0.2.0

# 4. Publish to Docker Hub
./publish-docker.sh

# 5. Create GitHub Release (optional, manual)
# Visit: https://github.com/techbutton/arrmate/releases/new
```

## Detailed Instructions

### 1. Prepare the Release

**Update Version Number**

Edit `pyproject.toml`:
```toml
[project]
name = "arrmate"
version = "0.3.0"  # Update this
```

**Update CHANGELOG** (create if doesn't exist):
```markdown
# Changelog

## [0.3.0] - 2026-02-15

### Added
- New feature X
- New feature Y

### Fixed
- Bug fix A
- Bug fix B

### Changed
- Improvement C
```

**Commit Changes**:
```bash
git add pyproject.toml CHANGELOG.md
git commit -m "Bump version to 0.3.0"
git push origin main
```

### 2. Create Git Tag

Tags mark specific points in git history for releases:

```bash
# Create annotated tag
git tag -a v0.3.0 -m "Release version 0.3.0"

# Push tag to GitHub
git push origin v0.3.0

# Or push all tags
git push --tags
```

**Tag Naming Convention:**
- Format: `vMAJOR.MINOR.PATCH`
- Examples: `v0.2.0`, `v1.0.0`, `v1.2.3`

### 3. Publish to Docker Hub

**Login** (one time):
```bash
docker login
# Username: techbutton
# Password: <access-token>
```

**Get Access Token:**
1. Go to https://hub.docker.com/settings/security
2. Click "New Access Token"
3. Name: "Arrmate Publishing"
4. Permissions: Read & Write
5. Copy and save the token

**Run Publish Script:**
```bash
./publish-docker.sh
```

This will:
- ✅ Extract version from `pyproject.toml`
- ✅ Build `techbutton/arrmate:0.3.0`
- ✅ Build `techbutton/arrmate:latest`
- ✅ Push both to Docker Hub

**Manual Publish** (if script fails):
```bash
VERSION=$(grep '^version = ' pyproject.toml | sed 's/version = "\(.*\)"/\1/')

# Build
docker build -t techbutton/arrmate:$VERSION .
docker build -t techbutton/arrmate:latest .

# Push
docker push techbutton/arrmate:$VERSION
docker push techbutton/arrmate:latest
```

### 4. Create GitHub Release

**Option A: Using GitHub Web UI** (Recommended)

1. Go to https://github.com/techbutton/arrmate/releases/new
2. Choose tag: `v0.3.0`
3. Release title: `Arrmate v0.3.0`
4. Description: Copy from CHANGELOG.md
5. Check "Set as the latest release"
6. Click "Publish release"

**Option B: Using GitHub CLI**

```bash
# Install gh CLI if needed
# https://cli.github.com/

gh release create v0.3.0 \
  --title "Arrmate v0.3.0" \
  --notes "Release notes here"
```

**Release Notes Template:**
```markdown
## What's New

- 🎉 Major new feature
- ✨ Enhancement to existing feature
- 🐛 Bug fix for issue #123

## Docker

```bash
docker pull techbutton/arrmate:0.3.0
docker pull techbutton/arrmate:latest
```

## Installation

See [README.md](README.md) for installation instructions.

## Full Changelog

See [CHANGELOG.md](CHANGELOG.md) for complete details.
```

### 5. Verify Release

**Check Docker Hub:**
- Visit: https://hub.docker.com/r/techbutton/arrmate
- Verify tags: `0.3.0` and `latest` are present
- Check image size and layers

**Check GitHub:**
- Visit: https://github.com/techbutton/arrmate/releases
- Verify release is published
- Verify tag is created

**Test Installation:**
```bash
# Pull from Docker Hub
docker pull techbutton/arrmate:0.3.0

# Run it
docker run -p 8000:8000 \
  -e LLM_PROVIDER=ollama \
  -e OLLAMA_BASE_URL=http://host.docker.internal:11434 \
  techbutton/arrmate:0.3.0

# Visit http://localhost:8000/web/
```

## Version Numbering (Semantic Versioning)

Format: `MAJOR.MINOR.PATCH`

**MAJOR (1.0.0, 2.0.0)**
- Breaking changes
- Incompatible API changes
- Major redesign

**MINOR (0.2.0, 0.3.0)**
- New features
- Backwards compatible
- New functionality

**PATCH (0.2.1, 0.2.2)**
- Bug fixes
- Security patches
- Minor improvements

**Examples:**
- `0.1.0` → `0.2.0` - Added web UI (new feature)
- `0.2.0` → `0.2.1` - Fixed bug in command parser
- `0.9.0` → `1.0.0` - First stable release (breaking changes)

## Automated Publishing with GitHub Actions

Create `.github/workflows/release.yml`:

```yaml
name: Release

on:
  push:
    tags:
      - 'v*'

jobs:
  docker:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Get version
        id: version
        run: |
          VERSION=$(grep '^version = ' pyproject.toml | sed 's/version = "\(.*\)"/\1/')
          echo "VERSION=$VERSION" >> $GITHUB_OUTPUT
      
      - name: Login to Docker Hub
        uses: docker/login-action@v3
        with:
          username: techbutton
          password: ${{ secrets.DOCKERHUB_TOKEN }}
      
      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: |
            techbutton/arrmate:${{ steps.version.outputs.VERSION }}
            techbutton/arrmate:latest
  
  github-release:
    runs-on: ubuntu-latest
    needs: docker
    steps:
      - uses: actions/checkout@v4
      
      - name: Create Release
        uses: actions/create-release@v1
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        with:
          tag_name: ${{ github.ref }}
          release_name: Release ${{ github.ref }}
          draft: false
          prerelease: false
```

**Setup Secrets:**
1. Go to https://github.com/techbutton/arrmate/settings/secrets/actions
2. Add `DOCKERHUB_TOKEN` with your Docker Hub access token

**Trigger Release:**
```bash
git tag v0.3.0
git push origin v0.3.0
# GitHub Actions will automatically build and publish
```

## Release Checklist

Before releasing:

- [ ] All tests pass
- [ ] Documentation updated
- [ ] CHANGELOG.md updated
- [ ] Version bumped in pyproject.toml
- [ ] Committed and pushed to main
- [ ] Git tag created and pushed
- [ ] Docker Hub published
- [ ] GitHub release created
- [ ] Release tested locally
- [ ] Release announcement (optional)

## Rollback

If a release has issues:

**Unpublish from GitHub:**
1. Go to https://github.com/techbutton/arrmate/releases
2. Click on the bad release
3. Click "Delete release"

**Docker Hub** (can't delete, but can update):
```bash
# Rebuild and push with :latest only
docker build -t techbutton/arrmate:latest .
docker push techbutton/arrmate:latest
```

**Revert Git Tag:**
```bash
git tag -d v0.3.0
git push origin :refs/tags/v0.3.0
```

## Best Practices

1. **Test Before Release**
   - Build and run locally
   - Test all major features
   - Verify documentation

2. **Semantic Versioning**
   - Follow MAJOR.MINOR.PATCH
   - Document breaking changes
   - Keep backwards compatibility when possible

3. **Release Notes**
   - Clear and concise
   - Group by category (Added, Fixed, Changed)
   - Include upgrade instructions if needed

4. **Regular Releases**
   - Don't batch too many changes
   - Release when features are stable
   - Fix critical bugs ASAP with patch releases

5. **Changelog**
   - Keep it updated with each change
   - Makes release notes easy to write
   - Users appreciate transparency

## Troubleshooting

**Docker push denied:**
```
denied: requested access to the resource is denied
```
Solution: Run `docker login` with correct credentials

**Tag already exists:**
```
fatal: tag 'v0.3.0' already exists
```
Solution: Delete tag first:
```bash
git tag -d v0.3.0
git push origin :refs/tags/v0.3.0
```

**Build fails:**
Check:
- Dockerfile syntax
- Dependencies in pyproject.toml
- Build context (.dockerignore)

## Links

- Docker Hub: https://hub.docker.com/r/techbutton/arrmate
- GitHub Releases: https://github.com/techbutton/arrmate/releases
- Semantic Versioning: https://semver.org/
- GitHub Actions: https://docs.github.com/en/actions
