# Chatty

A personal AI assistant built on a **Staged ReACT (Reasoning and Acting) agent** with dynamically loaded **skills**. It runs as a Telegram bot (and/or web chat) with persistent per-user memory, background "heartbeat" tasks, and pluggable integrations (Gmail, Amazon/Walmart order tracking, budgeting via Plaid/RocketMoney, notes, reminders, weather, web search, and more).

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for how the agent pipeline and skill system work, and [docs/heartbeat.md](docs/heartbeat.md) for the background task scheduler.

## Setup

1. **Install dependencies**
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Configure environment**
   ```bash
   cp .env.example .env
   # edit .env with your own API keys / tokens
   ```
   See `.env.example` for the full list of supported variables (OpenAI, Telegram, Gmail, Plaid, Google search, etc). Only the skills you actually use need their variables filled in.

3. **Per-skill credentials**
   Some skills need additional local credential files that are intentionally excluded from version control (see `.gitignore`):
   - `skills/gmail/credentials.json` — Google Cloud OAuth client, see `skills/gmail/gmail.md`
   - `data/` — local databases, OAuth tokens, and any personal data the skills generate at runtime live here and are never committed

4. **Run**
   ```bash
   ./start.sh
   ```

## Project layout

```
chatty/
├── src/              # Lean framework: agent loop, config, skill loader, managers
├── skills/           # Skill implementations (tools.py + a .md description per skill)
├── docs/             # Architecture and subsystem docs
├── scripts/          # One-off maintenance/import scripts
├── tests/            # Test suite
└── order_explorer_site/  # Optional standalone web UI for browsing order history
```

## Adding a new skill

See the "Creating a New Skill" section in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## License

MIT — see [LICENSE](LICENSE).
