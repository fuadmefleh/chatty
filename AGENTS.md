# Atlas Bot - AI Telegram Assistant

## Project Overview

This is a Python Telegram bot with a staged ReACT (Reasoning and Acting) agent architecture. Users interact via Telegram, the bot uses OpenAI function calling with dynamically loaded skills.

## Tech Stack

- **Python 3.12** with asyncio
- **python-telegram-bot v20+** for Telegram integration
- **OpenAI API** with function calling for the agent
- **pm2** for process management
- **Virtual environment** at `venv/`

## Project Structure

```
src/                    # Framework code only
  agents/               # Staged ReACT agent (7 stages)
  core/                 # Config, memory, skills_manager, skill_tool base class
  managers/             # Heartbeat and reminder managers
  main.py               # Entry point, Telegram handlers, /code command
  tools/                # Core memory tools (always loaded)
skills/                 # All skill implementations (auto-discovered)
  <skill_name>/         # Each skill is a folder
    <skill_name>.md     # Skill description (required)
    tools.py            # SkillTool classes (optional)
    *.py                # Implementation files
tests/                  # Test files
memory/                 # User memory storage (per user_id)
docs/                   # Documentation
```

## Key Conventions

### Adding a New Skill

1. Create folder: `skills/<skill_name>/`
2. Create `skills/<skill_name>/<skill_name>.md` with Description, Usage, Examples sections
3. Create `skills/<skill_name>/tools.py` with classes inheriting from `SkillTool`
4. Tools are auto-discovered by `skills_manager.py` — no registration needed

### Skill Markdown Format

```markdown
# Skill Name

## Description
What the skill does.

## Usage
When to use this skill.

## Examples
- Example user queries
```

### SkillTool Class Pattern

```python
from src.core.skill_tool import SkillTool
import json

class MyTool(SkillTool):
    name = "unique_tool_name"
    description = "What this tool does (for LLM)"
    parameters = {
        "type": "object",
        "properties": {
            "param_name": {
                "type": "string",
                "description": "Param description"
            }
        },
        "required": ["param_name"]
    }

    async def execute(self, param_name: str) -> str:
        result = {"success": True, "data": "..."}
        return json.dumps(result)
```

### Import Pattern

All imports use absolute paths from `src`:
```python
from src.core import config
from src.core.skill_tool import SkillTool
from src.core.memory import MemoryManager
```

Skills load implementation modules dynamically:
```python
_api_path = Path(__file__).parent / "my_api.py"
_spec = importlib.util.spec_from_file_location("my_api_module", _api_path)
_my_api = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_my_api)
```

## Build & Run Commands

```bash
# Activate venv
source venv/bin/activate

# Start services
pm2 start chatty-bot
pm2 start chatty-mini-apps

# Restart after changes
pm2 restart chatty-bot

# View logs
pm2 logs chatty-bot --lines 50
tail -f logs/pm2-error.log

# Run tests
python -m pytest tests/
python -m pytest tests/test_memory_tools.py -v
```

## pm2 Services

- **chatty-bot** (id:1) — Main Telegram bot (`src/main.py`)
- **chatty-mini-apps** (id:16) — Mini app server (`mini_app_server.py`)
- **chatty-web-server** (id:15) — FastAPI backend for the web dashboard
  (`chatty_web_server.py`, port 8016)
- **order-explorer-frontend** (id:19) — React dashboard
  (`order_explorer_site/frontend`). Runs `vite preview` against the
  committed `dist/` build, **not** the vite dev server — editing files
  under `src/` has no effect until you rebuild:
  ```bash
  cd order_explorer_site/frontend && npm run build
  pm2 restart order-explorer-frontend
  ```
  A plain `pm2 restart` alone just re-serves the stale build.

## Important Files

- `src/core/config.py` — All env vars and paths
- `src/core/skills_manager.py` — Skill auto-discovery and loading
- `src/core/skill_tool.py` — Base class for all skill tools
- `src/agents/staged_react_agent.py` — 7-stage ReACT agent
- `ecosystem.config.js` — pm2 process definitions
- `opencode.json` — OpenCode CLI configuration
- `data/authorized_users.json` — Allowed Telegram user IDs

## Testing

- Always run tests after modifying skills or core code
- Test files go in `tests/` with `test_` prefix
- Use `python -m pytest` from project root (pytest-asyncio is in `auto` mode
  via `pyproject.toml` - async `test_*` functions don't need an explicit
  `@pytest.mark.asyncio`)
- If you change a non-test source file, add or update a test alongside it -
  enforced for the self-upgrade pipeline (see Guardrails below), and good
  practice for manual changes too

## Guardrails

A git pre-commit hook (`.githooks/pre-commit`, enabled via
`git config core.hooksPath .githooks`) runs on every commit to this repo -
human or the self-upgrade pipeline (`src/managers/self_upgrade_manager.py`):
- `ruff check --select E9,F` on staged Python files (real correctness bugs -
  undefined names, use-before-assignment, syntax errors, unused
  imports/vars - not style)
- the full test suite (`pytest tests/`)
- `eslint` on staged frontend files

If a commit is rejected, fix the issue and try again - do not bypass with
`--no-verify` unless you have a specific, understood reason to. The
self-upgrade pipeline treats a hook rejection the same as a failing test: it
feeds the output back to the coding agent for a fix attempt (up to
`SELF_UPGRADE_MAX_TEST_ATTEMPTS`) before giving up and leaving the branch
for manual review.

## After Making Changes

Always restart the affected pm2 service:
```bash
pm2 restart chatty-bot
```
