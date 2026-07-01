"""Pi agent runner - spawns the `pi` coding-agent CLI as a subprocess and
streams parsed progress events.

Pi (https://pi.dev/) is configured with a custom "llama-cpp" provider
pointing at a local OpenAI-compatible server running qwen3.6-27b
(see ~/.pi/agent/models.json). This mirrors skills/opencode/runner.py's
subprocess + JSON-event-streaming pattern, adapted to Pi's event schema.
"""
import asyncio
import json
import logging
import os
import re
from pathlib import Path
from typing import AsyncGenerator, Optional

logger = logging.getLogger(__name__)

PROJECT_DIR = Path(__file__).parent.parent.parent  # chatty/

# Full path to pi binary (nvm-installed)
PI_BIN = os.environ.get(
    "PI_BIN",
    os.path.expanduser("~/.nvm/versions/node/v22.12.0/bin/pi")
)

# Local model configuration (see ~/.pi/agent/models.json)
PI_AGENT_PROVIDER = os.environ.get("PI_AGENT_PROVIDER", "llama-cpp")
PI_AGENT_MODEL = os.environ.get("PI_AGENT_MODEL", "qwen3.6-27b")

# Max time (seconds) before we kill a stuck pi process
MAX_RUN_SECONDS = 300  # 5 minutes

# Build a clean environment for the pi subprocess.
# pm2 may strip PATH/HOME which pi needs for its config + node.
_HOME = os.path.expanduser("~")
_PI_ENV = {
    **os.environ,
    "HOME": _HOME,
    "PATH": f"{os.path.dirname(PI_BIN)}:{os.environ.get('PATH', '/usr/bin:/bin')}",
    "NODE_ENV": "production",
}

# Track the currently running process
_active_process: Optional[asyncio.subprocess.Process] = None
_active_prompt: Optional[str] = None


def is_running() -> bool:
    """Check if a Pi agent process is currently running."""
    return _active_process is not None and _active_process.returncode is None


async def run_pi_agent(prompt: str) -> AsyncGenerator[dict, None]:
    """Spawn `pi ... --print --mode json` and yield parsed events.

    Args:
        prompt: The coding task to send to the Pi agent.

    Yields:
        dict events with keys: type, content
        type can be: started, progress, tool_call, file_change, completed, error
    """
    global _active_process, _active_prompt

    if is_running():
        yield {"type": "error", "content": "Pi agent is already running a request. Please wait."}
        return

    _active_prompt = prompt

    yield {"type": "started", "content": f"Launching Pi agent ({PI_AGENT_PROVIDER}/{PI_AGENT_MODEL})..."}

    parser = _EventParser()
    saw_agent_end = False

    try:
        _active_process = await asyncio.create_subprocess_exec(
            PI_BIN,
            "--provider", PI_AGENT_PROVIDER,
            "--model", PI_AGENT_MODEL,
            "--print",
            "--mode", "json",
            "--no-extensions",  # a broken global extension crashes pi otherwise
            prompt,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,  # merge stderr into stdout
            cwd=str(PROJECT_DIR),
            env=_PI_ENV,
            limit=10 * 1024 * 1024,  # Pi's message_update lines carry the full
            # growing partial message and can exceed asyncio's 64KB default.
        )

        logger.info(f"Pi subprocess PID={_active_process.pid}, env HOME={_HOME}, bin={PI_BIN}")
        yield {"type": "progress", "content": "Connected, thinking..."}

        last_content = ""
        got_events = False
        raw_lines = []
        thinking_seconds = 0
        total_seconds = 0

        while True:
            try:
                line = await asyncio.wait_for(_active_process.stdout.readline(), timeout=10.0)
            except asyncio.TimeoutError:
                thinking_seconds += 10
                total_seconds += 10
                if total_seconds >= MAX_RUN_SECONDS:
                    logger.warning(f"Pi agent exceeded {MAX_RUN_SECONDS}s timeout, killing")
                    _active_process.kill()
                    yield {"type": "error", "content": f"Pi agent timed out after {MAX_RUN_SECONDS // 60} minutes. The request may be too complex."}
                    break
                yield {"type": "progress", "content": f"Thinking... ({thinking_seconds}s)"}
                continue

            if not line:
                break

            thinking_seconds = 0

            decoded = line.decode("utf-8", errors="replace").strip()
            if not decoded:
                continue

            if not got_events:
                logger.info(f"Pi agent first output: {decoded[:300]}")
            else:
                logger.debug(f"Pi agent raw: {decoded[:200]}")

            try:
                event = json.loads(decoded)
                got_events = True
                if event.get("type") == "agent_end":
                    saw_agent_end = True
                for parsed in parser.feed(event):
                    if not parsed.get("content"):
                        continue
                    # Only de-dupe streamed "progress" text (which repeats as
                    # it accumulates token by token). Discrete events like
                    # tool_call/file_change/error/completed must never be
                    # dropped just because their text happens to match the
                    # last thing shown.
                    if parsed["type"] == "progress" and parsed["content"] == last_content:
                        continue
                    if parsed["type"] == "progress":
                        last_content = parsed["content"]
                    yield parsed
            except json.JSONDecodeError:
                clean = _strip_ansi(decoded)
                if clean and clean != last_content:
                    last_content = clean
                    raw_lines.append(clean)
                    yield {"type": "progress", "content": clean}

        await _active_process.wait()
        rc = _active_process.returncode

        if saw_agent_end:
            # The agent completed its turn (agent_end was emitted) even if the
            # process itself then exited uncleanly (e.g. a crash during Pi's
            # own shutdown/session-write). The actual work already happened.
            if rc == 0:
                yield {"type": "completed", "content": "Pi agent finished successfully."}
            else:
                yield {"type": "completed", "content": f"Pi agent finished (process exited with code {rc} during shutdown)."}
        elif rc == 0 and not got_events:
            stderr_msg = "\n".join(raw_lines[:5]) if raw_lines else "No output received"
            yield {"type": "error", "content": f"Pi agent produced no output. stderr: {stderr_msg[:300]}"}
        else:
            err_msg = "\n".join(raw_lines[:5])[:500] if raw_lines else f"Process exited with code {rc}"
            yield {"type": "error", "content": f"Pi agent failed: {err_msg}"}

    except FileNotFoundError:
        yield {"type": "error", "content": f"Pi binary not found at: {PI_BIN}"}
    except Exception as e:
        logger.error(f"Pi agent runner error: {e}", exc_info=True)
        if _active_process is not None and _active_process.returncode is None:
            try:
                _active_process.kill()
            except ProcessLookupError:
                pass
        if saw_agent_end:
            # Same reasoning as above: the agent already finished its turn
            # before this (e.g. a stream-reading error) hit.
            yield {"type": "completed", "content": "Pi agent finished (a non-fatal error occurred after completion)."}
        else:
            yield {"type": "error", "content": f"Pi agent error: {str(e)}"}
    finally:
        _active_process = None
        _active_prompt = None


class _EventParser:
    """Stateful parser for Pi's --mode json event stream.

    Tracks in-flight tool calls (tool_execution_start -> tool_execution_end)
    so file_change events can report the file path, and accumulates
    streamed assistant text into readable progress chunks.
    """

    def __init__(self):
        self._pending_tool_args: dict[str, dict] = {}

    def feed(self, event: dict):
        """Yield zero or more simplified events for one raw Pi event."""
        etype = event.get("type", "")

        if etype == "message_update":
            sub = event.get("assistantMessageEvent", {})
            # Only surface the finished message, not every intermediate
            # token — Pi streams text_delta per token, which would otherwise
            # turn one sentence into dozens of growing-substring log lines.
            if sub.get("type") == "text_end":
                text = sub.get("content", "").strip()
                if text:
                    display = text[:300] + "..." if len(text) > 300 else text
                    yield {"type": "progress", "content": display}
            return

        if etype == "tool_execution_start":
            tool_name = event.get("toolName", "unknown")
            args = event.get("args", {}) or {}
            self._pending_tool_args[event.get("toolCallId", "")] = args
            content = _format_tool_call(tool_name, args)
            if content:
                yield {"type": "tool_call", "content": content}
            if tool_name in ("write", "edit"):
                # write/edit happen synchronously on the fs before the tool
                # even reports back — flag the file as changed now rather
                # than waiting for tool_execution_end, which can be lost if
                # the process crashes during its own shutdown right after.
                path = args.get("path") or args.get("filePath") or args.get("file")
                if path:
                    yield {"type": "file_change", "content": f"{'Writing' if tool_name == 'write' else 'Editing'}: {_short_path(path)}"}
            return

        if etype == "tool_execution_end":
            tool_name = event.get("toolName", "unknown")
            call_id = event.get("toolCallId", "")
            args = self._pending_tool_args.pop(call_id, {})
            is_error = event.get("isError", False)

            if is_error:
                # A single tool call failing (e.g. a grep with no matches, exit
                # code 1) is routine agentic back-and-forth, not a fatal error
                # for the whole request — just log it and let the agent continue.
                result = event.get("result", {})
                text = _result_text(result)
                yield {"type": "tool_call", "content": f"⚠ {tool_name} failed: {text[:200]}"}
                return

            if tool_name in ("write", "edit"):
                path = args.get("path") or args.get("filePath") or args.get("file") or "unknown"
                yield {"type": "file_change", "content": f"{'Writing' if tool_name == 'write' else 'Editing'}: {_short_path(path)}"}
            elif tool_name == "bash":
                result = event.get("result", {})
                out = _result_text(result).strip()
                if out:
                    yield {"type": "tool_call", "content": f"↳ {out[:200]}"}
            return

        if etype == "error":
            err = event.get("error", {})
            msg = err.get("message") or err.get("data", {}).get("message", "") or "Unknown error"
            yield {"type": "error", "content": msg}
            return

        # session, agent_start, turn_start, message_start/end, turn_end,
        # agent_end: no additional progress content needed here.
        return


def _format_tool_call(tool_name: str, args: dict) -> Optional[str]:
    if tool_name == "write":
        path = args.get("path") or args.get("filePath") or "unknown"
        return f"Writing: {_short_path(path)}"
    if tool_name == "edit":
        path = args.get("path") or args.get("filePath") or "unknown"
        return f"Editing: {_short_path(path)}"
    if tool_name == "bash":
        cmd = str(args.get("command", ""))[:100]
        return f"$ {cmd}"
    if tool_name == "read":
        path = args.get("path") or args.get("filePath") or "unknown"
        return f"Reading: {_short_path(path)}"
    if tool_name in ("grep", "find"):
        pattern = str(args.get("pattern", args.get("query", "")))[:60]
        return f"Searching: {pattern}"
    if tool_name == "ls":
        path = args.get("path", ".")
        return f"Listing: {_short_path(path)}"
    return f"Tool: {tool_name}"


def _result_text(result: dict) -> str:
    content = result.get("content", []) if isinstance(result, dict) else []
    parts = [c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"]
    return "\n".join(parts)


def _short_path(filepath: str) -> str:
    """Shorten a file path for display, making it relative to project dir."""
    try:
        p = Path(filepath)
        if not p.is_absolute():
            return filepath
        return str(p.relative_to(PROJECT_DIR))
    except (ValueError, TypeError):
        return filepath


_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text).strip()
