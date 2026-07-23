"""Env-derived constants for the Atlas web API.

Deliberately separate from src/core/config.py, which is the Telegram bot's
own config module - the web server has always read its own env vars
independently (see WEB_USER_ID being duplicated in both places so
heartbeat_manager.py can scope per-user work without importing this
package). Not unifying that pre-existing duplication here to avoid
behavior changes outside the scope of this refactor.
"""
import os
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

API_KEY = os.getenv("CHATTY_WEB_API_KEY", "changeme")
WEB_USER_ID = os.getenv("WEB_USER_ID", "")
REMINDERS_DIR = PROJECT_ROOT / "reminders"
MEMORY_DIR = PROJECT_ROOT / "memory"
PORT = int(os.getenv("CHATTY_WEB_PORT", "8016"))

# ── Atlas blog ("Notes by Atlas") ───────────────────────────────────────────
# The chatty-notes-api sidecar (Docker, localhost) hard-scopes the agent to its
# own publication. The scheduled writer only ever creates drafts; nothing here
# publishes without a human approve action.
BLOG_API_URL = os.getenv("BLOG_API_URL", "http://127.0.0.1:3210")
BLOG_API_TOKEN = os.getenv("AGENT_API_TOKEN", "")
BLOG_WRITE_INTERVAL_HOURS = int(os.getenv("BLOG_WRITE_INTERVAL_HOURS", "72"))  # ~every 3 days
BLOG_STATE_FILE = PROJECT_ROOT / "data" / "blog_state.json"

# ── Code browser ──────────────────────────────────────────────────────────────
CODE_EXCLUDE_DIRS = {
    ".git", "venv", "env", "ENV", "node_modules", "__pycache__",
    "data", "memory", "logs", "reminders", "dist", "build",
    ".vite", ".opencode", ".claude", ".vscode", ".idea",
    ".pytest_cache", "coverage",
}
CODE_EXCLUDE_FILE_GLOBS = (
    ".env", ".env.*", "credentials.json", "web_credentials.json", "*_token*", "*_tokens*",
    "*.pickle", "*.db", "*.sqlite", "*.sqlite3", "*.pem", "*.key", "*secret*",
)
CODE_BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".webp", ".bmp", ".pdf",
    ".zip", ".tar", ".gz", ".whl", ".pyc", ".so", ".woff", ".woff2", ".ttf", ".eot",
}
CODE_LANGUAGE_MAP = {
    ".py": "python", ".ts": "typescript", ".tsx": "tsx", ".js": "javascript",
    ".jsx": "jsx", ".json": "json", ".css": "css", ".html": "markup",
    ".md": "markdown", ".sh": "bash", ".yml": "yaml", ".yaml": "yaml",
    ".toml": "toml", ".cfg": "text", ".ini": "text", ".txt": "text",
}
CODE_MAX_FILE_BYTES = 500_000  # reject rather than truncate

# ── Media ingestion + chat attachments ───────────────────────────────────────
MEDIA_MAX_BYTES = 200 * 1024 * 1024  # videos arrive pre-compressed to 720p, so this is generous
MEDIA_IMAGE_FORMATS = {"image/jpeg": "jpg", "image/heic": "heic", "image/png": "png", "image/webp": "webp"}
MEDIA_VIDEO_FORMATS = {"video/quicktime": "mov", "video/mp4": "mp4", "video/webm": "webm"}
MEDIA_VIDEO_KEYFRAME_COUNT = 3

CHAT_ATTACHMENT_MAX_BYTES = 50 * 1024 * 1024
CHAT_MEDIA_FILENAME_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.(jpg|jpeg|png|webp|heic|mp4|mov|webm)$"
)
CHAT_MEDIA_EXT_TO_MIME = {
    "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
    "webp": "image/webp", "heic": "image/heic",
    "mp4": "video/mp4", "mov": "video/quicktime", "webm": "video/webm",
}
CHAT_MEDIA_VIDEO_EXTS = {"mp4", "mov", "webm"}
