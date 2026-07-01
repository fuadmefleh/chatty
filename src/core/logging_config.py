"""Centralized logging configuration for the bot with separate log files."""
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Dict

# Log directory
LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

# Maximum log file size (10MB)
MAX_BYTES = 10 * 1024 * 1024
BACKUP_COUNT = 5

# Log format
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'


class LoggerFactory:
    """Factory for creating specialized loggers."""
    
    _loggers: Dict[str, logging.Logger] = {}
    _initialized = False
    
    @classmethod
    def setup_logging(cls):
        """Initialize all loggers with their respective handlers."""
        if cls._initialized:
            return
        
        cls._initialized = True
        
        # Create formatters
        standard_formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)
        detailed_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - [%(filename)s:%(lineno)d] - %(levelname)s - %(message)s',
            datefmt=DATE_FORMAT
        )
        
        # Console handler (for all logs)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(standard_formatter)
        
        # === Main Bot Logger ===
        cls._create_logger(
            'bot.main',
            LOG_DIR / 'bot_main.log',
            logging.INFO,
            standard_formatter,
            console_handler
        )
        
        # === Agent Operations Logger (ReACT loop, reasoning) ===
        cls._create_logger(
            'bot.agent',
            LOG_DIR / 'agent.log',
            logging.DEBUG,
            detailed_formatter,
            console_handler
        )
        
        # === Tool Execution Logger ===
        cls._create_logger(
            'bot.tools',
            LOG_DIR / 'tools.log',
            logging.DEBUG,
            detailed_formatter,
            console_handler
        )
        
        # === Memory Operations Logger ===
        cls._create_logger(
            'bot.memory',
            LOG_DIR / 'memory.log',
            logging.DEBUG,
            standard_formatter,
            console_handler
        )
        
        # === Reminder Manager Logger ===
        cls._create_logger(
            'bot.reminders',
            LOG_DIR / 'reminders.log',
            logging.DEBUG,
            standard_formatter,
            console_handler
        )
        
        # === Heartbeat Manager Logger ===
        cls._create_logger(
            'bot.heartbeat',
            LOG_DIR / 'heartbeat.log',
            logging.DEBUG,
            standard_formatter,
            console_handler
        )
        
        # === API Calls Logger (OpenAI, Telegram, etc.) ===
        cls._create_logger(
            'bot.api',
            LOG_DIR / 'api.log',
            logging.DEBUG,
            detailed_formatter,
            console_handler
        )
        
        # === Skills Execution Logger ===
        cls._create_logger(
            'bot.skills',
            LOG_DIR / 'skills.log',
            logging.DEBUG,
            standard_formatter,
            console_handler
        )
        
        # === User Interactions Logger ===
        cls._create_logger(
            'bot.interactions',
            LOG_DIR / 'interactions.log',
            logging.INFO,
            standard_formatter,
            console_handler
        )
        
        # === Error Logger (errors only from all components) ===
        cls._create_logger(
            'bot.errors',
            LOG_DIR / 'errors.log',
            logging.ERROR,
            detailed_formatter,
            console_handler,
            error_only=True
        )
        
        # === Debug Logger (verbose everything) ===
        cls._create_logger(
            'bot.debug',
            LOG_DIR / 'debug.log',
            logging.DEBUG,
            detailed_formatter,
            None  # No console output for debug
        )
    
    @classmethod
    def _create_logger(
        cls,
        name: str,
        log_file: Path,
        level: int,
        formatter: logging.Formatter,
        console_handler: logging.Handler = None,
        error_only: bool = False
    ) -> logging.Logger:
        """Create a logger with file and optional console handlers.
        
        Args:
            name: Logger name
            log_file: Path to log file
            level: Logging level
            formatter: Log formatter
            console_handler: Optional console handler
            error_only: If True, only log ERROR and above
        
        Returns:
            Configured logger
        """
        logger = logging.getLogger(name)
        logger.setLevel(logging.DEBUG)  # Set to DEBUG, handlers will filter
        logger.propagate = False  # Don't propagate to parent loggers
        
        # File handler
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=MAX_BYTES,
            backupCount=BACKUP_COUNT
        )
        file_handler.setLevel(logging.ERROR if error_only else level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        # Console handler (if provided and not error_only)
        if console_handler and not error_only:
            logger.addHandler(console_handler)
        
        cls._loggers[name] = logger
        return logger
    
    @classmethod
    def get_logger(cls, name: str) -> logging.Logger:
        """Get a logger by name.
        
        Args:
            name: Logger name (e.g., 'bot.agent', 'bot.tools')
        
        Returns:
            Logger instance
        """
        if not cls._initialized:
            cls.setup_logging()
        
        return cls._loggers.get(name, logging.getLogger(name))


# Convenience functions for getting specific loggers
def get_main_logger() -> logging.Logger:
    """Get the main bot logger."""
    return LoggerFactory.get_logger('bot.main')


def get_agent_logger() -> logging.Logger:
    """Get the agent operations logger."""
    return LoggerFactory.get_logger('bot.agent')


def get_tools_logger() -> logging.Logger:
    """Get the tools execution logger."""
    return LoggerFactory.get_logger('bot.tools')


def get_memory_logger() -> logging.Logger:
    """Get the memory operations logger."""
    return LoggerFactory.get_logger('bot.memory')


def get_reminders_logger() -> logging.Logger:
    """Get the reminders logger."""
    return LoggerFactory.get_logger('bot.reminders')


def get_heartbeat_logger() -> logging.Logger:
    """Get the heartbeat logger."""
    return LoggerFactory.get_logger('bot.heartbeat')


def get_api_logger() -> logging.Logger:
    """Get the API calls logger."""
    return LoggerFactory.get_logger('bot.api')


def get_skills_logger() -> logging.Logger:
    """Get the skills execution logger."""
    return LoggerFactory.get_logger('bot.skills')


def get_interactions_logger() -> logging.Logger:
    """Get the user interactions logger."""
    return LoggerFactory.get_logger('bot.interactions')


def get_error_logger() -> logging.Logger:
    """Get the error logger."""
    return LoggerFactory.get_logger('bot.errors')


def get_debug_logger() -> logging.Logger:
    """Get the debug logger."""
    return LoggerFactory.get_logger('bot.debug')


# Initialize logging on module import
LoggerFactory.setup_logging()
