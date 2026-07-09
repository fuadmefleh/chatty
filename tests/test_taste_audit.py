"""Tests for the UI Taste Auditor endpoint (GET /api/chatty/taste-audit,
POST /api/chatty/taste-audit/fix) and the heuristic scanner."""
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

import chatty_web_server as server
from src.web import config, state
from src.web.routers import taste_audit


@pytest.fixture
def client():
    return TestClient(server.app)


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
    # Skills manager must have frontend_editor skill for the body validation
    # check to run (otherwise it returns 503 before reaching it)
    mock_sm = AsyncMock()
    mock_sm.skills = {"frontend_editor": AsyncMock()}
    orig_sm = state.skills_manager
    state.skills_manager = mock_sm
    try:
        resp = client.post(
            "/api/chatty/taste-audit/fix",
            headers=_headers(),
            json={"findings": "not a list"},
        )
        assert resp.status_code == 400
    finally:
        state.skills_manager = orig_sm


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
