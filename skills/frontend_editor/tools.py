"""Frontend editor tools for the Atlas Vite/React dashboard."""
import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict, List

from src.core.skill_tool import SkillTool

logger = logging.getLogger(__name__)

# Resolve paths relative to the project root (chatty/)
PROJECT_ROOT = Path(__file__).parent.parent.parent  # chatty/
FRONTEND_DIR = PROJECT_ROOT / "order_explorer_site" / "frontend"
FRONTEND_SRC = FRONTEND_DIR / "src"
FRONTEND_DIST = FRONTEND_DIR / "dist"

# Allowed file extensions for editing
SAFE_EXTENSIONS = {
    ".tsx", ".ts", ".jsx", ".js", ".css", ".html", ".json",
    ".svg", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico",
    ".md", ".txt", ".yml", ".yaml",
}

# Files that are safe to list/edit (never node_modules or hidden dirs)
def _is_safe_path(path: Path) -> bool:
    """Check that the path is within the frontend src directory."""
    try:
        path.relative_to(FRONTEND_DIR)
    except ValueError:
        return False
    parts = path.relative_to(FRONTEND_DIR).parts
    for part in parts:
        if part.startswith(".") or part == "node_modules":
            return False
    return True


def _short_path(filepath: Path) -> str:
    """Return path relative to frontend dir for display."""
    try:
        return str(filepath.relative_to(FRONTEND_DIR))
    except ValueError:
        return str(filepath)


# ---------------------------------------------------------------------------
# Tool: list frontend source files
# ---------------------------------------------------------------------------

class ListFrontendFiles(SkillTool):
    name = "list_frontend_files"
    description = "List all source files in the Vite/React frontend directory. " \
                  "Use this to explore the frontend structure before making changes."
    parameters = {
        "type": "object",
        "properties": {
            "subdir": {
                "type": "string",
                "description": "Optional subdirectory to list (e.g., 'src/pages', 'src/components'). "
                               "Leave empty to list the entire src/ tree."
            },
            "extensions": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional list of file extensions to filter (e.g., ['.tsx', '.ts']). "
                               "If omitted, lists all files."
            }
        },
        "required": []
    }

    async def execute(self, subdir: str = "", extensions: List[str] = None) -> str:
        # subdir is relative to frontend dir (e.g. 'src/pages'), not to src/
        search_dir = FRONTEND_DIR / subdir if subdir else FRONTEND_SRC
        if not search_dir.exists():
            return json.dumps({"error": f"Directory not found: {_short_path(search_dir)}"})

        ext_set = set(extensions) if extensions else None
        files = []
        for p in sorted(search_dir.rglob("*" if not ext_set else f"*{extensions[0]}")):
            if not p.is_file():
                continue
            if ext_set and p.suffix not in ext_set:
                continue
            files.append(_short_path(p))

        return json.dumps({
            "directory": _short_path(search_dir),
            "file_count": len(files),
            "files": files
        }, indent=2)


# ---------------------------------------------------------------------------
# Tool: read a frontend source file
# ---------------------------------------------------------------------------

class ReadFrontendFile(SkillTool):
    name = "read_frontend_file"
    description = "Read the contents of a frontend source file. " \
                  "Path is relative to the frontend directory " \
                  "(e.g., 'src/pages/Chat.tsx', 'src/App.tsx')."
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path relative to frontend directory (e.g., 'src/App.tsx')."
            }
        },
        "required": ["file_path"]
    }

    async def execute(self, file_path: str) -> str:
        target = FRONTEND_DIR / file_path
        if not _is_safe_path(target):
            return json.dumps({"error": f"Path not allowed: {file_path}"})
        if not target.exists():
            return json.dumps({"error": f"File not found: {file_path}"})
        if not target.is_file():
            return json.dumps({"error": f"Not a file: {file_path}"})

        try:
            content = target.read_text(encoding="utf-8")
            return json.dumps({
                "file": file_path,
                "lines": content.count("\n") + 1,
                "content": content
            }, indent=2)
        except Exception as e:
            return json.dumps({"error": f"Failed to read file: {e}"})


# ---------------------------------------------------------------------------
# Tool: write (create or overwrite) a frontend source file
# ---------------------------------------------------------------------------

class WriteFrontendFile(SkillTool):
    name = "write_frontend_file"
    description = "Write (create or overwrite) a frontend source file. " \
                  "Path is relative to the frontend directory. " \
                  "Use this to create new pages, components, or replace existing files."
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path relative to frontend directory (e.g., 'src/pages/NewPage.tsx')."
            },
            "content": {
                "type": "string",
                "description": "Full file content to write."
            }
        },
        "required": ["file_path", "content"]
    }

    async def execute(self, file_path: str, content: str) -> str:
        target = FRONTEND_DIR / file_path
        if not _is_safe_path(target):
            return json.dumps({"error": f"Path not allowed: {file_path}"})

        if target.suffix and target.suffix not in SAFE_EXTENSIONS:
            return json.dumps({"error": f"File extension not allowed: {target.suffix}"})

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            logger.info(f"Frontend file written: {file_path}")
            return json.dumps({
                "success": True,
                "file": file_path,
                "message": f"File written: {file_path} ({len(content)} chars)",
                "next_step": "Run build_frontend to compile changes."
            }, indent=2)
        except Exception as e:
            return json.dumps({"error": f"Failed to write file: {e}"})


# ---------------------------------------------------------------------------
# Tool: rebuild the frontend (npm run build)
# ---------------------------------------------------------------------------

class BuildFrontend(SkillTool):
    name = "build_frontend"
    description = "Rebuild the frontend production bundle with `npm run build`. " \
                  "Run this after modifying any frontend source files so changes " \
                  "take effect in the running vite preview server. " \
                  "Also restarts the order-explorer-frontend pm2 service."
    parameters = {
        "type": "object",
        "properties": {
            "restart_service": {
                "type": "boolean",
                "description": "Whether to restart the pm2 frontend service after building. "
                               "Default: true."
            }
        },
        "required": []
    }

    async def execute(self, restart_service: bool = True) -> str:
        try:
            # Run npm run build
            proc = await asyncio.create_subprocess_exec(
                "npm", "run", "build",
                cwd=str(FRONTEND_DIR),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            output = stdout.decode("utf-8", errors="replace")
            err_output = stderr.decode("utf-8", errors="replace")

            if proc.returncode != 0:
                return json.dumps({
                    "success": False,
                    "error": f"Build failed (exit {proc.returncode})",
                    "stdout": output[-1000:],
                    "stderr": err_output[-1000:]
                }, indent=2)

            # Check dist was created
            dist_files = list(FRONTEND_DIST.glob("*")) if FRONTEND_DIST.exists() else []

            result = {
                "success": True,
                "message": "Frontend built successfully",
                "dist_files": len(dist_files),
                "output": output[-500:]
            }

            # Restart pm2 service
            if restart_service:
                try:
                    restart_proc = await asyncio.create_subprocess_exec(
                        "pm2", "restart", "order-explorer-frontend",
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    _, _ = await restart_proc.communicate()
                    result["service_restarted"] = True
                    result["message"] = "Frontend built and pm2 service restarted"
                except Exception as e:
                    result["service_restart_error"] = str(e)

            return json.dumps(result, indent=2)

        except Exception as e:
            return json.dumps({"error": f"Build process failed: {e}"})


# ---------------------------------------------------------------------------
# Tool: restart the frontend pm2 service (without rebuilding)
# ---------------------------------------------------------------------------

class RestartFrontendService(SkillTool):
    name = "restart_frontend_service"
    description = "Restart the order-explorer-frontend pm2 service. " \
                  "Use this to apply changes without a full rebuild, or to " \
                  "recover from a stuck frontend server."
    parameters = {
        "type": "object",
        "properties": {},
        "required": []
    }

    async def execute(self) -> str:
        try:
            proc = await asyncio.create_subprocess_exec(
                "pm2", "restart", "order-explorer-frontend",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            return json.dumps({
                "success": True,
                "message": "Frontend service restarted",
                "output": stdout.decode("utf-8", errors="replace").strip()
            }, indent=2)
        except Exception as e:
            return json.dumps({"error": f"Failed to restart service: {e}"})


# ---------------------------------------------------------------------------
# Tool: get frontend project info
# ---------------------------------------------------------------------------

class GetFrontendInfo(SkillTool):
    name = "get_frontend_info"
    description = "Get information about the frontend project structure, " \
                  "including routes, pages, and dependencies. Useful for understanding " \
                  "the current state before making changes."
    parameters = {
        "type": "object",
        "properties": {
            "section": {
                "type": "string",
                "description": "Which info to retrieve: 'routes' (App.tsx routes), "
                               "'dependencies' (package.json), 'pages' (list of page files), "
                               "'components' (list of component files), or 'all'."
            }
        },
        "required": []
    }

    async def execute(self, section: str = "all") -> str:
        result: Dict[str, Any] = {}

        if section in ("routes", "all"):
            # Parse routes from App.tsx
            app_file = FRONTEND_SRC / "App.tsx"
            if app_file.exists():
                content = app_file.read_text(encoding="utf-8")
                import re
                routes = re.findall(r'<Route\s+path="(/[^"]*)"', content)
                result["routes"] = sorted(set(routes))

        if section in ("dependencies", "all"):
            pkg_file = FRONTEND_DIR / "package.json"
            if pkg_file.exists():
                pkg = json.loads(pkg_file.read_text(encoding="utf-8"))
                result["dependencies"] = pkg.get("dependencies", {})
                result["dev_dependencies"] = pkg.get("devDependencies", {})
                result["scripts"] = pkg.get("scripts", {})

        if section in ("pages", "all"):
            pages_dir = FRONTEND_SRC / "pages"
            if pages_dir.exists():
                result["pages"] = [
                    p.name for p in sorted(pages_dir.glob("*.tsx"))
                ]

        if section in ("components", "all"):
            comp_dir = FRONTEND_SRC / "components"
            if comp_dir.exists():
                result["components"] = [
                    _short_path(p) for p in sorted(comp_dir.rglob("*.tsx"))
                ]

        return json.dumps(result, indent=2)
