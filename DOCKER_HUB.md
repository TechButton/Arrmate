# Publishing Arrmate to Docker Hub

Guide for publishing the Arrmate Docker image to Docker Hub.

## Quick Publish

```bash
# One-command publish (interactive)
./publish-docker.sh
```

This script will:
1. ✅ Extract version from `pyproject.toml`
2. ✅ Build image with version tag and `latest`
3. ✅ Prompt for confirmation
4. ✅ Push to Docker Hub

## Manual Publishing Steps

### 1. Login to Docker Hub

```bash
docker login
# Enter username: techbutton
# Enter password: <your-token>
```

**Best Practice:** Use an access token instead of your password:
- Go to https://hub.docker.com/settings/security
- Create new access token
- Use token as password when logging in

### 2. Build the Image

```bash
# Get current version
VERSION=$(grep '^version = ' pyproject.toml | sed 's/version = "\(.*\)"/\1/')

# Build with version tag
docker build -t techbutton/arrmate:$VERSION .

# Also tag as latest
docker build -t techbutton/arrmate:latest .
```

### 3. Test the Image Locally

```bash
# Test the image works
docker run -p 8000:8000 techbutton/arrmate:latest

# Visit http://localhost:8000/web/
```

### 4. Push to Docker Hub

```bash
# Push version tag
docker push techbutton/arrmate:$VERSION

# Push latest tag
docker push techbutton/arrmate:latest
```

### 5. Verify on Docker Hub

Visit: https://hub.docker.com/r/techbutton/arrmate

## Using Published Images

### For Development (docker-compose.yml)
Uses local build - good for testing changes:
```bash
docker compose up -d
```

### For Production (docker-compose.prod.yml)
Uses published image from Docker Hub:
```bash
docker compose -f docker-compose.prod.yml up -d
```

## Tagging Strategy

### Version Tags
- `techbutton/arrmate:0.2.0` - Specific version (from pyproject.toml)
- `techbutton/arrmate:latest` - Always points to newest version

### When to Tag

**Major Release (1.0.0, 2.0.0)**
- Breaking changes
- Major new features
- Incompatible with previous versions

**Minor Release (0.2.0, 0.3.0)**
- New features
- Backwards compatible
- Enhanced functionality

**Patch Release (0.2.1, 0.2.2)**
- Bug fixes
- Security patches
- Minor improvements

## Multi-Platform Builds

To build for multiple architectures (AMD64, ARM64):

```bash
# Setup buildx (one time)
docker buildx create --name multiplatform --use

# Build and push for multiple platforms
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t techbutton/arrmate:$VERSION \
  -t techbutton/arrmate:latest \
  --push \
  .
```

This enables:
- ✅ x86_64 / AMD64 (standard PCs, cloud)
- ✅ ARM64 / aarch64 (Raspberry Pi, Apple Silicon)

## Automated Publishing with GitHub Actions

Create `.github/workflows/docker-publish.yml`:

```yaml
name: Publish Docker Image

on:
  push:
    tags:
      - 'v*'

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Login to Docker Hub
        uses: docker/login-action@v3
        with:
          username: techbutton
          password: ${{ secrets.DOCKERHUB_TOKEN }}
      
      - name: Extract version
        id: version
        run: echo "VERSION=$(grep '^version = ' pyproject.toml | sed 's/version = \"\(.*\)\"/\1/')" >> $GITHUB_OUTPUT
      
      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: |
            techbutton/arrmate:${{ steps.version.outputs.VERSION }}
            techbutton/arrmate:latest
```

Then publish by creating a git tag:
```bash
git tag v0.2.0
git push origin v0.2.0
```

## Security Best Practices

### 1. Use Access Tokens
- Never use your Docker Hub password in scripts
- Create tokens at https://hub.docker.com/settings/security
- Set appropriate permissions (Read & Write)

### 2. Scan Images for Vulnerabilities
```bash
# Using Docker Scout (built-in)
docker scout cves techbutton/arrmate:latest

# Using Trivy
docker run aquasec/trivy image techbutton/arrmate:latest
```

### 3. Keep Images Updated
- Regularly rebuild to get security patches
- Update base image (python:3.11-slim)
- Monitor for CVEs

### 4. Use Multi-Stage Builds
Already implemented in our Dockerfile:
- Smaller image size
- Fewer attack surfaces
- No build tools in final image

## Image Optimization

Current optimizations:
- ✅ Multi-stage build (if needed)
- ✅ Minimal base image (python:3.11-slim)
- ✅ .dockerignore to exclude unnecessary files
- ✅ Layer caching optimization
- ✅ Non-root user

Check image size:
```bash
docker images techbutton/arrmate:latest
```

## Troubleshooting

### Push Denied
```
Error: unauthorized: authentication required
```
**Solution:** Run `docker login` first

### Image Too Large
```
Image size: 1.2GB
```
**Solution:**
- Check .dockerignore is working
- Remove unnecessary dependencies
- Use smaller base image

### Build Fails
```
failed to solve: failed to compute cache key
```
**Solution:**
- Clear build cache: `docker builder prune`
- Rebuild: `docker build --no-cache`

### Wrong Platform
```
WARNING: The requested image's platform (linux/amd64) does not match
```
**Solution:** Use buildx for multi-platform builds

## Registry Alternatives

While we use Docker Hub, alternatives include:

- **GitHub Container Registry** (ghcr.io)
- **Google Container Registry** (gcr.io)
- **Amazon ECR** (AWS)
- **Azure Container Registry** (Microsoft)

## Quick Reference

```bash
# Publish workflow
docker login
./publish-docker.sh

# Use published image
docker compose -f docker-compose.prod.yml up -d

# Check image
docker pull techbutton/arrmate:latest
docker run -p 8000:8000 techbutton/arrmate:latest

# Update to new version
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
```

## Links

- Docker Hub Repository: https://hub.docker.com/r/techbutton/arrmate
- Docker Hub Docs: https://docs.docker.com/docker-hub/
- Dockerfile Best Practices: https://docs.docker.com/develop/dev-best-practices/
