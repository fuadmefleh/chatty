# Memory System Overview

This document provides a comprehensive overview of the dual-tier memory system used in the Chatty application.

## Architecture

The memory system implements a **dual-tier architecture** that manages conversational context and persistent knowledge across time, ensuring both immediate context and long-term understanding.

---

## Two Memory Types

### 1. Short-Term Memory

**Location**: `memory/{user_id}/short_term/`

**Characteristics**:
- Daily conversation logs stored as markdown files (e.g., `2026-04-02.md`)
- Contains timestamped interactions with raw user/assistant messages
- Recent 7 days are actively loaded into agent context
- After 7 days, files become eligible for consolidation
- Files are archived after being processed into long-term memory

**Purpose**: Provides immediate conversational context and recent interaction history

**Example Structure**:
```markdown
# Memory Log - 2026-04-02

## [14:23:15]

**User**: What's the weather like?

**Assistant**: I don't have access to real-time weather data...

---

## [14:25:30]

**User**: Can you help me with Python?

**Assistant**: Of course! What do you need help with?

---
```

### 2. Long-Term Memory

**Location**: `memory/{user_id}/long_term/`

**Characteristics**:
- Category-based knowledge files (e.g., `personal_preferences.md`, `important_facts.md`)
- Consolidated insights extracted from old short-term memories
- Permanent storage that persists across all conversations
- Continuously updated with new insights
- Organized by semantic categories

**Purpose**: Maintains persistent understanding of user preferences, facts, goals, and relationships

**Categories**:
- `personal_preferences.md` - User's likes, dislikes, habits, preferences
- `important_facts.md` - Key facts about the user (name, location, job, family)
- `goals_and_projects.md` - User's aspirations, ongoing projects, objectives
- `relationships.md` - Important people in the user's life
- `recurring_topics.md` - Topics the user frequently discusses
- `key_insights.md` - Important insights or decisions made

---

## Memory Lifecycle

```
┌─────────────────┐
│ New Conversation│
└────────┬────────┘
         │
         ▼
┌─────────────────────────┐
│ Short-Term Memory       │
│ (daily .md files)       │
│ Active for 7 days       │
└────────┬────────────────┘
         │
         │ (After 7 days)
         │
         ▼
┌─────────────────────────┐
│ AI-Powered              │
│ Consolidation Process   │
│ (heartbeat cycle)       │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ Long-Term Memory        │
│ (categorized .md files) │
│ Permanent storage       │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ Archive Old             │
│ Short-Term Files        │
└─────────────────────────┘
```

---

## Key Components

### Memory Manager (`src/core/memory.py`)

The `MemoryManager` class handles all memory operations for a specific user.

**Key Methods**:

- **`add_interaction(user_message, assistant_message)`**
  - Logs conversations to today's short-term memory file
  - Automatically creates file if it doesn't exist
  - Adds timestamps to each interaction

- **`get_recent_memory(days=7)`**
  - Retrieves last N days of conversations
  - Returns formatted string of all interactions
  - Used to load context for agent

- **`consolidate_memories(agent)`**
  - AI analyzes conversations older than 7 days
  - Extracts important information by category
  - Stores insights in long-term memory files
  - Archives processed short-term files

- **`add_long_term_memory(title, content)`**
  - Stores persistent facts in category files
  - Appends to existing files or creates new ones
  - Timestamps all entries

- **`get_long_term_memory()`**
  - Retrieves all long-term memory content
  - Returns formatted string of all categories
  - Used to load persistent knowledge for agent

- **`archive_short_term_memory(file_path)`**
  - Moves processed files to `short_term/archived/`
  - Keeps main directory clean
  - Preserves historical data

### Memory Tools (`src/tools/memory_tools.py`)

The agent has access to powerful search and retrieval tools:

**Search Tools**:
- **`search_memory_grep`** - Grep search with context lines
  - Parameters: `search_term`, `context_lines`
  - Searches across all memory files
  - Case-insensitive matching

- **`search_recent_mentions`** - Find topic mentions in recent days
  - Parameters: `topic`, `days`
  - Focuses on recent conversations
  - Returns relevant excerpts

- **`search_pattern`** - Regex pattern matching
  - Parameters: `regex_pattern`, `memory_type`
  - Advanced pattern matching
  - Supports complex queries

**File Operations**:
- **`read_memory_file`** - Read specific memory file
  - Parameters: `filename`, `memory_type`
  - Returns complete file content
  - Access to both short-term and long-term

- **`list_memory_files`** - List all available memory files
  - Parameters: `memory_type`
  - Shows file sizes
  - Helps navigation

**Management Tools**:
- **`get_memory_summary`** - Get overview statistics
  - Returns counts and dates
  - Provides system health check
  - No parameters needed

- **`save_important_fact`** - Manually store important information
  - Parameters: `category`, `content`
  - Immediate long-term storage
  - Bypasses consolidation wait

---

## Consolidation Process

### When It Happens
- Automatically during heartbeat cycles (every 15 minutes by default)
- Processes short-term memories older than 7 days
- Can be manually triggered with `/heartbeat` command

### How It Works

1. **Collection Phase**
   - System identifies all short-term memory files older than 7 days
   - Reads and combines content from these files
   - Prepares data for AI analysis

2. **Analysis Phase**
   - AI agent receives combined conversation logs
   - Analyzes content for important patterns and information
   - Identifies facts, preferences, goals, relationships, etc.

3. **Categorization Phase**
   - Extracted insights are sorted into predefined categories:
     - Personal Preferences
     - Important Facts
     - Goals and Projects
     - Relationships
     - Recurring Topics
     - Key Insights

4. **Storage Phase**
   - Categorized information is appended to long-term memory files
   - Each entry is timestamped
   - Existing files are updated or new ones created

5. **Archiving Phase**
   - Processed short-term files are moved to `short_term/archived/`
   - Original files are preserved for reference
   - Main directory remains clean and organized

### Consolidation Prompt

The AI receives a structured prompt asking it to analyze conversations and extract important information by category. The output is parsed using regex patterns to identify `CATEGORY:` and `CONTENT:` pairs.

---

## Agent Context Loading

When the agent processes a user message, it strategically loads memory to balance recent context with long-term knowledge.

### Memory Budget Allocation

**Token Budget Split**:
- **50% of memory token budget**: All long-term memory (persistent knowledge)
- **50% of memory token budget**: Last 3 days of short-term memory (recent context)

### Why This Approach?

This dual-loading strategy ensures the agent has:
- **Deep Understanding**: Access to all consolidated knowledge about the user
- **Immediate Context**: Recent conversations for continuity
- **Efficient Use**: Balanced allocation prevents context overflow
- **Relevance**: Most recent interactions are always available

### Loading Process

```python
# Pseudocode representation
long_term_content = await memory_manager.get_long_term_memory()
short_term_content = await memory_manager.get_recent_memory(days=3)

agent_context = {
    "long_term": long_term_content,  # 50% of budget
    "short_term": short_term_content  # 50% of budget
}
```

---

## Directory Structure

```
memory/
├── 1234567890/                    # User ID (phone number)
│   ├── short_term/
│   │   ├── 2026-04-02.md         # Today's conversations
│   │   ├── 2026-04-01.md         # Yesterday
│   │   ├── 2026-03-31.md         # Recent history
│   │   ├── 2026-03-30.md
│   │   └── archived/              # Processed files
│   │       ├── 2026-03-15.md
│   │       ├── 2026-03-14.md
│   │       └── ...
│   ├── long_term/
│   │   ├── personal_preferences.md
│   │   ├── important_facts.md
│   │   ├── goals_and_projects.md
│   │   ├── relationships.md
│   │   ├── recurring_topics.md
│   │   └── key_insights.md
│   ├── uploads/                   # User-uploaded files
│   └── face_data/                 # Facial recognition data
├── system/                         # System-level memory
│   ├── long_term/
│   └── short_term/
└── test_user/                     # Test user for development
    ├── long_term/
    ├── short_term/
    └── uploads/
```

---

## Benefits of the Dual-Tier System

### 1. **No Information Loss**
- All conversations are preserved
- Important details are automatically extracted
- Historical data is archived, not deleted

### 2. **Efficient Context Management**
- Only relevant recent conversations are loaded
- Long-term knowledge is consolidated and compressed
- Agent stays within token limits

### 3. **Continuous Learning**
- System learns user preferences over time
- Patterns and preferences are identified automatically
- Knowledge base grows without intervention

### 4. **Flexible Retrieval**
- Tools allow searching by date, topic, or pattern
- Agent can access any historical information when needed
- Manual and automatic access methods available

### 5. **Scalability**
- System handles unlimited conversation history
- Older data is compressed into insights
- Performance remains consistent over time

---

## Usage Examples

### For Users

**Triggering Manual Consolidation**:
```
User: /heartbeat
```
This forces immediate consolidation of old memories.

**Searching Past Conversations**:
The agent automatically uses memory tools when needed, but users can ask:
- "When did we discuss pizza?"
- "What have I told you about my job?"
- "Show me conversations from last week"

### For Developers

**Initializing Memory Manager**:
```python
from src.core.memory import MemoryManager

memory = MemoryManager(user_id="1234567890")
```

**Adding Interactions**:
```python
await memory.add_interaction(
    user_message="Hello!",
    assistant_message="Hi! How can I help?"
)
```

**Getting Recent Context**:
```python
recent = await memory.get_recent_memory(days=7)
```

**Manual Consolidation**:
```python
from src.agents.react_agent import ReACTAgent

agent = ReACTAgent(user_id="1234567890")
result = await memory.consolidate_memories(agent)
```

---

## Related Documentation

- [MEMORY_SYSTEM.md](docs/MEMORY_SYSTEM.md) - Original implementation notes
- [MEMORY_TOOLS.md](docs/MEMORY_TOOLS.md) - Tool usage for ReACT agent
- [heartbeat.md](docs/heartbeat.md) - Heartbeat system documentation
- [LOGGING_SYSTEM.md](docs/LOGGING_SYSTEM.md) - How memory operations are logged

---

## Future Enhancements

### Potential Improvements
- **Semantic Search**: Use embeddings for similarity-based retrieval
- **Memory Compression**: Further compress long-term memories over time
- **Importance Weighting**: Prioritize more important memories
- **Memory Visualization**: Dashboard showing memory growth and categories
- **Cross-User Insights**: Learn patterns across multiple users (privacy-safe)
- **Automatic Categorization**: AI-suggested new categories based on usage

### Maintenance Considerations
- Monitor archive directory growth
- Periodic cleanup of very old archived files (configurable retention)
- Optimize consolidation prompt based on results
- Balance between memory detail and token efficiency

---

## Troubleshooting

### Common Issues

**Problem**: Agent doesn't remember old conversations
- **Check**: Are files being consolidated? Check `heartbeat` logs
- **Solution**: Manually trigger with `/heartbeat`

**Problem**: Memory files growing too large
- **Check**: Are long-term files properly categorizing content?
- **Solution**: Review consolidation prompt, may need refinement

**Problem**: Consolidation failing
- **Check**: AI agent errors in logs
- **Solution**: Verify agent has proper permissions and context limits

**Problem**: Archived files accumulating
- **Check**: Archive directory size
- **Solution**: Implement retention policy if needed

---

## Technical Implementation Notes

### File Format
- All memory files use Markdown format for human readability
- UTF-8 encoding
- Async file operations for performance

### Date Format
- Short-term filenames: `YYYY-MM-DD.md` (ISO 8601)
- Timestamps: `HH:MM:SS` (24-hour format)
- Consolidation timestamps: `YYYY-MM-DD HH:MM:SS`

### Logging
- All memory operations are logged via `get_memory_logger()`
- Logs include file operations, sizes, and timing
- See [LOGGING_SYSTEM.md](docs/LOGGING_SYSTEM.md) for details

### Error Handling
- File I/O errors are caught and logged
- Consolidation failures don't prevent normal operation
- System degrades gracefully if memory unavailable

---

*Last Updated: April 2, 2026*
