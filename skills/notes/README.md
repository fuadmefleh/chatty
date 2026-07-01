# Notes Skill

A simple note-taking system integrated into the chatbot.

## Overview

The notes skill allows users to save quick notes through natural conversation and manage them through a Telegram interface.

## Features

- **Natural Note Creation**: Just tell the bot to "take note" of something
- **Persistent Storage**: Notes are stored in JSON files per user
- **Telegram UI**: Use `/notes` command to browse and manage notes
- **Search Functionality**: Find notes by keyword
- **Timestamps**: All notes are automatically timestamped

## Storage

Notes are stored in `/home/edgeworks-server/chatty/data/notes/{user_id}.json`

## Usage

### Via Conversation
- "Take note that I need to buy milk"
- "Write down: Meeting with Sarah on Friday"
- "Note to self: Check the oven temperature"

### Via Commands
- `/notes` - View all notes with inline keyboard for management

## Implementation

The skill consists of:
- `tools.py` - Tool definitions for the LLM
- `notes_manager.py` - Core note management logic
- `notes.md` - Skill documentation for the LLM
