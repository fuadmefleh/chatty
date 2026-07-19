"""UI Taste Auditor — scan frontend source files against anti-slop heuristics
and optionally apply targeted fixes via the Frontend Editor skill tools.

Endpoints:
  GET  /api/chatty/taste-audit           — run the scan, return structured report
  POST /api/chatty/taste-audit/fix       — kick off applying fixes for selected
                                            findings in the background
  GET  /api/chatty/taste-audit/fix/status — poll the current fix job's progress
"""
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from src.managers import taste_fix_manager
from src.web import config, state
from src.web.auth import require_api_key

router = APIRouter(
    prefix="/api/chatty/taste-audit",
    tags=["taste-audit"],
    dependencies=[Depends(require_api_key)],
)

# ── Resolve paths relative to project root ──────────────────────────────────
PROJECT_ROOT = config.PROJECT_ROOT
FRONTEND_SRC = PROJECT_ROOT / "order_explorer_site" / "frontend" / "src"

# ── Heuristics ───────────────────────────────────────────────────────────────
# All patterns MUST be simple (no nested lookaheads, no .* in lookaheads)
# to avoid catastrophic backtracking on large files.
# severity: "critical" | "warning" | "info"

HEURISTICS: List[Dict[str, Any]] = [
    # Inline styles (should use CSS classes / CSS variables)
    {
        "id": "inline-style",
        "title": "Inline style attribute",
        "description": "Inline style={...} should be replaced with a CSS class or Tailwind utility",
        "severity": "warning",
        "pattern": r'style=\{[^}]+\}',
        "fix_template": True,
    },
    # Hardcoded hex colors (simple pattern — filter in post-processing)
    {
        "id": "hex-color",
        "title": "Hardcoded hex color",
        "description": "Use CSS variables (var(--ink), var(--surface), etc.) instead of hex literals",
        "severity": "warning",
        "pattern": r'#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b',
        "fix_template": True,
    },
    # Hardcoded color names
    {
        "id": "color-name",
        "title": "Hardcoded color name",
        "description": "Use semantic color variables instead of literal color names",
        "severity": "info",
        "pattern": r'"(?:red|blue|green|yellow|orange|purple|pink)"',
        "fix_template": False,
    },
    # console.log / console.warn in source
    {
        "id": "console-statement",
        "title": "Console statement in source",
        "description": "Remove or replace console.log/warn/error with proper logging",
        "severity": "info",
        "pattern": r'console\.(log|warn|error|debug)\s*\(',
        "fix_template": True,
    },
    # Hardcoded padding/margin values in style props
    {
        "id": "hardcoded-spacing",
        "title": "Hardcoded spacing in style prop",
        "description": "Use Tailwind spacing utilities (p-*, m-*) instead of inline spacing",
        "severity": "warning",
        "pattern": r'(?:padding|margin(?:Top|Bottom|Left|Right)?)\s*:\s*"\d+px"',
        "fix_template": False,
    },
    # Using 'any' type in TypeScript
    {
        "id": "any-type",
        "title": "Use of 'any' type",
        "description": "Replace 'any' with proper TypeScript types",
        "severity": "warning",
        "pattern": r':\s*any\b',
        "fix_template": True,
    },
    # Generic placeholder text
    {
        "id": "placeholder-text",
        "title": "Generic placeholder text",
        "description": "Replace generic placeholder text with meaningful content",
        "severity": "info",
        "pattern": r'"(?:Lorem ipsum|lorem ipsum|FIXME|PLACEHOLDER|click here)"',
        "fix_template": True,
    },
    # 'const x = undefined' (unused variable pattern indicator)
    {
        "id": "unused-import-suspicion",
        "title": "Potential unused variable",
        "description": "Check for variables declared but never used",
        "severity": "info",
        "pattern": r'^\s*const\s+\w+\s*=\s*undefined\s*;',
        "fix_template": False,
    },
]


@dataclass
class AuditFinding:
    """A single finding from the taste audit."""
    rule_id: str
    title: str
    description: str
    severity: str
    file: str
    line: int
    line_content: str
    fixable: bool = False
    fix_suggestion: Optional[str] = None


@dataclass
class AuditReport:
    """The full audit report."""
    timestamp: str
    files_scanned: int
    total_findings: int
    findings: List[Dict[str, Any]]
    summary: Dict[str, int]
    score: float
    scan_duration_ms: int


def _should_skip_hex_color(line: str) -> bool:
    """Filter out false positives for hex-color heuristic."""
    lower = line.lower()
    # Skip CSS variable references
    if "var(--" in lower:
        return True
    # Skip comments
    if "/*" in line:
        return True
    # Skip tailwind class color keywords
    if "bg-surface" in lower or "text-bg" in lower:
        return True
    # Skip hex values in hash contexts (not colors)
    if "hash" in lower or "md5" in lower or "sha" in lower:
        return True
    return False


def _scan_file(filepath: Path) -> List[AuditFinding]:
    """Run all heuristics against a single file."""
    findings: List[AuditFinding] = []
    try:
        content = filepath.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return findings

    lines = content.split("\n")
    try:
        rel_path = str(filepath.relative_to(FRONTEND_SRC))
    except ValueError:
        # File is outside FRONTEND_SRC (e.g. temp test files)
        rel_path = str(filepath)

    for heuristic in HEURISTICS:
        pattern = heuristic["pattern"]
        try:
            compiled = re.compile(pattern, re.MULTILINE)
        except re.error:
            continue

        for match in compiled.finditer(content):
            # Calculate line number from match start
            line_num = content[:match.start()].count("\n") + 1
            line_text = lines[line_num - 1] if line_num <= len(lines) else ""

            # Post-process: skip false positives for hex-color
            if heuristic["id"] == "hex-color":
                if _should_skip_hex_color(line_text):
                    continue

            # For any-type, skip lines with Record or unknown
            if heuristic["id"] == "any-type":
                if "Record" in line_text or "unknown" in line_text:
                    continue

            findings.append(AuditFinding(
                rule_id=heuristic["id"],
                title=heuristic["title"],
                description=heuristic["description"],
                severity=heuristic["severity"],
                file=rel_path,
                line=line_num,
                line_content=line_text.strip()[:120],
                fixable=bool(heuristic.get("fix_template", False)),
                fix_suggestion=heuristic.get("fix_template"),
            ))

    return findings


def _calculate_score(findings: List[AuditFinding]) -> float:
    """Calculate a 0-100 quality score based on findings."""
    if not findings:
        return 100.0

    # Weighted penalty system
    weights = {"critical": 10, "warning": 5, "info": 2}
    total_penalty = sum(weights.get(f.severity, 1) for f in findings)
    return max(0.0, round(100.0 - min(total_penalty, 100.0), 1))


def _collect_files() -> List[Path]:
    """Collect all scannable frontend source files."""
    files = []
    extensions = {".tsx", ".ts", ".jsx", ".js", ".css"}
    for ext in extensions:
        files.extend(FRONTEND_SRC.rglob(f"*{ext}"))
    return sorted(files)


def _run_scan() -> AuditReport:
    """Execute the full taste audit scan."""
    import time
    start = time.monotonic()

    files = _collect_files()
    all_findings: List[AuditFinding] = []

    for filepath in files:
        all_findings.extend(_scan_file(filepath))

    # Sort by severity then file
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    all_findings.sort(key=lambda f: (severity_order.get(f.severity, 3), f.file, f.line))

    # Build summary
    summary: Dict[str, int] = {"critical": 0, "warning": 0, "info": 0}
    for f in all_findings:
        summary[f.severity] = summary.get(f.severity, 0) + 1

    elapsed_ms = int((time.monotonic() - start) * 1000)

    return AuditReport(
        timestamp=datetime.now(timezone.utc).isoformat(),
        files_scanned=len(files),
        total_findings=len(all_findings),
        findings=[asdict(f) for f in all_findings],
        summary=summary,
        score=_calculate_score(all_findings),
        scan_duration_ms=elapsed_ms,
    )


@router.get("")
async def run_taste_audit():
    """Scan frontend source files against anti-slop heuristics and return a
    structured quality report."""
    report = _run_scan()
    return {
        "timestamp": report.timestamp,
        "files_scanned": report.files_scanned,
        "total_findings": report.total_findings,
        "score": report.score,
        "summary": report.summary,
        "scan_duration_ms": report.scan_duration_ms,
        "findings": report.findings,
    }


async def _run_apply_fixes(fixes_by_file: Dict[str, List[Dict[str, Any]]]) -> None:
    """Background worker: apply fixes file by file, recording progress into
    taste_fix_manager after each file so /fix/status reflects live progress
    instead of only the end result."""
    total_applied = 0
    total_errors = 0

    for file_path, file_fixes in fixes_by_file.items():
        taste_fix_manager.set_current_file(file_path)
        file_applied: List[Dict[str, Any]] = []
        file_errors: List[Dict[str, Any]] = []

        # Findings report paths relative to FRONTEND_SRC (see _scan_file
        # above), but the Frontend Editor skill's tools resolve file_path
        # relative to FRONTEND_DIR one level up - reading/writing without
        # the "src/" prefix always 404'd, silently no-op'ing every fix.
        skill_path = f"src/{file_path}"

        # Read current file content
        read_result = await state.skills_manager.execute_tool(
            "read_frontend_file",
            {"file_path": skill_path},
        )
        read_data = json.loads(read_result)
        if "error" in read_data:
            file_errors.append({"file": file_path, "error": read_data["error"]})
            taste_fix_manager.record_file_result(file_path, file_applied, file_errors)
            total_errors += len(file_errors)
            continue

        current_content = read_data["content"]

        # Apply fixes line by line
        lines = current_content.split("\n")

        # Sort fixes by line descending so earlier lines aren't affected
        sorted_fixes = sorted(file_fixes, key=lambda f: f.get("line", 0), reverse=True)

        for fix in sorted_fixes:
            line_num = fix.get("line", 0)
            rule_id = fix.get("rule_id", "")
            fix_instruction = fix.get("fix", "")

            if line_num < 1 or line_num > len(lines):
                file_errors.append({
                    "file": file_path,
                    "line": line_num,
                    "error": "Line number out of range",
                })
                continue

            line_idx = line_num - 1
            original_line = lines[line_idx]

            # Apply fix based on rule type
            new_line = _apply_line_fix(original_line, rule_id, fix_instruction)
            if new_line != original_line:
                lines[line_idx] = new_line
                file_applied.append({
                    "file": file_path,
                    "line": line_num,
                    "rule_id": rule_id,
                    "original": original_line.strip(),
                    "fixed": new_line.strip(),
                })

        new_content = "\n".join(lines)

        # Write the updated file
        write_result = await state.skills_manager.execute_tool(
            "write_frontend_file",
            {"file_path": skill_path, "content": new_content},
        )
        write_data = json.loads(write_result)
        if "error" in write_data:
            file_errors.append({"file": file_path, "error": write_data["error"]})

        taste_fix_manager.record_file_result(file_path, file_applied, file_errors)
        total_applied += len(file_applied)
        total_errors += len(file_errors)

    taste_fix_manager.finish(
        f"Applied {total_applied} fix(es) across {len(fixes_by_file)} file(s). "
        f"{total_errors} error(s)."
    )


@router.get("/fix/status")
async def get_fix_status():
    """Poll the current fix job's progress - see src/managers/taste_fix_manager.py.
    Lets the frontend disconnect while a fix job runs in the background and
    pick the result back up later."""
    return taste_fix_manager.get_state()


@router.post("/fix")
async def apply_fixes(body: Dict[str, Any], background_tasks: BackgroundTasks):
    """Kick off applying targeted fixes for selected findings using the
    Frontend Editor skill, in the background. Poll /fix/status for live
    progress (current file, how many done of how many) and the final result.

    Expects:
      {
        "findings": [
          {
            "file": "src/pages/Example.tsx",
            "line": 42,
            "rule_id": "inline-style",
            "fix": "replacement text or instruction"
          }
        ]
      }"""
    findings_input = body.get("findings", [])
    if not isinstance(findings_input, list):
        raise HTTPException(400, "Body must contain a 'findings' array")

    # Validate each finding has required fields
    for idx, finding in enumerate(findings_input):
        if not isinstance(finding, dict):
            raise HTTPException(400, f"Finding at index {idx} must be an object")
        if "file" not in finding or "rule_id" not in finding:
            raise HTTPException(400, f"Finding at index {idx} must have 'file' and 'rule_id'")

    if not state.skills_manager:
        raise HTTPException(503, "Skills manager not initialized")

    # Check that the Frontend Editor skill's tools are available. Skills are
    # keyed by the display name parsed from their .md heading (see
    # SkillsManager._parse_skill_file), which for this skill is "Frontend
    # Editor", not the "frontend_editor" folder name - checking the tools we
    # actually call below instead of guessing at that key avoids the mismatch.
    required_tools = ("read_frontend_file", "write_frontend_file")
    missing_tools = [t for t in required_tools if state.skills_manager.get_tool(t) is None]
    if missing_tools:
        raise HTTPException(503, f"Frontend Editor skill not available (missing tools: {', '.join(missing_tools)})")

    current = taste_fix_manager.get_state()
    if current["status"] == "running":
        return current

    # Group fixes by file
    fixes_by_file: Dict[str, List[Dict[str, Any]]] = {}
    for finding in findings_input:
        file_path = finding["file"]
        fixes_by_file.setdefault(file_path, []).append(finding)

    new_state = taste_fix_manager.start(len(fixes_by_file))
    background_tasks.add_task(_run_apply_fixes, fixes_by_file)
    return new_state


def _apply_line_fix(line: str, rule_id: str, fix_instruction: str) -> str:
    """Apply a targeted fix to a single line of code based on the rule ID.
    Returns the modified line, or the original line if no fix was applied."""

    if rule_id == "inline-style":
        if "style=" in line:
            return f"// TODO: replace inline style with Tailwind class\n{line}"

    elif rule_id == "hex-color":
        hex_to_var = {
            "#000000": "var(--ink)",
            "#ffffff": "var(--surface)",
            "#fff": "var(--surface)",
            "#000": "var(--ink)",
            "#333333": "var(--ink-dim)",
            "#666666": "var(--muted)",
            "#999999": "var(--muted)",
            "#e94560": "var(--alert-red)",
            "#2ecc71": "var(--alert-green)",
            "#f39c12": "var(--alert-amber)",
            "#3498db": "var(--signal)",
        }
        for hex_color, css_var in hex_to_var.items():
            if hex_color in line:
                line = line.replace(hex_color, css_var)
                line = line.replace(hex_color.lower(), css_var)
        return line

    elif rule_id == "console-statement":
        if "console." in line and not line.strip().startswith("//"):
            return f"// {line}"

    elif rule_id == "any-type":
        if ": any" in line and "Record" not in line:
            return line.replace(": any", ": unknown")

    elif rule_id == "placeholder-text":
        replacements = {
            "Lorem ipsum": "Content goes here",
            "FIXME": "Fix this text",
            "PLACEHOLDER": "Replace with actual content",
            "click here": "Learn more",
        }
        for old, new in replacements.items():
            line = line.replace(old, new)
            line = line.replace(old.lower(), new.lower())

    return line
