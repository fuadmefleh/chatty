# VS Code Bridge

This skill allows you to send code change requests to a VS Code agent running on the development server. When the user wants to modify, update, or improve the chatbot's own code, you can queue a request that will be picked up by VS Code's Copilot agent running in autopilot mode.

## When to Use

Use this skill when the user:
- Asks you to change, update, or fix your own code
- Wants to add a new feature to the chatbot
- Requests bug fixes or improvements to the bot
- Says things like "update yourself to...", "change the code so that...", "add a feature that..."
- Explicitly uses the /code command

## Tools

- **send_vscode_request**: Queue a code change request for the VS Code agent. The request will be picked up automatically and executed by Copilot in agent mode.
- **check_vscode_requests**: Check the status of previously submitted code requests.

## How It Works

1. User sends a code change request via Telegram
2. You use `send_vscode_request` to queue it
3. The VS Code extension polls for new requests
4. It sends the request to Copilot agent (autopilot mode)
5. Copilot makes the code changes
6. Status is updated and user can check progress

## Notes

- Be specific in the request message - include what to change, where, and why
- The user can check status anytime by asking about their code requests
- Requests go through a queue, so they are processed in order
