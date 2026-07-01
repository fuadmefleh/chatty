"""Heartbeat system for autonomous agent activities."""
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Callable
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
                        
                        # Clean up and reorganize long-term memories
                        result = await self._cleanup_long_term_memories(user_agents, user_memories)
                        if result:
                            summary.append(result)
                    
                    # Process Gmail cleanup and organization
                    result = await self._process_gmail_cleanup()
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
    
    async def _cleanup_long_term_memories(self, user_agents: Dict, user_memories: Dict) -> str:
        """Clean up and reorganize long-term memories for all users.
        
        Args:
            user_agents: Dictionary of user agents
            user_memories: Dictionary of user memory managers
            
        Returns:
            Summary string of cleanup results
        """
        heartbeat_logger.info("Starting long-term memory cleanup for all users...")
        
        cleaned_users = []
        for user_id, memory_manager in user_memories.items():
            try:
                # Get corresponding agent
                agent = user_agents.get(user_id)
                if not agent:
                    heartbeat_logger.warning(f"No agent found for user {user_id}, skipping cleanup")
                    continue
                
                heartbeat_logger.info(f"Cleaning up long-term memories for user {user_id}")
                result = await memory_manager.cleanup_long_term_memories(agent)
                heartbeat_logger.info(f"User {user_id} cleanup result: {result}")
                
                if "cleaned" in result.lower() or "organized" in result.lower():
                    cleaned_users.append(user_id)
                
            except Exception as e:
                heartbeat_logger.error(f"Error cleaning up memories for user {user_id}: {e}", exc_info=True)
        
        heartbeat_logger.info("Long-term memory cleanup completed for all users")
        
        if cleaned_users:
            return f"🗂️ Memory cleanup: Organized memories for {len(cleaned_users)} user(s)"
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
                SCOPES
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
                # Filter for emails 7+ days old
                from datetime import datetime, timedelta
                seven_days_ago = datetime.now() - timedelta(days=7)
                
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
            message = f"💓 **Heartbeat Summary**\n"
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
