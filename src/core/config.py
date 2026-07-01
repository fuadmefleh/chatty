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

# Chat LLM provider — "openai" (default) or "local" (a local OpenAI-compatible
# server, e.g. llama.cpp serving qwen). Used by both the Telegram bot
# (StagedReACTAgent) and the web dashboard (WebChatAgent).
CHAT_PROVIDER = os.getenv("CHAT_PROVIDER", "openai")
LOCAL_LLM_BASE_URL = os.getenv("LOCAL_LLM_BASE_URL", "http://192.168.18.150:8080/v1")
LOCAL_LLM_MODEL = os.getenv("LOCAL_LLM_MODEL", "qwen3.6-27b")

CHAT_MODEL = LOCAL_LLM_MODEL if CHAT_PROVIDER == "local" else OPENAI_MODEL
CHAT_BASE_URL = LOCAL_LLM_BASE_URL if CHAT_PROVIDER == "local" else None
CHAT_API_KEY = "not-needed" if CHAT_PROVIDER == "local" else OPENAI_API_KEY

# Telegram Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_PHONE_NUMBER = os.getenv("ALLOWED_PHONE_NUMBER", "")

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

# Google Search Configuration
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID")  # Custom Search Engine ID

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
