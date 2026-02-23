#!/bin/sh
# Entrypoint: ensure the data directory exists, then start the app.
# Runs as root for maximum compatibility with named volumes and bind mounts.
DATA_DIR="${AUTH_DATA_DIR:-/data}"
mkdir -p "$DATA_DIR"
exec "$@"
