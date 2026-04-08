#Requires -Version 5.1
$ErrorActionPreference = "Stop"

# Fix console encoding for UTF-8 output
[Console]::OutputEncoding = [Text.Encoding]::UTF8

# Configuration
$DOCKER_USER = "techbutton"
$IMAGE_NAME  = "arrmate"

# Get version from pyproject.toml
$versionLine = Select-String -Path "pyproject.toml" -Pattern '^version = "(.+)"'
if (-not $versionLine) {
    Write-Host "ERROR: Could not determine version from pyproject.toml" -ForegroundColor Red
    exit 1
}
$VERSION = $versionLine.Matches[0].Groups[1].Value

Write-Host ""
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "         Publishing Arrmate to Docker Hub                       " -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Image:   $DOCKER_USER/$IMAGE_NAME" -ForegroundColor White
Write-Host "Version: $VERSION" -ForegroundColor White
Write-Host ""

# Check Docker Hub login
Write-Host "Checking Docker Hub authentication..." -ForegroundColor Yellow
$dockerInfo = docker info 2>&1 | Out-String
if ($dockerInfo -notmatch "Username:\s*$DOCKER_USER") {
    Write-Host "Not logged in to Docker Hub as $DOCKER_USER" -ForegroundColor Yellow
    Write-Host "Running: docker login" -ForegroundColor Gray
    docker login
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Docker login failed" -ForegroundColor Red
        exit 1
    }
}

# Build the image (single build, tag twice)
Write-Host ""
Write-Host "Building Docker image..." -ForegroundColor Yellow
docker build -t "${DOCKER_USER}/${IMAGE_NAME}:${VERSION}" -t "${DOCKER_USER}/${IMAGE_NAME}:latest" .
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Build failed" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Build complete!" -ForegroundColor Green
Write-Host ""

# Show image size
Write-Host "Image Information:" -ForegroundColor White
docker images "${DOCKER_USER}/${IMAGE_NAME}" --format "table {{.Repository}}:{{.Tag}}`t{{.Size}}"
Write-Host ""

# Confirm push
$reply = Read-Host "Push to Docker Hub? (y/N)"
if ($reply -notmatch '^[Yy]$') {
    Write-Host "Push cancelled." -ForegroundColor Yellow
    exit 0
}

# Push both tags
Write-Host ""
Write-Host "Pushing to Docker Hub..." -ForegroundColor Yellow
docker push "${DOCKER_USER}/${IMAGE_NAME}:${VERSION}"
if ($LASTEXITCODE -ne 0) { Write-Host "ERROR: Push failed" -ForegroundColor Red; exit 1 }

docker push "${DOCKER_USER}/${IMAGE_NAME}:latest"
if ($LASTEXITCODE -ne 0) { Write-Host "ERROR: Push failed" -ForegroundColor Red; exit 1 }

Write-Host ""
Write-Host "================================================================" -ForegroundColor Green
Write-Host "                 Published Successfully!                        " -ForegroundColor Green
Write-Host "================================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Docker Hub: https://hub.docker.com/r/$DOCKER_USER/$IMAGE_NAME" -ForegroundColor Cyan
Write-Host ""
Write-Host "Pull Commands:" -ForegroundColor White
Write-Host "  docker pull ${DOCKER_USER}/${IMAGE_NAME}:${VERSION}"
Write-Host "  docker pull ${DOCKER_USER}/${IMAGE_NAME}:latest"
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor White
Write-Host "  1. Verify: https://hub.docker.com/r/$DOCKER_USER/$IMAGE_NAME"
Write-Host "  2. Test:   docker run -p 8000:8000 ${DOCKER_USER}/${IMAGE_NAME}:latest"
Write-Host "  3. Deploy: docker compose -f docker-compose.prod.yml up -d"
Write-Host ""
