"""Tests for the PDF file-existence guards in the Walmart order pipeline.

Covers:
- heartbeat_manager._process_walmart_orders skips missing PDFs with a warning
- walmart_parser.extract_text_from_pdf raises FileNotFoundError for missing files
- walmart_parser.execute (parse-all path) skips missing files
"""
import io
import logging
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FAKE_PDF_BYTES = b"%PDF-1.4 fake pdf content for testing purposes\n"


def _write_fake_pdf(path: Path) -> Path:
    """Write a minimal fake PDF file at *path* and return the path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_FAKE_PDF_BYTES)
    return path


# ---------------------------------------------------------------------------
# heartbeat_manager._process_walmart_orders
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_heartbeat_walmart_skips_missing_pdf():
    """_process_walmart_orders should log a warning and skip when the PDF
    that glob found no longer exists on disk."""
    import src.managers.heartbeat_manager as hb_module
    from src.managers.heartbeat_manager import HeartbeatManager
    from src.core.skills_manager import SkillsManager

    # Build a real HeartbeatManager so the logger and config are wired up.
    skills_mgr = MagicMock(spec=SkillsManager)
    hb = HeartbeatManager(skills_mgr)

    # Use a temporary directory so we don't touch the real data/walmart folder
    with tempfile.TemporaryDirectory() as tmpdir:
        fake_walmart_dir = Path(tmpdir) / "walmart"
        fake_walmart_dir.mkdir()

        # Create one PDF that exists and one that we'll delete before processing
        pdf_exists = fake_walmart_dir / "order_1.pdf"
        pdf_gone = fake_walmart_dir / "order_2.pdf"
        _write_fake_pdf(pdf_exists)
        _write_fake_pdf(pdf_gone)

        # Remove the second one — simulating the race condition where
        # glob found it but it was deleted/moved before we got to it
        pdf_gone.unlink()

        # Redirect logging to a StringIO so we can inspect it
        log_capture = io.StringIO()
        handler = logging.StreamHandler(log_capture)
        handler.setLevel(logging.WARNING)
        hb_logger = logging.getLogger("bot.heartbeat")
        hb_logger.addHandler(handler)
        hb_logger.setLevel(logging.WARNING)

        # Monkey-patch the module-level Path class so glob returns our fake paths
        original_path = hb_module.Path

        class FakePath(Path):
            def glob(self, pattern):
                if str(self) == "data/walmart":
                    return [pdf_exists, pdf_gone]
                if "archived" in str(self):
                    return []
                return original_path(str(self)).glob(pattern)

        # Ensure the archived dir exists so shutil.move works
        archived = fake_walmart_dir / "archived"
        archived.mkdir(exist_ok=True)

        hb_module.Path = FakePath
        try:
            with patch(
                "skills.walmart_orders.walmart_parser.execute",
                new=AsyncMock(return_value={
                    "success": True, "order": {"order_id": "X"},
                    "items_count": 0
                }),
            ):
                await hb._process_walmart_orders()
        finally:
            hb_module.Path = original_path
            hb_logger.removeHandler(handler)

        output = log_capture.getvalue()
        assert "Walmart PDF missing" in output, (
            f"Expected warning about missing PDF but got: {output!r}"
        )
        assert "order_2.pdf" in output, (
            f"Expected filename in warning but got: {output!r}"
        )


@pytest.mark.asyncio
async def test_heartbeat_walmart_no_pdfs_returns_none():
    """When there are no PDFs, _process_walmart_orders returns None."""
    from src.managers.heartbeat_manager import HeartbeatManager
    from src.core.skills_manager import SkillsManager

    skills_mgr = MagicMock(spec=SkillsManager)
    hb = HeartbeatManager(skills_mgr)

    # Patch glob to return empty list
    with patch.object(Path, "glob", return_value=[]):
        result = await hb._process_walmart_orders()
        assert result is None


# ---------------------------------------------------------------------------
# walmart_parser.extract_text_from_pdf
# ---------------------------------------------------------------------------

def test_extract_text_from_pdf_raises_for_missing_file():
    """extract_text_from_pdf should raise FileNotFoundError for a path that
    doesn't exist, rather than a generic IOError."""
    from skills.walmart_orders.walmart_parser import WalmartPDFParser

    parser = WalmartPDFParser()
    with pytest.raises(FileNotFoundError, match="PDF file not found"):
        parser.extract_text_from_pdf("/nonexistent/path/to/order.pdf")


# ---------------------------------------------------------------------------
# walmart_parser.execute — "parse all" path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_execute_parse_all_skips_missing_files():
    """When action='parse' and pdf_path is None, missing files are skipped
    with a warning rather than raising an exception."""
    from skills.walmart_orders.walmart_parser import execute

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a fake "data/walmart" directory with one real PDF
        # and one phantom path we'll feed via monkey-patching
        fake_walmart = Path(tmpdir) / "data" / "walmart"
        fake_walmart.mkdir(parents=True)

        real_pdf = fake_walmart / "good_order.pdf"
        _write_fake_pdf(real_pdf)
        # Write enough text for the parser to find an order ID
        real_pdf.write_text(
            "Order #12345-67890\n"
            "Order Date: Jan 15, 2026\n"
            "Order Total: $50.00\n"
            "Widget Shopped Qty 1 $50.00\n"
            "Subtotal: $50.00\n"
            "Total: $50.00\n"
        )

        # phantom_pdf is a Path object that *looks* valid but the file
        # doesn't actually exist — simulating a race condition after glob()
        phantom_pdf = fake_walmart / "gone_order.pdf"

        # We patch the Path.glob calls inside execute() to return both paths
        # but only "good_order.pdf" actually exists on disk
        def fake_glob(pattern):
            if "pdf" in pattern.lower():
                return [real_pdf, phantom_pdf]
            if "xlsx" in pattern.lower():
                return []
            return []

        with patch.object(Path, "glob", side_effect=fake_glob):
            result = await execute(action="parse")

        assert result["success"] is True
        # The result should contain info about the real file
        results = result.get("results", [])
        file_names = {r.get("file") for r in results}
        assert "good_order.pdf" in file_names
        # Missing file should NOT appear as a failure/error entry
        assert "gone_order.pdf" not in file_names
