# Comprehensive Logging System

## Overview
The bot now has an extensive logging system with separate log files for different components, making it easy to review and refine specific aspects of the bot's behavior.

## Log Files

All log files are located in `/home/edgeworks-server/chatty/logs/` with automatic rotation (10MB max, 5 backups).

### 1. **bot_main.log**
- **Purpose**: Main bot operations, initialization, and general flow
- **Level**: INFO
- **Contains**: 
  - Bot startup/shutdown
  - User authentication
  - Command handling
  - General operational messages

### 2. **agent.log**
- **Purpose**: ReACT agent reasoning and decision-making
- **Level**: DEBUG (most detailed)
- **Contains**:
  - ReACT loop iterations
  - Tool call decisions
  - Agent reasoning steps
  - Memory loading
  - Final answers

### 3. **tools.log**
- **Purpose**: Tool execution and results
- **Level**: DEBUG
- **Contains**:
  - Tool registration
  - Tool execution starts
  - Tool parameters
  - Execution results
  - Tool errors

### 4. **memory.log**
- **Purpose**: Memory operations (reading/writing)
- **Level**: DEBUG
- **Contains**:
  - Memory file creation
  - Interaction saves
  - Memory retrieval
  - File sizes and statistics
  - Memory consolidation

### 5. **reminders.log**
- **Purpose**: Reminder management
- **Level**: DEBUG
- **Contains**:
  - Reminder creation
  - Reminder checks
  - Reminder delivery
  - Reminder errors

### 6. **heartbeat.log**
- **Purpose**: Autonomous heartbeat operations
- **Level**: DEBUG
- **Contains**:
  - Heartbeat cycles
  - Autonomous checks
  - Memory consolidation triggers
  - Walmart order checks

### 7. **api.log**
- **Purpose**: External API calls
- **Level**: DEBUG
- **Contains**:
  - OpenAI API calls
  - Token usage statistics
  - API parameters
  - API responses
  - API errors

### 8. **skills.log**
- **Purpose**: Skills loading and execution
- **Level**: DEBUG
- **Contains**:
  - Skill discovery
  - Skill loading
  - Skill tool loading
  - Skill errors

### 9. **interactions.log**
- **Purpose**: User interactions (conversations)
- **Level**: INFO
- **Contains**:
  - User messages
  - Bot responses
  - Photo uploads
  - Conversation flow

### 10. **errors.log**
- **Purpose**: Errors from all components
- **Level**: ERROR only
- **Contains**:
  - All errors with full stack traces
  - Critical failures
  - Exception details

### 11. **debug.log**
- **Purpose**: Verbose debugging from all components
- **Level**: DEBUG
- **Contains**:
  - Everything at DEBUG level
  - No console output (file only)

## Usage

### Importing Loggers
```python
from src.core.logging_config import (
    get_main_logger,
    get_agent_logger,
    get_tools_logger,
    get_memory_logger,
    get_reminders_logger,
    get_heartbeat_logger,
    get_api_logger,
    get_skills_logger,
    get_interactions_logger,
    get_error_logger,
    get_debug_logger
)

# Use the appropriate logger
logger = get_main_logger()
logger.info("Main operation")

agent_logger = get_agent_logger()
agent_logger.debug("Agent reasoning step")
```

### Logging Levels
- **DEBUG**: Detailed information for debugging
- **INFO**: General informational messages
- **WARNING**: Warning messages
- **ERROR**: Error messages with stack traces

## Benefits

1. **Easy Debugging**: Find issues quickly in the relevant log file
2. **Performance Analysis**: Track API usage and response times
3. **User Behavior**: Review interactions to understand usage patterns
4. **System Health**: Monitor heartbeat and autonomous operations
5. **Memory Operations**: Track memory growth and consolidation
6. **Tool Usage**: See which tools are being called and how often

## Best Practices

1. **Use appropriate logger**: Choose the logger that matches your component
2. **Log at correct level**: 
   - DEBUG for detailed flow
   - INFO for important events
   - WARNING for recoverable issues
   - ERROR for failures
3. **Include context**: Add user IDs, file names, and relevant data
4. **Log results**: Include result sizes and success/failure status
5. **Use exc_info=True**: For ERROR level logs with exceptions

## Example Patterns

### Agent Operation
```python
agent_logger.info(f"Starting ReACT loop for user {user_id}")
agent_logger.debug(f"Loaded {len(tools)} tools")
agent_logger.info(f"Tool call: {function_name}({args})")
agent_logger.info(f"Final answer: {response[:200]}...")
```

### Memory Operation
```python
memory_logger.info(f"Saving interaction for user {user_id}")
memory_logger.debug(f"Memory file: {file_path}")
memory_logger.info(f"Saved: user_msg={len(msg)} chars, assistant_msg={len(resp)} chars")
```

### API Call
```python
api_logger.debug(f"OpenAI API call: model={model}, messages={len(msgs)}")
api_logger.info(f"Token usage - Prompt: {prompt_tokens}, Completion: {completion_tokens}")
```

### Tool Execution
```python
tools_logger.info(f"Executing tool: {tool_name}")
tools_logger.debug(f"Arguments: {args}")
tools_logger.info(f"Result: {len(result)} chars")
```

## Monitoring

To monitor logs in real-time:

```bash
# Watch all errors
tail -f logs/errors.log

# Watch agent reasoning
tail -f logs/agent.log

# Watch user interactions
tail -f logs/interactions.log

# Watch everything
tail -f logs/debug.log
```

To search logs:
```bash
# Find all mentions of a tool
grep "search_memory" logs/tools.log

# Find API token usage
grep "Token usage" logs/api.log

# Find errors for a specific user
grep "user 1234567890" logs/errors.log
```
