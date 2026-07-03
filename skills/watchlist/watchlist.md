# Watchlist

## Description
Lets you tell the bot to keep an eye on something so it can proactively surface what's new without being asked. Three kinds of things can be watched:
- **news** (default): any topic, project, person, or event - checked against web news
- **stock**: a ticker symbol - alerts on a large single-day price move
- **github**: an "owner/repo" GitHub repository - alerts on a new release or commit

Watched topics are checked periodically in the background (see the World Watch heartbeat task) and notable updates are sent to you and saved to the Insights dashboard. The bot may also occasionally suggest a topic worth watching based on things you've mentioned repeatedly in conversation - you can accept those the same way you'd add any other topic.

## Usage
When the user asks to be kept updated on something, add it to the watchlist with the right `kind`. When they no longer care about a topic, remove it. You can also list what's currently being watched.

## Examples
- "Keep an eye on SpaceX Starship launches" (kind: news)
- "Watch for news about the Fed's interest rate decisions" (kind: news)
- "Watch AAPL stock" (kind: stock, topic: "AAPL")
- "Keep an eye on the anthropics/claude-code repo" (kind: github, topic: "anthropics/claude-code")
- "Stop watching Bitcoin"
- "What am I watching right now?"

## Tools

### add_watch_topic
Adds a topic to the watchlist.

**Parameters:**
- `user_id` (string, required): The user's ID
- `topic` (string, required): The topic/query (news), ticker symbol (stock), or "owner/repo" (github)
- `kind` (string, optional): One of "news" (default), "stock", "github"

**Returns:** Success status and the created topic's ID

### remove_watch_topic
Removes a topic from the watchlist, matched by exact ID or by a substring of its text.

**Parameters:**
- `user_id` (string, required): The user's ID
- `topic_or_id` (string, required): The topic text (or its ID) to stop watching

**Returns:** Success status

### list_watch_topics
Lists all topics currently being watched for a user.

**Parameters:**
- `user_id` (string, required): The user's ID

**Returns:** List of topics with IDs, creation dates, and when each was last checked
