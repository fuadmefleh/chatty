# OpenCode Integration

Send messages to your Chatty bot on Telegram, and they get routed to the OpenCode AI coding agent. Progress is streamed back to you in real-time on Telegram.

> **Note**: This replaces the previous VS Code extension bridge. OpenCode runs as a direct subprocess — no extension, no polling, no queue files.

---

## How It Works

```
┌──────────────┐     /code "add weather skill"     ┌──────────────┐
│   Telegram   │ ─────────────────────────────────► │  Chatty Bot  │
│   (you)      │                                    │  (src/main)  │
└──────┬───────┘                                    └──────┬───────┘
       │                                                   │
       │  ◄── real-time updates ──                         │ spawns
       │                                                   ▼
       │                                            ┌──────────────┐
       │                                            │  opencode    │
       │◄─── stdout JSON events ────────────────────│  run         │
       │                                            │  (subprocess)│
       │                                            └──────┬───────┘
       │                                                   │
       │                                                   │ uses
       │                                                   ▼
       │                                            ┌──────────────┐
       │                                            │  GitHub      │
       │                                            │  Copilot     │
       │                                            │  (provider)  │
       └                                            └──────────────┘
```

### Step by Step

1. **You send** `/code Add a weather skill` on Telegram.
2. **Chatty bot** spawns `opencode run "Add a weather skill" --format json` as an async subprocess.
3. **OpenCode** creates a session, analyzes the codebase, and starts making changes.
4. **stdout JSON events** are parsed line-by-line by the bot's async runner.
5. Events are categorized (file changes, tool calls, progress) and **sent to Telegram** in real-time.
6. When the process exits, a **completion or error message** is sent.

---

## Components

### 1. OpenCode Runner (`skills/opencode/runner.py`)

Async generator that spawns `opencode run` and yields parsed events:

```python
async for event in run_opencode("Add a weather skill"):
    print(event)
    # {"type": "started", "content": "Launching OpenCode agent..."}
    # {"type": "file_change", "content": "Writing: skills/weather/tools.py"}
    # {"type": "tool_call", "content": "Running: python -m pytest"}
    # {"type": "completed", "content": "OpenCode finished successfully."}
```

### 2. Code Command Handler (`src/main.py`)

The `/code` command:
- Checks if OpenCode is already running (only one at a time)
- Spawns the runner as a background asyncio task
- Streams each event to the user on Telegram

### 3. Chatty Skill Tools (`skills/opencode/tools.py`)

Two tools the ReACT agent can use:
- **`run_opencode`** — Launch the OpenCode agent
- **`check_opencode_status`** — Check if OpenCode is currently running

### 4. Config (`opencode.json`)

Project-level OpenCode configuration:
```json
{
  "$schema": "https://opencode.ai/config.json",
  "model": "copilot/claude-sonnet-4",
  "permission": {
    "*": "grant",
    "bash": "grant",
    "write": "grant",
    "edit": "grant"
  },
  "snapshot": false,
  "autoupdate": false,
  "share": "disabled"
}
```

### 5. Mini App Server API (`mini_app_server.py`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/opencode/status` | Check if OpenCode is running |
| POST | `/api/opencode/restart` | Restart services via pm2 |

---

## What You See on Telegram

When you send `/code add error handling to the weather skill`:

```
🚀 Launching OpenCode agent...

Request: add error handling to the weather skill
```

Then, as the agent works:

```
💭 Analyzing the codebase...

🔧 Reading: skills/weather/tools.py

💾 Editing: skills/weather/tools.py

🔧 Reading: tests/test_weather.py

💾 Writing: tests/test_weather.py

🔧 Running: python -m pytest tests/test_weather.py

✅ OpenCode finished successfully.
```

---

## Event Types

| Type | Icon | Meaning |
|------|------|---------|
| `started` | 🚀 | OpenCode process launched |
| `progress` | 💭 | Agent thinking / text output |
| `tool_call` | 🔧 | Running a tool (bash, read, search) |
| `file_change` | 💾 | Writing or editing a file |
| `completed` | ✅ | Agent finished successfully |
| `error` | ❌ | Something went wrong |

---

## Setup

### First-time setup

1. Install OpenCode: `npm install -g opencode-ai@latest`
2. Authenticate with GitHub Copilot: `opencode auth login` → select GitHub Copilot → follow device auth flow
3. Verify: `opencode auth list` should show copilot credentials

### Running

1. Start the mini app server: `pm2 start chatty-mini-apps`
2. Start the Chatty bot: `pm2 start chatty-bot`
3. Send `/code your request here` on Telegram

---

## Architecture Advantages vs. Old VS Code Bridge

| Aspect | Old (VS Code Extension) | New (OpenCode) |
|--------|------------------------|----------------|
| Dependencies | VS Code + extension + queue file | Just `opencode` CLI binary |
| Latency | 3-5s polling delay | Near-instant subprocess pipe |
| Complexity | 5 components (queue, API, extension, monitor, tools) | 2 components (runner, command handler) |
| Auth | N/A (used VS Code's Copilot login) | `opencode auth login` (one-time) |
| Model access | Whatever VS Code Copilot provided | Any model via Copilot or other providers |
| Headless | Required VS Code GUI running | Fully headless CLI |

---

*Last Updated: July 2025*
