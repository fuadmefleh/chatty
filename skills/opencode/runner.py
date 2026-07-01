"""OpenCode runner - spawns opencode CLI as a subprocess and streams output."""
import asyncio
import json
import logging
import os
import re
from pathlib import Path
from typing import AsyncGenerator, Optional

logger = logging.getLogger(__name__)

PROJECT_DIR = Path(__file__).parent.parent.parent  # chatty/

# Full path to opencode binary (nvm-installed)
OPENCODE_BIN = os.environ.get(
    "OPENCODE_BIN",
    os.path.expanduser("~/.nvm/versions/node/v22.12.0/bin/opencode")
)

# Max time (seconds) before we kill a stuck opencode process
MAX_RUN_SECONDS = 300  # 5 minutes

# Build a clean environment for the opencode subprocess.
# pm2 may strip PATH/HOME which opencode needs for auth + node.
_HOME = os.path.expanduser("~")
_OPENCODE_ENV = {
    **os.environ,
    "HOME": _HOME,
    "PATH": f"{os.path.dirname(OPENCODE_BIN)}:{os.environ.get('PATH', '/usr/bin:/bin')}",
    "NODE_ENV": "production",
}

# Track the currently running process
_active_process: Optional[asyncio.subprocess.Process] = None
_active_prompt: Optional[str] = None


def is_running() -> bool:
    """Check if an OpenCode process is currently running."""
    return _active_process is not None and _active_process.returncode is None


async def run_opencode(prompt: str) -> AsyncGenerator[dict, None]:
    """Spawn opencode run and yield parsed events.

    Args:
        prompt: The coding task to send to OpenCode.

    Yields:
        dict events with keys: type, content
        type can be: started, progress, tool_call, file_change, completed, error
    """
    global _active_process, _active_prompt

    if is_running():
        yield {"type": "error", "content": "OpenCode is already running a request. Please wait."}
        return

    _active_prompt = prompt

    yield {"type": "started", "content": "Launching OpenCode agent..."}

    try:
        _active_process = await asyncio.create_subprocess_exec(
            OPENCODE_BIN, "run", prompt,
            "--format", "json",
            stdin=asyncio.subprocess.DEVNULL,   # no interactive input
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,  # merge stderr into stdout
            cwd=str(PROJECT_DIR),
            env=_OPENCODE_ENV,
        )

        logger.info(f"OpenCode subprocess PID={_active_process.pid}, env HOME={_HOME}, bin={OPENCODE_BIN}")
        yield {"type": "progress", "content": "Connected, thinking..."}

        # Read stdout line by line for JSON events (stderr merged in)
        last_text = ""
        got_events = False
        stderr_lines = []
        thinking_seconds = 0
        total_seconds = 0
        while True:
            try:
                line = await asyncio.wait_for(_active_process.stdout.readline(), timeout=10.0)
            except asyncio.TimeoutError:
                # No output for 10s — model is still thinking
                thinking_seconds += 10
                total_seconds += 10
                # Kill if total time exceeds max
                if total_seconds >= MAX_RUN_SECONDS:
                    logger.warning(f"OpenCode exceeded {MAX_RUN_SECONDS}s timeout, killing")
                    _active_process.kill()
                    yield {"type": "error", "content": f"OpenCode timed out after {MAX_RUN_SECONDS // 60} minutes. The request may be too complex."}
                    break
                yield {"type": "progress", "content": f"Thinking... ({thinking_seconds}s)"}
                continue

            if not line:
                break

            thinking_seconds = 0  # reset thinking counter on output
            # Don't reset total_seconds — that tracks wall clock

            decoded = line.decode("utf-8", errors="replace").strip()
            if not decoded:
                continue
            
            # Log first few lines at INFO level for debugging
            if not got_events:
                logger.info(f"OpenCode first output: {decoded[:300]}")
            else:
                logger.debug(f"OpenCode raw: {decoded[:200]}")

            try:
                event = json.loads(decoded)
                got_events = True
                parsed = _parse_event(event)
                if parsed and parsed.get("content") and parsed["content"] != last_text:
                    last_text = parsed["content"]
                    yield parsed
            except json.JSONDecodeError:
                # Non-JSON output (e.g. plain text progress)
                clean = _strip_ansi(decoded)
                if clean and clean != last_text:
                    last_text = clean
                    stderr_lines.append(clean)
                    yield {"type": "progress", "content": clean}

        await _active_process.wait()
        rc = _active_process.returncode

        if rc == 0 and got_events:
            yield {"type": "completed", "content": "OpenCode finished successfully."}
        elif rc == 0 and not got_events:
            stderr_msg = "\n".join(stderr_lines[:5]) if stderr_lines else "No output received"
            yield {"type": "error", "content": f"OpenCode produced no output. stderr: {stderr_msg[:300]}"}
        else:
            err_msg = "\n".join(stderr_lines[:5])[:500] if stderr_lines else f"Process exited with code {rc}"
            yield {"type": "error", "content": f"OpenCode failed: {err_msg}"}

    except FileNotFoundError:
        yield {"type": "error", "content": f"OpenCode binary not found at: {OPENCODE_BIN}"}
    except Exception as e:
        logger.error(f"OpenCode runner error: {e}", exc_info=True)
        yield {"type": "error", "content": f"OpenCode error: {str(e)}"}
    finally:
        _active_process = None
        _active_prompt = None


def _parse_event(event: dict, last_assistant_text: str = "") -> Optional[dict]:
    """Parse a JSON event from opencode run --format json into a simplified dict.

    Actual event types from OpenCode CLI:
      step_start  - new reasoning step begins
      text        - assistant text in part.text
      tool_use    - tool invocation in part.tool, part.state.*
      step_finish - step done, part.reason = "stop" | "tool-calls"
      error       - error object
    """
    etype = event.get("type", "")
    part = event.get("part", {})

    # --- assistant text ---
    if etype == "text":
        text = part.get("text", "").strip()
        if not text:
            return None
        # Truncate long responses for the live view
        display = text[:300] + "..." if len(text) > 300 else text
        return {"type": "progress", "content": display}

    # --- tool usage ---
    if etype == "tool_use":
        tool_name = part.get("tool", "unknown")
        state = part.get("state", {})
        status = state.get("status", "")
        inp = state.get("input", {})
        title = part.get("title", "")

        if tool_name == "write":
            filepath = inp.get("filePath", title or "unknown")
            return {"type": "file_change", "content": f"Writing: {_short_path(filepath)}"}
        elif tool_name == "edit":
            filepath = inp.get("filePath", title or "unknown")
            return {"type": "file_change", "content": f"Editing: {_short_path(filepath)}"}
        elif tool_name == "bash":
            cmd = inp.get("command", "")[:100]
            if status == "completed":
                output = state.get("output", "")
                short_out = output.strip()[:120] if output else ""
                if short_out:
                    return {"type": "tool_call", "content": f"$ {cmd}\n↳ {short_out}"}
            return {"type": "tool_call", "content": f"$ {cmd}"}
        elif tool_name == "read":
            filepath = inp.get("filePath", title or "unknown")
            return {"type": "tool_call", "content": f"Reading: {_short_path(filepath)}"}
        elif tool_name in ("glob", "grep"):
            pattern = inp.get("pattern", inp.get("query", ""))[:60]
            return {"type": "tool_call", "content": f"Searching: {pattern}"}
        elif tool_name == "todowrite":
            return None  # internal tracking, skip
        else:
            label = title or tool_name
            return {"type": "tool_call", "content": f"Tool: {label}"}

    # --- step boundaries ---
    if etype == "step_start":
        return None  # suppress, we show content from text/tool events

    if etype == "step_finish":
        return None  # completion handled by process exit code

    # --- error ---
    if etype == "error":
        err = event.get("error", {})
        msg = err.get("data", {}).get("message", "") or err.get("name", "Unknown error")
        return {"type": "error", "content": msg}

    return None


def _short_path(filepath: str) -> str:
    """Shorten a file path for display, making it relative to project dir."""
    try:
        p = Path(filepath)
        return str(p.relative_to(PROJECT_DIR))
    except (ValueError, TypeError):
        return filepath


# Regex to strip ANSI escape codes
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text."""
    return _ANSI_RE.sub("", text).strip()
