"""Reminder and alarm management system."""
import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Callable
import re
from dataclasses import dataclass, asdict
import aiofiles
from src.core.logging_config import get_reminders_logger

# Get reminders logger
reminders_logger = get_reminders_logger()


@dataclass
class Reminder:
    """Represents a single reminder."""
    id: str
    user_id: str
    message: str
    scheduled_time: str  # ISO format timestamp
    created_at: str
    is_sent: bool = False
    
    def to_dict(self):
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict):
        """Create from dictionary."""
        return cls(**data)


class ReminderManager:
    """Manages reminders and alarms for users."""
    
    def __init__(self, storage_dir: Path):
        """Initialize reminder manager.
        
        Args:
            storage_dir: Directory to store reminder data
        """
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.reminders: Dict[str, List[Reminder]] = {}
        self.callback: Optional[Callable] = None
        self._running = False
        self._check_task = None
    
    def set_callback(self, callback: Callable):
        """Set callback function to trigger when reminders are due.
        
        Args:
            callback: Async function that takes (user_id, message) as arguments
        """
        self.callback = callback
    
    async def load_reminders(self):
        """Load all reminders from disk."""
        self.reminders.clear()
        
        for reminder_file in self.storage_dir.glob("*.json"):
            try:
                async with aiofiles.open(reminder_file, 'r') as f:
                    content = await f.read()
                    data = json.loads(content)
                    
                user_id = reminder_file.stem
                self.reminders[user_id] = [
                    Reminder.from_dict(r) for r in data
                ]
                
                reminders_logger.info(f"Loaded {len(self.reminders[user_id])} reminders for user {user_id}")
            except Exception as e:
                reminders_logger.error(f"Error loading reminders from {reminder_file}: {e}")
    
    async def save_reminders(self, user_id: str):
        """Save reminders for a specific user.
        
        Args:
            user_id: User ID to save reminders for
        """
        if user_id not in self.reminders:
            return
        
        reminder_file = self.storage_dir / f"{user_id}.json"
        
        try:
            # Filter out sent reminders older than 7 days
            cutoff = datetime.now() - timedelta(days=7)
            active_reminders = [
                r for r in self.reminders[user_id]
                if not r.is_sent or datetime.fromisoformat(r.scheduled_time) > cutoff
            ]
            
            self.reminders[user_id] = active_reminders
            
            data = [r.to_dict() for r in active_reminders]
            
            async with aiofiles.open(reminder_file, 'w') as f:
                await f.write(json.dumps(data, indent=2))
                
            reminders_logger.info(f"Saved {len(active_reminders)} reminders for user {user_id}")
        except Exception as e:
            reminders_logger.error(f"Error saving reminders for user {user_id}: {e}")
    
    async def add_reminder(self, user_id: str, message: str, scheduled_time: datetime) -> str:
        """Add a new reminder.
        
        Args:
            user_id: User ID
            message: Reminder message
            scheduled_time: When to send the reminder
            
        Returns:
            Reminder ID
        """
        if user_id not in self.reminders:
            self.reminders[user_id] = []
        
        reminder_id = f"{user_id}_{int(datetime.now().timestamp())}"
        
        reminder = Reminder(
            id=reminder_id,
            user_id=user_id,
            message=message,
            scheduled_time=scheduled_time.isoformat(),
            created_at=datetime.now().isoformat(),
            is_sent=False
        )
        
        self.reminders[user_id].append(reminder)
        await self.save_reminders(user_id)
        
        reminders_logger.info(f"Added reminder for user {user_id}: {message} at {scheduled_time}")
        
        return reminder_id
    
    async def get_user_reminders(self, user_id: str, include_sent: bool = False) -> List[Reminder]:
        """Get all reminders for a user.
        
        Args:
            user_id: User ID
            include_sent: Whether to include already sent reminders
            
        Returns:
            List of reminders
        """
        if user_id not in self.reminders:
            return []
        
        reminders = self.reminders[user_id]
        
        if not include_sent:
            reminders = [r for r in reminders if not r.is_sent]
        
        return sorted(reminders, key=lambda r: r.scheduled_time)
    
    async def cancel_reminder(self, user_id: str, reminder_id: str) -> bool:
        """Cancel a reminder.
        
        Args:
            user_id: User ID
            reminder_id: Reminder ID to cancel
            
        Returns:
            True if cancelled, False if not found
        """
        if user_id not in self.reminders:
            return False
        
        original_count = len(self.reminders[user_id])
        self.reminders[user_id] = [
            r for r in self.reminders[user_id]
            if r.id != reminder_id
        ]
        
        if len(self.reminders[user_id]) < original_count:
            await self.save_reminders(user_id)
            reminders_logger.info(f"Cancelled reminder {reminder_id} for user {user_id}")
            return True
        
        return False
    
    def parse_time_expression(self, expression: str, reference_time: datetime = None) -> Optional[datetime]:
        """Parse natural language time expression.
        
        Args:
            expression: Time expression like "in 5 minutes", "3pm tomorrow", etc.
            reference_time: Reference time (default: now)
            
        Returns:
            Parsed datetime or None if parsing failed
        """
        if reference_time is None:
            reference_time = datetime.now()
        
        expression = expression.lower().strip()
        
        # Handle "in X minutes/hours/days"
        relative_pattern = r'in\s+(\d+)\s+(second|seconds|minute|minutes|hour|hours|day|days)'
        match = re.search(relative_pattern, expression)
        if match:
            amount = int(match.group(1))
            unit = match.group(2)
            
            if 'second' in unit:
                return reference_time + timedelta(seconds=amount)
            elif 'minute' in unit:
                return reference_time + timedelta(minutes=amount)
            elif 'hour' in unit:
                return reference_time + timedelta(hours=amount)
            elif 'day' in unit:
                return reference_time + timedelta(days=amount)
        
        # Handle "tomorrow"
        if 'tomorrow' in expression:
            base_time = reference_time + timedelta(days=1)
            # Try to extract time
            time_match = re.search(r'(\d{1,2}):?(\d{2})?\s*(am|pm)?', expression)
            if time_match:
                hour = int(time_match.group(1))
                minute = int(time_match.group(2)) if time_match.group(2) else 0
                am_pm = time_match.group(3)
                
                if am_pm == 'pm' and hour < 12:
                    hour += 12
                elif am_pm == 'am' and hour == 12:
                    hour = 0
                
                return base_time.replace(hour=hour, minute=minute, second=0, microsecond=0)
            else:
                return base_time.replace(hour=9, minute=0, second=0, microsecond=0)
        
        # Handle specific time today "3pm", "15:30"
        time_pattern = r'(\d{1,2}):?(\d{2})?\s*(am|pm)?'
        match = re.search(time_pattern, expression)
        if match and 'tomorrow' not in expression:
            hour = int(match.group(1))
            minute = int(match.group(2)) if match.group(2) else 0
            am_pm = match.group(3)
            
            if am_pm == 'pm' and hour < 12:
                hour += 12
            elif am_pm == 'am' and hour == 12:
                hour = 0
            
            scheduled = reference_time.replace(hour=hour, minute=minute, second=0, microsecond=0)
            
            # If time has passed today, schedule for tomorrow
            if scheduled <= reference_time:
                scheduled += timedelta(days=1)
            
            return scheduled
        
        return None
    
    async def check_due_reminders(self):
        """Check for due reminders and trigger callbacks."""
        now = datetime.now()
        
        for user_id, reminders in self.reminders.items():
            for reminder in reminders:
                if reminder.is_sent:
                    continue
                
                scheduled = datetime.fromisoformat(reminder.scheduled_time)
                
                if now >= scheduled:
                    # Mark as sent
                    reminder.is_sent = True
                    
                    # Trigger callback
                    if self.callback:
                        try:
                            await self.callback(user_id, reminder.message)
                            reminders_logger.info(f"Sent reminder to user {user_id}: {reminder.message}")
                        except Exception as e:
                            reminders_logger.error(f"Error sending reminder to user {user_id}: {e}")
                    
                    # Save updated status
                    await self.save_reminders(user_id)
    
    async def start(self):
        """Start the reminder checking loop."""
        if self._running:
            reminders_logger.warning("Reminder manager already running")
            return
        
        self._running = True
        await self.load_reminders()
        
        reminders_logger.info("Starting reminder manager")
        
        # Create background task
        self._check_task = asyncio.create_task(self._run_check_loop())
    
    async def _run_check_loop(self):
        """Background loop to check reminders."""
        while self._running:
            try:
                await self.check_due_reminders()
                await asyncio.sleep(10)  # Check every 10 seconds
            except Exception as e:
                reminders_logger.error(f"Error in reminder check loop: {e}")
                await asyncio.sleep(30)  # Wait longer on error
    
    async def stop(self):
        """Stop the reminder checking loop."""
        self._running = False
        
        if self._check_task:
            self._check_task.cancel()
            try:
                await self._check_task
            except asyncio.CancelledError:
                pass
        
        reminders_logger.info("Stopped reminder manager")
