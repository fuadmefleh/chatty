# Easy self-hosting on DigitalOcean

**Status:** approved, not yet implemented
**Date:** 2026-07-21

## Goal

Let a stranger go from a fresh DigitalOcean droplet to a working, HTTPS-secured
Chatty instance with one command, without reading the source to figure out which
of the ~60 environment variables actually matter.

Chatty already has a competent `docker-compose.yml` — six services, nginx
routing, healthcheck-gated startup. The gap is not orchestration. It is that the
documented happy path produces an **insecure** instance, and that several
defaults point at services a fresh droplet does not run.

## Non-goals

- **Multi-tenancy.** Chatty is single-user by design (`WEB_USER_ID` is one global
  string; there is no user table). Nothing here changes that.
- **DigitalOcean App Platform.** Architecturally incompatible: self-upgrade needs
  a live bind-mounted git repo, the restarter sidecar needs the Docker socket,
  and SQLite needs a persistent disk. A plain Droplet is the target.
- **DO Marketplace 1-Click.** Deferred, not rejected. It requires a Packer build
  validated by `cleanup.sh`/`img_check.sh` (no root password, no root SSH keys,
  cleared bash history, active ufw), a first-boot script in
  `/var/lib/cloud/scripts/per-instance`, a `99`-prefixed MOTD, and a partner
  review cycle. The bootstrap script specified here is most of that image's
  payload, so this work is a prerequisite rather than a detour.

## Phasing

**Phase 1 (security fixes) is independently landable and should ship first.** It
is a self-contained bugfix set that does not depend on any bootstrap work. Phases
2–4 build the deployment experience on top.

---

## Phase 1 — Security and default-value fixes

These are live bugs today, independent of any deployment story.

### 1.1 Telegram authorization fails open

`src/main.py:1453`:

```python
if phone_number.endswith(allowed_number) or allowed_number.endswith(phone_number):
```

`ALLOWED_PHONE_NUMBER` defaults to `""` (`src/core/config.py:74`). Both clauses
are true against an empty string, so **any Telegram user who shares a contact is
authorized**. The second clause is independently wrong: it lets a shorter stored
number match a longer supplied one.

Fix: refuse all authorization when `ALLOWED_PHONE_NUMBER` is unset, and compare
full normalized numbers rather than suffixes.

### 1.2 Web dashboard ships a known API key

`src/web/config.py:16` reads `os.getenv("CHATTY_WEB_API_KEY", "changeme")`, and
`.env.example` ships the var blank. Compose publishes nginx on `0.0.0.0:80`
(`docker-compose.yml:129`). Following the README verbatim therefore yields a
publicly reachable dashboard whose key is the literal string `changeme`.

Fix: remove the default. Unset means the web server refuses to start with a clear
error. Failing to boot is strictly better than booting compromised.

The surrounding auth implementation is sound and stays as-is: `src/web/auth.py`
uses `hmac.compare_digest` with per-IP brute-force lockout.

### 1.3 `validate_config()` demands the wrong key

`src/core/config.py:207-218` hard-requires `OPENAI_API_KEY` **and**
`TELEGRAM_BOT_TOKEN`, contradicting `.env.example`, which advertises Anthropic as
a supported provider. Setting `CHAT_PROVIDER=anthropic` still fails validation
without an OpenAI key.

Fix: require the key matching the selected `CHAT_PROVIDER`. Make
`TELEGRAM_BOT_TOKEN` optional — when absent, the bot process logs
"no Telegram token, dashboard-only mode" and **exits 0** rather than raising,
which would otherwise crash-loop forever under compose's restart policy.

### 1.4 Defaults pointing at absent services

- `STT_PROVIDER` defaults to `whisperx_http` → `127.0.0.1:8003`, which is behind
  an optional profile and is explicitly a scaffold (`docker/whisperx/Dockerfile:1`).
- `TTS_PROVIDER` defaults to `local` → `127.0.0.1:8002`, a microservice not in
  this repo at all.
- The SearXNG default is `localhost:8081` but the bundled service publishes
  `8090` — the default does not match the shipped service.

Fix, in two parts so Phase 1 stands alone:

- **Phase 1 (code default):** both `STT_PROVIDER` and `TTS_PROVIDER` default to
  `off`. A fresh install with no audio configuration then does nothing, rather
  than timing out against a port with no listener. Existing `.env` files are
  unaffected — they set these explicitly.
- **Phase 2 (wizard):** the bootstrap writes an explicit value, choosing the
  provider whose key the user just supplied (e.g. `openai` when they gave an
  OpenAI key), else leaving `off`.

Also correct the SearXNG default port from `8081` to the `8090` the bundled
service actually publishes.

### 1.5 Face recognition default

`docker-compose.yml:23,47` sets `INSTALL_FACE_RECOGNITION` to `true` by default,
compiling dlib from source. This is the single largest first-build cost and will
OOM a 1GB droplet. Flip to `false`; keep it a documented opt-in.

---

## Phase 2 — `scripts/bootstrap.sh`

An interactive wizard taking a fresh droplet to a running instance.

### Flow

Preflight → prompt → generate → firewall → bring up → verify → report.

**Preflight:** root/sudo check, OS check (Ubuntu/Debian), warn if RAM < 2GB,
install Docker if absent.

**Prompts:**

| Prompt | Blank means |
|---|---|
| Domain | local-only mode, no TLS |
| LLM provider (anthropic/openai/local) | — (required) |
| Provider API key | — (required) |
| Telegram bot token | skip Telegram, dashboard-only |
| Phone number | only asked if a token was supplied |

**Generated, never prompted:** `CHATTY_WEB_API_KEY` and
`WHATSAPP_BRIDGE_SECRET`, each `openssl rand -hex 32`. Written to `.env` at mode
`600`. The API key is echoed exactly once, in the final summary.

**Idempotence:** an existing `.env` triggers a keep-or-reconfigure prompt. Secrets
are never silently overwritten.

### Testability

The script takes two flags that make it exercisable without a droplet:

- `--non-interactive` — answers supplied via environment variables.
- `--dry-run` — writes `.env` to a temp dir; skips Docker and ufw entirely.

`tests/test_bootstrap.py` drives it as a subprocess and asserts on the generated
`.env`:

- `CHATTY_WEB_API_KEY` is 64 hex characters
- `.env` mode is `600`
- omitting the Telegram token omits the var rather than writing it empty
- no generated secret appears on stdout except in the final summary block
- re-running against an existing `.env` preserves the original secrets

`shellcheck` is added to the pre-commit hook for staged `.sh` files.

### Error handling

`set -euo pipefail` throughout. Preflight failures abort before any file is
written. **If TLS certificate issuance fails, the script falls back to
localhost-only binding** rather than leaving a plaintext dashboard on `0.0.0.0`
— the failure mode must never be "insecure but working".

---

## Phase 3 — TLS via Caddy

A `caddy` service under a `tls` compose profile terminates TLS and reverse-proxies
to the existing nginx.

Caddy sits **in front of** nginx rather than replacing it. nginx's routing
(`/api/explorer/` → 8015, `/api/chatty/` → 8016 with WebSocket upgrade, `/` →
frontend) is untouched, so there is no duplicated route logic to drift. The
Caddyfile is roughly six lines and Caddy handles Let's Encrypt issuance and
renewal itself.

Port binding becomes env-driven so the default is safe:

```yaml
ports: ["${HTTP_BIND:-127.0.0.1}:${HTTP_PORT:-80}:80"]
```

- **Domain supplied:** Caddy publishes 80/443; nginx stays internal; ufw allows
  22/80/443.
- **No domain:** nginx binds `127.0.0.1`; ufw allows 22 only; the script prints
  the SSH tunnel command.

---

## Phase 4 — whatsapp-bridge containerization and docs

### Containerization

`whatsapp-bridge` is absent from `docker-compose.yml` entirely, despite being a
first-class app in `ecosystem.config.js:78-89`. Worse,
`whatsapp-bridge/index.js:280` binds `127.0.0.1`, which inside a container is the
container's own loopback — so `WHATSAPP_BRIDGE_URL=http://127.0.0.1:8017` from
`chatty-bot` can never reach it. **WhatsApp is silently dead under Docker today.**

Fix: add the service to compose on the internal network. `index.js` gains a
`WHATSAPP_BRIDGE_HOST` env var defaulting to `127.0.0.1` — bare-metal behavior is
unchanged — which the container sets to `0.0.0.0`. The service is **not**
published; it is reachable only on the Docker network and still gated by
`WHATSAPP_BRIDGE_SECRET`. Auth state lives on a named volume so rebuilds do not
force a QR re-scan.

Also add the `whatsapp-bridge/README.md` that `.env.example:38` already
references but which does not exist.

### `docs/DEPLOY.md`

Droplet sizing (2GB/2vCPU baseline; 4GB if enabling face recognition), the
install command, DNS setup, post-install steps for integrations that cannot
complete over SSH (Gmail OAuth, LinkedIn cookies — both need the dashboard),
backup/restore of `data/`, and the upgrade procedure.

**On `curl | sudo bash`:** the README leads with the download-inspect-run form.
The piped one-liner is documented as a convenience, not the headline. Piping a
remote script into a root shell is a genuine supply-chain risk and the docs
should not normalize it.

---

## Out of scope

`ecosystem.config.js` hardcodes `/home/edgeworks-server/chatty` in twelve places,
and `self_upgrade_manager.py:86`, `skills/pi_agent/runner.py:24`, and
`skills/opencode/runner.py:17` hardcode an exact nvm Node path
(`~/.nvm/versions/node/v22.12.0/bin/...`). These break the **pm2/bare-metal**
path for anyone but the author. The Docker path is unaffected — `Dockerfile.app`
installs Node 22 to that same path deliberately.

Since this spec targets Docker deployment, these are left alone. They should be
fixed before anyone is told to self-host bare-metal.

Similarly untouched: `skills/gmail/gmail_integration.py:46` defaults the OAuth
redirect to the author's personal domain. It is overridable via
`GMAIL_OAUTH_REDIRECT_URI`, but that variable is undocumented — `DEPLOY.md` will
document it in the Gmail post-install section.
