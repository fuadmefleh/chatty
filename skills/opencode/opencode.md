# OpenCode Agent

This skill allows you to send code change requests to the OpenCode AI coding agent. When the user wants to modify, update, or improve the chatbot's own code, you can run OpenCode which will directly make changes to the codebase.

## When to Use

Use this skill when the user:
- Asks you to change, update, or fix your own code
- Wants to add a new feature to the chatbot
- Requests bug fixes or improvements to the bot
- Says things like "update yourself to...", "change the code so that...", "add a feature that..."
- Explicitly uses the /code command

## Tools

- **run_opencode**: Run the OpenCode agent to make code changes. The request will be executed immediately and progress streamed back.
- **check_opencode_status**: Check whether the OpenCode agent is currently running.

## How It Works

1. User sends a code change request via Telegram
2. You use `run_opencode` to launch the OpenCode agent
3. OpenCode analyzes the codebase and makes changes directly
4. Progress is streamed back to the user in real-time
5. When complete, a summary of changes is sent

## Notes

- Be specific in the request message - include what to change, where, and why
- Only one OpenCode request can run at a time
- OpenCode uses GitHub Copilot as the AI provider
- After code changes, you may want to restart services with pm2
