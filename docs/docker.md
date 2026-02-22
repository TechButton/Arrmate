# Docker Deployment

## Pre-built image (recommended)

Use `docker-compose.prod.yml` to pull from Docker Hub:

```bash
curl -O https://raw.githubusercontent.com/techbutton/arrmate/main/docker-compose.prod.yml
curl -O https://raw.githubusercontent.com/techbutton/arrmate/main/.env.example
cp .env.example .env
# edit .env
docker compose -f docker-compose.prod.yml up -d
```

This pulls `techbutton/arrmate:latest` and starts Ollama alongside it. If you're using an external Ollama instance, OpenAI, or Anthropic, comment out the `ollama` service block.

## Build from source

Use `docker-compose.yml` to build locally:

```bash
git clone https://github.com/techbutton/arrmate.git
cd arrmate
cp .env.example .env
# edit .env
docker compose up -d
```

## Full stack (testing)

`docker-compose.full.yml` includes Sonarr and Radarr alongside Arrmate and Ollama — useful for testing without an existing media stack:

```bash
docker compose -f docker-compose.full.yml up -d
```

After it starts, configure Sonarr (`http://localhost:8989`) and Radarr (`http://localhost:7878`) through their setup wizards, grab the API keys from Settings → General, add them to `.env`, then `docker compose restart arrmate`.

## Ollama models

`qwen2.5:7b` is a solid default for tool-calling accuracy:

```bash
docker compose exec ollama ollama pull qwen2.5:7b
```

To switch models, update `OLLAMA_MODEL` in `.env` and restart Arrmate. The model only needs to be pulled once — it's stored in the `ollama-data` volume.

## GPU acceleration

NVIDIA:
```bash
docker compose -f docker-compose.prod.yml -f docker-compose.ollama-nvidia.yml up -d
```

AMD:
```bash
docker compose -f docker-compose.prod.yml -f docker-compose.ollama-amd.yml up -d
```

## Connecting to existing services

If Sonarr/Radarr are on a different Docker network, add that network to the Arrmate service in your compose file:

```yaml
services:
  arrmate:
    networks:
      - arrmate-net
      - your-existing-network

networks:
  your-existing-network:
    external: true
```

Or just use IP addresses in `SONARR_URL` / `RADARR_URL` instead of container names.

## H.265 transcoding

For the transcode feature to work, media files need to be accessible inside the container at the same paths Sonarr/Radarr report. Uncomment and edit the volume mounts in the compose file:

```yaml
volumes:
  - /your/movies:/movies
  - /your/tv:/tv
```

## Traefik

Labels are included in `docker-compose.prod.yml` as comments. Uncomment them and set `TRAEFIK_DOMAIN`, `TRAEFIK_ENTRYPOINT`, `TRAEFIK_CERTRESOLVER`, and `TRAEFIK_NETWORK` in `.env`. See [simplehomelab-traefik.md](simplehomelab-traefik.md) for a drop-in config.

## Useful commands

```bash
# Logs
docker compose logs -f arrmate

# Restart after config change
docker compose restart arrmate

# Update to latest image
docker compose -f docker-compose.prod.yml pull && docker compose -f docker-compose.prod.yml up -d

# Shell access
docker compose exec arrmate bash
```
