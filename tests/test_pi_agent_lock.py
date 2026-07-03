"""Tests for skills/pi_agent/lock.py - the cross-process Pi agent lock."""
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from skills.pi_agent import lock as pi_lock


@pytest.fixture
def tmp_lock_file(tmp_path):
    lock_file = tmp_path / "pi_agent.lock"
    with patch("skills.pi_agent.lock.LOCK_FILE", lock_file):
        yield lock_file


def test_acquire_when_free(tmp_lock_file):
    assert pi_lock.acquire("owner_a") is True
    assert tmp_lock_file.exists()
    assert pi_lock.is_locked() is True


def test_second_acquire_fails_while_held(tmp_lock_file):
    assert pi_lock.acquire("owner_a") is True
    assert pi_lock.acquire("owner_b") is False


def test_release_by_owner_frees_it(tmp_lock_file):
    pi_lock.acquire("owner_a")
    pi_lock.release("owner_a")
    assert pi_lock.is_locked() is False
    assert pi_lock.acquire("owner_b") is True


def test_release_by_non_owner_is_noop(tmp_lock_file):
    pi_lock.acquire("owner_a")
    pi_lock.release("owner_b")  # not the owner - should not release
    assert pi_lock.is_locked() is True
    assert pi_lock.acquire("owner_b") is False


def test_release_when_not_locked_is_safe(tmp_lock_file):
    # Should not raise even though nothing is held.
    pi_lock.release("owner_a")
    assert pi_lock.is_locked() is False


def test_stale_lock_is_reclaimable(tmp_lock_file):
    pi_lock.acquire("owner_a")
    # Backdate the lock past the staleness window.
    data = tmp_lock_file.read_text()
    import json
    parsed = json.loads(data)
    parsed["acquired_at"] = time.time() - pi_lock.STALE_SECONDS - 60
    tmp_lock_file.write_text(json.dumps(parsed))

    assert pi_lock.is_locked() is False
    assert pi_lock.acquire("owner_b") is True


def test_corrupt_lock_file_treated_as_free(tmp_lock_file):
    tmp_lock_file.parent.mkdir(parents=True, exist_ok=True)
    tmp_lock_file.write_text("not valid json{{{")
    assert pi_lock.is_locked() is False
    assert pi_lock.acquire("owner_a") is True
