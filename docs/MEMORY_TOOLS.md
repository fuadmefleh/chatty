# Memory Tools for ReACT Agent

## Overview

The ReACT agent now has access to powerful memory search and retrieval tools that allow it to search through markdown memory files using grep, regex patterns, date ranges, and more.

## Available Tools

### 1. search_memory_grep(search_term, context_lines=2)
Searches all memory files for a specific term using grep with context.

**Parameters:**
- `search_term` (str): The term to search for (case-insensitive)
- `context_lines` (int): Number of lines before/after match to show (default: 2)

**Example Usage in ReACT:**
```
THOUGHT: I need to find when we discussed pizza.
ACTION: use tool search_memory_grep with search_term="pizza" and context_lines=3
OBSERVATION: [Results from grep search]
```

### 2. list_memory_files(memory_type="all")
Lists all available memory files with their sizes.

**Parameters:**
- `memory_type` (str): "short_term", "long_term", or "all" (default: "all")

**Example Usage:**
```
THOUGHT: I should see what memory files are available.
ACTION: use tool list_memory_files with memory_type="all"
```

### 3. read_memory_file(filename, memory_type="short_term")
Reads the complete content of a specific memory file.

**Parameters:**
- `filename` (str): Name of the file (e.g., "2026-01-30.md")
- `memory_type` (str): "short_term" or "long_term" (default: "short_term")

**Example Usage:**
```
THOUGHT: I need to read the full conversation from January 25th.
ACTION: use tool read_memory_file with filename="2026-01-25.md" and memory_type="short_term"
```

### 4. search_by_date_range(start_date, end_date)
Retrieves all short-term memories between two dates.

**Parameters:**
- `start_date` (str): Start date in YYYY-MM-DD format
- `end_date` (str): End date in YYYY-MM-DD format

**Example Usage:**
```
THOUGHT: I should look at conversations from last week.
ACTION: use tool search_by_date_range with start_date="2026-01-23" and end_date="2026-01-29"
```

### 5. search_pattern(regex_pattern, memory_type="all")
Searches memory files using regular expressions for complex patterns.

**Parameters:**
- `regex_pattern` (str): Regular expression pattern
- `memory_type` (str): "short_term", "long_term", or "all" (default: "all")

**Example Usage:**
```
THOUGHT: I need to find all mentions of phone numbers or calls.
ACTION: use tool search_pattern with pattern="\\b(phone|call|contact)\\b" and memory_type="all"
```

### 6. get_memory_summary()
Gets an overview of available memory files and categories.

**Parameters:** None

**Example Usage:**
```
THOUGHT: I should check what memory is available.
ACTION: use tool get_memory_summary
```

### 7. search_recent_mentions(topic, days=7)
Finds recent mentions of a topic in the last N days.

**Parameters:**
- `topic` (str): Topic to search for
- `days` (int): Number of recent days to search (default: 7)

**Example Usage:**
```
THOUGHT: When did we last discuss the project?
ACTION: use tool search_recent_mentions with topic="project" and days=14
```

## Implementation Details

### Files Modified/Created

1. **memory_tools.py** (NEW)
   - Contains the `MemoryTools` class with all search functions
   - Implements grep, file reading, regex search, and date-based queries
   - Includes logging for debugging

2. **react_agent.py** (MODIFIED)
   - Added import for `MemoryTools` and `get_tools_description`
   - Initialized `self.memory_tools` in `__init__`
   - Updated system prompt to include tool descriptions
   - Enhanced `_execute_action()` to parse and execute tool calls
   - Added `_parse_and_execute_tool()` for tool parsing logic

3. **test_memory_tools.py** (NEW)
   - Test script to demonstrate tool functionality
   - Can add test data and run all tool tests

## Usage in ReACT Loop

The AI agent can now use these tools during its reasoning process:

```
User: "What did I say about my favorite food last week?"

AI Response:
THOUGHT: I need to search recent conversations for mentions of favorite food.
ACTION: use tool search_recent_mentions with topic="favorite food" and days=7
OBSERVATION: [Results showing past mentions]
THOUGHT: I found that the user mentioned they love Italian cuisine and pasta.
FINAL ANSWER: Last week you mentioned that you love Italian cuisine, especially pasta!
```

## Tool Call Format

The AI can call tools using natural language in the ACTION step:
- `ACTION: use tool search_memory_grep with search_term="keyword"`
- `ACTION: search for "pattern" in memory files`
- `ACTION: list all memory files`
- `ACTION: read memory file "2026-01-30.md"`

The parser uses regex to extract parameters from various formats:
- Quoted values: `search_term="value"` or `search_term='value'`
- Unquoted numbers: `days=7` or `context_lines=3`
- Flexible naming: `search_term=` or `search term:` or `searchterm:`

## Testing

Run the test script:
```bash
# Add test data first
python test_memory_tools.py --add-data

# Run all tests
python test_memory_tools.py
```

## Benefits

1. **Deep Memory Access**: Agent can search through all historical conversations
2. **Flexible Search**: Multiple search methods for different use cases
3. **Context Awareness**: Better understanding of user through historical data
4. **Efficient Retrieval**: Targeted searches instead of loading all memory
5. **Date-Based Queries**: Can answer "what did I say last week?" type questions

## Future Enhancements

Potential improvements:
- Semantic search using embeddings
- Memory indexing for faster searches
- Automatic tool suggestion based on query type
- Memory summarization tools
- Cross-reference detection between memories
- Timeline visualization tools
