"""Main Telegram bot application."""
import asyncio
import json
import logging
import base64
from datetime import datetime
from pathlib import Path
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes
)
from typing import Dict, List

from src.core import config
from src.core.memory import MemoryManager, ConversationHistoryManager, MAX_SESSIONS_SHOWN
from src.core.skills_manager import SkillsManager  # Use the new dynamic skills manager
from src.core.llm import get_llm_provider
from src.core.llm.openai_provider import OpenAIProvider
from src.agents.staged_react_agent import StagedReACTAgent  # Use staged ReACT agent
from src.managers.reminder_manager import ReminderManager
from skills.reminder.tools import set_reminder_manager
from skills.notes.notes_manager import NotesManager
from skills.notes.tools import set_notes_manager
from skills.watchlist.watchlist_manager import WatchlistManager
from skills.watchlist.tools import set_watchlist_manager
from src.managers.heartbeat_manager import HeartbeatManager
from src.core.logging_config import get_main_logger, get_interactions_logger, get_error_logger, get_api_logger
from src.core.telegram_utils import safe_send_reply, safe_send_message
from src.core.request_context import current_chat_id

# Get specialized loggers
logger = get_main_logger()
interactions_logger = get_interactions_logger()
error_logger = get_error_logger()
api_logger = get_api_logger()

# Global managers
skills_manager = SkillsManager()
reminder_manager = ReminderManager(config.BASE_DIR / "reminders")
notes_manager = NotesManager()
watchlist_manager = WatchlistManager()
heartbeat_manager = HeartbeatManager(skills_manager)

# Store user agents and memory managers
user_agents: Dict[str, StagedReACTAgent] = {}
user_memories: Dict[str, MemoryManager] = {}
user_history_managers: Dict[str, ConversationHistoryManager] = {}
authorized_users: Dict[str, str] = {}  # user_id -> phone_number

_AUTH_FILE = Path(__file__).parent.parent / "data" / "authorized_users.json"


def _load_authorized_users():
    """Load authorized users from disk."""
    global authorized_users
    try:
        if _AUTH_FILE.exists():
            authorized_users = json.loads(_AUTH_FILE.read_text())
            logger.info(f"Loaded {len(authorized_users)} authorized user(s) from disk")
    except Exception as e:
        logger.error(f"Failed to load authorized users: {e}")


def _save_authorized_users():
    """Persist authorized users to disk."""
    try:
        _AUTH_FILE.parent.mkdir(parents=True, exist_ok=True)
        _AUTH_FILE.write_text(json.dumps(authorized_users))
    except Exception as e:
        logger.error(f"Failed to save authorized users: {e}")


_load_authorized_users()

# OpenCode streaming state
_opencode_task = None  # Currently running opencode asyncio.Task


def get_user_agent(user_id: str) -> StagedReACTAgent:
    """Get or create agent for a user.

    Args:
        user_id: Telegram user ID

    Returns:
        Staged ReACT agent for the user
    """
    if user_id not in user_agents:
        logger.info(f"Creating new StagedReACTAgent for user {user_id}")
        memory_manager = MemoryManager(user_id)
        user_memories[user_id] = memory_manager
        user_agents[user_id] = StagedReACTAgent(memory_manager, skills_manager)
        history_mgr = ConversationHistoryManager(user_id)
        user_history_managers[user_id] = history_mgr
        logger.info(f"Agent created successfully for user {user_id}")

    return user_agents[user_id]


def is_user_authorized(user_id: str) -> bool:
    """Check if user is authorized to use the bot.
    
    Args:
        user_id: Telegram user ID
        
    Returns:
        True if authorized, False otherwise
    """
    return user_id in authorized_users


async def send_reminder(user_id: str, message: str):
    """Send a reminder to a user.
    
    Args:
        user_id: Telegram user ID
        message: Reminder message
    """
    try:
        from telegram import Bot
        bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
        await safe_send_message(
            bot,
            chat_id=user_id,
            text=f"⏰ **Reminder**\n\n{message}",
        )
        logger.info(f"Sent reminder to user {user_id}")
    except Exception as e:
        logger.error(f"Error sending reminder to user {user_id}: {e}")


# ============================================================================
# OPENCODE STREAMING
# ============================================================================

def _opencode_icon(event_type: str) -> str:
    icons = {
        "started": "🚀",
        "progress": "💭",
        "tool_call": "🔧",
        "tool_result": "↩️",
        "file_change": "💾",
        "completed": "✅",
        "error": "❌",
    }
    return icons.get(event_type, "📌")


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    user = update.effective_user
    user_id = str(user.id)
    
    # Check if user is already authorized
    if is_user_authorized(user_id):
        welcome_message = f"""👋 Hello {user.first_name}! I'm your AI companion.

I have memory of our conversations and various skills to help you. I can:
- Remember our past conversations
- Set reminders and alarms for you
- Think through complex problems step by step
- Use specialized skills to assist you

Just send me a message and I'll do my best to help!

Commands:
/start - Show this welcome message
/history - View your chat history (survives restarts!)
/continue - Continue a previous conversation
/sessions - List all past conversation sessions
/memory - View your memory statistics
/skills - List my available skills
/stocks - Show today's top stock movers
/reminders - View your active reminders
/consolidate - Move old memories to long-term storage
/clear - Clear chat history
/help - Show help information
"""
        await safe_send_reply(update.message, welcome_message)
        
        # Initialize user's agent
        get_user_agent(user_id)
    else:
        # Request phone number verification
        from telegram import KeyboardButton, ReplyKeyboardMarkup
        
        keyboard = [[KeyboardButton("Share Phone Number", request_contact=True)]]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        
        await safe_send_reply(
            update.message,
            "👋 Hello! To use this bot, please verify your phone number by clicking the button below.",
            reply_markup=reply_markup
        )


async def memory_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /memory command."""
    try:
        user_id = str(update.effective_user.id)
        
        logger.info(f"User {user_id} requested memory stats")
        
        if not is_user_authorized(user_id):
            await safe_send_reply(update.message, "🔒 Please verify your phone number first with /start")
            return
        
        if user_id not in user_memories:
            memory_manager = MemoryManager(user_id)
            user_memories[user_id] = memory_manager
        
        memory_manager = user_memories[user_id]
        stats = await memory_manager.get_summary()
        
        response = f"""📚 Memory Statistics:

**Short-Term Memory (Daily Conversations):**
- Days recorded: {stats['total_days']}
- Oldest: {stats['oldest_date'] or 'N/A'}
- Newest: {stats['newest_date'] or 'N/A'}

**Long-Term Memory (Consolidated Knowledge):**
- Entries: {stats['long_term_entries']}

**Storage:**
- Total size: {stats['total_size_bytes'] / 1024:.2f} KB

Short-term memories are your recent daily conversations. Every 7 days during heartbeat cycles, I consolidate older conversations into long-term memory categories (preferences, goals, important facts, etc.).
"""
        
        await safe_send_reply(update.message, response)
    except Exception as e:
        logger.error(f"Error in memory_command: {e}", exc_info=True)
        await safe_send_reply(update.message, "An error occurred retrieving memory stats.")


async def forget_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /forget <text> - delete a long-term memory fact by content search."""
    user_id = str(update.effective_user.id)

    if not is_user_authorized(user_id):
        await safe_send_reply(update.message, "🔒 Please verify your phone number first with /start")
        return

    if not context.args:
        await safe_send_reply(update.message, "Usage: /forget <text to search for>\nExample: /forget I like sushi")
        return

    search_term = " ".join(context.args)
    try:
        from src.core.memory_tools import MemoryTools

        memory_tools = MemoryTools(user_id)
        matches = memory_tools._facts_store.search_facts(search_term)

        if not matches:
            await safe_send_reply(update.message, f"No matching memory found for '{search_term}'.")
        elif len(matches) == 1:
            result = await memory_tools.forget_fact(search_term)
            await safe_send_reply(update.message, result)
        else:
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup

            keyboard = [
                [InlineKeyboardButton(f["content"][:40], callback_data=f"forget_del_{f['id']}")]
                for f in matches[:10]
            ]
            await safe_send_reply(
                update.message,
                f"Found {len(matches)} matching facts - tap one to delete it:",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
    except Exception as e:
        logger.error(f"Error in forget_command: {e}", exc_info=True)
        await safe_send_reply(update.message, "An error occurred while trying to forget that.")


async def skills_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /skills command."""
    all_skills = skills_manager.get_all_skills()
    
    if not all_skills:
        await safe_send_reply(update.message, "🔧 No skills loaded yet. Add skill folders with tools.py to the skills directory!")
        return
    
    skills_list = ["🔧 *Available Skills:*\n"]
    
    for skill in all_skills:
        # Escape markdown special chars in dynamic content
        name = skill.name.replace("_", "\\_").replace("*", "\\*")
        desc = skill.description[:100] + "..." if len(skill.description) > 100 else skill.description
        desc = desc.replace("_", "\\_").replace("*", "\\*")
        skills_list.append(f"*{name}*")
        skills_list.append(f"_{desc}_")
        
        # Show tools provided by this skill
        if skill.tools:
            tool_names = [t.name.replace("_", "\\_") for t in skill.tools]
            skills_list.append(f"Tools: {', '.join(tool_names[:5])}")
            if len(tool_names) > 5:
                skills_list.append(f"  ...and {len(tool_names) - 5} more")
        skills_list.append("")
    
    # Show total stats
    total_tools = len(skills_manager.get_all_tools())
    skills_list.append(f"\n📊 Total: {len(all_skills)} skills, {total_tools} tools")
    
    try:
        await safe_send_reply(update.message, "\n".join(skills_list), parse_mode="Markdown")
    except Exception:
        # Fallback to plain text if markdown still fails
        await safe_send_reply(update.message, "\n".join(skills_list))


async def reminders_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /reminders command."""
    user_id = str(update.effective_user.id)
    
    if not is_user_authorized(user_id):
        await safe_send_reply(update.message, "🔒 Please verify your phone number first with /start")
        return
    
    try:
        reminders = await reminder_manager.get_user_reminders(user_id)
        
        if not reminders:
            await safe_send_reply(update.message, "📭 You don't have any active reminders.")
            return
        
        from datetime import datetime
        response_lines = ["⏰ **Your Active Reminders:**\n"]
        
        for i, reminder in enumerate(reminders, 1):
            scheduled = datetime.fromisoformat(reminder.scheduled_time)
            time_str = scheduled.strftime("%Y-%m-%d %I:%M %p")
            response_lines.append(f"{i}. {reminder.message}")
            response_lines.append(f"   📅 {time_str}\n")
        
        await safe_send_reply(update.message, "\n".join(response_lines))
    except Exception as e:
        logger.error(f"Error in reminders_command: {e}", exc_info=True)
        await safe_send_reply(update.message, "An error occurred retrieving your reminders.")


async def notes_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /notes command."""
    user_id = str(update.effective_user.id)
    
    if not is_user_authorized(user_id):
        await safe_send_reply(update.message, "🔒 Please verify your phone number first with /start")
        return
    
    try:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
        
        notes = notes_manager.get_notes(user_id)
        
        # Always show the mini app button at the top
        keyboard = [[
            InlineKeyboardButton(
                "📱 Open Notes App",
                web_app=WebAppInfo(url="https://03b6419ead58.ngrok-free.app/notes")
            )
        ]]
        
        if not notes:
            await safe_send_reply(
                update.message,
                "📝 You don't have any notes yet.\n\n"
                "Tell me to 'take note' or 'write down' something to create your first note!\n\n"
                "Or tap the button below to open the Notes app:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return
        
        # Show first 10 notes with pagination
        page = 0
        notes_per_page = 10
        
        # If context.args has a page number, use it
        if context.args:
            try:
                page = int(context.args[0])
            except (ValueError, IndexError):
                page = 0
        
        start_idx = page * notes_per_page
        end_idx = start_idx + notes_per_page
        page_notes = notes[start_idx:end_idx]
        
        from datetime import datetime
        response_lines = [f"📝 **Your Notes** (Page {page + 1}/{(len(notes) - 1) // notes_per_page + 1})\n"]
        
        for i, note in enumerate(page_notes, start=start_idx + 1):
            response_lines.append(f"\n**{i}.** {note.content[:100]}{'...' if len(note.content) > 100 else ''}")
            
            # Parse and format timestamp
            try:
                note_time = datetime.fromisoformat(note.created_at.replace('Z', '+00:00'))
                formatted_time = note_time.strftime('%b %d, %Y at %I:%M %p')
                response_lines.append(f"   _ID: {note.id} | {formatted_time}_")
            except:
                response_lines.append(f"   _ID: {note.id}_")
        
        response_lines.append(f"\n💡 Total notes: {len(notes)}")
        response_lines.append("\nTo delete a note, say: 'delete note [ID]'")
        response_lines.append("To search notes, say: 'search my notes for [query]'")
        
        # Add mini app button at the top
        mini_app_row = [
            InlineKeyboardButton(
                "📱 Open Notes App",
                web_app=WebAppInfo(url="https://03b6419ead58.ngrok-free.app/notes")
            )
        ]
        
        # Add pagination buttons
        nav_row = []
        
        if page > 0:
            nav_row.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"notes_page_{page - 1}"))
        
        if end_idx < len(notes):
            nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"notes_page_{page + 1}"))
        
        keyboard = [mini_app_row]
        if nav_row:
            keyboard.append(nav_row)
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await safe_send_reply(
            update.message,
            "\n".join(response_lines),
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Error in notes_command: {e}", exc_info=True)
        await safe_send_reply(update.message, f"Error displaying notes: {str(e)}")


async def stocks_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stocks command - show today's top stock movers."""
    user_id = str(update.effective_user.id)
    
    if not is_user_authorized(user_id):
        await safe_send_reply(update.message, "🔒 Please verify your phone number first with /start")
        return
    
    await safe_send_reply(update.message, "📊 Fetching today's top stocks...")
    
    try:
        from skills.stocks.yahoo_client import get_top_stocks
        
        result = await get_top_stocks()
        
        if not result.get("success"):
            await safe_send_reply(
                update.message,
                f"❌ Failed to fetch stock data: {result.get('error', 'Unknown error')}"
            )
            return
        
        lines = ["📊 *Today's Stock Market*\n"]
        
        # Gainers
        gainers = result.get("gainers", [])
        if gainers:
            lines.append("🟢 *Top Gainers*\n")
            for stock in gainers[:5]:
                arrow = "🔺"
                change_str = f"+${stock['change']} (+{stock['change_percent']}%)"
                lines.append(f"{arrow} *{stock['symbol']}* ${stock['price']} {change_str}")
            lines.append("")
        
        # Losers
        losers = result.get("losers", [])
        if losers:
            lines.append("🔴 *Top Losers*\n")
            for stock in losers[:5]:
                arrow = "🔻"
                change_str = f"${stock['change']} ({stock['change_percent']}%)"
                lines.append(f"{arrow} *{stock['symbol']}* ${stock['price']} {change_str}")
            lines.append("")
        
        # Most Active
        active = result.get("most_active", [])
        if active:
            lines.append("📈 *Most Active*\n")
            for stock in active[:5]:
                vol = f"{stock['volume'] / 1_000_000:.1f}M" if stock.get('volume') else "-"
                lines.append(f"  *{stock['symbol']}* ${stock['price']} (Vol: {vol})")
            lines.append("")
        
        lines.append("💡 Ask me about any specific ticker for more details!")
        
        await safe_send_reply(update.message, "\n".join(lines), parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Error in stocks_command: {e}", exc_info=True)
        await safe_send_reply(update.message, f"❌ Error fetching stock data: {str(e)}")


async def walmart_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /walmart command."""
    user_id = str(update.effective_user.id)
    
    if not is_user_authorized(user_id):
        await safe_send_reply(update.message, "🔒 Please verify your phone number first with /start")
        return
    
    try:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
        
        keyboard = [[
            InlineKeyboardButton(
                "🛒 Open Walmart Orders App",
                web_app=WebAppInfo(url="https://03b6419ead58.ngrok-free.app/walmart")
            )
        ]]
        
        await safe_send_reply(
            update.message,
            "🛒 **Walmart Orders**\n\n"
            "View all your Walmart orders, spending by category, and search for specific items.\n\n"
            "Tap the button below to open the Walmart Orders app:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        logger.error(f"Error in walmart_command: {e}", exc_info=True)
        await safe_send_reply(update.message, f"Error displaying Walmart orders: {str(e)}")


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /clear command — clears both context window and persisted history."""
    user_id = str(update.effective_user.id)
    if user_id in user_history_managers:
        await user_history_managers[user_id].clear()

    await safe_send_reply(update.message, "🗑️ Conversation history cleared! (Memory files from /memory are preserved)")


async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /history command — view persisted chat history with pagination."""
    user_id = str(update.effective_user.id)

    if not is_user_authorized(user_id):
        await safe_send_reply(update.message, "🔒 Please verify your phone number first with /start")
        return

    get_user_agent(user_id)  # ensure manager exists
    history_mgr = user_history_managers[user_id]

    # Determine page
    page = 0
    if context.args:
        try:
            page = max(0, int(context.args[0]) - 1)  # 1-indexed
        except ValueError:
            page = 0

    messages, total_pages, total_count = await history_mgr.get_page(page)

    if total_count == 0:
        await safe_send_reply(update.message, "📭 No chat history yet. Start a conversation!")
        return

    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    lines = [f"📜 **Chat History** (Page {page + 1}/{total_pages})\n"]

    for msg in messages:
        ts = msg.get("ts", "")
        try:
            dt = datetime.fromisoformat(ts)
            time_str = dt.strftime("%b %d %H:%M")
        except Exception:
            time_str = ""

        role_emoji = "👤" if msg["role"] == "user" else "🤖"
        content = msg["content"]
        # Truncate long messages for display
        if len(content) > 200:
            content = content[:197] + "..."

        lines.append(f"{role_emoji} *[{time_str}]* {content}\n")

    lines.append(f"\n💬 Total messages: {total_count}")
    lines.append("\nUsage: `/history [page]` — e.g. `/history 2`")

    # Pagination buttons
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"hist_{page - 1}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"hist_{page + 1}"))

    reply_markup = InlineKeyboardMarkup([nav_buttons]) if nav_buttons else None

    await safe_send_reply(update.message, "\n".join(lines), parse_mode="Markdown", reply_markup=reply_markup)


async def continue_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /continue command — show recent sessions to pick from."""
    user_id = str(update.effective_user.id)

    if not is_user_authorized(user_id):
        await safe_send_reply(update.message, "🔒 Please verify your phone number first with /start")
        return

    get_user_agent(user_id)  # ensure manager exists
    history_mgr = user_history_managers[user_id]

    sessions = await history_mgr.get_sessions()

    if not sessions:
        await safe_send_reply(update.message, "📭 No previous sessions found. Start a conversation!")
        return

    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    keyboard = []
    for sess in sessions[:MAX_SESSIONS_SHOWN]:
        try:
            first_dt = datetime.fromisoformat(sess["first_ts"])
            label = first_dt.strftime("%b %d %H:%M")
        except Exception:
            label = ""

        summary = sess.get("summary", "(no summary)") or "(empty session)"
        # Truncate label to fit button
        display = f"🕐 {label} — {summary[:30]}…" if len(summary) > 30 else f"🕐 {label} — {summary}"
        keyboard.append([InlineKeyboardButton(display, callback_data=f"cont_{sess['id']}")])

    # Add sessions button for full list
    keyboard.append([InlineKeyboardButton("📋 See all sessions", callback_data="sessions_list")])

    await safe_send_reply(
        update.message,
        "🔄 *Continue a previous conversation*\n\n"
        "Tap a session below to load its context and continue chatting:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def sessions_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /sessions command — list all past sessions."""
    user_id = str(update.effective_user.id)

    if not is_user_authorized(user_id):
        await safe_send_reply(update.message, "🔒 Please verify your phone number first with /start")
        return

    get_user_agent(user_id)
    history_mgr = user_history_managers[user_id]

    sessions = await history_mgr.get_sessions()

    if not sessions:
        await safe_send_reply(update.message, "📭 No previous sessions found.")
        return

    lines = [f"📋 *Your Conversation Sessions* ({len(sessions)} total)\n"]
    for sess in sessions:
        try:
            first_dt = datetime.fromisoformat(sess["first_ts"])
            last_dt = datetime.fromisoformat(sess["last_ts"])
            first_label = first_dt.strftime("%Y-%m-%d %H:%M")
            last_label = last_dt.strftime("%H:%M")
        except Exception:
            first_label = sess.get("first_ts", "")
            last_label = sess.get("last_ts", "")

        summary = sess.get("summary", "") or "(empty)"
        msg_count = sess.get("message_count", 0)
        lines.append(f"*[{sess['id']}]* {first_label} – {last_label}")
        lines.append(f"  {msg_count} messages")
        lines.append(f"  _{summary}_\n")

    lines.append("💡 Use `/continue` to pick a session to resume.")

    await safe_send_reply(update.message, "\n".join(lines), parse_mode="Markdown")


async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle callback queries from inline keyboards."""
    query = update.callback_query
    user_id = str(query.from_user.id)
    
    if not is_user_authorized(user_id):
        await query.answer("🔒 Please verify your phone number first with /start")
        return
    
    await query.answer()  # Acknowledge the callback
    
    # -- Continue a previous session -----------------------------------------
    if query.data.startswith("cont_"):
        try:
            session_id = int(query.data.split("_")[1])
            get_user_agent(user_id)
            history_mgr = user_history_managers[user_id]
            messages = await history_mgr.get_session(session_id)
            if messages:
                # Save back into history so the window is updated
                full_history = await history_mgr.load()
                await history_mgr.save(full_history)  # no-op but keeps state consistent
                # Store the active session ID so the next message loads this context
                active_file = config.MEMORY_DIR / str(user_id) / "active_session.json"
                import json as _json
                import aiofiles as _aiofiles
                async with _aiofiles.open(active_file, "w") as f:
                    await f.write(_json.dumps({"session_id": session_id, "loaded": True}))

                # Show confirmation with preview
                preview = messages[-1]["content"][:100]
                await query.edit_message_text(
                    f"✅ *Session loaded!*\n\n" 
                    f"I've loaded the conversation context. Continue chatting below.\n\n" 
                    f"_Last message: {preview}..._",
                    parse_mode="Markdown",
                )
            else:
                await query.edit_message_text("Session not found.")
        except Exception as e:
            logger.error(f"Error loading session: {e}", exc_info=True)
            await query.edit_message_text("An error occurred loading the session.")
        return

    # -- Forget a long-term memory fact (from /forget's candidate list) -----
    if query.data.startswith("forget_del_"):
        try:
            fact_id = query.data[len("forget_del_"):]
            from src.core.memory_tools import MemoryTools

            memory_tools = MemoryTools(user_id)
            result = await memory_tools.delete_fact_by_id(fact_id)
            await query.edit_message_text(result)
        except Exception as e:
            logger.error(f"Error in callback_query_handler for forget: {e}", exc_info=True)
            await query.edit_message_text("An error occurred trying to forget that.")
        return

    # -- Sessions list (full) ------------------------------------------------
    if query.data == "sessions_list":
        try:
            get_user_agent(user_id)
            history_mgr = user_history_managers[user_id]
            sessions = await history_mgr.get_sessions()
            lines = [f"📋 *All Sessions* ({len(sessions)})\n"]
            for sess in sessions:
                try:
                    first_dt = datetime.fromisoformat(sess["first_ts"])
                    label = first_dt.strftime("%b %d %H:%M")
                except Exception:
                    label = ""
                summary = sess.get("summary", "") or "(empty)"
                msg_count = sess.get("message_count", 0)
                lines.append(f"[{sess['id']}] {label} — {msg_count} msgs — _{summary[:40]}_")
            lines.append("\nUse `/continue` to pick one to resume.")

            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            # Add buttons for each session
            btns = []
            for sess in sessions[:MAX_SESSIONS_SHOWN]:
                btns.append([InlineKeyboardButton(
                    f"▶ {sess['id']}", callback_data=f"cont_{sess['id']}"
                )])

            await query.edit_message_text(
                "\n".join(lines),
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(btns) if btns else None,
            )
        except Exception as e:
            logger.error(f"Error listing sessions: {e}", exc_info=True)
            await query.edit_message_text("An error occurred.")
        return

    # Handle notes pagination
    if query.data.startswith("notes_page_"):
        try:
            page = int(query.data.split("_")[2])
            notes = notes_manager.get_notes(user_id)
            
            notes_per_page = 10
            start_idx = page * notes_per_page
            end_idx = start_idx + notes_per_page
            page_notes = notes[start_idx:end_idx]

            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            
            response_lines = [f"📝 **Your Notes** (Page {page + 1}/{(len(notes) - 1) // notes_per_page + 1})\n"]
            
            for i, note in enumerate(page_notes, start=start_idx + 1):
                created = datetime.fromisoformat(note.created_at)
                date_str = created.strftime("%b %d, %Y %I:%M %p")
                
                # Truncate long notes for display
                content = note.content if len(note.content) <= 100 else note.content[:97] + "..."
                response_lines.append(f"{i}. {content}")
                response_lines.append(f"   🕒 {date_str}")
                response_lines.append(f"   🆔 `{note.id}`\n")
            
            response_lines.append(f"\n💡 Total notes: {len(notes)}")
            response_lines.append("\nTo delete a note, say: 'delete note [ID]'")
            response_lines.append("To search notes, say: 'search my notes for [query]'")
            
            # Add pagination buttons
            keyboard = []
            nav_row = []
            
            if page > 0:
                nav_row.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"notes_page_{page - 1}"))
            
            if end_idx < len(notes):
                nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"notes_page_{page + 1}"))
            
            if nav_row:
                keyboard.append(nav_row)
            
            reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
            
            await query.edit_message_text(
                "\n".join(response_lines),
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"Error in callback_query_handler for notes: {e}", exc_info=True)
            await query.edit_message_text("An error occurred retrieving your notes.")

    # Handle history pagination
    elif query.data.startswith("hist_"):
        try:
            page = int(query.data.split("_")[1])
            get_user_agent(user_id)  # ensure manager exists
            history_mgr = user_history_managers[user_id]
            total = await history_mgr.count()
            if total == 0:
                await query.edit_message_text("No history found.")
                return

            messages, total_pages, total_count = await history_mgr.get_page(page)

            from telegram import InlineKeyboardButton, InlineKeyboardMarkup

            lines = [f"📜 **Chat History** (Page {page + 1}/{total_pages})\n"]

            for msg in messages:
                ts = msg.get("ts", "")
                try:
                    dt = datetime.fromisoformat(ts)
                    time_str = dt.strftime("%b %d %H:%M")
                except Exception:
                    time_str = ""

                role_emoji = "👤" if msg["role"] == "user" else "🤖"
                content = msg["content"]
                if len(content) > 200:
                    content = content[:197] + "..."

                lines.append(f"{role_emoji} *[{time_str}]* {content}\n")

            lines.append(f"\n💬 Total messages: {total_count}")

            nav_buttons = []
            if page > 0:
                nav_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"hist_{page - 1}"))
            if page < total_pages - 1:
                nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"hist_{page + 1}"))

            reply_markup = InlineKeyboardMarkup([nav_buttons]) if nav_buttons else None

            await query.edit_message_text(
                "\n".join(lines), parse_mode="Markdown", reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"Error in callback_query_handler for history: {e}", exc_info=True)
            await query.edit_message_text("An error occurred retrieving your history.")


async def code_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /code command - run OpenCode agent to make code changes."""
    global _opencode_task
    user_id = str(update.effective_user.id)

    if not is_user_authorized(user_id):
        await safe_send_reply(update.message, "🔒 Please verify your phone number first with /start")
        return

    # Get the message after /code
    message_text = ' '.join(context.args) if context.args else ''

    if not message_text:
        await safe_send_reply(
            update.message,
            "💻 **OpenCode Agent**\n\n"
            "Run the AI coding agent to make changes to the codebase.\n\n"
            "Usage: `/code <your request>`\n\n"
            "Example: `/code Add a weather skill that uses the OpenWeatherMap API`",
            parse_mode="Markdown"
        )
        return

    from skills.opencode.runner import is_running, run_opencode

    if is_running():
        await safe_send_reply(
            update.message,
            "⏳ OpenCode is already running a request. Please wait for it to finish."
        )
        return

    # Send initial status message that we'll keep editing
    status_msg = await update.message.reply_text(
        f"🚀 **OpenCode Agent**\n\n"
        f"📋 {message_text[:200]}\n\n"
        f"⏳ Starting...",
        parse_mode="Markdown"
    )
    logger.info(f"OpenCode request from user {user_id}: {message_text[:80]}")

    # Capture bot reference from the handler context (already initialized with httpx session)
    bot = context.bot

    # Run opencode in background and stream output
    async def _stream_opencode():
        activity_log = []     # list of short status lines
        files_changed = set() # track unique files modified
        last_edit_time = 0.0  # allow first edit immediately
        edit_interval = 2.0   # minimum seconds between message edits
        pending_text = None   # latest text waiting to be pushed

        def _build_status_text(current_line=""):
            """Build the live status message text."""
            lines = ["🚀 OpenCode Agent\n"]
            lines.append(f"📋 {message_text[:150]}\n")

            if files_changed:
                lines.append("Files touched:")
                for f in sorted(files_changed):
                    lines.append(f"  💾 {f}")
                lines.append("")

            # Show last N activity lines
            recent = activity_log[-8:]
            if recent:
                lines.append("Activity:")
                for entry in recent:
                    lines.append(entry)
                lines.append("")

            if current_line:
                lines.append(f"▶️ {current_line}")

            return "\n".join(lines)

        async def _safe_edit(text):
            """Edit the status message, handling Telegram rate limits."""
            nonlocal last_edit_time, pending_text
            now = asyncio.get_event_loop().time()
            elapsed = now - last_edit_time
            if elapsed < edit_interval:
                pending_text = text  # store for later
                return
            pending_text = None
            try:
                await bot.edit_message_text(
                    chat_id=user_id,
                    message_id=status_msg.message_id,
                    text=text[:4096]
                )
                last_edit_time = asyncio.get_event_loop().time()
            except Exception as e:
                logger.warning(f"Failed to edit status message: {e}")

        try:
            logger.info("OpenCode streaming task started")
            async for event in run_opencode(message_text):
                etype = event.get("type", "info")
                content = event.get("content", "")
                icon = _opencode_icon(etype)
                logger.info(f"OpenCode event: {etype} - {content[:80]}")

                if etype == "file_change":
                    fname = content.split(": ", 1)[-1] if ": " in content else content
                    files_changed.add(fname)
                    activity_log.append(f"{icon} {content}")
                    await _safe_edit(_build_status_text())

                elif etype == "tool_call":
                    activity_log.append(f"{icon} {content}")
                    await _safe_edit(_build_status_text())

                elif etype == "tool_result":
                    activity_log.append(f"  {content}")
                    await _safe_edit(_build_status_text())

                elif etype == "progress":
                    await _safe_edit(_build_status_text(content[:150]))

                elif etype in ("started", "completed", "error"):
                    activity_log.append(f"{icon} {content}")
                    await _safe_edit(_build_status_text())

            # Flush any pending edit
            if pending_text:
                try:
                    await bot.edit_message_text(
                        chat_id=user_id,
                        message_id=status_msg.message_id,
                        text=pending_text[:4096]
                    )
                except Exception:
                    pass

            # Final summary message
            summary_lines = ["✅ OpenCode Complete\n"]
            summary_lines.append(f"📋 {message_text[:150]}\n")
            if files_changed:
                summary_lines.append(f"Files changed ({len(files_changed)}):")
                for f in sorted(files_changed):
                    summary_lines.append(f"  💾 {f}")
            else:
                summary_lines.append("No files were modified.")

            final_text = "\n".join(summary_lines)
            try:
                await bot.edit_message_text(
                    chat_id=user_id,
                    message_id=status_msg.message_id,
                    text=final_text[:4096]
                )
            except Exception as e:
                logger.warning(f"Failed to send final summary: {e}")

            logger.info("OpenCode streaming task completed")

        except Exception as e:
            logger.error(f"OpenCode streaming error: {e}", exc_info=True)
            try:
                await bot.edit_message_text(
                    chat_id=user_id,
                    message_id=status_msg.message_id,
                    text=f"❌ OpenCode error: {str(e)}"
                )
            except Exception:
                pass

    _opencode_task = asyncio.create_task(_stream_opencode())


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    help_text = """🤖 **AI Companion Bot Help**

**Available Commands:**
/start - Start the bot and verify your phone
/history - View your chat history (paginated)
/continue - Continue a previous conversation
/sessions - List all past conversation sessions
/memory - View your memory statistics
/skills - List available skills
/reminders - View your active reminders
/notes - View and manage your notes
/code - Run OpenCode agent to make code changes
/stocks - Show today's top stock movers
/consolidate - Manually consolidate memories to long-term storage
/heartbeat - Manually trigger heartbeat cycle (for testing)
/clear - Clear chat history
/help - Show this help

**Features:**
- 🧠 Memory: I remember our conversations in daily markdown files
- ⏰ Reminders: I can set reminders and alarms for you
- 🔄 ReACT: I think step-by-step through complex problems
- 🔧 Skills: I have specialized capabilities to assist you
- 💓 Heartbeat: Autonomous checks every {config.HEARTBEAT_INTERVAL_MINUTES} minutes
- 💬 Natural conversation: Just chat with me normally!

**Tips:**
- Ask me complex questions and I'll think through them
- I can reference our past conversations
- Tell me to remind you about something at a specific time
- You can ask me about my skills at any time
"""
    
    await safe_send_reply(update.message, help_text)


async def heartbeat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /heartbeat command - manually trigger heartbeat."""
    user_id = str(update.effective_user.id)
    
    if not is_user_authorized(user_id):
        await safe_send_reply(update.message, "🔒 Please verify your phone number first with /start")
        return
    
    try:
        await safe_send_reply(update.message, "💓 Triggering heartbeat cycle...\n\nI'll continue responding to you while the heartbeat runs in the background. You'll receive a summary when it completes.")
        
        # Run heartbeat in background task so it doesn't block the bot
        asyncio.create_task(heartbeat_manager.execute_heartbeat())
        
    except Exception as e:
        logger.error(f"Error in heartbeat_command: {e}", exc_info=True)
        await safe_send_reply(update.message, "An error occurred triggering the heartbeat.")


async def consolidate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /consolidate command - manually consolidate memories to long-term."""
    user_id = str(update.effective_user.id)
    
    if not is_user_authorized(user_id):
        await safe_send_reply(update.message, "🔒 Please verify your phone number first with /start")
        return
    
    try:
        await safe_send_reply(update.message, "🧠 Starting memory consolidation...\nThis will move short-term memories (older than 7 days) to long-term memory.")
        
        # Get the user's memory manager and agent
        memory_manager = user_memories.get(user_id)
        agent = user_agents.get(user_id)
        
        if not memory_manager or not agent:
            await safe_send_reply(update.message, "❌ Could not find your memory or agent. Try sending a message first.")
            return
        
        # Run consolidation
        result = await memory_manager.consolidate_memories(agent)
        
        if result:
            await safe_send_reply(update.message, f"✅ Memory consolidation completed!\n\n{result}")
        else:
            await safe_send_reply(update.message, "ℹ️ No memories needed consolidation (nothing older than 7 days found).")
        
    except Exception as e:
        logger.error(f"Error in consolidate_command: {e}", exc_info=True)
        await safe_send_reply(update.message, f"❌ An error occurred during consolidation: {str(e)}")


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle document uploads (PDF processing)."""
    user = update.effective_user
    user_id = str(user.id)

    # Only allow authorized users
    if not is_user_authorized(user_id):
        await safe_send_reply(update.message, "🔒 Sorry, this bot is private.")
        return

    try:
        document = update.message.document
        
        # Check if it's a PDF
        if not document.file_name.lower().endswith('.pdf'):
            await safe_send_reply(update.message, "📄 I can only process PDF files. Please send a PDF document.")
            return
        
        interactions_logger.info(f"USER {user_id} uploaded document: {document.file_name}")
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        
        logger.info(f"Processing document from user {user_id}: {document.file_name}")
        
        # Download the document to temp location
        file = await context.bot.get_file(document.file_id)
        temp_path = Path(f"/tmp/{document.file_name}")
        await file.download_to_drive(temp_path)
        
        logger.info(f"Document downloaded to {temp_path}")
        
        # Get caption if provided
        caption = update.message.caption or ""
        
        # Notify user we're processing
        await safe_send_reply(update.message, "📄 Processing PDF... Detecting order type...")
        
        # Process the PDF
        from src.tools.pdf_tools import process_order_pdf
        result = await process_order_pdf(str(temp_path), document.file_name, caption)
        
        if result.get("success"):
            order_type = result.get("type", "unknown").capitalize()
            order_id = result.get("order_id")
            order_date = result.get("order_date")
            total = result.get("total_amount", 0)
            items_count = result.get("items_count", 0)
            
            response = f"✅ **{order_type} Order Processed!**\n\n"
            response += f"📦 Order ID: `{order_id}`\n"
            response += f"📅 Date: {order_date}\n"
            response += f"💰 Total: ${total:.2f}\n"
            response += f"🛒 Items: {items_count}\n\n"
            response += "Order has been added to the database!"
            
            await safe_send_reply(update.message, response)
            
            # Add to memory
            if user_id not in user_memories:
                user_memories[user_id] = MemoryManager(user_id)
            memory_manager = user_memories[user_id]
            
            await memory_manager.add_note(
                f"Uploaded {order_type} order PDF: {order_id} from {order_date} - ${total:.2f} ({items_count} items)"
            )
        else:
            error_msg = result.get("error", "Unknown error")
            order_type = result.get("type")
            
            if order_type:
                response = f"❌ Found {order_type.capitalize()} order but failed to process:\n{error_msg}"
            else:
                response = f"❌ Could not process PDF:\n{error_msg}\n\nPlease make sure this is a Walmart or Amazon order PDF."
            
            await safe_send_reply(update.message, response)
        
        # Clean up temp file if it still exists
        if temp_path.exists():
            temp_path.unlink()
            
    except Exception as e:
        logger.error(f"Error handling document from user {user_id}: {e}", exc_info=True)
        await safe_send_reply(
            update.message,
            "I apologize, but I encountered an error processing your document. Please try again."
        )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle photo uploads for analysis."""
    user = update.effective_user
    user_id = str(user.id)

    # Only allow authorized users
    if not is_user_authorized(user_id):
        await safe_send_reply(update.message, "🔒 Sorry, this bot is private.")
        return

    try:
        interactions_logger.info(f"USER {user_id} uploaded photo with caption: {update.message.caption or '(none)'}")
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        
        logger.info(f"Processing photo from user {user_id}")

        # Get the largest photo
        photo = update.message.photo[-1]
        api_logger.debug(f"Downloading photo file_id={photo.file_id}")
        
        # Get memory manager to access uploads directory
        if user_id not in user_memories:
            user_memories[user_id] = MemoryManager(user_id)
        memory_manager = user_memories[user_id]
        
        # Download photo
        file = await context.bot.get_file(photo.file_id)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = memory_manager.uploads_dir / f"photo_{timestamp}.jpg"
        await file.download_to_drive(file_path)
        
        logger.info(f"Photo saved to {file_path}")
        
        # Get caption if provided
        caption = update.message.caption or ""
        
        # Step 1: Use facial recognition to detect and identify faces
        await safe_send_reply(update.message, "🔍 Detecting faces...")
        
        try:
            # Import the facial recognition skill
            from skills.facial_recognition import face_recognition_tool
            
            # Detect faces
            detect_result = await face_recognition_tool.detect_faces(str(file_path), user_id)
            logger.info(f"Face detection: {detect_result}")
            
            # Try to identify faces
            identify_result = await face_recognition_tool.identify_faces(str(file_path), user_id)
            logger.info(f"Face identification: {identify_result}")
            
            face_info = f"\n\n**Facial Recognition:**\n{identify_result}"
            
            # Check if user is labeling someone in the caption
            # Only learn names if caption explicitly indicates labeling (not questions!)
            if caption:
                caption_lower = caption.lower().strip()
                
                # Exclude questions and common non-name phrases
                question_words = ["who", "what", "where", "when", "why", "how", "?"]
                is_question = any(word in caption_lower for word in question_words)
                
                # Only process if it's clearly a labeling statement
                label_indicators = ["this is", "meet", "that's", "thats", "that is"]
                has_label_indicator = any(indicator in caption_lower for indicator in label_indicators)
                
                # Check for possessive indicators that suggest relationship (my sister, my friend, etc.)
                possessive_patterns = ["my ", "our ", "his ", "her ", "their "]
                has_possessive = any(pattern in caption_lower for pattern in possessive_patterns)
                
                # Only learn if: has label indicator OR (has possessive AND short caption) AND NOT a question
                should_learn = (has_label_indicator or (has_possessive and len(caption.split()) <= 5)) and not is_question
                
                if should_learn:
                    # Extract potential name from caption
                    name = caption
                    
                    # Remove label indicators
                    for indicator in ["this is", "meet", "that's", "thats", "that is"]:
                        name = name.lower().replace(indicator, "").strip()
                    
                    # Handle possessive patterns (e.g., "my sister Sarah" -> "Sarah")
                    for pattern in possessive_patterns:
                        if pattern in name:
                            # Split and take the last part after possessive (likely the name)
                            parts = name.split(pattern, 1)[1].split()
                            # Take last word as it's likely the name
                            if len(parts) >= 2:
                                name = parts[-1]  # Last word is usually the name
                            else:
                                name = parts[0] if parts else ""
                            break
                    
                    name = name.strip().strip(",.!?").title()
                    
                    # Additional validation: name should be reasonable length and not empty
                    if name and 2 <= len(name) <= 30 and not any(q in name.lower() for q in question_words):
                        # Add this person to the database
                        add_result = await face_recognition_tool.add_person(
                            name, str(file_path), user_id, caption
                        )
                        logger.info(f"Added person: {add_result}")
                        face_info += f"\n\n{add_result}"
        
        except Exception as face_error:
            logger.warning(f"Facial recognition error (will continue with vision): {face_error}")
            face_info = "\n\n_Facial recognition not available, using vision analysis only._"
        
        # Step 2: Use vision analysis via the configured LLM provider
        await safe_send_reply(update.message, "📸 Analyzing image details...")

        # Read and encode image
        with open(file_path, "rb") as image_file:
            image_data = base64.b64encode(image_file.read()).decode('utf-8')

        analysis_prompt = f"""Analyze this image in detail. Focus on:
1. **People**: Describe any people visible (physical appearance, clothing, expressions, what they're doing)
2. **Context**: Where was this taken? What's the setting?
3. **Activity**: What's happening in this photo?
4. **Details**: Notable objects, background, mood/atmosphere

User's caption: "{caption or '(no caption)'}"

Provide a detailed but concise analysis."""

        provider = get_llm_provider()
        if provider.supports_vision:
            analysis = await provider.complete_vision(analysis_prompt, image_b64=image_data, max_tokens=800)
        elif config.OPENAI_API_KEY:
            # Primary provider (e.g. a local llama.cpp server) lacks vision,
            # but OpenAI creds exist - fall back to a one-off OpenAI vision call.
            fallback = OpenAIProvider(
                api_key=config.OPENAI_API_KEY, base_url=None, model="gpt-4o", supports_vision=True,
            )
            analysis = await fallback.complete_vision(analysis_prompt, image_b64=image_data, max_tokens=800)
        else:
            await safe_send_reply(
                update.message,
                "Image analysis needs OpenAI or Anthropic configured "
                "(set OPENAI_API_KEY, or CHAT_PROVIDER=anthropic with ANTHROPIC_API_KEY)."
            )
            return

        logger.info(f"Image analysis completed: {analysis[:200]}...")
        
        # Save analysis to long-term memory
        memory_content = f"""## Photo Analysis [{timestamp}]

**File**: {file_path.name}
**Caption**: {caption or "(no caption)"}

**Vision Analysis**:
{analysis}

**Facial Recognition**:
{identify_result}
"""
        
        # Save to appropriate memory categories
        if any(word in analysis.lower() for word in ['person', 'people', 'man', 'woman', 'child', 'friend', 'family']):
            await memory_manager.add_long_term_memory('relationships', memory_content)
            logger.info("Saved photo analysis to relationships memory")
        
        await memory_manager.add_long_term_memory('important_facts', memory_content)
        logger.info("Saved photo analysis to important_facts memory")
        
        # Add to today's short-term memory
        await memory_manager.add_note(f"Shared photo: {caption or '(no caption)'}\n\nAnalysis: {analysis}\n\nFaces: {identify_result}")
        
        # Send response
        response_text = f"📸 **Image Analysis**\n\n{analysis}{face_info}\n\n✅ Saved to memory!"
        await safe_send_reply(update.message, response_text)
        
    except Exception as e:
        logger.error(f"Error handling photo from user {user_id}: {e}", exc_info=True)
        await safe_send_reply(
            update.message,
            "I apologize, but I encountered an error analyzing your photo. Please try again."
        )


async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle contact sharing for phone verification."""
    try:
        user = update.effective_user
        user_id = str(user.id)
        contact = update.message.contact
        
        logger.info(f"User {user_id} ({user.username}) shared contact")
        
        # Check if contact is user's own contact
        if contact.user_id != user.id:
            await safe_send_reply(update.message, "❌ Please share your own contact information.")
            return
        
        # Get phone number and normalize (remove + and spaces)
        phone_number = contact.phone_number.replace("+", "").replace(" ", "").replace("-", "")
        
        # Check if phone number matches allowed number
        allowed_number = config.ALLOWED_PHONE_NUMBER.replace("+", "").replace(" ", "").replace("-", "")
        
        if phone_number.endswith(allowed_number) or allowed_number.endswith(phone_number):
            # Authorize user
            authorized_users[user_id] = phone_number
            _save_authorized_users()
            
            from telegram import ReplyKeyboardRemove
            await safe_send_reply(
                update.message,
                f"✅ Phone number verified! Welcome {user.first_name}!\n\nYou can now use all bot features. Send /start to begin.",
                reply_markup=ReplyKeyboardRemove()
            )
            
            logger.info(f"User {user_id} authorized with phone {phone_number}")
        else:
            await safe_send_reply(
                update.message,
                "❌ Sorry, your phone number is not authorized to use this bot."
            )
    except Exception as e:
        logger.error(f"Error in handle_contact: {e}", exc_info=True)
        await safe_send_reply(update.message, "An error occurred during verification. Please try again.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming messages."""
    # Handle both regular messages and edited messages
    message = update.message or update.edited_message
    
    if not message or not message.text:
        logger.debug("Received update without text message, ignoring")
        return
    
    user = update.effective_user
    user_id = str(user.id)
    message_text = message.text
    
    # Log the incoming interaction
    interactions_logger.info(f"USER {user_id} ({user.first_name} {user.last_name or ''}): {message_text}")
    
    # Only allow authorized users
    if not is_user_authorized(user_id):
        interactions_logger.warning(f"Unauthorized user {user_id} attempted access")
        await safe_send_reply(message, "🔒 Sorry, this bot is private.")
        return
    
    # Show typing indicator
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    # Let skill tools (e.g. skills/tts's speak_text) that have no direct
    # access to `context`/`update` reach the current chat - reset in the
    # finally below regardless of success/failure.
    chat_id_token = current_chat_id.set(update.effective_chat.id)

    try:
        logger.info(f"Processing message from user {user_id}: {message_text[:100]}...")
        
        # Get user's agent
        agent = get_user_agent(user_id)

        # Check if user loaded a session to continue from
        import aiofiles as _aiofiles
        active_file = config.MEMORY_DIR / user_id / "active_session.json"
        conversation_history: List[Dict] = []
        if active_file.exists():
            try:
                async with _aiofiles.open(active_file, "r") as f:
                    data = json.loads(await f.read())
                session_id = data.get("session_id")
                if session_id is not None:
                    history_mgr = user_history_managers[user_id]
                    conversation_history = await history_mgr.get_session(session_id)
                    logger.info(f"Loaded session {session_id} with {len(conversation_history)} messages for user {user_id}")
            except Exception as e:
                logger.warning(f"Failed to load active session for {user_id}: {e}")
        if not conversation_history:
            # Normal sliding window
            history_mgr = user_history_managers[user_id]
            conversation_history = await history_mgr.get_messages()

        # Clear the active session marker so subsequent messages use normal window
        if active_file.exists():
            try:
                active_file.unlink()
            except Exception:
                pass

        logger.debug(f"Conversation history length: {len(conversation_history)} messages")

        # Create a progress callback to send status updates
        async def send_progress(status_text: str):
            """Send a progress update to the user."""
            try:
                await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
                await safe_send_reply(message, f"_💭 {status_text}_", parse_mode="Markdown")
                logger.debug(f"Sent progress update to {user_id}: {status_text}")
            except Exception as e:
                logger.warning(f"Failed to send progress update: {e}")
        
        # Process message through ReACT agent with progress callback
        response = await agent.think(message_text, conversation_history, progress_callback=send_progress)
        
        # Persist conversation history (survives restarts)
        await history_mgr.append(message_text, response)

        # Save to daily memory
        memory_manager = user_memories[user_id]
        await memory_manager.add_interaction(message_text, response)
        logger.info(f"Successfully responded to user {user_id}")
        
        # Log the response
        interactions_logger.info(f"ASSISTANT -> USER {user_id}: {response[:200]}{'...' if len(response) > 200 else ''}")
        
        # Send response
        await safe_send_reply(message, response)
        
    except Exception as e:
        error_logger.error(f"Error handling message from user {user_id if 'user_id' in locals() else 'unknown'}: {e}", exc_info=True)
        try:
            await safe_send_reply(
                message,
                "I apologize, but I encountered an error processing your message. Please try again."
            )
        except:
            error_logger.error("Failed to send error message to user", exc_info=True)
    finally:
        current_chat_id.reset(chat_id_token)


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors."""
    logger.error(f"Update {update} caused error {context.error}", exc_info=context.error)
    
    # Try to notify user if possible
    try:
        if update and update.effective_message:
            await safe_send_reply(
                update.effective_message,
                "An unexpected error occurred. The issue has been logged."
            )
    except:
        pass


async def post_init(application: Application) -> None:
    """Initialize managers after application starts.
    
    Args:
        application: Telegram application instance
    """
    logger.info("Initializing bot...")
    
    # Validate configuration
    config.validate_config()
    
    # Inject reminder manager into reminder skill tools
    set_reminder_manager(reminder_manager)
    
    # Inject notes manager into notes skill tools
    set_notes_manager(notes_manager)

    # Inject watchlist manager into watchlist skill tools
    set_watchlist_manager(watchlist_manager)

    # Load skills
    await skills_manager.load_skills()
    logger.info(f"Loaded {len(skills_manager.get_all_skills())} skills")
    
    # Start reminder manager
    reminder_manager.set_callback(send_reminder)
    await reminder_manager.start()
    logger.info("Reminder manager started")
    
    # Setup and start heartbeat manager
    heartbeat_manager.set_user_agents_callback(lambda: user_agents)
    heartbeat_manager.set_user_memories_callback(lambda: user_memories)
    heartbeat_manager.set_send_message_callback(send_reminder)  # Reuse send_reminder for now
    await heartbeat_manager.start()
    logger.info(f"Heartbeat manager started with {config.HEARTBEAT_INTERVAL_MINUTES} minute interval")

    logger.info("OpenCode integration ready (use /code to trigger)")


async def post_shutdown(application: Application) -> None:
    """Clean up managers after application shuts down.
    
    Args:
        application: Telegram application instance
    """
    await reminder_manager.stop()
    await heartbeat_manager.stop()
    # Cancel any running OpenCode task
    global _opencode_task
    if _opencode_task and not _opencode_task.done():
        _opencode_task.cancel()
        _opencode_task = None
    logger.info("Managers stopped")


def main():
    """Start the bot."""
    # Suppress noisy httpx logging
    logging.getLogger("httpx").setLevel(logging.WARNING)
    
    # Create application
    application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).post_init(post_init).post_shutdown(post_shutdown).build()
    
    # Register handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("memory", memory_command))
    application.add_handler(CommandHandler("forget", forget_command))
    application.add_handler(CommandHandler("skills", skills_command))
    application.add_handler(CommandHandler("reminders", reminders_command))
    application.add_handler(CommandHandler("notes", notes_command))
    application.add_handler(CommandHandler("walmart", walmart_command))
    application.add_handler(CommandHandler("stocks", stocks_command))
    application.add_handler(CommandHandler("heartbeat", heartbeat_command))
    application.add_handler(CommandHandler("consolidate", consolidate_command))
    application.add_handler(CommandHandler("clear", clear_command))
    application.add_handler(CommandHandler("history", history_command))
    application.add_handler(CommandHandler("continue", continue_command))
    application.add_handler(CommandHandler("sessions", sessions_command))
    application.add_handler(CommandHandler("code", code_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(callback_query_handler))
    application.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.Document.PDF, handle_document))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Register error handler
    application.add_error_handler(error_handler)
    
    # Start bot
    logger.info("Starting bot...")
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        poll_interval=2.0,  # Wait 2 seconds between getUpdates calls
        timeout=30,  # Long polling timeout
        drop_pending_updates=True  # Ignore old messages on startup
    )


if __name__ == "__main__":
    main()
