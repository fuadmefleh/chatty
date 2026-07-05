"""Self-upgrade pipeline: Chatty thinks up improvements to its own codebase
and implements them autonomously, with safety rails.

Flow, driven by HeartbeatManager._process_self_upgrade_ideas():
1. generate_self_upgrade_idea() - LLM reflects on its own skills, recent
   error logs, past self-upgrade attempts, and recent conversation history
   to propose ONE small, concrete improvement (or nothing).
2. run_self_upgrade() - implements it:
   a. Create an isolated git worktree on a new branch off main (never edits
      the live checkout directly).
   b. Run the Pi coding agent inside that worktree.
   c. Commit, then run the test suite (+ frontend typecheck/build if
      frontend files changed) inside the worktree.
   d. Only if the test gate passes AND the live main checkout has no
      uncommitted changes AND is actually on main: merge the branch into
      main and restart the affected pm2 services.
   e. Any failure at any stage leaves the branch/worktree in place for
      manual inspection - main is never touched unless the gate fully passes.

A cross-process file lock (skills/pi_agent/lock.py) prevents this from ever
running the `pi` CLI at the same time as the dashboard's manual feature
request queue (chatty_web_server.py), since they're separate OS processes.
"""
import asyncio
import json
import os
import re
import tempfile
import time
import uuid
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from src.core import config
from src.core.logging_config import get_heartbeat_logger
from skills.pi_agent import lock as pi_lock
from skills.pi_agent.runner import run_pi_agent

logger = get_heartbeat_logger()


async def _run(args: List[str], cwd: Path, timeout: int = 120, env: Optional[dict] = None) -> Tuple[int, str]:
    """Run a subprocess to completion, returning (returncode, combined output).

    Output is captured via a temp file rather than asyncio.subprocess.PIPE +
    communicate(). Some git operations spawn a short-lived background helper
    that inherits the parent's stdout/stderr fds; communicate() waits for the
    pipe to see EOF from *every* holder of the write end, so it can hang long
    after the actual `git` process has exited if that helper is still alive.
    Gating on the primary process's exit (proc.wait()) instead sidesteps that
    entirely.
    """
    with tempfile.TemporaryFile() as out_file:
        proc = await asyncio.create_subprocess_exec(
            *args,
            cwd=str(cwd),
            stdin=asyncio.subprocess.DEVNULL,  # never inherit stdin - can hang waiting on it
            stdout=out_file,
            stderr=asyncio.subprocess.STDOUT,
            env=env,
        )
        try:
            await asyncio.wait_for(proc.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            out_file.seek(0)
            partial = out_file.read().decode("utf-8", errors="replace")
            return -1, f"Command timed out after {timeout}s: {' '.join(args)}\n{partial}"

        out_file.seek(0)
        output = out_file.read().decode("utf-8", errors="replace")
        return proc.returncode, output


async def _git(args: List[str], cwd: Path, timeout: int = 60) -> Tuple[int, str]:
    return await _run(["git"] + args, cwd=cwd, timeout=timeout)


def _subprocess_env() -> dict:
    """Env for npm/pytest subprococesses - pm2-launched processes can have a
    stripped PATH/HOME (see skills/pi_agent/runner.py's _PI_ENV for the same
    issue with the `pi` binary)."""
    home = os.path.expanduser("~")
    node_bin = os.path.dirname(os.path.expanduser("~/.nvm/versions/node/v22.12.0/bin/pi"))
    venv_bin = str(config.BASE_DIR / "venv" / "bin")
    return {
        **os.environ,
        "HOME": home,
        "PATH": f"{venv_bin}:{node_bin}:{os.environ.get('PATH', '/usr/bin:/bin')}",
    }


def _slugify(text: str, max_len: int = 40) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    slug = slug[:max_len].strip("-")
    return slug or "upgrade"


# Repeated here (not just left for Pi to discover) because these are the
# concrete gates the commit/merge will actually be checked against - a
# pre-commit git hook (.githooks/pre-commit) independently re-runs all of
# this at commit time, so getting it right the first time avoids a wasted
# retry round-trip.
_CONVENTIONS = """This repo enforces, on every commit (via a git hook - you cannot bypass it):
- `ruff check --select E9,F` on any Python file you touch: no undefined names, no
  use-before-assignment, no syntax errors. Unused imports/variables are also flagged - clean them up.
- The full test suite (`pytest tests/`) must pass. pytest-asyncio is in auto mode, so async test
  functions do NOT need an @pytest.mark.asyncio decorator - just name them `test_...`.
- If you change any non-test, non-doc source file, you MUST also add or update a test that
  exercises the change, in the tests/ directory. A change with no corresponding test change will
  be sent back to you, even if the existing suite still passes."""


def _wrap_idea_prompt(idea_prompt: str) -> str:
    return f"{idea_prompt}\n\n{_CONVENTIONS}"


# Extra guidance for run_feature_request (web-dashboard requests), on top of
# the same lint/test gates: Pi runs inside an isolated worktree there too, so
# it must not try to restart or curl the live server as its own verification
# step. That would (a) not even prove anything, since the live process is
# running a different checkout until this worktree is tested and merged, and
# (b) previously killed the `pi` subprocess mid-turn, since it's a plain
# child of the very chatty-web-server process pm2 would be restarting - see
# skills/pi_agent/runner.py's PM2_SELF_APP_NAME handling for the narrower
# fix that covers requests made before this existed.
_WORKTREE_NOTE = """You are working inside an isolated git worktree, not the live running
server - chatty-web-server/chatty-bot are running a separate checkout and won't see your changes
until this worktree is tested and merged by the platform after you finish. Because of this:
- Do NOT run `pm2 restart`, `pm2 reload`, or `systemctl restart` on any service, and don't try to
  curl/verify against the live server - it's running different code than what you're editing, so
  that wouldn't prove anything anyway. The platform restarts the right services automatically once
  your change is merged.
- Verify your work with the test suite (`pytest tests/`) and, for frontend changes,
  `npx tsc --noEmit` / `npm run build` - not by exercising the live server."""


def _wrap_feature_request_prompt(prompt: str) -> str:
    return f"{prompt}\n\n{_CONVENTIONS}\n\n{_WORKTREE_NOTE}"


def _build_fix_prompt(idea_prompt: str, reason: str, details: str) -> str:
    return f"""You previously attempted this change:

{idea_prompt}

{reason} Fix the underlying issue - do not weaken or remove test assertions, or delete a failing
test, just to make the gate pass. Details:

{details[-3000:]}

{_CONVENTIONS}"""


def _missing_test_coverage(changed_files: List[str]) -> bool:
    """True if source files changed but no tests/ file changed alongside them."""
    source_files = [
        f for f in changed_files
        if not f.startswith("tests/") and not f.endswith(".md")
    ]
    test_files = [f for f in changed_files if f.startswith("tests/")]
    return bool(source_files) and not test_files


def _affected_services(changed_files: List[str]) -> List[str]:
    """Map changed file paths to the pm2 services that need restarting."""
    services: List[str] = []
    frontend_touched = any(f.startswith("order_explorer_site/frontend/") for f in changed_files)
    order_backend_touched = any(f.startswith("order_explorer_site/backend/") for f in changed_files)
    backend_touched = any(
        not f.startswith("order_explorer_site/frontend/") and not f.startswith("order_explorer_site/backend/")
        for f in changed_files
    )

    if backend_touched:
        services += ["chatty-bot", "chatty-web-server"]
    if frontend_touched:
        services.append("order-explorer-frontend")
    if order_backend_touched:
        services.append("order-explorer-backend")
    return services


def _restart_services(services: List[str]) -> None:
    """Request a restart of the given services.

    Under Docker (see docker-compose.yml), there's no pm2 - instead this
    writes an atomic signal file into config.RESTART_REQUESTS_DIR, which a
    sidecar container (docker/restarter/restart_watcher.py) polls and
    translates into `docker restart <container>` calls. That sidecar is the
    only container with the Docker socket mounted, deliberately kept out of
    the codebase self-upgrade can modify.

    This may indirectly cause the very process calling it (chatty-bot) to be
    restarted, but does so asynchronously via the sidecar - this function
    itself just writes a file and returns immediately. Kept as its own
    function so tests can assert on the written file instead of mocking
    subprocess/filesystem calls inline.
    """
    if not services:
        return
    config.RESTART_REQUESTS_DIR.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({"services": services, "requested_at": time.time()})
    tmp_path = config.RESTART_REQUESTS_DIR / f".{uuid.uuid4().hex}.tmp"
    final_path = config.RESTART_REQUESTS_DIR / f"{uuid.uuid4().hex}.json"
    tmp_path.write_text(payload)
    tmp_path.rename(final_path)  # atomic on the same filesystem


async def _cleanup_worktree(worktree_dir: Path, branch: str, delete_branch: bool) -> None:
    rc, out = await _git(["worktree", "remove", str(worktree_dir), "--force"], cwd=config.BASE_DIR)
    if rc != 0:
        logger.warning(f"Could not remove self-upgrade worktree {worktree_dir}: {out[:300]}")
    if delete_branch:
        rc, out = await _git(["branch", "-d", branch], cwd=config.BASE_DIR)
        if rc != 0:
            logger.warning(f"Could not delete self-upgrade branch {branch}: {out[:300]}")


async def generate_self_upgrade_idea(skills_manager, memory_manager, feature_requests_manager) -> Optional[str]:
    """Ask the LLM for ONE small, concrete self-upgrade idea, or None."""
    try:
        from openai import AsyncOpenAI

        skills_summary = "\n".join(
            f"- {s.name}: {s.description} ({len(s.tools)} tools)"
            for s in skills_manager.get_all_skills()
        ) or "(no skills loaded)"

        recent_errors = ""
        errors_log_path = config.BASE_DIR / "src" / "logs" / "errors.log"
        if errors_log_path.exists():
            try:
                lines = errors_log_path.read_text(encoding="utf-8", errors="replace").splitlines()
                recent_errors = "\n".join(lines[-60:])
            except Exception:
                pass

        past_ideas = [r.prompt for r in feature_requests_manager.list_by_source("self_upgrade")]
        past_ideas_text = "\n".join(f"- {p}" for p in past_ideas) if past_ideas else "(none yet)"

        recent_chat = ""
        try:
            recent_chat = await memory_manager.get_recent_memory(days=14)
        except Exception:
            pass

        prompt = f"""You are Chatty, a personal AI assistant, reflecting on your own capabilities as
part of your autonomous heartbeat. Come up with ONE concrete, scoped improvement you could make to
your own codebase - a new skill, a bug fix, or a UX improvement. It must be small enough for a
single coding-agent session to implement and test in one sitting (not a multi-day project), and
specific enough that a coding agent could act on it without needing to ask clarifying questions.

Your current skills:
{skills_summary}

Recent errors from your logs (may be empty or noise - use judgement, don't over-index on old/one-off errors):
{(recent_errors[-3000:] if recent_errors else "(no recent errors logged)")}

Upgrade ideas already attempted - do NOT repeat these or close variants of them:
{past_ideas_text}

Recent conversation history - look for moments where the user was frustrated, asked for something
you couldn't do, or a tool of yours failed them:
{(recent_chat[-4000:] if recent_chat else "(no recent conversation history)")}

Reply with EITHER:
1. A single paragraph describing the ONE upgrade to make, phrased as a direct instruction to a
   coding agent (e.g. "Add a skill that ..." / "Fix the bug where ..."), OR
2. Exactly: NONE

Only suggest something if you have a genuinely good, well-scoped idea grounded in the context
above. It's fine - and often correct - to reply NONE."""

        client = AsyncOpenAI(api_key=config.CHAT_API_KEY, base_url=config.CHAT_BASE_URL)
        response = await client.chat.completions.create(
            model=config.CHAT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
        )

        text = (response.choices[0].message.content or "").strip()
        if not text or text.upper() == "NONE":
            return None
        return text

    except Exception as e:
        logger.error(f"Error generating self-upgrade idea: {e}", exc_info=True)
        return None


async def run_self_upgrade(
    idea_prompt: str,
    feature_requests_manager,
    send_message_callback: Optional[Callable],
    user_id: str,
) -> Optional[str]:
    """Implement one self-upgrade idea end-to-end. Returns a one-line summary
    for the heartbeat digest, or None if skipped/a no-op."""

    if not pi_lock.acquire("self_upgrade"):
        logger.info("Self-upgrade skipped - pi agent lock held by another process")
        return None

    request = feature_requests_manager.create(idea_prompt, source="self_upgrade")
    slug = _slugify(idea_prompt)
    unique = int(time.time())
    branch = f"self-upgrade/{slug}-{unique}"
    worktree_dir = config.SELF_UPGRADE_WORKTREES_DIR / f"{slug}-{unique}"

    async def fail(reason: str, keep_worktree: bool = True) -> str:
        feature_requests_manager.update(request.id, status="error", summary=reason, branch=branch)
        feature_requests_manager.append_log(request.id, reason)
        if send_message_callback:
            msg = f"🔧 **Self-Upgrade Failed**\n\n{idea_prompt[:200]}\n\n{reason}"
            if keep_worktree:
                msg += f"\n\nBranch `{branch}` preserved at `{worktree_dir}` for manual review."
            try:
                await send_message_callback(user_id, msg)
            except Exception:
                pass
        pi_lock.release("self_upgrade")
        return f"🔧 Self-upgrade failed: {reason[:80]}"

    try:
        feature_requests_manager.update(request.id, status="running", branch=branch)
        config.SELF_UPGRADE_WORKTREES_DIR.mkdir(parents=True, exist_ok=True)

        await _git(["worktree", "prune"], cwd=config.BASE_DIR)
        rc, out = await _git(["worktree", "add", str(worktree_dir), "-b", branch, "main"], cwd=config.BASE_DIR)
        if rc != 0:
            return await fail(f"Could not create worktree: {out[:400]}", keep_worktree=False)
        feature_requests_manager.append_log(request.id, f"Created worktree at {worktree_dir} on branch {branch}")

        env = _subprocess_env()
        venv_python = str(config.BASE_DIR / "venv" / "bin" / "python")
        current_prompt = _wrap_idea_prompt(idea_prompt)
        max_attempts = max(config.SELF_UPGRADE_MAX_TEST_ATTEMPTS, 1)

        for attempt in range(1, max_attempts + 1):
            # Run Pi entirely inside the isolated worktree - never the live checkout.
            saw_completion = False
            async for event in run_pi_agent(current_prompt, cwd=worktree_dir):
                etype = event.get("type")
                content = event.get("content", "")
                if etype == "file_change":
                    path = content.split(": ", 1)[-1] if ": " in content else content
                    feature_requests_manager.add_file_changed(request.id, path)
                    feature_requests_manager.append_log(request.id, content)
                elif etype == "completed":
                    saw_completion = True
                    feature_requests_manager.append_log(request.id, content)
                elif etype == "error":
                    feature_requests_manager.append_log(request.id, f"Error: {content}")
                    return await fail(f"Pi agent error: {content[:300]}")
                elif content:
                    feature_requests_manager.append_log(request.id, content)

            if not saw_completion:
                return await fail("Pi agent did not report completion.")

            await _git(["add", "-A"], cwd=worktree_dir)
            rc_diff, _ = await _git(["diff", "--cached", "--quiet"], cwd=worktree_dir)
            if rc_diff == 0:
                if attempt == 1:
                    # Nothing actually changed - a no-op idea, not a failure.
                    feature_requests_manager.update(request.id, status="completed", summary="No changes were necessary.")
                    await _cleanup_worktree(worktree_dir, branch, delete_branch=True)
                    pi_lock.release("self_upgrade")
                    return None
                # A fix attempt that made no further changes can't be retried further.
                return await fail(
                    f"Test suite still failing after {attempt - 1} fix attempt(s), and the last "
                    "attempt made no further changes."
                )

            commit_msg = f"Self-upgrade: {idea_prompt[:72]}"
            if attempt > 1:
                commit_msg += f" (fix attempt {attempt})"
            rc, out = await _git(["commit", "-m", commit_msg], cwd=worktree_dir)
            feature_requests_manager.append_log(request.id, f"commit (attempt {attempt}):\n{out[-2000:]}")
            if rc != 0:
                # The pre-commit hook (lint + full test suite) rejected this -
                # same retry mechanism as a post-commit test failure below.
                if attempt >= max_attempts:
                    return await fail(f"Commit rejected by pre-commit hook after {attempt} attempt(s). Tail:\n{out[-500:]}")
                feature_requests_manager.update(request.id, status="running")
                current_prompt = _build_fix_prompt(idea_prompt, "The commit was rejected by the pre-commit hook (lint/tests).", out)
                continue

            feature_requests_manager.update(request.id, status="testing")

            rc, out = await _run(
                [venv_python, "-m", "pytest", "tests/"], cwd=worktree_dir,
                timeout=config.SELF_UPGRADE_TEST_TIMEOUT_SECONDS, env=env,
            )
            feature_requests_manager.append_log(request.id, f"pytest (attempt {attempt}):\n{out[-2000:]}")
            if rc != 0:
                if attempt >= max_attempts:
                    return await fail(f"Test suite failed after {attempt} attempt(s) (exit {rc}). Tail:\n{out[-500:]}")
                feature_requests_manager.update(request.id, status="running")
                current_prompt = _build_fix_prompt(idea_prompt, "The test suite failed.", out)
                continue

            _, changed_files_out = await _git(["diff", "--name-only", "main", "HEAD"], cwd=worktree_dir)
            changed_files = [f.strip() for f in changed_files_out.splitlines() if f.strip()]

            if _missing_test_coverage(changed_files):
                if attempt >= max_attempts:
                    return await fail(
                        f"No test coverage added after {attempt} attempt(s). Changed: {', '.join(changed_files[:10])}"
                    )
                feature_requests_manager.update(request.id, status="running")
                current_prompt = _build_fix_prompt(
                    idea_prompt,
                    "Tests pass, but you didn't add or update any test for this change.",
                    f"Files changed so far: {', '.join(changed_files)}",
                )
                continue

            break  # test gate + coverage check passed - fall through to frontend checks / merge below

        touched_test_files = [f for f in changed_files if f.startswith("tests/")]
        frontend_touched = any(f.startswith("order_explorer_site/frontend/") for f in changed_files)

        if frontend_touched:
            frontend_dir = worktree_dir / "order_explorer_site" / "frontend"
            live_node_modules = config.BASE_DIR / "order_explorer_site" / "frontend" / "node_modules"
            worktree_node_modules = frontend_dir / "node_modules"

            if not live_node_modules.exists():
                return await fail("Frontend changed but node_modules missing - cannot verify build.")
            if not worktree_node_modules.exists():
                try:
                    os.symlink(live_node_modules, worktree_node_modules)
                except OSError as e:
                    return await fail(f"Could not link node_modules for frontend test: {e}")

            rc, out = await _run(["npx", "tsc", "--noEmit"], cwd=frontend_dir, timeout=180, env=env)
            feature_requests_manager.append_log(request.id, f"tsc --noEmit:\n{out[-1500:]}")
            if rc != 0:
                return await fail(f"Frontend typecheck failed. Tail:\n{out[-500:]}")

            rc, out = await _run(["npm", "run", "build"], cwd=frontend_dir, timeout=180, env=env)
            feature_requests_manager.append_log(request.id, f"npm run build:\n{out[-1500:]}")
            if rc != 0:
                return await fail(f"Frontend build failed. Tail:\n{out[-500:]}")

        # Safety gate: only merge onto a clean main that's actually checked
        # out, so this never clobbers concurrent manual work in the live
        # checkout (e.g. someone editing the repo directly at the same time).
        _, current_branch = await _git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=config.BASE_DIR)
        if current_branch.strip() != "main":
            return await fail(
                f"Main checkout is on branch '{current_branch.strip()}', not main - merge aborted "
                f"to avoid clobbering it. Merge branch `{branch}` manually once main is checked out."
            )

        _, status_out = await _git(["status", "--porcelain"], cwd=config.BASE_DIR)
        if status_out.strip():
            return await fail(
                "Tests passed, but the main checkout has uncommitted changes - merge aborted to "
                f"avoid clobbering in-progress work. Commit or stash those changes, then merge "
                f"branch `{branch}` manually."
            )

        rc, out = await _git(["merge", "--no-ff", branch, "-m", f"Self-upgrade: {idea_prompt[:72]}"], cwd=config.BASE_DIR)
        if rc != 0:
            await _git(["merge", "--abort"], cwd=config.BASE_DIR)
            return await fail(f"Merge failed: {out[:400]}")

        services = _affected_services(changed_files)
        if frontend_touched:
            # Rebuild against the live checkout's real node_modules before restart.
            await _run(
                ["npm", "run", "build"],
                cwd=config.BASE_DIR / "order_explorer_site" / "frontend",
                timeout=180, env=env,
            )

        test_warning = ""
        if touched_test_files:
            test_warning = f"\n\n⚠️ This change also modified test file(s): {', '.join(touched_test_files)} - worth a look."

        summary = f"Merged to main. Files changed: {', '.join(changed_files[:10])}. Restarting: {', '.join(services) or 'nothing'}."
        feature_requests_manager.update(request.id, status="completed", summary=summary)

        if send_message_callback:
            msg = f"🔧 **Self-Upgrade Merged**\n\n{idea_prompt[:200]}\n\n{summary}{test_warning}"
            try:
                await send_message_callback(user_id, msg)
            except Exception:
                pass

        await _cleanup_worktree(worktree_dir, branch, delete_branch=True)
        pi_lock.release("self_upgrade")

        if services:
            _restart_services(services)

        return f"🔧 Self-upgrade merged: {slug} (restarting {', '.join(services) if services else 'nothing'})"

    except Exception as e:
        logger.error(f"Unexpected error in self-upgrade pipeline: {e}", exc_info=True)
        return await fail(f"Unexpected error: {str(e)[:300]}")


async def run_feature_request(
    request_id: str,
    prompt: str,
    feature_requests_manager,
) -> Optional[str]:
    """Implement one web-dashboard feature request end-to-end, using the same
    isolated-worktree + gated-merge pattern as run_self_upgrade (see module
    docstring), so a request can never edit the live checkout mid-turn or
    restart the very server it's running under.

    Differences from run_self_upgrade, deliberate for a human-submitted,
    human-watched request rather than an unsupervised weekly job:
    - Takes the prompt as-is, no LLM idea generation.
    - Single attempt, no automatic fix-and-retry loop - the log is visible
      in the dashboard immediately, so a person can just resubmit with more
      direction instead of waiting on repeated automatic retries.
    - Missing test coverage is a warning appended to the summary, not a hard
      gate - reasonable to demand of unsupervised heartbeat changes, too
      strict for e.g. "add a stocks command".

    Caller must already hold the pi_agent lock - chatty_web_server.py's
    _process_pi_queue has its own bounded wait-for-lock loop (unlike
    run_self_upgrade, which acquires/releases the lock itself), so this
    function does not touch skills.pi_agent.lock at all.

    Returns a one-line summary, or None if it was a clean no-op.
    """
    slug = _slugify(prompt)
    unique = int(time.time())
    branch = f"feature-request/{slug}-{unique}"
    worktree_dir = config.SELF_UPGRADE_WORKTREES_DIR / f"{slug}-{unique}"

    async def fail(reason: str) -> str:
        feature_requests_manager.update(request_id, status="error", summary=reason, branch=branch)
        feature_requests_manager.append_log(request_id, reason)
        return reason

    feature_requests_manager.update(request_id, status="running", branch=branch)
    config.SELF_UPGRADE_WORKTREES_DIR.mkdir(parents=True, exist_ok=True)

    await _git(["worktree", "prune"], cwd=config.BASE_DIR)
    rc, out = await _git(["worktree", "add", str(worktree_dir), "-b", branch, "main"], cwd=config.BASE_DIR)
    if rc != 0:
        return await fail(f"Could not create worktree: {out[:400]}")
    feature_requests_manager.append_log(request_id, f"Created worktree at {worktree_dir} on branch {branch}")

    env = _subprocess_env()
    venv_python = str(config.BASE_DIR / "venv" / "bin" / "python")
    wrapped_prompt = _wrap_feature_request_prompt(prompt)

    saw_completion = False
    async for event in run_pi_agent(wrapped_prompt, cwd=worktree_dir):
        etype = event.get("type")
        content = event.get("content", "")
        if etype == "file_change":
            path = content.split(": ", 1)[-1] if ": " in content else content
            feature_requests_manager.add_file_changed(request_id, path)
            feature_requests_manager.append_log(request_id, content)
        elif etype == "completed":
            saw_completion = True
            feature_requests_manager.append_log(request_id, content)
        elif etype == "error":
            feature_requests_manager.append_log(request_id, f"Error: {content}")
            return await fail(f"Pi agent error: {content[:300]}")
        elif content:
            feature_requests_manager.append_log(request_id, content)

    if not saw_completion:
        return await fail("Pi agent did not report completion.")

    await _git(["add", "-A"], cwd=worktree_dir)
    rc_diff, _ = await _git(["diff", "--cached", "--quiet"], cwd=worktree_dir)
    if rc_diff == 0:
        feature_requests_manager.update(request_id, status="completed", summary="No changes were necessary.", branch=branch)
        await _cleanup_worktree(worktree_dir, branch, delete_branch=True)
        return None

    commit_msg = f"Feature request: {prompt[:72]}"
    rc, out = await _git(["commit", "-m", commit_msg], cwd=worktree_dir)
    feature_requests_manager.append_log(request_id, f"commit:\n{out[-2000:]}")
    if rc != 0:
        return await fail(f"Commit rejected by pre-commit hook (lint/tests). Branch `{branch}` preserved. Tail:\n{out[-500:]}")

    feature_requests_manager.update(request_id, status="testing")
    rc, out = await _run(
        [venv_python, "-m", "pytest", "tests/"], cwd=worktree_dir,
        timeout=config.SELF_UPGRADE_TEST_TIMEOUT_SECONDS, env=env,
    )
    feature_requests_manager.append_log(request_id, f"pytest:\n{out[-2000:]}")
    if rc != 0:
        return await fail(f"Test suite failed (exit {rc}). Branch `{branch}` preserved for manual fixing. Tail:\n{out[-500:]}")

    _, changed_files_out = await _git(["diff", "--name-only", "main", "HEAD"], cwd=worktree_dir)
    changed_files = [f.strip() for f in changed_files_out.splitlines() if f.strip()]
    frontend_touched = any(f.startswith("order_explorer_site/frontend/") for f in changed_files)

    test_warning = " (no test coverage was added for this change)" if _missing_test_coverage(changed_files) else ""

    if frontend_touched:
        frontend_dir = worktree_dir / "order_explorer_site" / "frontend"
        live_node_modules = config.BASE_DIR / "order_explorer_site" / "frontend" / "node_modules"
        worktree_node_modules = frontend_dir / "node_modules"

        if not live_node_modules.exists():
            return await fail("Frontend changed but node_modules missing - cannot verify build.")
        if not worktree_node_modules.exists():
            try:
                os.symlink(live_node_modules, worktree_node_modules)
            except OSError as e:
                return await fail(f"Could not link node_modules for frontend test: {e}")

        rc, out = await _run(["npx", "tsc", "--noEmit"], cwd=frontend_dir, timeout=180, env=env)
        feature_requests_manager.append_log(request_id, f"tsc --noEmit:\n{out[-1500:]}")
        if rc != 0:
            return await fail(f"Frontend typecheck failed. Branch `{branch}` preserved. Tail:\n{out[-500:]}")

        rc, out = await _run(["npm", "run", "build"], cwd=frontend_dir, timeout=180, env=env)
        feature_requests_manager.append_log(request_id, f"npm run build:\n{out[-1500:]}")
        if rc != 0:
            return await fail(f"Frontend build failed. Branch `{branch}` preserved. Tail:\n{out[-500:]}")

    # Same safety gate as run_self_upgrade: only merge onto a clean main
    # that's actually checked out, so this never clobbers concurrent manual
    # work in the live checkout.
    _, current_branch = await _git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=config.BASE_DIR)
    if current_branch.strip() != "main":
        return await fail(
            f"Main checkout is on branch '{current_branch.strip()}', not main - merge aborted. "
            f"Merge branch `{branch}` manually once main is checked out."
        )

    _, status_out = await _git(["status", "--porcelain"], cwd=config.BASE_DIR)
    if status_out.strip():
        return await fail(
            "Tests passed, but the main checkout has uncommitted changes - merge aborted to avoid "
            f"clobbering in-progress work. Merge branch `{branch}` manually once it's clean."
        )

    rc, out = await _git(["merge", "--no-ff", branch, "-m", commit_msg], cwd=config.BASE_DIR)
    if rc != 0:
        await _git(["merge", "--abort"], cwd=config.BASE_DIR)
        return await fail(f"Merge failed: {out[:400]}")

    services = _affected_services(changed_files)
    if frontend_touched:
        # Rebuild against the live checkout's real node_modules before restart.
        await _run(
            ["npm", "run", "build"],
            cwd=config.BASE_DIR / "order_explorer_site" / "frontend",
            timeout=180, env=env,
        )

    summary = (
        f"Merged to main. Files changed: {', '.join(changed_files[:10])}. "
        f"Restarting: {', '.join(services) or 'nothing'}.{test_warning}"
    )
    feature_requests_manager.update(request_id, status="completed", summary=summary, branch=branch)

    await _cleanup_worktree(worktree_dir, branch, delete_branch=True)

    # Detached, fire-and-forget - issued only after everything above is
    # already merged and persisted, so even if this restarts the very
    # process running this code, there's nothing left to lose. See
    # _restart_services's docstring.
    if services:
        _restart_services(services)

    return summary
