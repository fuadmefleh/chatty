# Chatty - LLM-Based Companion AI

An intelligent Telegram bot companion powered by OpenAI's GPT models, featuring memory persistence, ReACT (Reasoning and Acting) pattern, and extensible skills system.

## Features

🧠 **Memory System** - Stores conversations in daily markdown files for each user
🔄 **ReACT Loop** - Implements Reasoning and Acting pattern for complex problem solving
🔧 **Skills System** - Extensible agent capabilities defined in markdown files
💬 **Telegram Integration** - Chat naturally through Telegram
🤖 **OpenAI Powered** - Uses GPT-4 or other OpenAI models

## Project Structure

```
chatty/
├── src/                     # Main source code
│   ├── __init__.py
│   ├── main.py             # Telegram bot main application
│   ├── agents/             # AI agent implementations
│   │   ├── __init__.py
│   │   └── react_agent.py  # ReACT agent with function calling
│   ├── core/               # Core functionality modules
│   │   ├── __init__.py
│   │   ├── config.py       # Configuration management
│   │   ├── memory.py       # Memory system (daily markdown files)
│   │   ├── memory_tools.py # Memory search and retrieval tools
│   │   └── skills.py       # Skills loading and management
│   └── managers/           # Manager modules
│       ├── __init__.py
│       ├── heartbeat_manager.py  # Autonomous periodic tasks
│       └── reminder_manager.py   # Reminder and alarm system
├── tests/                  # Test files
│   ├── __init__.py
│   └── test_memory_tools.py
├── docs/                   # Documentation
│   ├── README.md
│   ├── MEMORY_SYSTEM.md
│   ├── MEMORY_TOOLS.md
│   └── heartbeat.md
├── skills/                 # Agent skills (markdown files)
│   ├── web_search.md
│   ├── calculate.md
│   ├── remember.md
│   ├── code_review.md
│   └── explain.md
├── memory/                 # User conversation memories (auto-created)
│   └── [user_id]/
│       ├── short_term/
│       │   └── 2026-01-30.md
│       └── long_term/
│           ├── important_facts.md
│           ├── relationships.md
│           └── ...
├── reminders/              # User reminders (auto-created)
├── logs/                   # Application logs (auto-created)
├── requirements.txt        # Python dependencies
├── .env.example           # Environment variables template
└── .gitignore             # Git ignore rules
```

## Setup

### 1. Prerequisites

- Python 3.8 or higher
- OpenAI API key
- Telegram Bot Token (from [@BotFather](https://t.me/botfather))

### 2. Installation

```bash
# Clone or navigate to the project directory
cd chatty

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Linux/Mac:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration

Create a `.env` file based on `.env.example`:

```bash
cp .env.example .env
```

Edit `.env` and add your API keys:

```env
# OpenAI Configuration
OPENAI_API_KEY=sk-your-openai-api-key-here
OPENAI_MODEL=gpt-4-turbo-preview

# Telegram Configuration
TELEGRAM_BOT_TOKEN=your-telegram-bot-token-here

# Memory Configuration
MEMORY_DIR=memory
MAX_MEMORY_TOKENS=4000

# Agent Configuration
SKILLS_DIR=skills
MAX_ITERATIONS=5
TEMPERATURE=0.7
```

### 4. Get Your API Keys

**OpenAI API Key:**
1. Go to [OpenAI Platform](https://platform.openai.com/)
2. Sign up or log in
3. Navigate to API Keys section
4. Create a new API key

**Telegram Bot Token:**
1. Open Telegram and search for [@BotFather](https://t.me/botfather)
2. Send `/newbot` command
3. Follow instructions to create your bot
4. Copy the provided token

## Usage

### Starting the Bot

```bash
python -m src.main
```

You should see:
```
INFO - Initializing bot...
INFO - Loaded 5 skills
INFO - Starting bot...
```

### Talking to Your Bot

1. Open Telegram
2. Search for your bot by username
3. Start a conversation with `/start`

### Available Commands

- `/start` - Welcome message and introduction
- `/memory` - View your memory statistics
- `/skills` - List available skills
- `/clear` - Clear conversation context (keeps memory files)
- `/help` - Show help information

### Example Conversations

```
You: Hello! What's 15% of 250?
Bot: THOUGHT: User wants to calculate a percentage.
ACTION: Calculate 15% of 250
The answer is 37.5

You: Remember that I prefer Python for backend development
Bot: I'll remember that you prefer Python for backend development!

You: What did I just tell you to remember?
Bot: You mentioned that you prefer Python for backend development.
```

## Memory System

The bot maintains memory of conversations using markdown files:

- One file per day per user
- Stored in `memory/[user_id]/YYYY-MM-DD.md`
- Includes timestamps for each interaction
- Automatically loaded for context in conversations

### Memory File Example

```markdown
# Memory Log - 2026-01-30

## [14:23:15]

**User**: Hello! How are you?

**Assistant**: I'm doing great! How can I help you today?

---

## [14:25:30]

**User**: What's the weather like?

**Assistant**: I'd need to search for current weather information...

---
```

## Skills System

Skills are defined in markdown files in the `skills/` directory. Each skill file follows this format:

```markdown
# Skill Name

## Description
What the skill does

## Usage
How to use it

## Examples
- Example 1
- Example 2
```

### Adding New Skills

1. Create a new `.md` file in the `skills/` directory
2. Follow the format above
3. Restart the bot to load the new skill

The bot will automatically load all skills and include them in its system prompt.

## ReACT Pattern

The bot uses the ReACT (Reasoning and Acting) pattern:

1. **THOUGHT**: Thinks about what needs to be done
2. **ACTION**: Decides on an action or skill to use
3. **OBSERVATION**: Considers the results
4. **Repeat or Answer**: Continues thinking or provides final answer

For simple queries, the bot responds directly without the full ReACT loop.

## Customization

### Changing the Model

Edit `.env` to use different OpenAI models:

```env
OPENAI_MODEL=gpt-4-turbo-preview  # More capable, higher cost
OPENAI_MODEL=gpt-3.5-turbo        # Faster, lower cost
```

### Adjusting Memory

Control how much memory is loaded:

```env
MAX_MEMORY_TOKENS=4000  # Maximum tokens of memory to load
```

In `main.py`, the `get_recent_memory()` call controls days:

```python
memory = await self.memory_manager.get_recent_memory(days=3)  # Load last 3 days
```

### Modifying System Prompt

Edit the `SYSTEM_PROMPT` in [config.py](config.py) to change the bot's personality and behavior.

## Development

### Project Architecture

- **main.py**: Telegram bot handlers and application loop
- **config.py**: Configuration and environment variables
- **memory.py**: `MemoryManager` class for conversation persistence
- **skills.py**: `SkillsManager` and `Skill` classes for capability system
- **react_agent.py**: `ReACTAgent` class implementing the reasoning loop

### Adding Features

1. **New Commands**: Add handlers in `main.py`
2. **New Skills**: Create markdown files in `skills/`
3. **Enhanced Actions**: Modify `_execute_action()` in `react_agent.py`
4. **Memory Features**: Extend `MemoryManager` in `memory.py`

## Troubleshooting

### Bot doesn't respond
- Check your `.env` file has correct API keys
- Ensure the bot is running (`python -m src.main`)
- Verify internet connectivity

### "Configuration errors" on startup
- Make sure `.env` file exists
- Verify all required environment variables are set

### Memory not saving
- Check `memory/` directory exists and is writable
- Look for error messages in console

### Skills not loading
- Verify markdown files are in `skills/` directory
- Check file format follows the expected structure
- Look for parsing errors in console

## Security Notes

- Never commit `.env` file to version control
- Keep your API keys secret
- The bot has access to OpenAI API - monitor usage
- Memory files contain conversation history - store securely

## License

This project is open source. Customize and use as needed.

## Contributing

Feel free to:
- Add new skills
- Improve the ReACT implementation
- Enhance memory management
- Add new features

## Future Enhancements

Potential improvements:
- Web search integration
- Image generation capabilities
- Voice message support
- Multi-language support
- Vector database for semantic memory search
- Tool calling for actual skill execution
- User preferences system
- Scheduled reminders
- Group chat support

## Support

For issues or questions:
1. Check the troubleshooting section
2. Review the code comments
3. Check OpenAI and Telegram Bot API documentation

---

**Enjoy your AI companion!** 🤖✨
