#!/bin/sh
set -e

# If the frontend's source has been bind-mounted over /app (the default in
# docker-compose.yml), rebuild from it before serving - this is what makes a
# plain `docker restart order-explorer-frontend` pick up a self-upgrade-merged
# frontend change (or any manual edit) without a full `docker compose build`.
# Set FRONTEND_LIVE_SOURCE=false to skip this and always serve the image's
# baked-in build from the Dockerfile's builder stage.
if [ "${FRONTEND_LIVE_SOURCE:-true}" = "true" ] && [ -f /app/package.json ]; then
    echo "[entrypoint] rebuilding order-explorer-frontend from live source..."
    cd /app
    npm ci --no-audit --no-fund
    npm run build
    rm -rf /usr/share/nginx/html/*
    cp -r dist/. /usr/share/nginx/html/
fi

exec nginx -g "daemon off;"
