"""Configuration management for the companion AI."""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Base directory (project root, not src/core)
BASE_DIR = Path(__file__).parent.parent.parent

# OpenAI Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4-turbo-preview")

# Chat LLM provider — "openai" (default), "local" (a local OpenAI-compatible
# server, e.g. llama.cpp serving qwen), or "anthropic" (Claude API). Used by
# both the Telegram bot (StagedReACTAgent) and the web dashboard (WebChatAgent).
CHAT_PROVIDER = os.getenv("CHAT_PROVIDER", "openai")
LOCAL_LLM_BASE_URL = os.getenv("LOCAL_LLM_BASE_URL", "http://localhost:8080/v1")
LOCAL_LLM_MODEL = os.getenv("LOCAL_LLM_MODEL", "qwen3.6-27b")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929")

if CHAT_PROVIDER == "local":
    CHAT_MODEL, CHAT_BASE_URL, CHAT_API_KEY = LOCAL_LLM_MODEL, LOCAL_LLM_BASE_URL, "not-needed"
elif CHAT_PROVIDER == "anthropic":
    CHAT_MODEL, CHAT_BASE_URL, CHAT_API_KEY = ANTHROPIC_MODEL, None, ANTHROPIC_API_KEY
else:
    CHAT_MODEL, CHAT_BASE_URL, CHAT_API_KEY = OPENAI_MODEL, None, OPENAI_API_KEY

# STT (speech-to-text) provider — used by the iOS-companion audio ingestion
# endpoint (POST /api/chatty/audio); the Telegram bot has no voice-message
# handling. "whisperx_http" (default) talks to an external WhisperX server
# (diarization + speaker embeddings); "openai" uses OpenAI's transcription
# API (no diarization); "local_whisper" runs faster-whisper in-process (no
# external server/API key, no diarization) - see requirements-local-stt.txt.
STT_PROVIDER = os.getenv("STT_PROVIDER", "whisperx_http")
STT_ENGINE_URL = os.getenv("STT_ENGINE_URL", "http://127.0.0.1:8003")
STT_OPENAI_MODEL = os.getenv("STT_OPENAI_MODEL", "whisper-1")
STT_LOCAL_MODEL_SIZE = os.getenv("STT_LOCAL_MODEL_SIZE", "base")
STT_LOCAL_DEVICE = os.getenv("STT_LOCAL_DEVICE", "cpu")

# Embeddings — for long-term memory semantic search (src/core/embeddings.py).
# Always uses real OpenAI's embeddings API via OPENAI_API_KEY directly,
# regardless of CHAT_PROVIDER (which may be "local"/"anthropic" and can't
# serve embeddings) - same "always real OpenAI for this one capability"
# precedent as STT_OPENAI_MODEL above.
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

# TTS (text-to-speech) provider - used by the Telegram bot's speak_text skill
# (skills/tts/) to reply with a real voice message instead of/alongside text.
#   local (default) - the tts_engine_api microservice already running on
#     this machine (kokoro/mms/chatterbox engines), no API key needed.
#   elevenlabs - ElevenLabs API, requires ELEVENLABS_API_KEY.
#   openai - OpenAI's audio.speech API, reuses OPENAI_API_KEY.
TTS_PROVIDER = os.getenv("TTS_PROVIDER", "local")
TTS_LOCAL_ENGINE_URL = os.getenv("TTS_LOCAL_ENGINE_URL", "http://127.0.0.1:8002")
TTS_LOCAL_ENGINE_ENGINE = os.getenv("TTS_LOCAL_ENGINE_ENGINE", "kokoro")
TTS_LOCAL_ENGINE_VOICE = os.getenv("TTS_LOCAL_ENGINE_VOICE", "af_sky")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")  # "Rachel" premade voice
ELEVENLABS_MODEL_ID = os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2")
OPENAI_TTS_MODEL = os.getenv("OPENAI_TTS_MODEL", "tts-1")
OPENAI_TTS_VOICE = os.getenv("OPENAI_TTS_VOICE", "alloy")

# OpenMontage Configuration (AI video generation — skills/video_production/).
# OPENMONTAGE_API_KEY is optional; the skill returns an error when absent.
OPENMONTAGE_API_KEY = os.getenv("OPENMONTAGE_API_KEY")
OPENMONTAGE_API_URL = os.getenv(
    "OPENMONTAGE_API_URL", "https://api.openmontage.ai"
)

# Telegram Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_PHONE_NUMBER = os.getenv("ALLOWED_PHONE_NUMBER", "")

# Web/iOS App Configuration (same env var chatty_web_server.py reads directly;
# duplicated here so heartbeat_manager.py can scope per-user work, e.g.
# transcription mining, without importing the web server module).
WEB_USER_ID = os.getenv("WEB_USER_ID", "")

# Memory Configuration
MEMORY_DIR = BASE_DIR / os.getenv("MEMORY_DIR", "memory")
MAX_MEMORY_TOKENS = int(os.getenv("MAX_MEMORY_TOKENS", "4000"))

# Skills Configuration
SKILLS_DIR = BASE_DIR / os.getenv("SKILLS_DIR", "skills")

# Agent Configuration
MAX_ITERATIONS = int(os.getenv("MAX_ITERATIONS", "5"))
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.7"))

# Heartbeat Configuration
HEARTBEAT_INTERVAL_MINUTES = int(os.getenv("HEARTBEAT_INTERVAL_MINUTES", "15"))
HEARTBEAT_FILE = BASE_DIR / "docs" / os.getenv("HEARTBEAT_FILE", "heartbeat.md")

# World Watch Configuration (proactive topic monitoring, runs from the heartbeat).
# Per-kind check intervals let fast-moving sources (stocks) be checked more
# often than slow ones (news, github) without hammering their APIs.
WORLD_WATCH_INTERVAL_HOURS = int(os.getenv("WORLD_WATCH_INTERVAL_HOURS", "24"))
STOCK_WATCH_INTERVAL_HOURS = int(os.getenv("STOCK_WATCH_INTERVAL_HOURS", "4"))
GITHUB_WATCH_INTERVAL_HOURS = int(os.getenv("GITHUB_WATCH_INTERVAL_HOURS", "12"))
STOCK_WATCH_MOVE_THRESHOLD_PERCENT = float(os.getenv("STOCK_WATCH_MOVE_THRESHOLD_PERCENT", "5.0"))

# Memory-driven watch suggestions: how often to mine long-term memory for
# candidate topics worth proactively watching (default: weekly).
MEMORY_SUGGESTION_INTERVAL_HOURS = int(os.getenv("MEMORY_SUGGESTION_INTERVAL_HOURS", "168"))

# Daily Briefing Configuration: local hour (0-23) at which to send a single
# digest combining weather, budget status, today's reminders, and recent
# insights. HOME_LOCATION is required for the weather section; leave blank
# to omit it from the briefing.
DAILY_BRIEFING_HOUR = int(os.getenv("DAILY_BRIEFING_HOUR", "8"))
HOME_LOCATION = os.getenv("HOME_LOCATION", "")

# SearXNG Configuration (self-hosted web search). Defaults to the SearXNG
# instance already running system-wide on this host; see docker-compose.yml
# for standing up a dedicated instance if you don't have one.
SEARXNG_BASE_URL = os.getenv("SEARXNG_BASE_URL", "http://localhost:8081")

# Self-Upgrade Configuration: Chatty periodically thinks of improvements to
# make to its own codebase (see src/managers/self_upgrade_manager.py). Each
# idea is implemented in an isolated git worktree/branch, tested, and only
# merged into main + auto-restarted if the test gate passes and main has no
# uncommitted changes. Failed attempts leave the branch/worktree in place for
# manual inspection rather than touching main.
SELF_UPGRADE_INTERVAL_HOURS = int(os.getenv("SELF_UPGRADE_INTERVAL_HOURS", "168"))
SELF_UPGRADE_WORKTREES_DIR = Path(os.getenv(
    "SELF_UPGRADE_WORKTREES_DIR", str(BASE_DIR.parent / "chatty_self_upgrade_worktrees")
))
SELF_UPGRADE_TEST_TIMEOUT_SECONDS = int(os.getenv("SELF_UPGRADE_TEST_TIMEOUT_SECONDS", "300"))
# How many total attempts (1 initial + N-1 fix retries) Pi gets to make its own
# test suite pass before the branch is left for manual review.
SELF_UPGRADE_MAX_TEST_ATTEMPTS = int(os.getenv("SELF_UPGRADE_MAX_TEST_ATTEMPTS", "3"))

# Directory _restart_services() (self_upgrade_manager.py) writes restart
# signal files into. Under Docker (see docker-compose.yml), a sidecar
# container (docker/restarter/) polls this directory and translates requests
# into `docker restart <container>` calls, since there's no pm2 inside a
# container. Outside Docker this directory is effectively unused.
RESTART_REQUESTS_DIR = Path(os.getenv("RESTART_REQUESTS_DIR", str(BASE_DIR / "restart_requests")))

# Trending Suggestions Configuration: Chatty periodically scans GitHub's
# trending repos (see src/managers/trending_manager.py) and curates a short
# list of ideas worth considering. Unlike self-upgrade, nothing here is ever
# implemented automatically - it's just a menu on the dashboard the user picks
# from ("Implement" routes the idea through the same feature-request pipeline
# as a manually-typed request).
TRENDING_LANGUAGES = os.getenv("TRENDING_LANGUAGES", "python,typescript,javascript")
TRENDING_SCAN_INTERVAL_HOURS = int(os.getenv("TRENDING_SCAN_INTERVAL_HOURS", "6"))
TRENDING_REPOS_PER_LANGUAGE = int(os.getenv("TRENDING_REPOS_PER_LANGUAGE", "10"))
TRENDING_MAX_SUGGESTIONS_PER_SCAN = int(os.getenv("TRENDING_MAX_SUGGESTIONS_PER_SCAN", "4"))

# Webcam Discovery Configuration: Chatty periodically searches (via the
# SearXNG integration above) for promising public live-webcam pages/threads
# and asks an LLM to curate best-effort suggestions (name/url/kind/location
# guessed from search snippets) - see src/managers/webcam_discovery.py.
# Nothing is added to the user's source list automatically; suggestions sit
# in a pending queue on the dashboard's /webcams page until approved or
# dismissed. Queries are semicolon-separated since they may contain commas.
WEBCAM_DISCOVERY_QUERIES = os.getenv(
    "WEBCAM_DISCOVERY_QUERIES",
    "site:reddit.com live traffic camera;site:reddit.com earthcam;"
    "live webcam city traffic feed;DOT traffic camera portal live view;"
    "live streaming webcam tourist attraction",
)
WEBCAM_DISCOVERY_INTERVAL_HOURS = int(os.getenv("WEBCAM_DISCOVERY_INTERVAL_HOURS", "12"))
WEBCAM_DISCOVERY_RESULTS_PER_QUERY = int(os.getenv("WEBCAM_DISCOVERY_RESULTS_PER_QUERY", "8"))
WEBCAM_DISCOVERY_MAX_SUGGESTIONS_PER_SCAN = int(os.getenv("WEBCAM_DISCOVERY_MAX_SUGGESTIONS_PER_SCAN", "5"))

# System Prompt
SYSTEM_PROMPT = """You are a helpful and friendly AI companion. You have access to your memory 
from previous conversations and various skills to help users. You think step by step and can 
take actions when needed.

When responding:
1. Be warm, personable, and engaging
2. Reference past conversations when relevant
3. Use your skills when they can help solve a problem
4. Think through complex problems step by step
"""

def validate_config():
    """Validate required configuration."""
    errors = []
    
    if not OPENAI_API_KEY:
        errors.append("OPENAI_API_KEY is not set")
    
    if not TELEGRAM_BOT_TOKEN:
        errors.append("TELEGRAM_BOT_TOKEN is not set")
    
    if errors:
        raise ValueError(f"Configuration errors: {', '.join(errors)}")
    
    # Create directories if they don't exist
    MEMORY_DIR.mkdir(exist_ok=True)
    SKILLS_DIR.mkdir(exist_ok=True)
