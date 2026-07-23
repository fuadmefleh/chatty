"""Atlas Web Server - entrypoint that assembles the FastAPI app from
src/web/ and runs it.

Port: 8016
Provides REST + WebSocket endpoints for:
- Chat (WebSocket, streams agent responses)
- Notes (CRUD)
- Transcriptions (create/list/delete - staged for automatic memory mining)
- Audio ingestion (raw-body upload -> WhisperX STT -> transcriptions queue)
- Media ingestion (raw-body photo/video upload -> vision/STT -> transcriptions queue)
- Reminders (read + delete)
- Memory viewer (read-only)
- Code browser (read-only)
- System status (skills, pm2)

Kept at the repo root (rather than moved into src/web/) so start_web.sh and
docker-compose.yml's `python chatty_web_server.py` invocations, and the
`uvicorn.run("chatty_web_server:app", ...)` call below, all keep working
unmodified. The actual routes live in src/web/routers/.
"""
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ── Ensure project root is on sys.path so src/ imports work ─────────────────
PROJECT_ROOT = Path(__file__).parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.web.app import create_app
from src.web.config import PORT

app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("chatty_web_server:app", host="0.0.0.0", port=PORT, reload=False)
