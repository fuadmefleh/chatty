# Long-Term and Short-Term Memory System

## Overview

The bot now has a dual memory system that separates short-term conversation logs from long-term consolidated knowledge.

## Memory Types

### Short-Term Memory
- **Location**: `memory/{user_id}/short_term/`
- **Format**: Daily markdown files (e.g., `2026-01-30.md`)
- **Content**: Raw conversation logs with timestamps
- **Lifecycle**: Active conversations and recent history (last 7 days used in agent context)
- **Purpose**: Immediate conversational context and recent interactions

### Long-Term Memory
- **Location**: `memory/{user_id}/long_term/`
- **Format**: Category-based markdown files (e.g., `personal_preferences.md`, `important_facts.md`)
- **Content**: Consolidated insights extracted from old short-term memories
- **Lifecycle**: Permanent knowledge base, continuously updated
- **Purpose**: Persistent understanding of user preferences, facts, goals, and relationships

## Memory Flow

```
User Conversation → Short-Term Memory (daily .md files)
                            ↓
                    (After 7 days)
                            ↓
         Heartbeat Consolidation Process
                            ↓
              AI Analysis & Extraction
                            ↓
         Long-Term Memory (categorized .md files)
                            ↓
              Archive Old Short-Term Files
```

## Consolidation Process

### When It Happens
- Automatically during heartbeat cycles (every 15 minutes by default)
- Processes short-term memories older than 7 days

### How It Works
1. **Collection**: Gathers all short-term memory files older than 7 days
2. **Analysis**: AI agent analyzes conversations for important information
3. **Categorization**: Extracts and categorizes insights into:
   - Personal Preferences (likes, dislikes, habits)
   - Important Facts (name, location, job, family)
   - Goals and Projects (aspirations, ongoing work)
   - Relationships (important people)
   - Recurring Topics (frequent discussion themes)
   - Key Insights (important decisions, realizations)
4. **Storage**: Appends consolidated information to long-term memory files
5. **Archiving**: Moves processed short-term files to `short_term/archived/`

### Manual Trigger
You can manually trigger memory consolidation using:
```
/heartbeat
```

## Agent Memory Usage

When the agent processes a message, it loads:
1. **Long-Term Memory** (50% of memory token budget)
   - All consolidated knowledge about the user
   - Persistent facts, preferences, and insights
   
2. **Short-Term Memory** (50% of memory token budget)
   - Last 3 days of conversations
   - Recent context and ongoing discussions

This dual approach ensures the agent has both:
- Deep understanding from past interactions (long-term)
- Immediate context from recent conversations (short-term)

## Directory Structure

```
memory/
└── {user_id}/
    ├── short_term/
    │   ├── 2026-01-30.md
    │   ├── 2026-01-29.md
    │   ├── 2026-01-28.md
    │   └── archived/
    │       ├── 2026-01-20.md
    │       └── 2026-01-19.md
    └── long_term/
        ├── personal_preferences.md
        ├── important_facts.md
        ├── goals_and_projects.md
        ├── relationships.md
        ├── recurring_topics.md
        └── key_insights.md
```

## Benefits

1. **Better Context Management**: Recent details in short-term, important facts in long-term
2. **Improved Performance**: Focuses on relevant information rather than all history
3. **Knowledge Persistence**: Important information isn't lost in old conversation logs
4. **Scalability**: System remains efficient as conversation history grows
5. **Intelligence**: AI actively learns and remembers what matters most

## Commands

- `/memory` - View memory statistics for both short-term and long-term
- `/heartbeat` - Manually trigger heartbeat (includes memory consolidation)

## Configuration

In `.env`:
```
HEARTBEAT_INTERVAL_MINUTES=15  # How often to run consolidation
```

## Technical Implementation

### Key Files
- `memory.py`: MemoryManager class with short/long-term support
- `heartbeat_manager.py`: Orchestrates consolidation during heartbeat
- `react_agent.py`: Uses both memory types in agent context
- `heartbeat.md`: Defines autonomous consolidation task

### Key Methods
- `MemoryManager.consolidate_memories()`: Main consolidation logic
- `MemoryManager.add_long_term_memory()`: Add/update long-term entries
- `MemoryManager.get_long_term_memory()`: Retrieve all long-term knowledge
- `MemoryManager.archive_short_term_memory()`: Archive processed files
