# Pi Agent

Backend plumbing for the web dashboard's "Requests" page. Not a Telegram-facing
skill (no tools.py) — it just spawns the local `pi` coding-agent CLI, configured
with a custom `llama-cpp` provider pointing at a local qwen3.6-27b model, to
implement feature requests submitted from the web UI directly against the
Chatty codebase.

See `runner.py` for the subprocess/event-parsing logic and
`requests_manager.py` for request persistence. Invoked from
`chatty_web_server.py`'s `/api/chatty/requests` endpoints.
