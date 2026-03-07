#!/bin/sh
# Fix /data ownership in case the volume was created as root,
# then drop to the non-root arrmate user before starting the app.
DATA_DIR="${AUTH_DATA_DIR:-/data}"
mkdir -p "$DATA_DIR"
chown arrmate:arrmate "$DATA_DIR"
exec su-exec arrmate "$@"
