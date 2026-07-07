"""Tests for src/managers/self_upgrade_manager.py - the safety-critical
branches of the self-upgrade pipeline (dirty-main check, wrong-branch check,
test-gate failure, no-op idea, lock unavailability). Git/Pi/the restart
signal are all mocked here; see tests/test_self_upgrade_git_integration.py
for a real-git smoke test of the worktree/merge plumbing.
"""
import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.managers import self_upgrade_manager as sum_


def test_slugify():
    assert sum_._slugify("Add a skill that tracks weather alerts!") == "add-a-skill-that-tracks-weather-alerts"
    assert sum_._slugify("") == "upgrade"
    assert sum_._slugify("???") == "upgrade"


def test_affected_services_backend_only():
    assert sum_._affected_services(["src/main.py", "skills/foo/tools.py"]) == ["chatty-bot", "chatty-web-server"]


def test_affected_services_frontend_only():
    assert sum_._affected_services(["order_explorer_site/frontend/src/App.tsx"]) == ["order-explorer-frontend"]


def test_affected_services_order_backend_only():
    assert sum_._affected_services(["order_explorer_site/backend/main.py"]) == ["order-explorer-backend"]


def test_affected_services_mixed():
    services = sum_._affected_services([
        "src/main.py",
        "order_explorer_site/frontend/src/App.tsx",
        "order_explorer_site/backend/main.py",
    ])
    assert set(services) == {"chatty-bot", "chatty-web-server", "order-explorer-frontend", "order-explorer-backend"}


def test_missing_test_coverage_true_when_only_source_changed():
    assert sum_._missing_test_coverage(["src/foo.py"]) is True


def test_missing_test_coverage_false_when_test_file_present():
    assert sum_._missing_test_coverage(["src/foo.py", "tests/test_foo.py"]) is False


def test_missing_test_coverage_false_for_docs_only():
    assert sum_._missing_test_coverage(["docs/heartbeat.md"]) is False


def test_missing_test_coverage_false_when_only_tests_changed():
    assert sum_._missing_test_coverage(["tests/test_foo.py"]) is False


@pytest.mark.asyncio
async def test_restart_services_writes_signal_file_when_no_pm2(tmp_path):
    """Under Docker there's no pm2 - _restart_services writes a JSON signal
    file for the restarter sidecar (docker/restarter/) instead of shelling
    out. This exercises the real function body, not a mock of it."""
    with patch("src.managers.self_upgrade_manager.config.RESTART_REQUESTS_DIR", tmp_path), \
         patch("src.managers.self_upgrade_manager.shutil.which", return_value=None):
        await sum_._restart_services(["chatty-web-server", "order-explorer-frontend"])

    written = list(tmp_path.glob("*.json"))
    assert len(written) == 1
    payload = json.loads(written[0].read_text())
    assert payload["services"] == ["chatty-web-server", "order-explorer-frontend"]
    assert "requested_at" in payload
    # No leftover temp file from the atomic write-then-rename.
    assert not list(tmp_path.glob("*.tmp"))


@pytest.mark.asyncio
async def test_restart_services_noop_for_empty_list(tmp_path):
    with patch("src.managers.self_upgrade_manager.config.RESTART_REQUESTS_DIR", tmp_path), \
         patch("src.managers.self_upgrade_manager.shutil.which", return_value=None):
        await sum_._restart_services([])
    assert list(tmp_path.glob("*.json")) == []


@pytest.mark.asyncio
async def test_restart_services_uses_pm2_when_available(tmp_path):
    """On a bare-metal/pm2 deployment (this host), restart directly instead
    of writing a signal file nothing is polling for - the real bug found
    while clearing a backlog of merge_pending requests: signal files had
    been piling up unconsumed since this host runs pm2, not Docker."""
    with patch("src.managers.self_upgrade_manager.config.RESTART_REQUESTS_DIR", tmp_path), \
         patch("src.managers.self_upgrade_manager.shutil.which", return_value="/usr/bin/pm2"), \
         patch("src.managers.self_upgrade_manager._run", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = (0, "restarted")
        await sum_._restart_services(["chatty-web-server", "order-explorer-frontend"])

    mock_run.assert_awaited_once()
    args = mock_run.await_args.args[0]
    assert args == ["pm2", "restart", "chatty-web-server", "order-explorer-frontend"]
    assert list(tmp_path.glob("*.json")) == []  # no Docker signal file written


@pytest.mark.asyncio
async def test_restart_services_pm2_failure_is_logged_not_raised(tmp_path):
    with patch("src.managers.self_upgrade_manager.shutil.which", return_value="/usr/bin/pm2"), \
         patch("src.managers.self_upgrade_manager._run", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = (1, "process not found")
        await sum_._restart_services(["nonexistent-service"])  # must not raise


def make_feature_requests_manager():
    frm = MagicMock()
    request = MagicMock()
    request.id = "req1"
    frm.create.return_value = request
    return frm, request


@pytest.mark.asyncio
async def test_run_self_upgrade_skips_when_lock_unavailable():
    with patch("src.managers.self_upgrade_manager.pi_lock.acquire", return_value=False):
        frm, _ = make_feature_requests_manager()
        result = await sum_.run_self_upgrade("do something", frm, AsyncMock(), "user1")

    assert result is None
    frm.create.assert_not_called()


@pytest.mark.asyncio
async def test_run_self_upgrade_no_changes_is_a_clean_noop():
    frm, request = make_feature_requests_manager()
    send = AsyncMock()

    async def fake_run_pi_agent(prompt, cwd=None):
        yield {"type": "completed", "content": "done, no changes needed"}

    with patch("src.managers.self_upgrade_manager.pi_lock.acquire", return_value=True), \
         patch("src.managers.self_upgrade_manager.pi_lock.release") as mock_release, \
         patch("src.managers.self_upgrade_manager._git", new_callable=AsyncMock) as mock_git, \
         patch("src.managers.self_upgrade_manager.run_pi_agent", fake_run_pi_agent), \
         patch("src.managers.self_upgrade_manager._cleanup_worktree", new_callable=AsyncMock) as mock_cleanup:

        # worktree add succeeds; `git add -A` then `diff --cached --quiet` reports no diff (rc=0)
        mock_git.side_effect = [
            (0, ""),   # worktree prune
            (0, ""),   # fetch origin
            (0, ""),   # rev-list main..origin/main --count -> empty means no new commits
            (0, ""),   # worktree add
            (0, ""),   # add -A
            (0, ""),   # diff --cached --quiet -> 0 means NO diff
        ]

        result = await sum_.run_self_upgrade("do something", frm, send, "user1")

    assert result is None
    frm.update.assert_any_call(request.id, status="completed", summary="No changes were necessary.")
    mock_cleanup.assert_awaited_once()
    mock_release.assert_called_once_with("self_upgrade")
    send.assert_not_awaited()  # no-op ideas don't need a notification


@pytest.mark.asyncio
async def test_run_self_upgrade_test_failure_never_touches_main():
    frm, request = make_feature_requests_manager()
    send = AsyncMock()

    async def fake_run_pi_agent(prompt, cwd=None):
        yield {"type": "file_change", "content": "Editing: src/foo.py"}
        yield {"type": "completed", "content": "done"}

    with patch("src.managers.self_upgrade_manager.pi_lock.acquire", return_value=True), \
         patch("src.managers.self_upgrade_manager.pi_lock.release") as mock_release, \
         patch("src.managers.self_upgrade_manager._git", new_callable=AsyncMock) as mock_git, \
         patch("src.managers.self_upgrade_manager._run", new_callable=AsyncMock) as mock_run, \
         patch("src.managers.self_upgrade_manager.run_pi_agent", fake_run_pi_agent), \
         patch("src.managers.self_upgrade_manager._cleanup_worktree", new_callable=AsyncMock) as mock_cleanup, \
         patch("src.managers.self_upgrade_manager.config.SELF_UPGRADE_MAX_TEST_ATTEMPTS", 1):

        mock_git.side_effect = [
            (0, ""),           # worktree prune
            (0, ""),           # fetch origin
            (0, ""),           # rev-list main..origin/main --count -> empty means no new commits
            (0, ""),           # worktree add
            (0, ""),           # add -A
            (1, ""),           # diff --cached --quiet -> 1 means there IS a diff
            (0, ""),           # commit
            (0, "src/foo.py"),  # diff --name-only main HEAD
        ]
        mock_run.return_value = (1, "FAILED test_something")  # pytest fails, every attempt

        result = await sum_.run_self_upgrade("fix a bug", frm, send, "user1")

    assert result is not None and "failed" in result.lower()
    # Test failure must be a terminal error - no merge/rev-parse/status call should follow.
    git_calls = [c.args[0] for c in mock_git.await_args_list]
    assert not any(call[:1] == ["merge"] for call in git_calls)
    assert not any(call[:1] == ["status"] for call in git_calls)
    mock_cleanup.assert_not_awaited()  # branch/worktree preserved for inspection
    last_update_kwargs = frm.update.call_args_list[-1].kwargs
    assert last_update_kwargs.get("status") == "error"
    assert "test suite failed" in last_update_kwargs.get("summary", "").lower()
    mock_release.assert_called_once_with("self_upgrade")


@pytest.mark.asyncio
async def test_run_self_upgrade_retries_after_test_failure_then_succeeds():
    """A failing test suite should get fed back to Pi for a fix attempt, not fail immediately."""
    frm, request = make_feature_requests_manager()
    send = AsyncMock()
    pi_call_count = 0

    async def fake_run_pi_agent(prompt, cwd=None):
        nonlocal pi_call_count
        pi_call_count += 1
        if pi_call_count == 2:
            # The retry prompt should include the previous failure's output.
            assert "FAILED test_something" in prompt
        yield {"type": "file_change", "content": "Editing: src/foo.py"}
        yield {"type": "completed", "content": "done"}

    with patch("src.managers.self_upgrade_manager.pi_lock.acquire", return_value=True), \
         patch("src.managers.self_upgrade_manager.pi_lock.release"), \
         patch("src.managers.self_upgrade_manager._git", new_callable=AsyncMock) as mock_git, \
         patch("src.managers.self_upgrade_manager._run", new_callable=AsyncMock) as mock_run, \
         patch("src.managers.self_upgrade_manager.run_pi_agent", fake_run_pi_agent), \
         patch("src.managers.self_upgrade_manager._cleanup_worktree", new_callable=AsyncMock), \
         patch("src.managers.self_upgrade_manager._restart_services"), \
         patch("src.managers.self_upgrade_manager.config.SELF_UPGRADE_MAX_TEST_ATTEMPTS", 2):

        mock_git.side_effect = [
            (0, ""),             # worktree prune
            (0, ""),             # fetch origin
            (0, ""),             # rev-list main..origin/main --count -> empty means no new commits
            (0, ""),             # worktree add
            (0, ""),             # attempt 1: add -A
            (1, ""),             # attempt 1: diff --cached --quiet -> has a diff
            (0, ""),             # attempt 1: commit
            (0, ""),             # attempt 2: add -A
            (1, ""),             # attempt 2: diff --cached --quiet -> has a diff
            (0, ""),             # attempt 2: commit
            (0, "src/foo.py\ntests/test_foo.py"),   # diff --name-only main HEAD (after loop)
            (0, "main"),         # rev-parse --abbrev-ref HEAD -> on main
            (0, ""),             # status --porcelain -> clean
            (0, ""),             # merge --no-ff
        ]
        mock_run.side_effect = [
            (1, "FAILED test_something"),  # attempt 1: pytest fails
            (0, "5 passed"),                # attempt 2: pytest passes
        ]

        result = await sum_.run_self_upgrade("fix a bug", frm, send, "user1")

    assert pi_call_count == 2
    assert result is not None and "merged" in result.lower()
    completed_calls = [c for c in frm.update.call_args_list if c.kwargs.get("status") == "completed"]
    assert len(completed_calls) == 1


@pytest.mark.asyncio
async def test_run_self_upgrade_gives_up_after_max_attempts():
    frm, request = make_feature_requests_manager()
    send = AsyncMock()

    async def fake_run_pi_agent(prompt, cwd=None):
        yield {"type": "file_change", "content": "Editing: src/foo.py"}
        yield {"type": "completed", "content": "done"}

    with patch("src.managers.self_upgrade_manager.pi_lock.acquire", return_value=True), \
         patch("src.managers.self_upgrade_manager.pi_lock.release"), \
         patch("src.managers.self_upgrade_manager._git", new_callable=AsyncMock) as mock_git, \
         patch("src.managers.self_upgrade_manager._run", new_callable=AsyncMock) as mock_run, \
         patch("src.managers.self_upgrade_manager.run_pi_agent", fake_run_pi_agent), \
         patch("src.managers.self_upgrade_manager._cleanup_worktree", new_callable=AsyncMock) as mock_cleanup, \
         patch("src.managers.self_upgrade_manager.config.SELF_UPGRADE_MAX_TEST_ATTEMPTS", 2):

        mock_git.side_effect = [
            (0, ""),   # worktree prune
            (0, ""),   # fetch origin
            (0, ""),   # rev-list main..origin/main --count -> empty means no new commits
            (0, ""),   # worktree add
            (0, ""),   # attempt 1: add -A
            (1, ""),   # attempt 1: diff --cached --quiet -> has a diff
            (0, ""),   # attempt 1: commit
            (0, ""),   # attempt 2: add -A
            (1, ""),   # attempt 2: diff --cached --quiet -> has a diff
            (0, ""),   # attempt 2: commit
        ]
        mock_run.return_value = (1, "FAILED test_something")  # always fails

        result = await sum_.run_self_upgrade("fix a bug", frm, send, "user1")

    assert result is not None and "failed" in result.lower()
    assert "after 2 attempt" in result.lower()
    git_calls = [c.args[0] for c in mock_git.await_args_list]
    assert not any(call[:1] == ["merge"] for call in git_calls)
    mock_cleanup.assert_not_awaited()  # branch/worktree preserved for inspection


@pytest.mark.asyncio
async def test_run_self_upgrade_retries_when_commit_rejected_by_hook():
    """The pre-commit hook (lint/tests) rejecting a commit should retry, not fail immediately."""
    frm, request = make_feature_requests_manager()
    send = AsyncMock()
    pi_call_count = 0

    async def fake_run_pi_agent(prompt, cwd=None):
        nonlocal pi_call_count
        pi_call_count += 1
        if pi_call_count == 2:
            assert "rejected by the pre-commit hook" in prompt
        yield {"type": "file_change", "content": "Editing: src/foo.py"}
        yield {"type": "completed", "content": "done"}

    with patch("src.managers.self_upgrade_manager.pi_lock.acquire", return_value=True), \
         patch("src.managers.self_upgrade_manager.pi_lock.release"), \
         patch("src.managers.self_upgrade_manager._git", new_callable=AsyncMock) as mock_git, \
         patch("src.managers.self_upgrade_manager._run", new_callable=AsyncMock) as mock_run, \
         patch("src.managers.self_upgrade_manager.run_pi_agent", fake_run_pi_agent), \
         patch("src.managers.self_upgrade_manager._cleanup_worktree", new_callable=AsyncMock), \
         patch("src.managers.self_upgrade_manager._restart_services"), \
         patch("src.managers.self_upgrade_manager.config.SELF_UPGRADE_MAX_TEST_ATTEMPTS", 2):

        mock_git.side_effect = [
            (0, ""),                                  # worktree prune
            (0, ""),                                  # fetch origin
            (0, ""),                                  # rev-list main..origin/main --count -> empty means no new commits
            (0, ""),                                  # worktree add
            (0, ""),                                  # attempt 1: add -A
            (1, ""),                                  # attempt 1: diff --cached --quiet -> has a diff
            (1, "hook: lint failed"),                  # attempt 1: commit REJECTED by hook
            (0, ""),                                  # attempt 2: add -A
            (1, ""),                                  # attempt 2: diff --cached --quiet -> has a diff
            (0, ""),                                  # attempt 2: commit succeeds
            (0, "src/foo.py\ntests/test_foo.py"),      # diff --name-only main HEAD
            (0, "main"),                               # rev-parse --abbrev-ref HEAD -> on main
            (0, ""),                                   # status --porcelain -> clean
            (0, ""),                                   # merge --no-ff
        ]
        mock_run.return_value = (0, "5 passed")  # pytest passes once the commit lands

        result = await sum_.run_self_upgrade("fix a bug", frm, send, "user1")

    assert pi_call_count == 2
    assert result is not None and "merged" in result.lower()
    # pytest should only have been invoked once - the rejected commit never got that far.
    assert mock_run.await_count == 1


def test_is_infra_failure_detects_missing_binary():
    assert sum_._is_infra_failure("venv/bin/ruff: No such file or directory") is True
    assert sum_._is_infra_failure("bash: npx: command not found") is True
    assert sum_._is_infra_failure("venv/bin/python: Permission denied") is True


def test_is_infra_failure_false_for_real_lint_or_test_output():
    assert sum_._is_infra_failure("foo.py:3:1: F821 undefined name 'bar'") is False
    assert sum_._is_infra_failure("1 failed, 4 passed in 0.42s") is False


@pytest.mark.asyncio
async def test_run_self_upgrade_fails_fast_on_infra_failure_without_retry():
    """A commit rejection that's actually a broken toolchain (e.g. the
    pre-commit hook once resolving venv/ruff against the wrong worktree, see
    .githooks/pre-commit) must not be treated as a fixable lint/test failure
    - the Pi agent can't fix a missing binary by editing code, so retrying
    just burns every attempt on the same doomed commit."""
    frm, request = make_feature_requests_manager()
    send = AsyncMock()
    pi_call_count = 0

    async def fake_run_pi_agent(prompt, cwd=None):
        nonlocal pi_call_count
        pi_call_count += 1
        yield {"type": "file_change", "content": "Editing: src/foo.py"}
        yield {"type": "completed", "content": "done"}

    with patch("src.managers.self_upgrade_manager.pi_lock.acquire", return_value=True), \
         patch("src.managers.self_upgrade_manager.pi_lock.release"), \
         patch("src.managers.self_upgrade_manager._git", new_callable=AsyncMock) as mock_git, \
         patch("src.managers.self_upgrade_manager._run", new_callable=AsyncMock) as mock_run, \
         patch("src.managers.self_upgrade_manager.run_pi_agent", fake_run_pi_agent), \
         patch("src.managers.self_upgrade_manager._cleanup_worktree", new_callable=AsyncMock), \
         patch("src.managers.self_upgrade_manager._restart_services"), \
         patch("src.managers.self_upgrade_manager.config.SELF_UPGRADE_MAX_TEST_ATTEMPTS", 3):

        mock_git.side_effect = [
            (0, ""),                                                        # worktree prune
            (0, ""),                                                        # fetch origin
            (0, ""),                                                        # rev-list main..origin/main --count -> empty means no new commits
            (0, ""),                                                        # worktree add
            (0, ""),                                                        # add -A
            (1, ""),                                                        # diff --cached --quiet -> has a diff
            (1, "venv/bin/ruff: No such file or directory\nFAILED"),        # commit rejected - infra, not lint
        ]

        result = await sum_.run_self_upgrade("fix a bug", frm, send, "user1")

    assert pi_call_count == 1  # no retry attempted
    assert result is not None and "failed" in result.lower()
    mock_run.assert_not_awaited()  # never even got to the pytest step


@pytest.mark.asyncio
async def test_run_self_upgrade_retries_when_test_coverage_missing():
    """Passing tests aren't enough - a source-only change should be sent back for a test."""
    frm, request = make_feature_requests_manager()
    send = AsyncMock()
    pi_call_count = 0

    async def fake_run_pi_agent(prompt, cwd=None):
        nonlocal pi_call_count
        pi_call_count += 1
        if pi_call_count == 2:
            assert "didn't add or update any test" in prompt
            yield {"type": "file_change", "content": "Editing: tests/test_foo.py"}
        else:
            yield {"type": "file_change", "content": "Editing: src/foo.py"}
        yield {"type": "completed", "content": "done"}

    with patch("src.managers.self_upgrade_manager.pi_lock.acquire", return_value=True), \
         patch("src.managers.self_upgrade_manager.pi_lock.release"), \
         patch("src.managers.self_upgrade_manager._git", new_callable=AsyncMock) as mock_git, \
         patch("src.managers.self_upgrade_manager._run", new_callable=AsyncMock) as mock_run, \
         patch("src.managers.self_upgrade_manager.run_pi_agent", fake_run_pi_agent), \
         patch("src.managers.self_upgrade_manager._cleanup_worktree", new_callable=AsyncMock), \
         patch("src.managers.self_upgrade_manager._restart_services"), \
         patch("src.managers.self_upgrade_manager.config.SELF_UPGRADE_MAX_TEST_ATTEMPTS", 2):

        mock_git.side_effect = [
            (0, ""),                              # worktree prune
            (0, ""),                              # fetch origin
            (0, ""),                              # rev-list main..origin/main --count -> empty means no new commits
            (0, ""),                              # worktree add
            (0, ""),                              # attempt 1: add -A
            (1, ""),                              # attempt 1: diff --cached --quiet -> has a diff
            (0, ""),                              # attempt 1: commit
            (0, "src/foo.py"),                    # attempt 1: diff --name-only main HEAD -> no test file!
            (0, ""),                              # attempt 2: add -A
            (1, ""),                              # attempt 2: diff --cached --quiet -> has a diff
            (0, ""),                              # attempt 2: commit
            (0, "src/foo.py\ntests/test_foo.py"),  # attempt 2: diff --name-only main HEAD -> now has one
            (0, "main"),                           # rev-parse --abbrev-ref HEAD -> on main
            (0, ""),                               # status --porcelain -> clean
            (0, ""),                               # merge --no-ff
        ]
        mock_run.return_value = (0, "5 passed")

        result = await sum_.run_self_upgrade("fix a bug", frm, send, "user1")

    assert pi_call_count == 2
    assert result is not None and "merged" in result.lower()


@pytest.mark.asyncio
async def test_run_self_upgrade_aborts_merge_when_main_is_dirty():
    frm, request = make_feature_requests_manager()
    send = AsyncMock()

    async def fake_run_pi_agent(prompt, cwd=None):
        yield {"type": "completed", "content": "done"}

    with patch("src.managers.self_upgrade_manager.pi_lock.acquire", return_value=True), \
         patch("src.managers.self_upgrade_manager.pi_lock.release") as mock_release, \
         patch("src.managers.self_upgrade_manager._git", new_callable=AsyncMock) as mock_git, \
         patch("src.managers.self_upgrade_manager._run", new_callable=AsyncMock) as mock_run, \
         patch("src.managers.self_upgrade_manager.run_pi_agent", fake_run_pi_agent), \
         patch("src.managers.self_upgrade_manager._cleanup_worktree", new_callable=AsyncMock) as mock_cleanup:

        mock_git.side_effect = [
            (0, ""),             # worktree prune
            (0, ""),             # fetch origin
            (0, ""),             # rev-list main..origin/main --count -> empty means no new commits
            (0, ""),             # worktree add
            (0, ""),             # add -A
            (1, ""),             # diff --cached --quiet -> has a diff
            (0, ""),             # commit
            (0, "src/foo.py\ntests/test_foo.py"),   # diff --name-only main HEAD
            (0, "main"),         # rev-parse --abbrev-ref HEAD -> on main
            (0, " M some_file.py"),  # status --porcelain -> DIRTY
        ]
        mock_run.return_value = (0, "5 passed")  # pytest succeeds

        result = await sum_.run_self_upgrade("fix a bug", frm, send, "user1")

    # Deferred, not failed - a dirty main is retried automatically (see
    # retry_pending_merges), not a dead end requiring manual intervention.
    assert result is not None and "deferred" in result.lower()
    git_calls = [c.args[0] for c in mock_git.await_args_list]
    assert not any(call[:1] == ["merge"] for call in git_calls)  # never attempted
    mock_cleanup.assert_not_awaited()
    mock_release.assert_called_once_with("self_upgrade")
    status_calls = [c.kwargs.get("status") for c in frm.update.call_args_list]
    assert "merge_pending" in status_calls
    assert "error" not in status_calls
    sent_msg = send.await_args.args[1]
    assert "uncommitted changes" in sent_msg


@pytest.mark.asyncio
async def test_run_self_upgrade_aborts_when_main_worktree_not_on_main():
    frm, request = make_feature_requests_manager()
    send = AsyncMock()

    async def fake_run_pi_agent(prompt, cwd=None):
        yield {"type": "completed", "content": "done"}

    with patch("src.managers.self_upgrade_manager.pi_lock.acquire", return_value=True), \
         patch("src.managers.self_upgrade_manager.pi_lock.release"), \
         patch("src.managers.self_upgrade_manager._git", new_callable=AsyncMock) as mock_git, \
         patch("src.managers.self_upgrade_manager._run", new_callable=AsyncMock) as mock_run, \
         patch("src.managers.self_upgrade_manager.run_pi_agent", fake_run_pi_agent), \
         patch("src.managers.self_upgrade_manager._cleanup_worktree", new_callable=AsyncMock) as mock_cleanup:

        mock_git.side_effect = [
            (0, ""),                    # worktree prune
            (0, ""),                    # fetch origin
            (0, ""),                    # rev-list main..origin/main --count -> empty means no new commits
            (0, ""),                    # worktree add
            (0, ""),                    # add -A
            (1, ""),                    # diff --cached --quiet -> has a diff
            (0, ""),                    # commit
            (0, "src/foo.py\ntests/test_foo.py"),          # diff --name-only main HEAD
            (0, "some-other-branch"),   # rev-parse --abbrev-ref HEAD -> NOT main
        ]
        mock_run.return_value = (0, "5 passed")

        result = await sum_.run_self_upgrade("fix a bug", frm, send, "user1")

    assert result is not None and "deferred" in result.lower()
    git_calls = [c.args[0] for c in mock_git.await_args_list]
    assert not any(call[:1] == ["status"] for call in git_calls)  # short-circuited before the dirty check
    assert not any(call[:1] == ["merge"] for call in git_calls)
    mock_cleanup.assert_not_awaited()
    status_calls = [c.kwargs.get("status") for c in frm.update.call_args_list]
    assert "merge_pending" in status_calls


@pytest.mark.asyncio
async def test_run_self_upgrade_happy_path_merges_and_restarts():
    frm, request = make_feature_requests_manager()
    send = AsyncMock()

    async def fake_run_pi_agent(prompt, cwd=None):
        yield {"type": "file_change", "content": "Editing: src/foo.py"}
        yield {"type": "completed", "content": "done"}

    with patch("src.managers.self_upgrade_manager.pi_lock.acquire", return_value=True), \
         patch("src.managers.self_upgrade_manager.pi_lock.release") as mock_release, \
         patch("src.managers.self_upgrade_manager._git", new_callable=AsyncMock) as mock_git, \
         patch("src.managers.self_upgrade_manager._run", new_callable=AsyncMock) as mock_run, \
         patch("src.managers.self_upgrade_manager.run_pi_agent", fake_run_pi_agent), \
         patch("src.managers.self_upgrade_manager._cleanup_worktree", new_callable=AsyncMock) as mock_cleanup, \
         patch("src.managers.self_upgrade_manager._restart_services") as mock_restart:

        mock_git.side_effect = [
            (0, ""),             # worktree prune
            (0, ""),             # fetch origin
            (0, ""),             # rev-list main..origin/main --count -> empty means no new commits
            (0, ""),             # worktree add
            (0, ""),             # add -A
            (1, ""),             # diff --cached --quiet -> has a diff
            (0, ""),             # commit
            (0, "src/foo.py\ntests/test_foo.py"),   # diff --name-only main HEAD
            (0, "main"),         # rev-parse --abbrev-ref HEAD -> on main
            (0, ""),             # status --porcelain -> CLEAN
            (0, ""),             # merge --no-ff
        ]
        mock_run.return_value = (0, "5 passed")

        result = await sum_.run_self_upgrade("fix a bug", frm, send, "user1")

    assert result is not None and "merged" in result.lower()
    completed_calls = [c for c in frm.update.call_args_list if c.kwargs.get("status") == "completed"]
    assert len(completed_calls) == 1
    assert "merged to main" in completed_calls[0].kwargs.get("summary", "").lower()
    mock_cleanup.assert_awaited_once()
    mock_release.assert_called_once_with("self_upgrade")
    mock_restart.assert_called_once()
    restarted_services = mock_restart.call_args.args[0]
    assert "chatty-bot" in restarted_services


# ── _sync_main_with_origin ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sync_main_with_origin_noop_when_origin_not_ahead():
    """Fetch succeeds, but origin/main is not ahead — nothing to do."""
    with patch("src.managers.self_upgrade_manager._git", new_callable=AsyncMock) as mock_git:
        mock_git.side_effect = [
            (0, ""),     # fetch origin
            (0, "0"),    # rev-list main..origin/main --count -> 0
        ]
        await sum_._sync_main_with_origin(Path("/fake"))

    git_calls = [c.args[0] for c in mock_git.await_args_list]
    assert git_calls[0] == ["fetch", "origin"]
    assert git_calls[1] == ["rev-list", "main..origin/main", "--count"]
    # Should NOT call merge
    assert not any(call[:1] == ["merge"] for call in git_calls)


@pytest.mark.asyncio
async def test_sync_main_with_origin_noop_on_empty_revlist_output():
    """rev-list returns empty string — treat as 0 (no new commits)."""
    with patch("src.managers.self_upgrade_manager._git", new_callable=AsyncMock) as mock_git:
        mock_git.side_effect = [
            (0, ""),     # fetch origin
            (0, ""),     # rev-list returns empty string
        ]
        await sum_._sync_main_with_origin(Path("/fake"))

    git_calls = [c.args[0] for c in mock_git.await_args_list]
    assert not any(call[:1] == ["merge"] for call in git_calls)


@pytest.mark.asyncio
async def test_sync_main_with_origin_fast_forwards_when_origin_ahead():
    """origin/main has new commits — fast-forward merge into local main."""
    with patch("src.managers.self_upgrade_manager._git", new_callable=AsyncMock) as mock_git:
        mock_git.side_effect = [
            (0, ""),     # fetch origin
            (0, "3"),    # rev-list main..origin/main --count -> 3 new commits
            (0, ""),     # merge --ff-only origin/main
        ]
        await sum_._sync_main_with_origin(Path("/fake"))

    git_calls = [c.args[0] for c in mock_git.await_args_list]
    assert git_calls[-1] == ["merge", "--ff-only", "origin/main"]


@pytest.mark.asyncio
async def test_sync_main_with_origin_noop_when_no_remote_tracking():
    """origin/main doesn't exist (no remote) — rev-list fails, no-op."""
    with patch("src.managers.self_upgrade_manager._git", new_callable=AsyncMock) as mock_git:
        mock_git.side_effect = [
            (0, ""),     # fetch origin
            (1, "fatal: ambiguous argument 'origin/main'"),  # rev-list fails
        ]
        await sum_._sync_main_with_origin(Path("/fake"))

    git_calls = [c.args[0] for c in mock_git.await_args_list]
    assert not any(call[:1] == ["merge"] for call in git_calls)


@pytest.mark.asyncio
async def test_sync_main_with_origin_raises_on_fetch_failure():
    """Fetch fails — raise RuntimeError."""
    with patch("src.managers.self_upgrade_manager._git", new_callable=AsyncMock) as mock_git:
        mock_git.return_value = (1, "fatal: unable to access origin")

        with pytest.raises(RuntimeError, match="git fetch origin failed"):
            await sum_._sync_main_with_origin(Path("/fake"))


@pytest.mark.asyncio
async def test_sync_main_with_origin_raises_on_ff_only_conflict():
    """--ff-only fails because local main has diverging changes — raise."""
    with patch("src.managers.self_upgrade_manager._git", new_callable=AsyncMock) as mock_git:
        mock_git.side_effect = [
            (0, ""),     # fetch origin
            (0, "2"),    # rev-list main..origin/main --count -> 2 new commits
            (1, "error: Your local changes to the following files would be overwritten"),  # merge fails
        ]

        with pytest.raises(RuntimeError, match="Cannot fast-forward main to origin/main"):
            await sum_._sync_main_with_origin(Path("/fake"))


# ── retry_pending_merges ──────────────────────────────────────────────────

def make_pending_request(request_id="req1", branch="feature-request/fix-thing-123", source="user", prompt="fix a bug"):
    request = MagicMock()
    request.id = request_id
    request.branch = branch
    request.source = source
    request.prompt = prompt
    return request


@pytest.mark.asyncio
async def test_retry_pending_merges_noop_when_queue_empty():
    frm = MagicMock()
    frm.list_pending_merges.return_value = []

    with patch("src.managers.self_upgrade_manager.pi_lock.acquire") as mock_acquire, \
         patch("src.managers.self_upgrade_manager._git", new_callable=AsyncMock) as mock_git:

        result = await sum_.retry_pending_merges(frm)

    assert result == []
    mock_acquire.assert_not_called()
    mock_git.assert_not_awaited()


@pytest.mark.asyncio
async def test_retry_pending_merges_skips_when_lock_unavailable():
    frm = MagicMock()
    frm.list_pending_merges.return_value = [make_pending_request()]

    with patch("src.managers.self_upgrade_manager.pi_lock.acquire", return_value=False) as mock_acquire, \
         patch("src.managers.self_upgrade_manager._git", new_callable=AsyncMock) as mock_git:

        result = await sum_.retry_pending_merges(frm)

    assert result == []
    mock_acquire.assert_called_once_with("merge_retry")
    mock_git.assert_not_awaited()
    frm.update.assert_not_called()


@pytest.mark.asyncio
async def test_retry_pending_merges_leaves_request_untouched_when_still_dirty(tmp_path):
    frm = MagicMock()
    request = make_pending_request(branch="feature-request/fix-thing-123")
    frm.list_pending_merges.return_value = [request]

    worktree_dir = tmp_path / "fix-thing-123"
    worktree_dir.mkdir()

    with patch("src.managers.self_upgrade_manager.config.SELF_UPGRADE_WORKTREES_DIR", tmp_path), \
         patch("src.managers.self_upgrade_manager.pi_lock.acquire", return_value=True), \
         patch("src.managers.self_upgrade_manager.pi_lock.release") as mock_release, \
         patch("src.managers.self_upgrade_manager._git", new_callable=AsyncMock) as mock_git:

        mock_git.side_effect = [
            (0, ""),                  # rev-parse --verify <branch>
            (0, "main"),              # rev-parse --abbrev-ref HEAD -> on main
            (0, " M some_file.py"),   # status --porcelain -> still dirty
        ]

        result = await sum_.retry_pending_merges(frm)

    assert result == []
    git_calls = [c.args[0] for c in mock_git.await_args_list]
    assert not any(call[:1] == ["merge"] for call in git_calls)
    frm.update.assert_not_called()  # left exactly as-is, retried again next tick
    mock_release.assert_called_once_with("merge_retry")


@pytest.mark.asyncio
async def test_retry_pending_merges_marks_error_when_branch_or_worktree_missing(tmp_path):
    frm = MagicMock()
    request = make_pending_request(branch="feature-request/fix-thing-123")
    frm.list_pending_merges.return_value = [request]

    with patch("src.managers.self_upgrade_manager.config.SELF_UPGRADE_WORKTREES_DIR", tmp_path), \
         patch("src.managers.self_upgrade_manager.pi_lock.acquire", return_value=True), \
         patch("src.managers.self_upgrade_manager.pi_lock.release"), \
         patch("src.managers.self_upgrade_manager._git", new_callable=AsyncMock) as mock_git:

        mock_git.side_effect = [(1, "fatal: not a valid ref")]  # rev-parse --verify fails

        result = await sum_.retry_pending_merges(frm)

    assert result == []
    frm.update.assert_called_once()
    assert frm.update.call_args.kwargs.get("status") == "error"
    assert "no longer exist" in frm.update.call_args.kwargs.get("summary", "").lower()


@pytest.mark.asyncio
async def test_retry_pending_merges_completes_once_main_is_clean(tmp_path):
    frm = MagicMock()
    request = make_pending_request(branch="feature-request/fix-thing-123", prompt="fix a bug")
    frm.list_pending_merges.return_value = [request]
    send = AsyncMock()

    worktree_dir = tmp_path / "fix-thing-123"
    worktree_dir.mkdir()

    with patch("src.managers.self_upgrade_manager.config.SELF_UPGRADE_WORKTREES_DIR", tmp_path), \
         patch("src.managers.self_upgrade_manager.pi_lock.acquire", return_value=True), \
         patch("src.managers.self_upgrade_manager.pi_lock.release") as mock_release, \
         patch("src.managers.self_upgrade_manager._git", new_callable=AsyncMock) as mock_git, \
         patch("src.managers.self_upgrade_manager._run", new_callable=AsyncMock) as mock_run, \
         patch("src.managers.self_upgrade_manager._cleanup_worktree", new_callable=AsyncMock) as mock_cleanup, \
         patch("src.managers.self_upgrade_manager._restart_services") as mock_restart:

        mock_git.side_effect = [
            (0, ""),                              # rev-parse --verify <branch>
            (0, "main"),                           # rev-parse --abbrev-ref HEAD -> on main
            (0, ""),                               # status --porcelain -> CLEAN now
            (0, "src/foo.py\ntests/test_foo.py"),  # diff --name-only main HEAD
            (0, ""),                               # merge --no-ff
        ]
        mock_run.return_value = (0, "")

        result = await sum_.retry_pending_merges(frm, send, "user1")

    assert len(result) == 1 and "completed" in result[0].lower()
    completed_calls = [c for c in frm.update.call_args_list if c.kwargs.get("status") == "completed"]
    assert len(completed_calls) == 1
    mock_cleanup.assert_awaited_once()
    mock_restart.assert_called_once()
    mock_release.assert_called_once_with("merge_retry")
    send.assert_awaited_once()
    assert "merge completed" in send.await_args.args[1].lower()
