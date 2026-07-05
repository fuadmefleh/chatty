# Tiny sidecar - deliberately the ONLY container in the whole compose file
# with the Docker socket mounted (see docker-compose.yml). Uses the `docker`
# Python SDK to talk to the socket's HTTP API directly, so no Docker
# CLI/engine package is needed in the image.
FROM python:3.12-alpine

# Without this, print() output sits in Python's fully-buffered stdout (the
# default when stdout isn't a TTY, as PID 1 in a container never is) and
# never reaches `docker compose logs` - confirmed while testing this image,
# where restart activity was invisible despite the restarts happening.
ENV PYTHONUNBUFFERED=1

RUN pip install --no-cache-dir docker==7.*

COPY restart_watcher.py /app/restart_watcher.py

CMD ["python", "/app/restart_watcher.py"]
