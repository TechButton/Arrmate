# Arrmate Docker Deployment

Complete Docker setup with Arrmate, Ollama, Sonarr, and Radarr.

## Quick Start

```bash
# 1. Run the setup script
./docker-setup.sh

# 2. Pull the Ollama model
docker compose exec ollama ollama pull llama3.2

# 3. Configure Sonarr and Radarr
# - Visit http://localhost:8989 (Sonarr)
# - Visit http://localhost:7878 (Radarr)
# - Complete setup wizards
# - Get API keys from Settings > General

# 4. Update .env with API keys
# Edit .env and add your SONARR_API_KEY and RADARR_API_KEY

# 5. Restart Arrmate
docker compose restart arrmate

# 6. Access the Web UI
# http://localhost:8000/web/
```

## Services Included

| Service | Port | Description | URL |
|---------|------|-------------|-----|
| Arrmate | 8000 | Main web UI & API | http://localhost:8000/web/ |
| Sonarr | 8989 | TV show management | http://localhost:8989 |
| Radarr | 7878 | Movie management | http://localhost:7878 |
| Ollama | 11434 | LLM provider | http://localhost:11434 |

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    arrmate-network                      │
│                                                         │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐         │
│  │  Sonarr  │    │  Radarr  │    │  Ollama  │         │
│  │  :8989   │    │  :7878   │    │  :11434  │         │
│  └────┬─────┘    └────┬─────┘    └────┬─────┘         │
│       │               │               │                │
│       └───────────────┴───────────────┘                │
│                       │                                │
│                 ┌─────▼──────┐                         │
│                 │  Arrmate   │                         │
│                 │   :8000    │                         │
│                 └────────────┘                         │
└─────────────────────────────────────────────────────────┘
```

## Volume Mounts

Data is persisted in Docker volumes:

- `ollama-data` - Ollama models and configuration
- `sonarr-config` - Sonarr configuration
- `sonarr-tv` - TV show storage
- `sonarr-downloads` - Download location for Sonarr
- `radarr-config` - Radarr configuration
- `radarr-movies` - Movie storage
- `radarr-downloads` - Download location for Radarr

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
nano .env
```

Key variables:
- `SONARR_API_KEY` - Get from Sonarr Settings > General
- `RADARR_API_KEY` - Get from Radarr Settings > General
- `OLLAMA_MODEL` - Default: llama3.2

### Initial Setup Steps

1. **Start Services**
   ```bash
   docker compose up -d
   ```

2. **Configure Sonarr** (http://localhost:8989)
   - Complete setup wizard
   - Go to Settings > General
   - Copy API Key
   - Add to `.env` as `SONARR_API_KEY`

3. **Configure Radarr** (http://localhost:7878)
   - Complete setup wizard
   - Go to Settings > General
   - Copy API Key
   - Add to `.env` as `RADARR_API_KEY`

4. **Pull Ollama Model**
   ```bash
   docker compose exec ollama ollama pull llama3.2
   ```

5. **Restart Arrmate**
   ```bash
   docker compose restart arrmate
   ```

6. **Test the Web UI**
   - Visit http://localhost:8000/web/
   - Check Services page to verify all are online
   - Try a command like "list my TV shows"

## Management Commands

### View Logs
```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f arrmate
docker compose logs -f sonarr
docker compose logs -f radarr
docker compose logs -f ollama
```

### Restart Services
```bash
# All services
docker compose restart

# Specific service
docker compose restart arrmate
```

### Stop Services
```bash
docker compose down
```

### Update Services
```bash
# Pull latest images
docker compose pull

# Rebuild Arrmate
docker compose build arrmate

# Restart with new images
docker compose up -d
```

### Access Container Shell
```bash
docker compose exec arrmate bash
docker compose exec sonarr bash
docker compose exec radarr bash
docker compose exec ollama bash
```

## Ollama Management

### Pull Different Models
```bash
# Llama 3.2 (default, ~2GB)
docker compose exec ollama ollama pull llama3.2

# Llama 3.1 (larger, better performance)
docker compose exec ollama ollama pull llama3.1

# Mistral (alternative)
docker compose exec ollama ollama pull mistral
```

### List Downloaded Models
```bash
docker compose exec ollama ollama list
```

### Remove a Model
```bash
docker compose exec ollama ollama rm llama3.2
```

### Change Model in Arrmate
Edit `.env`:
```bash
OLLAMA_MODEL=llama3.1
```

Then restart:
```bash
docker compose restart arrmate
```

## Troubleshooting

### Services Won't Start
```bash
# Check status
docker compose ps

# Check logs for errors
docker compose logs

# Verify Docker is running
docker info
```

### Can't Connect to Services
```bash
# Ensure all services are healthy
docker compose ps

# Check network
docker network ls
docker network inspect arrmate-network

# Test connectivity
docker compose exec arrmate curl http://sonarr:8989/ping
docker compose exec arrmate curl http://radarr:7878/ping
docker compose exec arrmate curl http://ollama:11434/api/tags
```

### Arrmate Can't Reach Services
1. Check API keys are correct in `.env`
2. Verify services are running: `docker compose ps`
3. Check Arrmate logs: `docker compose logs arrmate`
4. Test from inside container:
   ```bash
   docker compose exec arrmate bash
   curl http://sonarr:8989/api/v3/system/status?apikey=YOUR_KEY
   ```

### Reset Everything
```bash
# Stop and remove containers, volumes
docker compose down -v

# Remove images
docker compose down --rmi all

# Start fresh
./docker-setup.sh
```

## Production Deployment

For production use:

1. **Use External Volumes** for media storage
2. **Set Strong API Keys**
3. **Enable HTTPS** (use reverse proxy like Traefik/Nginx)
4. **Backup Volumes** regularly
5. **Monitor Resources** (CPU, RAM, disk)
6. **Update Regularly** for security patches

## Security Notes

- API keys are sensitive - keep `.env` secure
- Don't expose ports publicly without authentication
- Use strong passwords for all services
- Consider using Docker secrets for sensitive data
- Regular security updates recommended

## Performance Tips

- Ollama benefits from GPU acceleration (add GPU passthrough)
- Increase RAM if running larger models
- Use SSD storage for better performance
- Monitor container resource usage with `docker stats`

## Support

- Main documentation: `README.md`
- Web UI guide: `WEB_UI_GUIDE.md`
- Issues: https://github.com/techbutton/arrmate/issues
