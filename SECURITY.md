# Security Policy

Atlas is a personal AI assistant that integrates with sensitive accounts
and data (email, banking/Plaid, order history, messages, memory storage).
If you find a security vulnerability, please report it privately rather
than opening a public issue.

## Reporting a vulnerability

Email **fuad.mefleh@gmail.com** with:

- A description of the vulnerability and its potential impact
- Steps to reproduce, or a proof of concept if available
- Which component is affected (core agent, a specific skill, the web
  dashboard, etc.)

You should receive an acknowledgment within a few days. Please allow time
for a fix before any public disclosure.

## Scope notes

- Runtime secrets (`.env`, `skills/gmail/credentials.json`, OAuth tokens,
  anything under `data/` or `memory/`) are never committed to this repo —
  see `.gitignore`. If you find a leaked credential in the repository
  history, treat it as compromised and report it immediately.
- This project is intended to run under your own control with your own
  credentials; it is not designed for multi-tenant or public-facing
  deployment without additional hardening.

## Docker deployment: the `restarter` sidecar and the Docker socket

The self-upgrade feature (`src/managers/self_upgrade_manager.py`) lets Atlas
propose and merge code changes to itself, then needs to restart whichever
services were affected. Under Docker (see `docker-compose.yml`), this is
handled by a small `restarter` sidecar container that is **the only
container in the whole stack with `/var/run/docker.sock` mounted** —
effectively root-on-host access.

This is a deliberate, contained design, not an oversight:
- `chatty-bot`/`chatty-web-server` (the containers that run AI-modified
  code) never touch the socket. They only write a small JSON file naming
  which services need restarting (see `_restart_services()` and
  `docker/restarter/restart_watcher.py`).
- The sidecar's only inputs are those already-written JSON files; it never
  executes `pi`/`opencode` and never sees the bind-mounted repo source. A
  compromised bot/web-server process can therefore only ask it to restart
  one of a handful of known containers — not run arbitrary Docker/host
  commands.

If you're deploying in an environment where you'd rather not grant any
container Docker-socket access, disable the self-upgrade feature (leave the
worktrees/restart-signal machinery unused) rather than removing this
isolation — routing the socket into `chatty-bot`/`chatty-web-server`
directly would meaningfully widen the blast radius of a bad self-upgrade
merge.
