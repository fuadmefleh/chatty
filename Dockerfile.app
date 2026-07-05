# Shared image for the chatty-bot and chatty-web-server services - they run
# the same codebase/venv today under pm2, just with different entrypoints
# (see docker-compose.yml's `command:` override per service).
FROM python:3.12-slim

ARG INSTALL_FACE_RECOGNITION=true

# git            - self_upgrade_manager.py runs `git worktree`/`commit`/merge
#                  against a live checkout; this fails hard without it.
# tesseract-ocr  - pytesseract's runtime binary.
# poppler-utils  - pdf2image's pdftoppm/pdfinfo binaries.
# ffmpeg         - chatty_web_server.py shells out to it directly for
#                  audio/video re-encoding.
# curl/ca-certificates/gnupg + NodeSource setup - Node.js 22, matching the
#                  ~/.nvm/versions/node/v22.12.0 version skills/pi_agent and
#                  skills/opencode hardcode as their default binary path.
# procps         - real `ps`, useful for the pi_agent/opencode subprocess
#                  runners and general debugging.
RUN apt-get update && apt-get install -y --no-install-recommends \
      git \
      curl \
      ca-certificates \
      gnupg \
      tesseract-ocr \
      poppler-utils \
      ffmpeg \
      procps \
    && if [ "$INSTALL_FACE_RECOGNITION" = "true" ]; then \
         apt-get install -y --no-install-recommends \
           build-essential cmake libopenblas-dev liblapack-dev libx11-dev; \
       fi \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && npm install -g opencode-ai \
    && rm -rf /var/lib/apt/lists/*

# Extension point for the `pi` coding-agent CLI (https://pi.dev/), which has
# no public install package - a deployer who has access to it can mount their
# own binary at ./docker/pi-bin (see docker-compose.yml) and it'll be found
# on PATH. If nothing is mounted there, skills/pi_agent/runner.py already
# handles a missing binary gracefully (surfaces "Pi binary not found" through
# the dashboard rather than crashing).
ENV PATH="/opt/pi-bin:${PATH}"
RUN mkdir -p /opt/pi-bin

WORKDIR /app

COPY requirements.txt requirements-face.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && if [ "$INSTALL_FACE_RECOGNITION" = "true" ]; then \
         pip install --no-cache-dir -r requirements-face.txt; \
       fi

# No further COPY here - source arrives via a bind mount at runtime (see
# docker-compose.yml). Both chatty-bot's self-upgrade pipeline and
# order-explorer-backend's SQLite path resolution depend on the container
# seeing a live, full copy of the repo at the same relative layout as on
# disk, not a baked-in snapshot.
