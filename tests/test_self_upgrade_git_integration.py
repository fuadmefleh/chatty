"""Real-git smoke tests for the self-upgrade pipeline's worktree/merge/dirty-
check plumbing. Unlike test_self_upgrade_manager.py (which mocks _git
entirely), this runs actual `git` commands against a disposable scratch repo
to prove the worktree-create -> commit -> merge -> cleanup flow - and the
"never touch a dirty/wrong-branch main" safety gate - genuinely work, not
just that the mocked call sequence looks right.

Only run_pi_agent (no real Pi CLI), the pytest/npm test-gate subprocess
(_run's non-git commands), the pi_agent lock, and pm2 restart (_restart_services) are mocked.
"""
import asyncio
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.managers import self_upgrade_manager as sum_

# _git() itself calls _run() internally (they share the same subprocess
# primitive), so naively patching _run would silently intercept _git's calls
# too - defeating the point of this "real git" test. This fake dispatches
# git commands to the real implementation (captured before any patching) and
# only fakes the pytest/npm/npx test-gate invocations.
_real_run = sum_._run


async def _fake_run(args, cwd, timeout=120, env=None):
    if args and args[0] == "git":
        return await _real_run(args, cwd, timeout=timeout, env=env)
    return (0, "5 passed")


def _init_scratch_repo(repo_dir: Path) -> None:
    def run(args):
        result = subprocess.run(["git"] + args, cwd=repo_dir, capture_output=True, text=True)
        assert result.returncode == 0, f"git {args} failed: {result.stderr}"

    repo_dir.mkdir(parents=True, exist_ok=True)
    run(["init", "-b", "main"])
    run(["config", "user.email", "test@example.com"])
    run(["config", "user.name", "Test"])
    (repo_dir / "README.md").write_text("scratch repo\n")
    (repo_dir / "src").mkdir()
    (repo_dir / "src" / "existing.py").write_text("# existing file\n")
    run(["add", "-A"])
    run(["commit", "-m", "initial commit"])


async def _fake_pi_agent_writes_file(prompt, cwd=None):
    """Simulates Pi actually editing a file inside the given worktree."""
    new_file = Path(cwd) / "src" / "new_feature.py"
    new_file.write_text("# added by self-upgrade\n")
    yield {"type": "file_change", "content": f"Writing: src/new_feature.py"}
    yield {"type": "completed", "content": "Pi agent finished successfully."}


def make_feature_requests_manager():
    frm = MagicMock()
    request = MagicMock()
    request.id = "req1"
    frm.create.return_value = request
    return frm


@pytest.mark.asyncio
async def test_happy_path_actually_merges_into_real_main():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        repo_dir = tmp_path / "repo"
        worktrees_dir = tmp_path / "worktrees"
        _init_scratch_repo(repo_dir)

        frm = make_feature_requests_manager()
        send = AsyncMock()

        with patch("src.managers.self_upgrade_manager.config.BASE_DIR", repo_dir), \
             patch("src.managers.self_upgrade_manager.config.SELF_UPGRADE_WORKTREES_DIR", worktrees_dir), \
             patch("src.managers.self_upgrade_manager.pi_lock.acquire", return_value=True), \
             patch("src.managers.self_upgrade_manager.pi_lock.release"), \
             patch("src.managers.self_upgrade_manager.run_pi_agent", _fake_pi_agent_writes_file), \
             patch("src.managers.self_upgrade_manager._run", _fake_run), \
             patch("src.managers.self_upgrade_manager._restart_services") as mock_restart:

            result = await sum_.run_self_upgrade("add a new feature", frm, send, "user1")

        assert result is not None and "merged" in result.lower()

        # The change genuinely landed on main in the real scratch repo.
        assert (repo_dir / "src" / "new_feature.py").exists()

        # Main is clean and still on main.
        status = subprocess.run(["git", "status", "--porcelain"], cwd=repo_dir, capture_output=True, text=True)
        assert status.stdout.strip() == ""
        branch = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_dir, capture_output=True, text=True)
        assert branch.stdout.strip() == "main"

        # Worktree removed, branch deleted (merged, so -d succeeds).
        assert not worktrees_dir.exists() or not any(worktrees_dir.iterdir())
        branches = subprocess.run(["git", "branch", "--list"], cwd=repo_dir, capture_output=True, text=True)
        assert "self-upgrade/" not in branches.stdout

        # pm2 restart was issued (detached), not awaited.
        mock_restart.assert_called_once()


@pytest.mark.asyncio
async def test_dirty_main_blocks_merge_and_preserves_branch():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        repo_dir = tmp_path / "repo"
        worktrees_dir = tmp_path / "worktrees"
        _init_scratch_repo(repo_dir)

        # Simulate a human mid-edit on main - an uncommitted change.
        (repo_dir / "src" / "existing.py").write_text("# someone is editing this right now\n")

        frm = make_feature_requests_manager()
        send = AsyncMock()

        with patch("src.managers.self_upgrade_manager.config.BASE_DIR", repo_dir), \
             patch("src.managers.self_upgrade_manager.config.SELF_UPGRADE_WORKTREES_DIR", worktrees_dir), \
             patch("src.managers.self_upgrade_manager.pi_lock.acquire", return_value=True), \
             patch("src.managers.self_upgrade_manager.pi_lock.release"), \
             patch("src.managers.self_upgrade_manager.run_pi_agent", _fake_pi_agent_writes_file), \
             patch("src.managers.self_upgrade_manager._run", _fake_run), \
             patch("src.managers.self_upgrade_manager._restart_services") as mock_restart:

            result = await sum_.run_self_upgrade("add a new feature", frm, send, "user1")

        assert result is not None and "failed" in result.lower()

        # The uncommitted work on main must survive untouched.
        assert (repo_dir / "src" / "existing.py").read_text() == "# someone is editing this right now\n"
        # The self-upgrade's own change must NOT have landed on main.
        assert not (repo_dir / "src" / "new_feature.py").exists()

        # Branch/worktree preserved for manual inspection.
        branches = subprocess.run(["git", "branch", "--list"], cwd=repo_dir, capture_output=True, text=True)
        assert "self-upgrade/" in branches.stdout
        assert worktrees_dir.exists() and any(worktrees_dir.iterdir())

        mock_restart.assert_not_called()
