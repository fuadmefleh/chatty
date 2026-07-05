"""Polls restart_requests/ for signal files written by
src.managers.self_upgrade_manager._restart_services() and restarts the named
containers via the Docker socket.

This is the only container in the compose stack with /var/run/docker.sock
mounted. It intentionally never executes AI-modifiable code (no pi/opencode,
no bind-mounted repo source) - its only inputs are JSON files it moves after
reading, so a compromised chatty-bot/chatty-web-server process can only ask
it to restart one of a few known containers, not run arbitrary commands.
"""
import glob
import json
import os
import time

import docker

WATCH_DIR = "/restart_requests"
PROCESSED_DIR = os.path.join(WATCH_DIR, "processed")
POLL_SECONDS = 2

# pm2-era app name -> actual compose container_name. Currently 1:1 by design
# (docker-compose.yml sets container_name: to match these exactly) but kept
# as an explicit map so renaming a container later doesn't require touching
# src/managers/self_upgrade_manager.py.
ALIASES = {
    "chatty-bot": "chatty-bot",
    "chatty-web-server": "chatty-web-server",
    "order-explorer-backend": "order-explorer-backend",
    "order-explorer-frontend": "order-explorer-frontend",
}


def _process_request(client: docker.DockerClient, path: str) -> None:
    try:
        with open(path) as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"[restarter] could not read {path}: {e}")
        return

    for name in data.get("services", []):
        container_name = ALIASES.get(name, name)
        try:
            client.containers.get(container_name).restart(timeout=10)
            print(f"[restarter] restarted {container_name}")
        except docker.errors.NotFound:
            print(f"[restarter] skip: container {container_name!r} not running (optional profile?)")
        except docker.errors.APIError as e:
            print(f"[restarter] docker API error restarting {container_name!r}: {e}")


def main() -> None:
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    client = docker.from_env()
    print("[restarter] watching", WATCH_DIR)

    while True:
        for path in sorted(glob.glob(os.path.join(WATCH_DIR, "*.json"))):
            _process_request(client, path)
            os.rename(path, os.path.join(PROCESSED_DIR, os.path.basename(path)))
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
