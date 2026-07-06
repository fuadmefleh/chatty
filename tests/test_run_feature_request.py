"""Tests for src/managers/self_upgrade_manager.run_feature_request - the
worktree-isolated pipeline the web dashboard's Requests queue uses so Pi can
never edit the live checkout mid-turn or restart the very server it runs
under. Mirrors tests/test_self_upgrade_manager.py's mocking style; see that
file for the sibling run_self_upgrade pipeline this was extracted from.
"""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.managers import self_upgrade_manager as sum_


def make_feature_requests_manager():
    return MagicMock()


def test_wrap_feature_request_prompt_tells_pi_not_to_restart_services():
    """The actual bug fix: Pi must never try to verify its own change by
    restarting/curling the live server, since that's a plain child process
    of the very service being restarted (see skills/pi_agent/runner.py)."""
    wrapped = sum_._wrap_feature_request_prompt("add a feature")
    assert "do not run" in wrapped.lower() or "don't try" in wrapped.lower()
    assert "pm2 restart" in wrapped.lower()
    assert "isolated git worktree" in wrapped.lower()


@pytest.mark.asyncio
async def test_run_feature_request_no_changes_is_a_clean_noop():
    frm = make_feature_requests_manager()

    async def fake_run_pi_agent(prompt, cwd=None):
        yield {"type": "completed", "content": "done, no changes needed"}

    with patch("src.managers.self_upgrade_manager._git", new_callable=AsyncMock) as mock_git, \
         patch("src.managers.self_upgrade_manager.run_pi_agent", fake_run_pi_agent), \
         patch("src.managers.self_upgrade_manager._cleanup_worktree", new_callable=AsyncMock) as mock_cleanup:

        mock_git.side_effect = [
            (0, ""),   # worktree prune
            (0, ""),   # worktree add
            (0, ""),   # add -A
            (0, ""),   # diff --cached --quiet -> 0 means NO diff
        ]

        result = await sum_.run_feature_request("req1", "do something", frm)

    assert result is None
    last_kwargs = frm.update.call_args_list[-1].kwargs
    assert last_kwargs.get("status") == "completed"
    assert last_kwargs.get("summary") == "No changes were necessary."
    mock_cleanup.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_feature_request_agent_error_is_terminal():
    frm = make_feature_requests_manager()

    async def fake_run_pi_agent(prompt, cwd=None):
        yield {"type": "error", "content": "Pi binary not found"}

    with patch("src.managers.self_upgrade_manager._git", new_callable=AsyncMock) as mock_git:
        mock_git.side_effect = [(0, ""), (0, "")]  # worktree prune, worktree add

        result = await sum_.run_feature_request("req1", "do something", frm)

    assert result is not None and "pi agent error" in result.lower()
    last_kwargs = frm.update.call_args_list[-1].kwargs
    assert last_kwargs.get("status") == "error"


@pytest.mark.asyncio
async def test_run_feature_request_test_failure_never_touches_main():
    """Unlike run_self_upgrade, a single failure is terminal - no retry loop,
    since a human is watching the request log and can just resubmit."""
    frm = make_feature_requests_manager()

    async def fake_run_pi_agent(prompt, cwd=None):
        yield {"type": "file_change", "content": "Editing: src/foo.py"}
        yield {"type": "completed", "content": "done"}

    with patch("src.managers.self_upgrade_manager._git", new_callable=AsyncMock) as mock_git, \
         patch("src.managers.self_upgrade_manager._run", new_callable=AsyncMock) as mock_run, \
         patch("src.managers.self_upgrade_manager.run_pi_agent", fake_run_pi_agent), \
         patch("src.managers.self_upgrade_manager._cleanup_worktree", new_callable=AsyncMock) as mock_cleanup:

        mock_git.side_effect = [
            (0, ""),   # worktree prune
            (0, ""),   # worktree add
            (0, ""),   # add -A
            (1, ""),   # diff --cached --quiet -> has a diff
            (0, ""),   # commit
        ]
        mock_run.return_value = (1, "FAILED test_something")

        result = await sum_.run_feature_request("req1", "fix a bug", frm)

    assert result is not None and "test suite failed" in result.lower()
    git_calls = [c.args[0] for c in mock_git.await_args_list]
    assert not any(call[:1] == ["merge"] for call in git_calls)
    mock_cleanup.assert_not_awaited()  # branch/worktree preserved for inspection


@pytest.mark.asyncio
async def test_run_feature_request_commit_rejected_by_hook_is_terminal():
    frm = make_feature_requests_manager()

    async def fake_run_pi_agent(prompt, cwd=None):
        yield {"type": "file_change", "content": "Editing: src/foo.py"}
        yield {"type": "completed", "content": "done"}

    with patch("src.managers.self_upgrade_manager._git", new_callable=AsyncMock) as mock_git, \
         patch("src.managers.self_upgrade_manager.run_pi_agent", fake_run_pi_agent), \
         patch("src.managers.self_upgrade_manager._cleanup_worktree", new_callable=AsyncMock) as mock_cleanup:

        mock_git.side_effect = [
            (0, ""),                    # worktree prune
            (0, ""),                    # worktree add
            (0, ""),                    # add -A
            (1, ""),                    # diff --cached --quiet -> has a diff
            (1, "hook: lint failed"),   # commit REJECTED by hook
        ]

        result = await sum_.run_feature_request("req1", "fix a bug", frm)

    assert result is not None and "rejected by pre-commit hook" in result.lower()
    mock_cleanup.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_feature_request_missing_test_coverage_is_a_soft_warning():
    """Unlike run_self_upgrade, missing tests must not block the merge - too
    strict a bar for a human-submitted, human-watched request."""
    frm = make_feature_requests_manager()

    async def fake_run_pi_agent(prompt, cwd=None):
        yield {"type": "file_change", "content": "Editing: src/foo.py"}
        yield {"type": "completed", "content": "done"}

    with patch("src.managers.self_upgrade_manager._git", new_callable=AsyncMock) as mock_git, \
         patch("src.managers.self_upgrade_manager._run", new_callable=AsyncMock) as mock_run, \
         patch("src.managers.self_upgrade_manager.run_pi_agent", fake_run_pi_agent), \
         patch("src.managers.self_upgrade_manager._cleanup_worktree", new_callable=AsyncMock) as mock_cleanup, \
         patch("src.managers.self_upgrade_manager._restart_services") as mock_restart:

        mock_git.side_effect = [
            (0, ""),             # worktree prune
            (0, ""),             # worktree add
            (0, ""),             # add -A
            (1, ""),             # diff --cached --quiet -> has a diff
            (0, ""),             # commit
            (0, "src/foo.py"),   # diff --name-only main HEAD -> no test file
            (0, "main"),         # rev-parse --abbrev-ref HEAD -> on main
            (0, ""),             # status --porcelain -> clean
            (0, ""),             # merge --no-ff
        ]
        mock_run.return_value = (0, "5 passed")

        result = await sum_.run_feature_request("req1", "add a small tweak", frm)

    assert result is not None and "merged to main" in result.lower()
    assert "no test coverage was added" in result.lower()
    mock_cleanup.assert_awaited_once()
    mock_restart.assert_called_once()


@pytest.mark.asyncio
async def test_run_feature_request_aborts_merge_when_main_is_dirty():
    frm = make_feature_requests_manager()

    async def fake_run_pi_agent(prompt, cwd=None):
        yield {"type": "completed", "content": "done"}

    with patch("src.managers.self_upgrade_manager._git", new_callable=AsyncMock) as mock_git, \
         patch("src.managers.self_upgrade_manager._run", new_callable=AsyncMock) as mock_run, \
         patch("src.managers.self_upgrade_manager.run_pi_agent", fake_run_pi_agent), \
         patch("src.managers.self_upgrade_manager._cleanup_worktree", new_callable=AsyncMock) as mock_cleanup:

        mock_git.side_effect = [
            (0, ""),                              # worktree prune
            (0, ""),                              # worktree add
            (0, ""),                              # add -A
            (1, ""),                              # diff --cached --quiet -> has a diff
            (0, ""),                              # commit
            (0, "src/foo.py\ntests/test_foo.py"),  # diff --name-only main HEAD
            (0, "main"),                           # rev-parse --abbrev-ref HEAD -> on main
            (0, " M some_file.py"),               # status --porcelain -> DIRTY
        ]
        mock_run.return_value = (0, "5 passed")

        result = await sum_.run_feature_request("req1", "fix a bug", frm)

    assert result is not None and "uncommitted changes" in result.lower()
    git_calls = [c.args[0] for c in mock_git.await_args_list]
    assert not any(call[:1] == ["merge"] for call in git_calls)
    mock_cleanup.assert_not_awaited()
    # Deferred, not a dead end - retry_pending_merges retries this automatically
    # once main is clean, so it's marked merge_pending rather than error.
    status_calls = [c.kwargs.get("status") for c in frm.update.call_args_list]
    assert "merge_pending" in status_calls
    assert "error" not in status_calls


@pytest.mark.asyncio
async def test_run_feature_request_aborts_when_main_worktree_not_on_main():
    frm = make_feature_requests_manager()

    async def fake_run_pi_agent(prompt, cwd=None):
        yield {"type": "completed", "content": "done"}

    with patch("src.managers.self_upgrade_manager._git", new_callable=AsyncMock) as mock_git, \
         patch("src.managers.self_upgrade_manager._run", new_callable=AsyncMock) as mock_run, \
         patch("src.managers.self_upgrade_manager.run_pi_agent", fake_run_pi_agent), \
         patch("src.managers.self_upgrade_manager._cleanup_worktree", new_callable=AsyncMock) as mock_cleanup:

        mock_git.side_effect = [
            (0, ""),                               # worktree prune
            (0, ""),                               # worktree add
            (0, ""),                               # add -A
            (1, ""),                               # diff --cached --quiet -> has a diff
            (0, ""),                               # commit
            (0, "src/foo.py\ntests/test_foo.py"),   # diff --name-only main HEAD
            (0, "some-other-branch"),              # rev-parse --abbrev-ref HEAD -> NOT main
        ]
        mock_run.return_value = (0, "5 passed")

        result = await sum_.run_feature_request("req1", "fix a bug", frm)

    assert result is not None and "not main" in result.lower()
    git_calls = [c.args[0] for c in mock_git.await_args_list]
    assert not any(call[:1] == ["status"] for call in git_calls)  # short-circuited before the dirty check
    assert not any(call[:1] == ["merge"] for call in git_calls)
    mock_cleanup.assert_not_awaited()
    status_calls = [c.kwargs.get("status") for c in frm.update.call_args_list]
    assert "merge_pending" in status_calls


@pytest.mark.asyncio
async def test_run_feature_request_happy_path_merges_and_restarts_after_pi_exits():
    """The core fix under test: services are only restarted via a detached,
    fire-and-forget call made by this orchestrator - never by Pi's own bash
    tool - and only after Pi has already fully exited and everything is
    merged. Confirms _restart_services is called exactly once, after commit
    and merge, not from inside the run_pi_agent event loop."""
    frm = make_feature_requests_manager()
    call_order = []

    async def fake_run_pi_agent(prompt, cwd=None):
        call_order.append("pi_agent_ran")
        yield {"type": "file_change", "content": "Editing: chatty_web_server.py"}
        yield {"type": "completed", "content": "done"}

    def fake_restart(services):
        call_order.append("restart_services")

    with patch("src.managers.self_upgrade_manager._git", new_callable=AsyncMock) as mock_git, \
         patch("src.managers.self_upgrade_manager._run", new_callable=AsyncMock) as mock_run, \
         patch("src.managers.self_upgrade_manager.run_pi_agent", fake_run_pi_agent), \
         patch("src.managers.self_upgrade_manager._cleanup_worktree", new_callable=AsyncMock) as mock_cleanup, \
         patch("src.managers.self_upgrade_manager._restart_services", side_effect=fake_restart) as mock_restart:

        mock_git.side_effect = [
            (0, ""),                                          # worktree prune
            (0, ""),                                          # worktree add
            (0, ""),                                          # add -A
            (1, ""),                                          # diff --cached --quiet -> has a diff
            (0, ""),                                          # commit
            (0, "chatty_web_server.py\ntests/test_foo.py"),   # diff --name-only main HEAD
            (0, "main"),                                      # rev-parse --abbrev-ref HEAD -> on main
            (0, ""),                                          # status --porcelain -> clean
            (0, ""),                                          # merge --no-ff
        ]
        mock_run.return_value = (0, "5 passed")

        result = await sum_.run_feature_request("req1", "monitor server health", frm)

    assert result is not None and "merged to main" in result.lower()
    assert call_order == ["pi_agent_ran", "restart_services"]
    mock_restart.assert_called_once()
    restarted_services = mock_restart.call_args.args[0]
    assert "chatty-web-server" in restarted_services
    mock_cleanup.assert_awaited_once()
    completed_calls = [c for c in frm.update.call_args_list if c.kwargs.get("status") == "completed"]
    assert len(completed_calls) == 1
