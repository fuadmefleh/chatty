"""Tests for the UI Taste Auditor endpoint (GET /api/chatty/taste-audit,
POST /api/chatty/taste-audit/fix) and the heuristic scanner."""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

import chatty_web_server as server
from src.managers import taste_fix_manager
from src.web import config, state
from src.web.routers import taste_audit


@pytest.fixture
def client():
    return TestClient(server.app)


@pytest.fixture(autouse=True)
def isolated_fix_state(monkeypatch, tmp_path):
    monkeypatch.setattr(taste_fix_manager, "_STATE_PATH", tmp_path / "state.json")
    yield


def _headers(**overrides):
    headers = {"X-API-Key": config.API_KEY}
    headers.update(overrides)
    return headers


# ── Auth ─────────────────────────────────────────────────────────────────────

def test_scan_requires_auth(client):
    resp = client.get("/api/chatty/taste-audit")
    assert resp.status_code == 401


def test_fix_requires_auth(client):
    resp = client.post("/api/chatty/taste-audit/fix", json={})
    assert resp.status_code == 401


# ── GET scan ─────────────────────────────────────────────────────────────────

def test_scan_returns_report(client):
    resp = client.get("/api/chatty/taste-audit", headers=_headers())
    assert resp.status_code == 200

    data = resp.json()
    assert "timestamp" in data
    assert "files_scanned" in data
    assert "total_findings" in data
    assert "score" in data
    assert "summary" in data
    assert "scan_duration_ms" in data
    assert "findings" in data
    assert isinstance(data["files_scanned"], int)
    assert data["files_scanned"] > 0
    assert isinstance(data["score"], (int, float))
    assert 0 <= data["score"] <= 100
    assert isinstance(data["summary"], dict)
    assert "critical" in data["summary"]
    assert "warning" in data["summary"]
    assert "info" in data["summary"]
    assert isinstance(data["findings"], list)


def test_scan_findings_have_required_fields(client):
    resp = client.get("/api/chatty/taste-audit", headers=_headers())
    assert resp.status_code == 200

    data = resp.json()
    for finding in data["findings"]:
        assert "rule_id" in finding
        assert "title" in finding
        assert "description" in finding
        assert "severity" in finding
        assert finding["severity"] in ("critical", "warning", "info")
        assert "file" in finding
        assert "line" in finding
        assert isinstance(finding["line"], int)
        assert "line_content" in finding
        assert "fixable" in finding


def test_scan_total_matches_findings_list(client):
    resp = client.get("/api/chatty/taste-audit", headers=_headers())
    data = resp.json()
    assert data["total_findings"] == len(data["findings"])


def test_scan_finds_inline_styles(client):
    resp = client.get("/api/chatty/taste-audit", headers=_headers())
    data = resp.json()
    inline_findings = [f for f in data["findings"] if f["rule_id"] == "inline-style"]
    assert len(inline_findings) > 0, "Should find inline style issues"


def test_scan_finds_hex_colors(client):
    resp = client.get("/api/chatty/taste-audit", headers=_headers())
    data = resp.json()
    hex_findings = [f for f in data["findings"] if f["rule_id"] == "hex-color"]
    assert len(hex_findings) > 0, "Should find hex color issues"


# ── POST fix ─────────────────────────────────────────────────────────────────

def test_fix_bad_body_findings_not_list(client):
    # Body validation (400) happens before the skills-manager tool check, so
    # a bad body should 400 regardless of skill availability.
    resp = client.post(
        "/api/chatty/taste-audit/fix",
        headers=_headers(),
        json={"findings": "not a list"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_fix_available_with_real_skills_manager(client):
    """Regression test: the fix endpoint used to check
    `"frontend_editor" in state.skills_manager.skills`, but skills are keyed
    by the display name parsed from their .md heading ("Frontend Editor"),
    not the folder name - so that check was always False and the endpoint
    always 503'd, even with the skill fully loaded. Loads a real
    SkillsManager from disk (no mocking of the skill registry itself) so a
    reintroduced name-based check would be caught here instead of only in a
    test that happens to mock the same wrong key.

    The fix itself now runs as a background job (see taste_fix_manager) -
    TestClient's ASGI transport drives BackgroundTasks to completion before
    the request returns, so the status endpoint already has the final result
    by the time we poll it here."""
    from src.core.skills_manager import SkillsManager

    sm = SkillsManager()
    await sm.load_skills()
    assert sm.get_tool("read_frontend_file") is not None
    assert sm.get_tool("write_frontend_file") is not None

    orig_sm = state.skills_manager
    state.skills_manager = sm
    try:
        resp = client.post(
            "/api/chatty/taste-audit/fix",
            headers=_headers(),
            json={"findings": [{"file": "src/nonexistent-taste-audit-test.tsx", "rule_id": "hex-color"}]},
        )
    finally:
        state.skills_manager = orig_sm

    assert resp.status_code == 200

    status_resp = client.get("/api/chatty/taste-audit/fix/status", headers=_headers())
    assert status_resp.status_code == 200
    data = status_resp.json()
    assert data["status"] == "done"
    assert len(data["errors"]) == 1
    assert "not found" in data["errors"][0]["error"].lower()


@pytest.mark.asyncio
async def test_fix_writes_to_real_file(client):
    """Regression test: findings report `file` relative to FRONTEND_SRC (e.g.
    "pages/Foo.tsx"), but the Frontend Editor skill's read/write tools
    resolve `file_path` relative to FRONTEND_DIR one level up (expects
    "src/pages/Foo.tsx") - passing the bare finding path through unchanged
    always hit "File not found" and silently no-op'd every fix. Uses a real
    SkillsManager and a real scratch file under frontend/src so a
    reintroduced path mismatch is caught here instead of only manifesting
    as a mysterious 100% failure rate in the running app."""
    from src.core.skills_manager import SkillsManager

    fixture_path = taste_audit.FRONTEND_SRC / "__taste_audit_fix_fixture.tsx"
    fixture_path.write_text('const c = "#000000";\n')
    try:
        sm = SkillsManager()
        await sm.load_skills()

        orig_sm = state.skills_manager
        state.skills_manager = sm
        try:
            resp = client.post(
                "/api/chatty/taste-audit/fix",
                headers=_headers(),
                json={"findings": [
                    {"file": "__taste_audit_fix_fixture.tsx", "line": 1, "rule_id": "hex-color"},
                ]},
            )
        finally:
            state.skills_manager = orig_sm

        assert resp.status_code == 200

        status_resp = client.get("/api/chatty/taste-audit/fix/status", headers=_headers())
        data = status_resp.json()
        assert data["status"] == "done"
        assert data["errors"] == []
        assert len(data["applied"]) == 1
        assert fixture_path.read_text() == 'const c = "var(--ink)";\n'
    finally:
        fixture_path.unlink(missing_ok=True)


def test_fix_missing_fields(client):
    resp = client.post(
        "/api/chatty/taste-audit/fix",
        headers=_headers(),
        json={"findings": [{"file": "src/App.tsx"}]},
    )
    assert resp.status_code == 400


def test_fix_no_skills_manager(client):
    original = state.skills_manager
    state.skills_manager = None  # type: ignore[assignment]
    try:
        resp = client.post(
            "/api/chatty/taste-audit/fix",
            headers=_headers(),
            json={"findings": [{"file": "src/App.tsx", "rule_id": "hex-color"}]},
        )
        assert resp.status_code == 503
    finally:
        state.skills_manager = original


# ── Heuristic scanner unit tests ────────────────────────────────────────────

def test_scan_file_detects_console_log(tmp_path):
    test_file = tmp_path / "test.tsx"
    test_file.write_text('console.log("hello");\nexport default App;\n')
    findings = taste_audit._scan_file(test_file)
    assert any(f.rule_id == "console-statement" for f in findings)


def test_scan_file_detects_inline_style(tmp_path):
    test_file = tmp_path / "test.tsx"
    test_file.write_text('<div style={{color: "red"}}>\n')
    findings = taste_audit._scan_file(test_file)
    assert any(f.rule_id == "inline-style" for f in findings)


def test_scan_file_detects_hex_color(tmp_path):
    test_file = tmp_path / "test.tsx"
    test_file.write_text('const c = "#ff0000";\n')
    findings = taste_audit._scan_file(test_file)
    assert any(f.rule_id == "hex-color" for f in findings)


def test_scan_file_detects_any_type(tmp_path):
    test_file = tmp_path / "test.tsx"
    test_file.write_text('const x: any = null;\n')
    findings = taste_audit._scan_file(test_file)
    assert any(f.rule_id == "any-type" for f in findings)


def test_scan_file_detects_placeholder(tmp_path):
    test_file = tmp_path / "test.tsx"
    test_file.write_text('const text = "FIXME";\n')
    findings = taste_audit._scan_file(test_file)
    assert any(f.rule_id == "placeholder-text" for f in findings)


def test_scan_file_empty(tmp_path):
    test_file = tmp_path / "empty.tsx"
    test_file.write_text('')
    findings = taste_audit._scan_file(test_file)
    assert findings == []


def test_scan_file_nonexistent(tmp_path):
    findings = taste_audit._scan_file(tmp_path / "nope.tsx")
    assert findings == []


def test_hex_color_filters_css_vars(tmp_path):
    """hex-color heuristic should skip lines with CSS variable references."""
    test_file = tmp_path / "test.tsx"
    test_file.write_text('const c = "#ff0000" + " var(--ink)";\n')
    findings = taste_audit._scan_file(test_file)
    # Should skip because line contains var(--
    hex_findings = [f for f in findings if f.rule_id == "hex-color"]
    assert len(hex_findings) == 0


def test_calculate_score_perfect(tmp_path):
    score = taste_audit._calculate_score([])
    assert score == 100.0


def test_calculate_score_with_findings():
    from src.web.routers.taste_audit import AuditFinding
    findings = [AuditFinding(
        rule_id="test", title="Test", description="d",
        severity="critical", file="f.tsx", line=1, line_content="x",
    )]
    score = taste_audit._calculate_score(findings)
    assert score == 90.0  # 100 - 10 (critical weight)


def test_collect_files_finds_frontend_sources():
    files = taste_audit._collect_files()
    assert len(files) > 0
    assert any(f.name == "App.tsx" for f in files)


def test_run_scan_returns_report():
    report = taste_audit._run_scan()
    assert report.files_scanned > 0
    assert isinstance(report.score, float)
    assert 0 <= report.score <= 100
    assert isinstance(report.findings, list)
    assert report.total_findings == len(report.findings)


def test_apply_line_fix_inline_style():
    line = '<div style={{color: "red"}}>'
    result = taste_audit._apply_line_fix(line, "inline-style", "")
    assert "TODO" in result


def test_apply_line_fix_hex_color():
    line = 'color: "#000000"'
    result = taste_audit._apply_line_fix(line, "hex-color", "")
    assert "var(--ink)" in result


def test_apply_line_fix_console():
    line = 'console.log("test");'
    result = taste_audit._apply_line_fix(line, "console-statement", "")
    assert result.startswith("//")


def test_apply_line_fix_any_type():
    line = 'const x: any = null;'
    result = taste_audit._apply_line_fix(line, "any-type", "")
    assert ": unknown" in result
    assert ": any" not in result
