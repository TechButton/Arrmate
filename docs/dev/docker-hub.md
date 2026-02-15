# Publishing to Docker Hub

Publishing to Docker Hub makes it easier for users to run Arrmate without building from source.

## Do You Need Docker Hub?

**Pros:**
- ✅ Users can pull pre-built images: `docker pull yourusername/arrmate`
- ✅ Faster deployment for users (no build time)
- ✅ Looks more professional
- ✅ Easier CI/CD for releases

**Cons:**
- ❌ Extra maintenance (build and push for each release)
- ❌ Requires Docker Hub account
- ❌ Free tier limits (1 private repo, rate limits for pulls)

**Recommendation:**
- **Yes, publish to Docker Hub** - It's free for public repos and makes deployment much easier for users
- Consider GitHub Container Registry (ghcr.io) as alternative/addition

## Option 1: Manual Docker Hub Publishing

### Step 1: Create Docker Hub Account

1. Go to https://hub.docker.com/
2. Sign up / Create account
3. Create new repository:
   - Name: `arrmate`
   - Visibility: Public
   - Description: "🤝 Your AI companion for Sonarr, Radarr, and Lidarr"

### Step 2: Build and Tag Image

```bash
cd /mnt/c/tools/arrmate

# Build the image
docker build -f docker/Dockerfile -t arrmate:latest .

# Tag for Docker Hub (replace 'yourusername')
docker tag arrmate:latest yourusername/arrmate:latest
docker tag arrmate:latest yourusername/arrmate:0.1.0
```

### Step 3: Login and Push

```bash
# Login to Docker Hub
docker login

# Push images
docker push yourusername/arrmate:latest
docker push yourusername/arrmate:0.1.0
```

### Step 4: Update docker-compose.yml

Update your `docker/docker-compose.yml` to use the published image:

```yaml
services:
  arrmate:
    image: yourusername/arrmate:latest  # Instead of build:
    # Remove build: section
    container_name: arrmate
    # ... rest of config
```

Or provide both options (for developers vs users):

```yaml
services:
  arrmate:
    # For users: pull from Docker Hub
    image: yourusername/arrmate:latest

    # For developers: uncomment to build locally
    # build:
    #   context: ..
    #   dockerfile: docker/Dockerfile

    container_name: arrmate
    # ... rest
```

## Option 2: Automated Publishing with GitHub Actions

This automatically builds and publishes to Docker Hub when you create a release.

### Step 1: Create Docker Hub Access Token

1. Go to https://hub.docker.com/settings/security
2. Click "New Access Token"
3. Description: "GitHub Actions - Arrmate"
4. Permissions: Read & Write
5. Copy the token (you won't see it again!)

### Step 2: Add Secrets to GitHub

1. Go to your GitHub repo → Settings → Secrets and variables → Actions
2. Click "New repository secret"
3. Add these secrets:
   - Name: `DOCKERHUB_USERNAME`, Value: your Docker Hub username
   - Name: `DOCKERHUB_TOKEN`, Value: the token you just created

### Step 3: Create GitHub Actions Workflow

Create `.github/workflows/docker-publish.yml`:

```yaml
name: Build and Publish Docker Image

on:
  release:
    types: [published]
  workflow_dispatch:  # Allow manual trigger

env:
  REGISTRY: docker.io
  IMAGE_NAME: ${{ secrets.DOCKERHUB_USERNAME }}/arrmate

jobs:
  build-and-push:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Log in to Docker Hub
        uses: docker/login-action@v3
        with:
          username: ${{ secrets.DOCKERHUB_USERNAME }}
          password: ${{ secrets.DOCKERHUB_TOKEN }}

      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.IMAGE_NAME }}
          tags: |
            type=semver,pattern={{version}}
            type=semver,pattern={{major}}.{{minor}}
            type=raw,value=latest,enable={{is_default_branch}}

      - name: Build and push Docker image
        uses: docker/build-push-action@v5
        with:
          context: .
          file: ./docker/Dockerfile
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=registry,ref=${{ env.IMAGE_NAME }}:latest
          cache-to: type=inline
          platforms: linux/amd64,linux/arm64

      - name: Update Docker Hub description
        uses: peter-evans/dockerhub-description@v3
        with:
          username: ${{ secrets.DOCKERHUB_USERNAME }}
          password: ${{ secrets.DOCKERHUB_TOKEN }}
          repository: ${{ env.IMAGE_NAME }}
          short-description: "🤝 Your AI companion for Sonarr, Radarr, and Lidarr"
          readme-filepath: ./README.md
```

### Step 4: Commit and Push

```bash
git add .github/workflows/docker-publish.yml
git commit -m "Add automated Docker Hub publishing"
git push
```

Now when you create a new release (e.g., v0.2.0), GitHub Actions will:
1. Build the Docker image
2. Tag it as `yourusername/arrmate:0.2.0` and `yourusername/arrmate:latest`
3. Push to Docker Hub
4. Update the Docker Hub README

## Option 3: GitHub Container Registry (Alternative)

GitHub also provides free container registry at ghcr.io.

### Advantages:
- Integrated with GitHub
- Better rate limits
- Free for public repos
- No separate account needed

### Disadvantages:
- Less discoverable than Docker Hub
- Users less familiar with ghcr.io

### Quick Setup:

1. Create `.github/workflows/ghcr-publish.yml`:

```yaml
name: Publish to GHCR

on:
  release:
    types: [published]

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  build-and-push:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Log in to GHCR
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}

      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: .
          file: ./docker/Dockerfile
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
```

2. Users would then pull with:
```bash
docker pull ghcr.io/yourusername/arrmate:latest
```

## Recommendation: Use Both!

Publish to **both** Docker Hub (primary) and GHCR (backup):

1. Primary for users: `docker pull yourusername/arrmate:latest`
2. Backup on GHCR: `docker pull ghcr.io/yourusername/arrmate:latest`

Combine both workflows or create a single workflow that publishes to both registries.

## Update Documentation

After publishing to Docker Hub, update these files:

### README.md

```markdown
## Quick Start

### Docker (Recommended)

```bash
docker pull yourusername/arrmate:latest
cd arrmate/docker
docker-compose up -d
```
```

### docker-compose.yml

```yaml
services:
  arrmate:
    image: yourusername/arrmate:latest
    # ... rest of config
```

### QUICKSTART.md

Update all docker examples to use the published image.

## Maintenance

### For Each Release:

1. Update version in `pyproject.toml`
2. Create git tag: `git tag v0.2.0`
3. Push tag: `git push origin v0.2.0`
4. Create GitHub release
5. GitHub Actions automatically builds and pushes Docker image
6. Verify on Docker Hub: https://hub.docker.com/r/yourusername/arrmate

### Manual Build (if needed):

```bash
# Build for multiple platforms
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t yourusername/arrmate:0.2.0 \
  -t yourusername/arrmate:latest \
  --push \
  -f docker/Dockerfile .
```

## Summary

**Minimum (without Docker Hub):**
- Users clone repo and build locally
- Longer setup time for users
- More support questions

**With Docker Hub (Recommended):**
- One-line pull: `docker pull yourusername/arrmate`
- Much easier for users
- More professional
- Free for public repos

**Setup Time:**
- Manual: ~15 minutes
- Automated (GitHub Actions): ~30 minutes first time, then automatic

**Verdict: Yes, publish to Docker Hub!** It's worth the small effort for much better user experience.
