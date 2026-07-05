# Build context for this Dockerfile is the REPO ROOT (see docker-compose.yml:
# order-explorer-frontend uses `context: .`, `dockerfile:
# order_explorer_site/frontend/Dockerfile`), so all COPY paths below are
# repo-root-relative. This lets the image also pull in docker/frontend/*
# support files alongside the frontend's own source.

# --- builder stage: produce a baked-in default dist/, so the image is
# self-sufficient even for someone who never bind-mounts live source ---
FROM node:22-alpine AS builder
WORKDIR /app
COPY order_explorer_site/frontend/package.json order_explorer_site/frontend/package-lock.json ./
RUN npm ci
COPY order_explorer_site/frontend/ ./
RUN npm run build

# --- final stage: nginx to serve, Node kept around so the entrypoint can
# rebuild from a bind-mounted live source on every container start (needed
# so a plain `docker restart order-explorer-frontend` picks up a
# self-upgrade-merged frontend change without a full `docker compose build`) ---
FROM node:22-alpine
RUN apk add --no-cache nginx
WORKDIR /app
COPY --from=builder /app /app
COPY --from=builder /app/dist /usr/share/nginx/html
COPY docker/frontend/nginx-frontend.conf /etc/nginx/http.d/default.conf
COPY docker/frontend/docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh
EXPOSE 80
ENTRYPOINT ["/docker-entrypoint.sh"]
