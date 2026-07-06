"""Tests for skills/pi_agent/runner.py - timeout configuration and event
parsing helpers. Does not exercise the actual subprocess (requires a real
`pi` binary + local model), which is tested in CI integration tests."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from skills.pi_agent import runner


def test_max_run_seconds_default_is_15_minutes():
    """Default timeout should be 15 minutes (900s), not the old 5 min."""
    # Force a clean read by re-evaluating the env-var default.
    env_val = os.environ.get("PI_AGENT_MAX_RUN_SECONDS")
    expected = int(env_val) if env_val else 900
    assert runner.MAX_RUN_SECONDS == expected


def test_max_run_seconds_from_env(monkeypatch):
    """PI_AGENT_MAX_RUN_SECONDS env var should override the default."""
    monkeypatch.setenv("PI_AGENT_MAX_RUN_SECONDS", "1800")

    # Re-import to pick up the new env var.
    import importlib

    importlib.reload(runner)
    assert runner.MAX_RUN_SECONDS == 1800


def test_short_path_relative():
    base = Path("/some/project")
    assert runner._short_path("/some/project/src/foo.py", base) == "src/foo.py"


def test_short_path_absolute_outside_base():
    """Paths outside base_dir are returned as-is."""
    base = Path("/some/project")
    assert runner._short_path("/other/path/file.py", base) == "/other/path/file.py"


def test_short_path_relative_input():
    """Non-absolute paths are returned as-is."""
    assert runner._short_path("relative/file.py", Path("/any")) == "relative/file.py"


def test_strip_ansi():
    assert runner._strip_ansi("\x1b[31mred\x1b[0m text") == "red text"
    assert runner._strip_ansi("clean text") == "clean text"


def test_format_tool_call_bash():
    result = runner._format_tool_call("bash", {"command": "ls -la"}, Path("/"))
    assert result == "$ ls -la"


def test_format_tool_call_write():
    result = runner._format_tool_call("write", {"path": "/proj/src/foo.py"}, Path("/proj"))
    assert result == "Writing: src/foo.py"


def test_format_tool_call_read():
    result = runner._format_tool_call("read", {"path": "/proj/README.md"}, Path("/proj"))
    assert result == "Reading: README.md"


def test_format_tool_call_unknown():
    result = runner._format_tool_call("custom_tool", {}, Path("/"))
    assert result == "Tool: custom_tool"


def test_format_tool_call_command_truncation():
    long_cmd = "a" * 200
    result = runner._format_tool_call("bash", {"command": long_cmd}, Path("/"))
    assert "$ " in result
    assert len(result) < 105  # prefix "$ " + 100 char limit


def test_is_self_restart_command_detects_restart():
    runner.PM2_SELF_APP_NAME = "chatty-web-server"
    assert runner._is_self_restart_command("pm2 restart chatty-web-server") is True
    assert runner._is_self_restart_command("pm2 reload chatty-web-server") is True
    assert runner._is_self_restart_command("pm2 stop chatty-web-server") is True
    assert runner._is_self_restart_command("pm2 delete chatty-web-server") is True


def test_is_self_restart_command_ignores_other_apps():
    runner.PM2_SELF_APP_NAME = "chatty-web-server"
    assert runner._is_self_restart_command("pm2 restart chatty-bot") is False


def test_is_self_restart_command_ignores_non_pm2():
    runner.PM2_SELF_APP_NAME = "chatty-web-server"
    assert runner._is_self_restart_command("systemctl restart nginx") is False


def test_result_text():
    result = {
        "content": [
            {"type": "text", "text": "line one"},
            {"type": "text", "text": "line two"},
        ]
    }
    assert runner._result_text(result) == "line one\nline two"


def test_result_text_empty():
    assert runner._result_text({}) == ""
    assert runner._result_text({"content": []}) == ""
