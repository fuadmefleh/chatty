# Chatty Bot - AI Telegram Assistant

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
- Use `python -m pytest` from project root

## After Making Changes

Always restart the affected pm2 service:
```bash
pm2 restart chatty-bot
```
