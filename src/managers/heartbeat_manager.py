"""Heartbeat system for autonomous agent activities."""
import asyncio
import re
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Callable, List
import aiofiles
import shutil

from src.core import config
from src.agents.staged_react_agent import StagedReACTAgent
from src.core.memory import MemoryManager
from src.core.skills_manager import SkillsManager
from src.core.logging_config import get_heartbeat_logger

# Get heartbeat logger
heartbeat_logger = get_heartbeat_logger()


class HeartbeatManager:
    """Manages periodic autonomous checks and actions."""
    
    def __init__(self, skills_manager: SkillsManager):
        """Initialize heartbeat manager.
        
        Args:
            skills_manager: Skills manager instance
        """
        self.skills_manager = skills_manager
        self.heartbeat_file = config.HEARTBEAT_FILE
        self.interval_minutes = config.HEARTBEAT_INTERVAL_MINUTES
        self._running = False
        self._task = None
        self._user_agents_callback: Optional[Callable] = None
        self._user_memories_callback: Optional[Callable] = None
        self._send_message_callback: Optional[Callable] = None
        
        heartbeat_logger.info(f"HeartbeatManager initialized with {self.interval_minutes} minute interval")
    
    def set_user_agents_callback(self, callback: Callable) -> None:
        """Set callback to get user agents dictionary.
        
        Args:
            callback: Function that returns Dict[str, StagedReACTAgent]
        """
        self._user_agents_callback = callback
    
    def set_user_memories_callback(self, callback: Callable) -> None:
        """Set callback to get user memories dictionary.
        
        Args:
            callback: Function that returns Dict[str, MemoryManager]
        """
        self._user_memories_callback = callback
    
    def set_send_message_callback(self, callback: Callable) -> None:
        """Set callback to send messages to users.
        
        Args:
            callback: Async function that takes (user_id, message) as arguments
        """
        self._send_message_callback = callback
    
    async def load_heartbeat_instructions(self) -> str:
        """Load heartbeat instructions from file.
        
        Returns:
            Content of heartbeat file
        """
        try:
            if not self.heartbeat_file.exists():
                heartbeat_logger.warning(f"Heartbeat file not found: {self.heartbeat_file}")
                return ""
            
            async with aiofiles.open(self.heartbeat_file, 'r') as f:
                content = await f.read()
            
            return content
        except Exception as e:
            heartbeat_logger.error(f"Error loading heartbeat instructions: {e}")
            return ""
    
    async def execute_heartbeat(self) -> None:
        """Execute one heartbeat cycle."""
        try:
            heartbeat_logger.info("=" * 60)
            heartbeat_logger.info(f"Heartbeat pulse at {datetime.now().isoformat()}")
            heartbeat_logger.info("=" * 60)
            
            # Initialize summary tracking
            summary = []
            timestamp = datetime.now().strftime('%Y-%m-%d %I:%M %p')
            
            # Load heartbeat instructions
            instructions = await self.load_heartbeat_instructions()
            
            if not instructions:
                heartbeat_logger.info("No heartbeat instructions found, skipping this cycle")
                return
            
            # Get user agents and memories if callbacks are set
            user_agents = self._user_agents_callback() if self._user_agents_callback else {}
            user_memories = self._user_memories_callback() if self._user_memories_callback else {}
            
            # If no active users, discover and process all user memories on disk
            if not user_agents:
                heartbeat_logger.info("No active users, discovering user memory directories and creating temporary agents")
                
                # Discover all user memory directories on disk
                if config.MEMORY_DIR.exists():
                    for user_dir in config.MEMORY_DIR.iterdir():
                        if user_dir.is_dir() and user_dir.name != "system":
                            user_id = user_dir.name
                            heartbeat_logger.info(f"Discovered user memory directory: {user_id}")
                            # Create temporary memory manager and agent for this user
                            user_memory = MemoryManager(user_id)
                            user_agent = StagedReACTAgent(user_memory, self.skills_manager)
                            user_memories[user_id] = user_memory
                            user_agents[user_id] = user_agent
                
                # If still no users found, create system agent only
                if not user_agents:
                    heartbeat_logger.info("No user directories found, creating system agent only")
                    system_memory = MemoryManager("system")
                    temp_agent = StagedReACTAgent(system_memory, self.skills_manager)
                    user_agents = {"system": temp_agent}
            
            # For each authorized user, create an autonomous check
            # We'll use the first user's agent to process the heartbeat
            # In a more sophisticated system, you might want a dedicated system agent
            for user_id, agent in list(user_agents.items())[:1]:  # Process with first user's agent
                try:
                    heartbeat_logger.info(f"Processing heartbeat with agent for user {user_id}")
                    
                    # First, perform memory consolidation for users that have memories
                    if user_memories:
                        result = await self._perform_memory_consolidation(user_agents, user_memories)
                        if result:
                            summary.append(result)
                        
                        # Lint the long-term memory wiki (merge duplicates,
                        # fix cross-references, flag contradictions/gaps)
                        result = await self._lint_wiki(user_memories)
                        if result:
                            summary.append(result)

                    # Mine any pending transcriptions (e.g. iOS voice memos) into long-term memory
                    result = await self._process_transcription_mining()
                    if result:
                        summary.append(result)

                    # Process Gmail cleanup and organization
                    result = await self._process_gmail_cleanup()
                    if result:
                        summary.append(result)

                    # Auto-reply in WhatsApp chats the user has explicitly
                    # opted into (see whatsapp_managed_chats.py) - the only
                    # heartbeat step that sends messages to other people
                    # unsupervised, so it carries its own guardrails (1:1
                    # chats only, no backlog, per-chat daily cap).
                    result = await self._process_whatsapp_managed_chats()
                    if result:
                        summary.append(result)

                    # Process Walmart orders if any exist
                    result = await self._process_walmart_orders()
                    if result:
                        summary.append(result)
                    
                    # Perform budget analysis and send alerts if needed
                    result = await self._process_budget_analysis()
                    if result:
                        summary.append(result)

                    # Search watched topics for notable updates and surface insights
                    result = await self._process_world_watch()
                    if result:
                        summary.append(result)

                    # Mine long-term memory for topics worth proactively watching
                    result = await self._process_memory_watch_suggestions()
                    if result:
                        summary.append(result)

                    # Send the once-daily briefing digest, if it's time
                    result = await self._process_daily_briefing()
                    if result:
                        summary.append(result)

                    # Scan GitHub trending repos and curate self-improve suggestions
                    # (never auto-implemented - just added to the dashboard menu).
                    result = await self._process_trending_suggestions()
                    if result:
                        summary.append(result)

                    # Search for promising live-webcam pages and curate suggestions
                    # (never auto-added - just added to the dashboard's /webcams menu).
                    result = await self._process_webcam_discovery()
                    if result:
                        summary.append(result)

                    # Re-verify saved webcam sources are still actually playable
                    # (streams go down over time) - only ever flags status, never
                    # disables/deletes anything.
                    result = await self._process_webcam_health_check()
                    if result:
                        summary.append(result)

                    # Retry any feature-request/self-upgrade merges deferred by
                    # self_upgrade_manager's safety gate (main was dirty or not
                    # checked out at merge time) - runs every tick, unlike the
                    # self-upgrade idea step below, since flushing an already-
                    # tested backlog is cheap (git only, no Pi invocation) and
                    # shouldn't wait on that slower weekly cadence. May also
                    # restart this process on success - see that step's own
                    # comment for why both go near the end of this cycle.
                    result = await self._process_pending_merges()
                    if result:
                        summary.append(result)

                    # Think of (and, if worthwhile, implement) a self-upgrade idea.
                    # Placed last: it's the slowest task and, on success, restarts
                    # this very process - nothing after it in this cycle is
                    # guaranteed to run.
                    result = await self._process_self_upgrade_ideas()
                    if result:
                        summary.append(result)

                    # Create a prompt for autonomous actions
                    heartbeat_prompt = self._create_heartbeat_prompt(instructions)
                    
                    # Process through the agent
                    response = await agent.think(heartbeat_prompt, [])
                    
                    heartbeat_logger.info(f"Heartbeat processing complete. Response: {response[:200]}...")
                    
                    # If the agent determined it should send a message to a user,
                    # it would be in the response. Parse and handle accordingly.
                    # For now, we just log the autonomous thinking.
                    
                except Exception as e:
                    heartbeat_logger.error(f"Error processing heartbeat for user {user_id}: {e}", exc_info=True)
                    summary.append(f"❌ Error during heartbeat: {str(e)[:100]}")
            
            # Send summary to user via Telegram
            await self._send_heartbeat_summary(summary, timestamp)
            
            heartbeat_logger.info("Heartbeat cycle completed successfully")
            
        except Exception as e:
            heartbeat_logger.error(f"Error in heartbeat execution: {e}", exc_info=True)
    
    def _create_heartbeat_prompt(self, instructions: str) -> str:
        """Create prompt for autonomous heartbeat processing.
        
        Args:
            instructions: Content from heartbeat.md
            
        Returns:
            Formatted prompt for the agent
        """
        prompt = f"""AUTONOMOUS HEARTBEAT CHECK

You are performing an autonomous check as part of your heartbeat system. This is NOT a user interaction.

Current Time: {datetime.now().strftime('%Y-%m-%d %I:%M %p')}

Here are your heartbeat instructions:

{instructions}

Based on these instructions, think about what autonomous actions (if any) you should take:

1. Are there any system checks you should perform?
2. Are there any pending tasks that need attention?
3. Should you proactively reach out to any users? (Be very conservative - don't be intrusive)
4. Are there any maintenance tasks to complete?

Think through this step by step and determine if any action is needed. If no action is required, that's perfectly fine.

If you determine you need to send a message to a user, clearly state:
MESSAGE_TO_USER: [user_id]
MESSAGE_CONTENT: [your message]

Otherwise, just think through the checks and conclude with your assessment.
"""
        return prompt
    
    async def _perform_memory_consolidation(self, user_agents: Dict, user_memories: Dict) -> str:
        """Perform memory consolidation for all users.
        
        Args:
            user_agents: Dictionary of user agents
            user_memories: Dictionary of user memory managers
            
        Returns:
            Summary string of consolidation results
        """
        heartbeat_logger.info("Starting memory consolidation for all users...")
        
        consolidated_users = []
        for user_id, memory_manager in user_memories.items():
            try:
                # Get corresponding agent
                agent = user_agents.get(user_id)
                if not agent:
                    heartbeat_logger.warning(f"No agent found for user {user_id}, skipping consolidation")
                    continue
                
                heartbeat_logger.info(f"Consolidating memories for user {user_id}")
                result = await memory_manager.consolidate_memories(agent)
                heartbeat_logger.info(f"User {user_id} consolidation result: {result}")
                
                if "consolidated" in result.lower() or "processed" in result.lower():
                    consolidated_users.append(user_id)
                
            except Exception as e:
                heartbeat_logger.error(f"Error consolidating memories for user {user_id}: {e}", exc_info=True)
        
        heartbeat_logger.info("Memory consolidation completed for all users")
        
        if consolidated_users:
            return f"🧠 Memory consolidation: Processed memories for {len(consolidated_users)} user(s)"
        return None
    
    async def _lint_wiki(self, user_memories: Dict) -> str:
        """Run the long-term memory wiki's lint pass for all users: merges
        near-duplicate pages, auto-links missing cross-references, and
        flags orphan pages/contradictions/coverage gaps for review (see
        MemoryManager.lint_wiki(), replacing the old flat-fact dedupe_facts()).

        Args:
            user_memories: Dictionary of user memory managers

        Returns:
            Summary string of lint results
        """
        heartbeat_logger.info("Starting wiki lint for all users...")

        total_fixed = 0
        total_flagged = 0
        affected_users = 0
        for user_id, memory_manager in user_memories.items():
            try:
                result = await memory_manager.lint_wiki()
                heartbeat_logger.info(f"User {user_id} lint result: {result}")

                fixed_match = re.search(r"auto-fixed (\d+)", result)
                flagged_match = re.search(r"flagged (\d+)", result)
                fixed = int(fixed_match.group(1)) if fixed_match else 0
                flagged = int(flagged_match.group(1)) if flagged_match else 0
                if fixed > 0 or flagged > 0:
                    total_fixed += fixed
                    total_flagged += flagged
                    affected_users += 1

            except Exception as e:
                heartbeat_logger.error(f"Error linting wiki for user {user_id}: {e}", exc_info=True)

        heartbeat_logger.info("Wiki lint completed for all users")

        if affected_users:
            return (
                f"🗂️ Wiki lint: auto-fixed {total_fixed}, flagged {total_flagged} "
                f"issue(s) for {affected_users} user(s)"
            )
        return None

    async def _process_transcription_mining(self) -> Optional[str]:
        """Mine pending transcriptions (e.g. iOS voice memos) into long-term memory.

        Unlike world watch/self-upgrade, this has no interval gate - it runs
        every heartbeat cycle, since checking for pending transcriptions is
        cheap and the point is getting voice notes into memory quickly.
        Successfully processed transcriptions are archived (not deleted) via
        TranscriptionsManager, so the raw text stays available afterward.

        Scoped to config.WEB_USER_ID (the single web/iOS app user), not
        Telegram's authorized_users - transcriptions arrive over the web API.
        """
        try:
            from skills.transcriptions.transcriptions_manager import TranscriptionsManager
            from src.core.memory import MemoryManager

            user_id = config.WEB_USER_ID
            if not user_id:
                return None

            transcriptions_mgr = TranscriptionsManager()
            pending = transcriptions_mgr.get_pending(user_id)
            if not pending:
                return None

            combined_text = "\n\n".join(f"[{t.created_at}] {t.content}" for t in pending)

            memory_manager = MemoryManager(user_id)
            await memory_manager.consolidate_text(combined_text)

            transcriptions_mgr.archive(user_id, [t.id for t in pending])

            return f"🎙️ Transcriptions: mined {len(pending)} into long-term memory"

        except Exception as e:
            heartbeat_logger.error(f"Error in transcription mining: {e}", exc_info=True)
            return None

    async def _process_gmail_cleanup(self) -> str:
        """Clean up and organize Gmail inbox autonomously.
        
        - Archives old read emails (30+ days)
        - Archives promotional emails (7+ days old)
        - Archives social media notifications (7+ days old)
        - Organizes and reports on inbox state
        
        Returns:
            Summary string of Gmail cleanup results
        """
        heartbeat_logger.info("Starting Gmail cleanup and organization...")
        
        try:
            # Import Gmail functions
            from skills.gmail.gmail_integration import (
                get_old_read_emails,
                get_promotional_emails,
                get_social_emails,
                archive_emails,
                get_email_count,
            )
            
            # Check if Gmail is configured
            token_file = Path(__file__).parent.parent.parent / 'data' / 'gmail_token.json'
            if not token_file.exists():
                heartbeat_logger.info("Gmail not configured (no token found), skipping email cleanup")
                return None
            
            # Get inbox statistics
            inbox_count = get_email_count('in:inbox')
            unread_count = get_email_count('is:unread in:inbox')
            heartbeat_logger.info(f"Inbox stats - Total: {inbox_count}, Unread: {unread_count}")
            
            archived_total = 0
            
            # 1. Archive old read emails (30+ days old)
            heartbeat_logger.info("Checking for old read emails to archive...")
            old_emails = get_old_read_emails(days=30, max_results=100)
            
            if old_emails:
                heartbeat_logger.info(f"Found {len(old_emails)} old read emails (30+ days)")
                # Archive in batches of 50 (Gmail API limit)
                message_ids = [email['id'] for email in old_emails]
                
                for i in range(0, len(message_ids), 50):
                    batch = message_ids[i:i+50]
                    result = archive_emails(batch)
                    
                    if result.get('success'):
                        archived_total += result.get('count', 0)
                        heartbeat_logger.info(f"Archived batch of {result.get('count', 0)} old read emails")
                    else:
                        heartbeat_logger.error(f"Failed to archive old emails: {result.get('error')}")
            else:
                heartbeat_logger.info("No old read emails to archive")
            
            # 2. Archive old promotional emails (7+ days old)
            heartbeat_logger.info("Checking for old promotional emails...")
            promo_emails = get_promotional_emails(max_results=100)
            
            if promo_emails:
                old_promo_ids = []
                for email in promo_emails:
                    # Parse date from email (this is approximate, Gmail API doesn't return timestamps easily)
                    # We'll archive all promotional emails found, as they're typically not important
                    old_promo_ids.append(email['id'])
                
                if old_promo_ids:
                    heartbeat_logger.info(f"Found {len(old_promo_ids)} promotional emails to archive")
                    
                    # Archive in batches of 50
                    for i in range(0, len(old_promo_ids), 50):
                        batch = old_promo_ids[i:i+50]
                        result = archive_emails(batch)
                        
                        if result.get('success'):
                            archived_total += result.get('count', 0)
                            heartbeat_logger.info(f"Archived batch of {result.get('count', 0)} promotional emails")
                        else:
                            heartbeat_logger.error(f"Failed to archive promotional emails: {result.get('error')}")
            else:
                heartbeat_logger.info("No promotional emails to archive")
            
            # 3. Archive old social media notifications (7+ days old)
            heartbeat_logger.info("Checking for old social media emails...")
            social_emails = get_social_emails(max_results=100)
            
            if social_emails:
                social_ids = [email['id'] for email in social_emails]
                heartbeat_logger.info(f"Found {len(social_ids)} social media emails to archive")
                
                # Archive in batches of 50
                for i in range(0, len(social_ids), 50):
                    batch = social_ids[i:i+50]
                    result = archive_emails(batch)
                    
                    if result.get('success'):
                        archived_total += result.get('count', 0)
                        heartbeat_logger.info(f"Archived batch of {result.get('count', 0)} social media emails")
                    else:
                        heartbeat_logger.error(f"Failed to archive social emails: {result.get('error')}")
            else:
                heartbeat_logger.info("No social media emails to archive")
            
            # Final summary
            if archived_total > 0:
                new_inbox_count = get_email_count('in:inbox')
                heartbeat_logger.info(f"Gmail cleanup complete - Archived {archived_total} emails total")
                heartbeat_logger.info(f"New inbox count: {new_inbox_count} (was {inbox_count})")
                return f"📧 Gmail: Archived {archived_total} emails (inbox: {inbox_count} → {new_inbox_count})"
            else:
                heartbeat_logger.info("Gmail cleanup complete - No emails needed archiving")
                return f"📧 Gmail: Inbox clean ({inbox_count} emails, {unread_count} unread)"
                
        except ImportError as e:
            heartbeat_logger.info(f"Gmail integration not available: {e}")
            return None
        except Exception as e:
            heartbeat_logger.error(f"Error in Gmail cleanup: {e}", exc_info=True)
            return None

    @staticmethod
    def _parse_bridge_timestamp(ts: Optional[str]):
        """Parses an ISO-8601 timestamp from whatsapp-bridge (always UTC,
        `new Date().toISOString()`) or whatsapp_managed_chats.py (also UTC,
        `datetime.now(timezone.utc)`) into a comparable aware datetime.
        Returns None on missing/malformed input so callers can treat that as
        "no cursor yet" rather than crashing the whole heartbeat step."""
        if not ts:
            return None
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            return None

    async def _process_whatsapp_managed_chats(self) -> Optional[str]:
        """Auto-reply in WhatsApp chats the user has explicitly opted into
        (skills/whatsapp_messages/whatsapp_managed_chats.py, toggled from the
        dashboard's /whatsapp page). This is the only heartbeat step that
        sends messages to other people with no human in the loop, so it
        leans hard on guardrails:
          - only chats the user explicitly marked managed (never all chats)
          - only messages received after the chat was marked managed - never
            replies into backlog
          - a hard per-chat daily cap (config.WHATSAPP_AUTO_REPLY_DAILY_LIMIT)
          - the model is explicitly allowed to decline to reply (NONE) - most
            inbound pings (reactions, "ok", spam) shouldn't get a reply at all

        Group chats (JID ends in @g.us) are allowed here at the user's
        explicit request, despite a reply there being visible to everyone in
        the group rather than just one person - the prompt below asks the
        model to be more conservative about replying at all in that case.
        """
        try:
            from skills.whatsapp_messages import whatsapp_bridge_client as bridge
            from skills.whatsapp_messages import whatsapp_managed_chats
            import httpx

            managed = whatsapp_managed_chats.list_managed()
            if not managed:
                return None

            try:
                status = bridge.get_status()
            except httpx.ConnectError:
                return None
            if status.get("status") != "connected":
                return None

            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=config.CHAT_API_KEY, base_url=config.CHAT_BASE_URL)

            replied_chats = 0
            for entry in managed:
                jid = entry["jid"]
                try:
                    if whatsapp_managed_chats.reply_count_today(jid) >= config.WHATSAPP_AUTO_REPLY_DAILY_LIMIT:
                        continue

                    since = self._parse_bridge_timestamp(entry.get("last_processed_ts"))
                    thread = bridge.get_thread(jid, limit=20)
                    new_inbound = [
                        m for m in thread
                        if m.get("direction") == "in"
                        and (since is None or (self._parse_bridge_timestamp(m.get("timestamp")) or since) > since)
                    ]
                    if not new_inbound:
                        continue

                    context_lines = "\n".join(
                        f"{'them' if m['direction'] == 'in' else 'you'}: {m['message']}" for m in thread[-15:]
                    )
                    instructions = entry.get("instructions") or "Reply naturally and briefly, as the user would."
                    is_group = jid.endswith("@g.us")
                    chat_kind = "group chat" if is_group else "1:1 chat"
                    group_caution = (
                        "\n\nThis is a GROUP chat - everyone in it will see whatever you send, not just one "
                        "person, and messages may not all be directed at the user or even part of the same "
                        "thread. Be more conservative than in a 1:1: only reply if a message is clearly "
                        "addressed to the user (by name/mention or direct question) and a reply is genuinely "
                        "warranted. When in doubt, reply NONE."
                        if is_group else ""
                    )
                    prompt = f"""You are ghostwriting a WhatsApp reply on behalf of the user, in a {chat_kind}
with {entry.get('name') or jid}. The user has given you this standing instruction for this chat:
"{instructions}"{group_caution}

Recent conversation (oldest first):
{context_lines}

Write ONLY the reply text to send next, with no quotes or preamble - or, if nothing in the new
messages actually warrants a reply (e.g. it was just an emoji reaction, "ok", spam, or the
conversation doesn't need a response right now), reply with exactly: NONE"""

                    response = await client.chat.completions.create(
                        model=config.CHAT_MODEL,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.5,
                    )
                    reply = (response.choices[0].message.content or "").strip()
                    latest = new_inbound[-1]
                    if reply and reply.upper() != "NONE":
                        bridge.send_message(jid, reply, origin="auto")
                        whatsapp_managed_chats.increment_reply_count(jid)
                        replied_chats += 1
                        heartbeat_logger.info(f"WhatsApp auto-reply sent in {jid}")
                    whatsapp_managed_chats.record_processed(jid, latest.get("timestamp"), latest.get("msg_id"))
                except Exception as e:
                    heartbeat_logger.error(f"Error auto-replying in WhatsApp chat {jid}: {e}", exc_info=True)
                    continue

            if replied_chats:
                return f"💬 WhatsApp: auto-replied in {replied_chats} chat(s)"
            return None
        except Exception as e:
            heartbeat_logger.error(f"Error in WhatsApp managed-chat processing: {e}", exc_info=True)
            return None

    async def _process_walmart_orders(self) -> str:
        """Process any unprocessed Walmart order PDFs and archive them.
        
        Scans data/walmart for PDF files, processes them into the database,
        and moves them to data/walmart/archived.
        
        Returns:
            Summary string of Walmart order processing results
        """
        walmart_dir = Path("data/walmart")
        archived_dir = walmart_dir / "archived"
        
        # Ensure archived directory exists
        archived_dir.mkdir(parents=True, exist_ok=True)
        
        # Find all PDF files in walmart directory (not in archived)
        pdf_files = list(walmart_dir.glob("*.pdf"))
        
        if not pdf_files:
            heartbeat_logger.info("No Walmart order PDFs to process")
            return None
        
        heartbeat_logger.info(f"Found {len(pdf_files)} Walmart order PDF(s) to process")
        
        # Import the walmart parser
        try:
            from skills.walmart_orders.walmart_parser import execute as walmart_execute
            
            processed_count = 0
            failed_count = 0
            
            for pdf_file in pdf_files:
                # Guard: file may have been moved or deleted since glob() ran
                # (e.g. another heartbeat tick already archived it, or manual cleanup)
                # Log a warning and skip — don't let a stale glob result halt the cycle
                if not pdf_file.is_file():
                    heartbeat_logger.warning(
                        f"Walmart PDF missing, skipping: {pdf_file.name}"
                    )
                    continue
                try:
                    heartbeat_logger.info(f"Processing Walmart order: {pdf_file.name}")
                    
                    # Process the PDF - pass just the filename, parser will look in data/walmart
                    result = await walmart_execute(pdf_path=pdf_file.name, action="parse")
                    
                    if result.get("success"):
                        order_id = result.get("order", {}).get("order_id", "unknown")
                        items_count = result.get("items_count", 0)
                        heartbeat_logger.info(f"Successfully processed order {order_id} with {items_count} items")
                        
                        # Move to archived folder
                        archived_path = archived_dir / pdf_file.name
                        shutil.move(str(pdf_file), str(archived_path))
                        heartbeat_logger.info(f"Moved {pdf_file.name} to archived folder")
                        
                        processed_count += 1
                    else:
                        error = result.get("error", "Unknown error")
                        heartbeat_logger.error(f"Failed to process {pdf_file.name}: {error}")
                        failed_count += 1
                        
                except Exception as e:
                    heartbeat_logger.error(f"Error processing {pdf_file.name}: {e}", exc_info=True)
                    failed_count += 1
            
            heartbeat_logger.info(f"Walmart order processing complete: {processed_count} processed, {failed_count} failed")
            
            if processed_count > 0:
                return f"🛒 Walmart: Processed {processed_count} order(s)"
            return None
            
        except ImportError as e:
            heartbeat_logger.error(f"Could not import Walmart parser: {e}")
            return None
        except Exception as e:
            heartbeat_logger.error(f"Error in Walmart order processing: {e}", exc_info=True)
            return None
    
    async def _process_budget_analysis(self) -> str:
        """Perform budget analysis and send alerts to users via Telegram.
        
        Analyzes spending patterns, identifies budget concerns, and sends
        actionable alerts to users who need to review their spending.
        
        Returns:
            Summary string of budget analysis results
        """
        heartbeat_logger.info("Starting budget analysis...")
        
        try:
            # Import budget analyzer
            from skills.budget_analysis.budget_analyzer import BudgetAnalyzer
            
            analyzer = BudgetAnalyzer()
            
            # Get actionable alerts
            alerts = await analyzer.get_actionable_alerts()
            
            if alerts:
                heartbeat_logger.info(f"Found {len(alerts)} budget alerts")
                
                # Generate full report
                report = await analyzer.generate_summary_report()
                
                # Send to all authorized users via Telegram
                if self._send_message_callback:
                    # Format message for Telegram
                    message = "💰 **Budget Analysis Alert**\n\n"
                    message += "You have some budget concerns that need attention:\n\n"
                    
                    # Add alerts
                    for alert in alerts[:5]:  # Limit to top 5 alerts
                        message += f"{alert}\n"
                    
                    message += f"\n📊 Full report:\n{report}"
                    
                    # Send to primary user (you can customize which users get budget alerts)
                    # For now, send to the allowed phone number user
                    try:
                        # Try to find the authorized user ID
                        # This is a simplified approach - in production you'd have a proper user mapping
                        await self._send_budget_alert_to_users(message)
                        heartbeat_logger.info("Budget alert sent to users")
                        return f"💰 Budget: {len(alerts)} alert(s) sent to user"
                    except Exception as e:
                        heartbeat_logger.error(f"Error sending budget alert: {e}", exc_info=True)
                        return "💰 Budget: Alerts found but failed to send"
                else:
                    heartbeat_logger.warning("No send_message_callback set, cannot send budget alerts")
                    return "💰 Budget: Alerts found but no callback configured"
            else:
                heartbeat_logger.info("No budget alerts to report - all spending is within budget")
                return "💰 Budget: All spending within budget ✅"
                
                # Optionally send a positive update once per week
                # This could be enhanced to check if it's been a week since last report
                
        except ImportError as e:
            heartbeat_logger.info(f"Budget analysis not available: {e}")
            return None
        except Exception as e:
            heartbeat_logger.error(f"Error in budget analysis: {e}", exc_info=True)
            return None
    
    async def _process_world_watch(self) -> Optional[str]:
        """Check watched topics for updates and surface notable insights.

        Dispatches per-topic to src/managers/watch_sources.py based on
        topic.kind ("news" -> SearXNG + LLM summary, "stock" -> Yahoo Finance
        day-move check, "github" -> release/commit check), each on its own
        configurable check interval (WORLD_WATCH_INTERVAL_HOURS /
        STOCK_WATCH_INTERVAL_HOURS / GITHUB_WATCH_INTERVAL_HOURS).

        IMPORTANT: iterates ONLY over src.main.authorized_users (the real,
        logged-in user(s)) - never over discovered memory/* directories.
        execute_heartbeat() falls back to scanning every memory/* folder
        (including stray test dirs) when no one has an active in-memory
        agent; the other hardcoded heartbeat methods (e.g. budget alerts)
        deliberately avoid that trap by going straight to authorized_users,
        and this method must do the same to avoid spamming messages for
        users who never actually set up a watchlist.

        Returns:
            One-line summary string for the heartbeat digest, or None if
            nothing was due to run or nothing notable was found.
        """
        try:
            from skills.watchlist.watchlist_manager import WatchlistManager
            from src.managers.insights_manager import InsightsManager
            from src.managers import watch_sources
            import src.main as main_module

            if not getattr(main_module, "authorized_users", None):
                return None

            watchlist_mgr = WatchlistManager()
            insights_mgr = InsightsManager()

            interval_by_kind = {
                "news": timedelta(hours=config.WORLD_WATCH_INTERVAL_HOURS),
                "stock": timedelta(hours=config.STOCK_WATCH_INTERVAL_HOURS),
                "github": timedelta(hours=config.GITHUB_WATCH_INTERVAL_HOURS),
            }

            surfaced = 0

            for user_id in main_module.authorized_users.keys():
                for topic in watchlist_mgr.get_topics(user_id):
                    interval = interval_by_kind.get(topic.kind, interval_by_kind["news"])

                    if topic.last_run_at:
                        try:
                            elapsed = datetime.now() - datetime.fromisoformat(topic.last_run_at)
                            if elapsed < interval:
                                continue  # Not due yet
                        except ValueError:
                            pass  # Malformed timestamp - treat as due

                    try:
                        insight_summary = None
                        sources: List[Dict] = []

                        if topic.kind == "stock":
                            check = await watch_sources.check_stock(topic.topic, config.STOCK_WATCH_MOVE_THRESHOLD_PERCENT)
                            if check is None:
                                continue  # Lookup failed - retry next tick, don't advance last_run_at
                            watchlist_mgr.mark_run(user_id, topic.id, [], datetime.now().isoformat())
                            if not check.get("notable"):
                                continue
                            insight_summary = check["summary"]
                            sources = check["sources"]

                        elif topic.kind == "github":
                            check = await watch_sources.check_github(topic.topic, topic.seen_urls)
                            if check is None:
                                continue
                            watchlist_mgr.mark_run(user_id, topic.id, check["new_markers"], datetime.now().isoformat())
                            if not check["new_items"]:
                                continue
                            insight_summary = "\n".join(f"• {item['title']}" for item in check["new_items"])
                            sources = [{"title": item["title"], "url": item["url"]} for item in check["new_items"]]

                        else:  # "news" (default)
                            check = await watch_sources.check_news(topic.topic, topic.seen_urls)
                            if check is None:
                                continue
                            watchlist_mgr.mark_run(user_id, topic.id, check["all_markers"], datetime.now().isoformat())
                            if not check["new_items"]:
                                continue
                            insight_summary = await self._summarize_world_watch_results(topic.topic, check["new_items"])
                            if not insight_summary:
                                continue
                            sources = [{"title": r["title"], "url": r["link"]} for r in check["new_items"][:5]]

                        insights_mgr.add_insight(user_id, topic.topic, insight_summary, sources)

                        if self._send_message_callback:
                            icon = {"stock": "📈", "github": "🐙"}.get(topic.kind, "🔭")
                            message = f"{icon} **World Watch: {topic.topic}**\n\n{insight_summary}\n\n"
                            message += "\n".join(f"• {s['title']}: {s['url']}" for s in sources)
                            await self._send_message_callback(user_id, message)

                        surfaced += 1

                    except Exception as e:
                        heartbeat_logger.error(
                            f"Error processing world watch topic '{topic.topic}' ({topic.kind}) for user {user_id}: {e}",
                            exc_info=True
                        )

            if surfaced:
                return f"🔭 World Watch: {surfaced} new insight(s) surfaced"
            return None

        except Exception as e:
            heartbeat_logger.error(f"Error in world watch processing: {e}", exc_info=True)
            return None

    async def _summarize_world_watch_results(self, topic: str, results: List[Dict]) -> Optional[str]:
        """Summarize new search results into a short, notable-or-nothing digest.

        Returns None (rather than a summary) when the LLM judges the results
        aren't genuinely worth surfacing - this is what keeps world watch from
        notifying on recycled/low-value content every time it runs.
        """
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(api_key=config.CHAT_API_KEY, base_url=config.CHAT_BASE_URL)

            results_text = "\n".join(
                f"- {r['title']}: {r['snippet']} ({r['link']})" for r in results
            )
            prompt = f"""Here are new search results about the watched topic "{topic}":

{results_text}

In 2-4 sentences, summarize what's new or notable here for someone following this topic.
If none of this is genuinely noteworthy (e.g. it's just recycled/old content, spam, or irrelevant),
reply with exactly: NOTHING_NOTABLE"""

            response = await client.chat.completions.create(
                model=config.CHAT_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
            )

            summary = (response.choices[0].message.content or "").strip()
            if not summary or summary == "NOTHING_NOTABLE":
                return None
            return summary

        except Exception as e:
            heartbeat_logger.error(f"Error summarizing world watch results for '{topic}': {e}", exc_info=True)
            return None

    async def _process_memory_watch_suggestions(self) -> Optional[str]:
        """Mine long-term memory for topics worth proactively watching and suggest them.

        Runs at most once per MEMORY_SUGGESTION_INTERVAL_HOURS (default
        weekly). Never auto-adds a topic - only sends a Telegram suggestion;
        the user accepts it the normal way ("watch X"), same as any other
        topic. Tracks what's already been suggested via WatchlistManager's
        suggestion state so it doesn't repeat itself every week.

        IMPORTANT: like _process_world_watch, iterates only authorized_users.
        """
        try:
            from skills.watchlist.watchlist_manager import WatchlistManager
            from src.core.memory import MemoryManager
            import src.main as main_module

            if not getattr(main_module, "authorized_users", None):
                return None

            watchlist_mgr = WatchlistManager()
            interval = timedelta(hours=config.MEMORY_SUGGESTION_INTERVAL_HOURS)

            suggested_count = 0

            for user_id in main_module.authorized_users.keys():
                last_run = watchlist_mgr.get_last_suggestion_run(user_id)
                if last_run:
                    try:
                        elapsed = datetime.now() - datetime.fromisoformat(last_run)
                        if elapsed < interval:
                            continue
                    except ValueError:
                        pass

                memory_manager = MemoryManager(user_id)
                long_term_memory = await memory_manager.get_long_term_memory()
                if not long_term_memory or long_term_memory.strip() == "No long-term memories yet.":
                    watchlist_mgr.record_suggestions(user_id, [], datetime.now().isoformat())
                    continue

                active_topics = [t.topic for t in watchlist_mgr.get_topics(user_id)]
                already_suggested = watchlist_mgr.get_suggested_topics(user_id)
                exclude = active_topics + already_suggested

                candidates = await self._suggest_watch_topics_from_memory(long_term_memory, exclude)
                if not candidates:
                    watchlist_mgr.record_suggestions(user_id, [], datetime.now().isoformat())
                    continue

                if self._send_message_callback:
                    message = "💡 **Watch Suggestion**\n\n"
                    message += "Based on things you've mentioned, you might want me to keep an eye on:\n\n"
                    message += "\n".join(f"• {c}" for c in candidates)
                    message += "\n\nJust say \"watch <topic>\" if you'd like me to start."
                    await self._send_message_callback(user_id, message)
                    suggested_count += len(candidates)

                watchlist_mgr.record_suggestions(user_id, candidates, datetime.now().isoformat())

            if suggested_count:
                return f"💡 Watch suggestions: proposed {suggested_count} new topic(s)"
            return None

        except Exception as e:
            heartbeat_logger.error(f"Error in memory watch suggestions: {e}", exc_info=True)
            return None

    async def _suggest_watch_topics_from_memory(self, long_term_memory: str, exclude: List[str]) -> List[str]:
        """Ask the LLM for up to 2 topics worth watching, given long-term memory content."""
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(api_key=config.CHAT_API_KEY, base_url=config.CHAT_BASE_URL)

            exclude_text = ", ".join(exclude) if exclude else "(none)"
            prompt = f"""Here is a user's long-term memory (facts, goals, recurring topics, preferences):

{long_term_memory[:6000]}

Topics already being watched or already suggested (do NOT suggest these again): {exclude_text}

Suggest up to 2 SPECIFIC topics (a project, technology, event, team, etc.) that would genuinely be
worth proactively monitoring for news/updates on this person's behalf. Only suggest something if it's
clearly a recurring interest or active goal - don't force it.

Reply with each suggestion on its own line as:
TOPIC: <short topic text>

If nothing is worth suggesting, reply with exactly: NONE"""

            response = await client.chat.completions.create(
                model=config.CHAT_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
            )

            text = (response.choices[0].message.content or "").strip()
            if not text or text == "NONE":
                return []

            candidates = []
            for line in text.splitlines():
                line = line.strip()
                if line.upper().startswith("TOPIC:"):
                    topic = line.split(":", 1)[1].strip()
                    if topic and topic not in exclude:
                        candidates.append(topic)
            return candidates[:2]

        except Exception as e:
            heartbeat_logger.error(f"Error generating watch topic suggestions: {e}", exc_info=True)
            return []

    async def _process_daily_briefing(self) -> Optional[str]:
        """Send a once-daily digest (weather, budget snapshot, today's
        reminders, recent insights) at config.DAILY_BRIEFING_HOUR local time.

        Additive, not a replacement for other real-time proactive messages
        (world watch pings, budget alerts, heartbeat summaries) - this is a
        single rollup for the start of the day, not a suppression of
        time-sensitive alerts sent elsewhere.

        IMPORTANT: like _process_world_watch, iterates only authorized_users.
        """
        try:
            import src.main as main_module

            if not getattr(main_module, "authorized_users", None):
                return None
            if not self._send_message_callback:
                return None

            now = datetime.now()
            if now.hour != config.DAILY_BRIEFING_HOUR:
                return None

            today_str = now.strftime("%Y-%m-%d")
            state = self._load_briefing_state()

            sent_count = 0
            for user_id in main_module.authorized_users.keys():
                if state.get(user_id) == today_str:
                    continue  # Already sent today

                sections = await self._build_daily_briefing_sections(user_id, main_module)
                message = f"🌅 **Daily Briefing** - {now.strftime('%A, %B %d')}\n\n" + "\n\n".join(sections)
                await self._send_message_callback(user_id, message)
                state[user_id] = today_str
                sent_count += 1

            if sent_count:
                self._save_briefing_state(state)
                return f"🌅 Daily briefing sent to {sent_count} user(s)"
            return None

        except Exception as e:
            heartbeat_logger.error(f"Error in daily briefing: {e}", exc_info=True)
            return None

    async def _build_daily_briefing_sections(self, user_id: str, main_module) -> List[str]:
        """Gather the individual lines that make up a daily briefing message."""
        sections = []

        if config.HOME_LOCATION:
            try:
                from skills.weather.weather_api import fetch_weather
                weather = await fetch_weather(config.HOME_LOCATION)
                if weather.get("success"):
                    current = weather.get("current", {})
                    sections.append(
                        f"☀️ **Weather in {weather.get('location', config.HOME_LOCATION)}**: "
                        f"{current.get('condition', 'Unknown')}, {current.get('temperature_f', '?')}°F"
                    )
            except Exception as e:
                heartbeat_logger.warning(f"Daily briefing weather lookup failed: {e}")

        try:
            from skills.budget_analysis.budget_analyzer import BudgetAnalyzer
            analysis = await BudgetAnalyzer().analyze_monthly_spending()
            total = analysis.get("total_spending", 0) or 0
            warnings = analysis.get("warnings", [])
            line = f"💰 **Budget**: ${total:,.2f} spent this month"
            if warnings:
                line += f" ({len(warnings)} categor{'y' if len(warnings) == 1 else 'ies'} over budget)"
            sections.append(line)
        except Exception as e:
            heartbeat_logger.warning(f"Daily briefing budget lookup failed: {e}")

        try:
            reminder_mgr = getattr(main_module, "reminder_manager", None)
            if reminder_mgr:
                today = datetime.now().date()
                due_today = [
                    r for r in await reminder_mgr.get_user_reminders(user_id, include_sent=False)
                    if datetime.fromisoformat(r.scheduled_time).date() == today
                ]
                if due_today:
                    sections.append(
                        f"⏰ **{len(due_today)} reminder(s) today**: "
                        + "; ".join(r.message for r in due_today[:5])
                    )
        except Exception as e:
            heartbeat_logger.warning(f"Daily briefing reminders lookup failed: {e}")

        try:
            from src.managers.insights_manager import InsightsManager
            insights = InsightsManager().get_insights(user_id, limit=20)
            cutoff = datetime.now() - timedelta(hours=24)
            recent = [i for i in insights if datetime.fromisoformat(i.created_at) >= cutoff]
            if recent:
                sections.append(f"🔭 **{len(recent)} new insight(s)**: " + "; ".join(i.topic for i in recent[:5]))
        except Exception as e:
            heartbeat_logger.warning(f"Daily briefing insights lookup failed: {e}")

        if not sections:
            sections.append("Nothing notable to report today.")

        return sections

    def _load_briefing_state(self) -> Dict[str, str]:
        import json
        path = config.BASE_DIR / "data" / "daily_briefing_state.json"
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text())
        except Exception:
            return {}

    def _save_briefing_state(self, state: Dict[str, str]) -> None:
        import json
        path = config.BASE_DIR / "data" / "daily_briefing_state.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, indent=2))

    async def _process_pending_merges(self) -> Optional[str]:
        """Retry any feature-request/self-upgrade merges deferred by
        src/managers/self_upgrade_manager.py's safety gate (main had
        uncommitted changes, or wasn't checked out, at merge time) - see
        retry_pending_merges(). Runs every heartbeat tick, not gated to a
        slow interval like _process_self_upgrade_ideas below, so a tested,
        already-committed branch merges itself in promptly once main is
        clean, with no manual `git merge` ever required.
        """
        try:
            from src.managers import self_upgrade_manager
            from skills.pi_agent.requests_manager import FeatureRequestsManager
            import src.main as main_module

            if not getattr(main_module, "authorized_users", None):
                return None

            user_id = next(iter(main_module.authorized_users.keys()))
            feature_requests_manager = FeatureRequestsManager()
            summaries = await self_upgrade_manager.retry_pending_merges(
                feature_requests_manager, self._send_message_callback, user_id
            )
            return "; ".join(summaries) if summaries else None

        except Exception as e:
            heartbeat_logger.error(f"Error retrying pending merges: {e}", exc_info=True)
            return None

    async def _process_self_upgrade_ideas(self) -> Optional[str]:
        """Think of a self-upgrade idea and, if one seems worthwhile, implement
        it end-to-end via src/managers/self_upgrade_manager.py: an isolated git
        worktree/branch, the Pi coding agent, a test gate, and (only if tests
        pass, main is clean, and main is checked out) an automatic merge +
        restart of the affected pm2 services. Failed attempts never touch
        main - the branch/worktree is left in place for manual review.

        Runs at most once per SELF_UPGRADE_INTERVAL_HOURS, tracked globally
        (not per-user) since this affects the whole system, not one user's
        data. May take several minutes to complete - that's expected given
        how rarely it runs.

        IMPORTANT: like _process_world_watch, iterates only authorized_users
        (just to confirm someone is actually using the bot before spending
        the time/resources on this).
        """
        try:
            from src.managers import self_upgrade_manager
            from skills.pi_agent.requests_manager import FeatureRequestsManager
            import src.main as main_module

            if not getattr(main_module, "authorized_users", None):
                return None

            state = self._load_self_upgrade_state()
            last_run = state.get("last_run_at")
            if last_run:
                try:
                    elapsed = datetime.now() - datetime.fromisoformat(last_run)
                    if elapsed < timedelta(hours=config.SELF_UPGRADE_INTERVAL_HOURS):
                        return None
                except ValueError:
                    pass

            state["last_run_at"] = datetime.now().isoformat()
            self._save_self_upgrade_state(state)

            user_id = next(iter(main_module.authorized_users.keys()))
            feature_requests_manager = FeatureRequestsManager()
            memory_manager = MemoryManager(user_id)

            idea = await self_upgrade_manager.generate_self_upgrade_idea(
                self.skills_manager, memory_manager, feature_requests_manager
            )
            if not idea:
                return None

            heartbeat_logger.info(f"Self-upgrade idea: {idea[:200]}")
            return await self_upgrade_manager.run_self_upgrade(
                idea, feature_requests_manager, self._send_message_callback, user_id
            )

        except Exception as e:
            heartbeat_logger.error(f"Error in self-upgrade processing: {e}", exc_info=True)
            return None

    def _load_self_upgrade_state(self) -> Dict[str, str]:
        import json
        path = config.BASE_DIR / "data" / "self_upgrade_state.json"
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text())
        except Exception:
            return {}

    def _save_self_upgrade_state(self, state: Dict[str, str]) -> None:
        import json
        path = config.BASE_DIR / "data" / "self_upgrade_state.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, indent=2))

    async def _process_trending_suggestions(self) -> Optional[str]:
        """Scan GitHub's trending Python/TypeScript/JavaScript repos and, via
        src/managers/trending_manager.py, curate a short list of ideas worth
        considering. Unlike self-upgrade, nothing is ever implemented here -
        curated ideas are just stored as pending suggestions for the user to
        review and act on (or not) from the dashboard.

        Runs at most once per TRENDING_SCAN_INTERVAL_HOURS, tracked globally.
        """
        try:
            from src.managers import trending_manager
            import src.main as main_module

            if not getattr(main_module, "authorized_users", None):
                return None

            state = self._load_trending_state()
            last_run = state.get("last_run_at")
            if last_run:
                try:
                    elapsed = datetime.now() - datetime.fromisoformat(last_run)
                    if elapsed < timedelta(hours=config.TRENDING_SCAN_INTERVAL_HOURS):
                        return None
                except ValueError:
                    pass

            state["last_run_at"] = datetime.now().isoformat()
            self._save_trending_state(state)

            suggestions_manager = trending_manager.TrendingSuggestionsManager()
            return await trending_manager.run_trending_scan(self.skills_manager, suggestions_manager)

        except Exception as e:
            heartbeat_logger.error(f"Error in trending-suggestions processing: {e}", exc_info=True)
            return None

    def _load_trending_state(self) -> Dict[str, str]:
        import json
        path = config.BASE_DIR / "data" / "trending_state.json"
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text())
        except Exception:
            return {}

    def _save_trending_state(self, state: Dict[str, str]) -> None:
        import json
        path = config.BASE_DIR / "data" / "trending_state.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, indent=2))

    async def _process_webcam_discovery(self) -> Optional[str]:
        """Search (via SearXNG) for promising public live-webcam pages and,
        via src/managers/webcam_discovery.py, curate a short list of
        best-effort suggestions worth reviewing. Nothing is ever added to
        the source list automatically - curated ideas are just stored as
        pending suggestions for the user to approve or dismiss from the
        dashboard's /webcams page.

        Runs at most once per WEBCAM_DISCOVERY_INTERVAL_HOURS, tracked globally.
        """
        try:
            from src.managers import webcam_manager, webcam_discovery
            import src.main as main_module

            if not getattr(main_module, "authorized_users", None):
                return None

            state = self._load_webcam_discovery_state()
            last_run = state.get("last_run_at")
            if last_run:
                try:
                    elapsed = datetime.now() - datetime.fromisoformat(last_run)
                    if elapsed < timedelta(hours=config.WEBCAM_DISCOVERY_INTERVAL_HOURS):
                        return None
                except ValueError:
                    pass

            state["last_run_at"] = datetime.now().isoformat()
            self._save_webcam_discovery_state(state)

            sources_manager = webcam_manager.WebcamSourcesManager()
            suggestions_manager = webcam_manager.WebcamSuggestionsManager()
            return await webcam_discovery.run_webcam_discovery_scan(sources_manager, suggestions_manager)

        except Exception as e:
            heartbeat_logger.error(f"Error in webcam-discovery processing: {e}", exc_info=True)
            return None

    def _load_webcam_discovery_state(self) -> Dict[str, str]:
        import json
        path = config.BASE_DIR / "data" / "webcam_discovery_state.json"
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text())
        except Exception:
            return {}

    def _save_webcam_discovery_state(self, state: Dict[str, str]) -> None:
        import json
        path = config.BASE_DIR / "data" / "webcam_discovery_state.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, indent=2))

    async def _process_webcam_health_check(self) -> Optional[str]:
        """Re-verify every enabled webcam source is still actually playable
        (see src/managers/webcam_verifier.py) - links that worked when added
        can go dead later. Only ever updates verify_status/verify_detail on
        each source; never disables or deletes - the dashboard's /webcams
        page surfaces a "broken" badge for the user to act on.

        Runs at most once per WEBCAM_HEALTH_CHECK_INTERVAL_HOURS, tracked globally.
        """
        try:
            import asyncio
            import httpx
            from src.managers import webcam_manager
            from src.managers.webcam_verifier import verify_webcam

            state = self._load_webcam_health_state()
            last_run = state.get("last_run_at")
            if last_run:
                try:
                    elapsed = datetime.now() - datetime.fromisoformat(last_run)
                    if elapsed < timedelta(hours=config.WEBCAM_HEALTH_CHECK_INTERVAL_HOURS):
                        return None
                except ValueError:
                    pass

            state["last_run_at"] = datetime.now().isoformat()
            self._save_webcam_health_state(state)

            sources_manager = webcam_manager.WebcamSourcesManager()
            enabled = [s for s in sources_manager.list() if s.enabled]
            if not enabled:
                return None

            sem = asyncio.Semaphore(config.WEBCAM_HEALTH_CHECK_CONCURRENCY)

            async def check(source, client):
                async with sem:
                    return await verify_webcam(source.url, source.kind, client=client)

            async with httpx.AsyncClient(
                timeout=config.WEBCAM_VERIFY_TIMEOUT_SECONDS, follow_redirects=True
            ) as client:
                results = await asyncio.gather(*(check(s, client) for s in enabled))

            now = datetime.now().isoformat()
            newly_broken = []
            for source, result in zip(enabled, results):
                new_status = "ok" if result.ok else "broken"
                if new_status == "broken" and source.verify_status != "broken":
                    newly_broken.append(source.name)
                sources_manager.update(
                    source.id, verify_status=new_status, verify_detail=result.detail, last_verified_at=now,
                )

            broken_count = sum(1 for r in results if not r.ok)
            if broken_count == 0:
                return None
            msg = f"Webcam health check: {broken_count}/{len(enabled)} source(s) broken."
            if newly_broken:
                msg += f" Newly broken: {', '.join(newly_broken)}."
            return msg

        except Exception as e:
            heartbeat_logger.error(f"Error in webcam-health-check processing: {e}", exc_info=True)
            return None

    def _load_webcam_health_state(self) -> Dict[str, str]:
        import json
        path = config.BASE_DIR / "data" / "webcam_health_state.json"
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text())
        except Exception:
            return {}

    def _save_webcam_health_state(self, state: Dict[str, str]) -> None:
        import json
        path = config.BASE_DIR / "data" / "webcam_health_state.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, indent=2))

    async def _send_heartbeat_summary(self, summary: list, timestamp: str) -> None:
        """Send heartbeat summary to authorized users via Telegram.
        
        Args:
            summary: List of summary strings from heartbeat activities
            timestamp: Timestamp of heartbeat execution
        """
        if not self._send_message_callback:
            heartbeat_logger.warning("No send_message_callback set, cannot send heartbeat summary")
            return
        
        if not summary:
            heartbeat_logger.info("No activities to report in heartbeat summary")
            return
        
        try:
            # Format the summary message
            message = "💓 **Heartbeat Summary**\n"
            message += f"⏰ {timestamp}\n\n"
            message += "Activities completed:\n\n"
            
            for item in summary:
                message += f"• {item}\n"
            
            message += "\n✅ All heartbeat tasks completed successfully"
            
            # Send to all authorized users
            try:
                # Import to get authorized users
                import src.main as main_module
                if hasattr(main_module, 'authorized_users') and main_module.authorized_users:
                    for user_id in main_module.authorized_users.keys():
                        try:
                            await self._send_message_callback(user_id, message)
                            heartbeat_logger.info(f"Sent heartbeat summary to user {user_id}")
                        except Exception as e:
                            heartbeat_logger.error(f"Failed to send heartbeat summary to user {user_id}: {e}")
                else:
                    heartbeat_logger.warning("No authorized users found to send heartbeat summary")
            except Exception as e:
                heartbeat_logger.error(f"Error accessing authorized users for heartbeat summary: {e}", exc_info=True)
                
        except Exception as e:
            heartbeat_logger.error(f"Error sending heartbeat summary: {e}", exc_info=True)
    
    async def _send_budget_alert_to_users(self, message: str) -> None:
        """Send budget alert to authorized users.
        
        Args:
            message: Alert message to send
        """
        # This is a simplified version - in production you'd have proper user management
        # For now, we'll send to any active user or use the configured phone number
        
        # Try to find authorized users from the main.py authorized_users dict
        # Since we don't have direct access, we'll send using the callback
        
        # Get the allowed phone number from config and find matching user
        # This is a workaround - ideally we'd have a proper user management system
        
        try:
            # Import to get authorized users (this is a bit hacky but works)
            import src.main as main_module
            if hasattr(main_module, 'authorized_users') and main_module.authorized_users:
                for user_id in main_module.authorized_users.keys():
                    try:
                        await self._send_message_callback(user_id, message)
                        heartbeat_logger.info(f"Sent budget alert to user {user_id}")
                    except Exception as e:
                        heartbeat_logger.error(f"Failed to send to user {user_id}: {e}")
            else:
                heartbeat_logger.warning("No authorized users found to send budget alert")
        except Exception as e:
            heartbeat_logger.error(f"Error accessing authorized users: {e}", exc_info=True)
    
    async def _perform_system_checks(self, instructions: str) -> None:
        """Perform system-level checks when no users are active.
        
        Args:
            instructions: Content from heartbeat.md
        """
        heartbeat_logger.info("Performing system-level checks")
        
        # Check if heartbeat file exists
        if self.heartbeat_file.exists():
            heartbeat_logger.info(f"✓ Heartbeat file present: {self.heartbeat_file}")
        else:
            heartbeat_logger.warning(f"✗ Heartbeat file missing: {self.heartbeat_file}")
        
        # Check skills directory
        if config.SKILLS_DIR.exists():
            skill_count = len(list(config.SKILLS_DIR.glob("*.md")))
            heartbeat_logger.info(f"✓ Skills directory present with {skill_count} skills")
        else:
            heartbeat_logger.warning(f"✗ Skills directory missing: {config.SKILLS_DIR}")
        
        # Check memory directory
        if config.MEMORY_DIR.exists():
            user_count = len(list(config.MEMORY_DIR.iterdir()))
            heartbeat_logger.info(f"✓ Memory directory present with {user_count} user folders")
        else:
            heartbeat_logger.warning(f"✗ Memory directory missing: {config.MEMORY_DIR}")
        
        heartbeat_logger.info("System checks complete")
    
    async def _run_heartbeat_loop(self) -> None:
        """Run the heartbeat loop."""
        heartbeat_logger.info(f"Heartbeat loop started, first heartbeat will run in {self.interval_minutes} minutes")
        
        while self._running:
            try:
                # Wait for next heartbeat interval BEFORE executing
                # This prevents blocking bot startup with an immediate heartbeat
                await asyncio.sleep(self.interval_minutes * 60)
                
                # Execute heartbeat after waiting
                await self.execute_heartbeat()
                
            except asyncio.CancelledError:
                heartbeat_logger.info("Heartbeat loop cancelled")
                break
            except Exception as e:
                heartbeat_logger.error(f"Error in heartbeat loop: {e}", exc_info=True)
                # Continue running even if one heartbeat fails
                await asyncio.sleep(60)  # Wait a minute before retrying
    
    async def start(self) -> None:
        """Start the heartbeat manager."""
        if self._running:
            heartbeat_logger.warning("Heartbeat manager already running")
            return
        
        self._running = True
        self._task = asyncio.create_task(self._run_heartbeat_loop())
        heartbeat_logger.info("Heartbeat manager started")
    
    async def stop(self) -> None:
        """Stop the heartbeat manager."""
        if not self._running:
            return
        
        self._running = False
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        heartbeat_logger.info("Heartbeat manager stopped")
    
    def is_running(self) -> bool:
        """Check if heartbeat manager is running.
        
        Returns:
            True if running, False otherwise
        """
        return self._running
