# Project Structure

This document describes the organization of the Chatty bot project.

## Directory Layout

```
chatty/
├── src/                    # Main application source code
│   ├── agents/            # AI agent implementations
│   ├── core/              # Core functionality (config, memory, skills)
│   ├── managers/          # Manager classes (heartbeat, reminders)
│   └── main.py           # Application entry point
├── tests/                 # Test files
├── docs/                  # Documentation
├── skills/                # Agent skill definitions (markdown)
├── memory/                # User memory storage (auto-created)
├── reminders/             # User reminders (auto-created)
├── logs/                  # Application logs (auto-created)
└── venv/                  # Python virtual environment

```

## Module Organization

### src/agents/
Contains AI agent implementations:
- `react_agent.py` - ReACT (Reasoning and Acting) agent with OpenAI function calling

### src/core/
Core business logic modules:
- `config.py` - Configuration management and environment variables
- `memory.py` - Memory system with daily markdown files
- `memory_tools.py` - Memory search and retrieval functionality
- `skills.py` - Skills system for loading agent capabilities

### src/managers/
Manager classes for background tasks:
- `heartbeat_manager.py` - Autonomous periodic checks and actions
- `reminder_manager.py` - Reminder and alarm management system

### src/main.py
Main application entry point - Telegram bot setup and handlers

## Running the Application

```bash
# From the project root
python -m src.main
```

## Testing

```bash
# Run tests
python -m pytest tests/

# Run specific test
python tests/test_memory_tools.py
```

## Import Structure

All modules use absolute imports from the `src` package:

```python
from src.core import config
from src.core.memory import MemoryManager
from src.agents.react_agent import ReACTAgent
from src.managers.reminder_manager import ReminderManager
```

## Adding New Modules

1. Create module in appropriate subdirectory
2. Add to `__init__.py` if it should be exported
3. Update tests in `tests/` directory
4. Update documentation in `docs/`
