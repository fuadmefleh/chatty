"""Memory management system using daily markdown files."""
import os
import aiofiles
from datetime import datetime
from pathlib import Path
from typing import List, Dict
from src.core import config
from src.core.logging_config import get_memory_logger

# Get memory logger
memory_logger = get_memory_logger()


class MemoryManager:
    """Manages conversation memory stored in daily markdown files."""
    
    def __init__(self, user_id: str):
        """Initialize memory manager for a specific user.
        
        Args:
            user_id: Unique identifier for the user
        """
        self.user_id = user_id
        self.user_memory_dir = config.MEMORY_DIR / str(user_id)
        self.short_term_dir = self.user_memory_dir / "short_term"
        self.long_term_dir = self.user_memory_dir / "long_term"
        self.uploads_dir = self.user_memory_dir / "uploads"
        
        # Create directories
        self.user_memory_dir.mkdir(parents=True, exist_ok=True)
        self.short_term_dir.mkdir(parents=True, exist_ok=True)
        self.long_term_dir.mkdir(parents=True, exist_ok=True)
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        
        memory_logger.info(f"Initialized MemoryManager for user {user_id}")
    
    def _get_today_file(self) -> Path:
        """Get the path to today's short-term memory file."""
        today = datetime.now().strftime("%Y-%m-%d")
        return self.short_term_dir / f"{today}.md"
    
    def _get_recent_files(self, days: int = 7) -> List[Path]:
        """Get list of recent short-term memory files.
        
        Args:
            days: Number of recent days to retrieve
            
        Returns:
            List of file paths sorted by date (newest first)
        """
        files = sorted(
            self.short_term_dir.glob("*.md"),
            key=lambda p: p.stem,
            reverse=True
        )
        return files[:days]
    
    async def add_interaction(self, user_message: str, assistant_message: str):
        """Add a conversation interaction to today's memory.
        
        Args:
            user_message: Message from the user
            assistant_message: Response from the assistant
        """
        today_file = self._get_today_file()
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        memory_logger.debug(f"Adding interaction for user {self.user_id} to {today_file.name}")
        
        # Create file with header if it doesn't exist
        if not today_file.exists():
            async with aiofiles.open(today_file, 'w') as f:
                date_str = datetime.now().strftime("%Y-%m-%d")
                await f.write(f"# Memory Log - {date_str}\n\n")
            memory_logger.info(f"Created new memory file: {today_file.name} for user {self.user_id}")
        
        # Append interaction
        async with aiofiles.open(today_file, 'a') as f:
            await f.write(f"## [{timestamp}]\n\n")
            await f.write(f"**User**: {user_message}\n\n")
            await f.write(f"**Assistant**: {assistant_message}\n\n")
            await f.write("---\n\n")
        
        memory_logger.info(f"Saved interaction for user {self.user_id}: user_msg_len={len(user_message)}, assistant_msg_len={len(assistant_message)}")
    
    async def get_recent_memory(self, days: int = 7) -> str:
        """Retrieve recent memory as a formatted string.
        
        Args:
            days: Number of recent days to retrieve
            
        Returns:
            Formatted memory string
        """
        recent_files = self._get_recent_files(days)
        
        memory_logger.debug(f"Retrieving recent memory for user {self.user_id}: {len(recent_files)} files from last {days} days")
        
        if not recent_files:
            memory_logger.info(f"No recent memory files found for user {self.user_id}")
            return "No previous conversations found."
        
        memory_parts = []
        for file_path in recent_files:
            try:
                async with aiofiles.open(file_path, 'r') as f:
                    content = await f.read()
                    memory_parts.append(content)
                    memory_logger.debug(f"Loaded memory file {file_path.name}: {len(content)} chars")
            except Exception as e:
                memory_logger.error(f"Error reading memory file {file_path}: {e}")
        
        total_chars = sum(len(part) for part in memory_parts)
        memory_logger.info(f"Retrieved recent memory for user {self.user_id}: {len(memory_parts)} files, {total_chars} total chars")
        return "\n\n".join(memory_parts) if memory_parts else "No previous conversations found."
    
    async def add_note(self, note: str):
        """Add a standalone note to today's memory.
        
        Args:
            note: Note text to add
        """
        today = datetime.now().strftime("%Y-%m-%d")
        today_file = self.short_term_dir / f"{today}.md"
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        memory_logger.debug(f"Adding note for user {self.user_id} to {today_file.name}")
        
        # Create file with header if it doesn't exist
        if not today_file.exists():
            async with aiofiles.open(today_file, 'w') as f:
                date_str = datetime.now().strftime("%Y-%m-%d")
                await f.write(f"# Memory Log - {date_str}\n\n")
            memory_logger.info(f"Created new memory file: {today_file.name} for user {self.user_id}")
        
        # Append note
        async with aiofiles.open(today_file, 'a') as f:
            await f.write(f"### Note [{timestamp}]\n\n")
            await f.write(f"{note}\n\n")
            await f.write("---\n\n")
        
        memory_logger.info(f"Added note for user {self.user_id}: {note[:100]}...")
    
    async def get_summary(self) -> Dict[str, int]:
        """Get summary statistics about user's memory.
        
        Returns:
            Dictionary with memory statistics
        """
        short_term_files = list(self.short_term_dir.glob("*.md"))
        long_term_files = list(self.long_term_dir.glob("*.md"))
        all_files = short_term_files + long_term_files
        total_size = sum(f.stat().st_size for f in all_files)
        
        return {
            "total_days": len(short_term_files),
            "long_term_entries": len(long_term_files),
            "total_size_bytes": total_size,
            "oldest_date": min(f.stem for f in short_term_files) if short_term_files else None,
            "newest_date": max(f.stem for f in short_term_files) if short_term_files else None,
        }
    
    async def get_long_term_memory(self) -> str:
        """Retrieve all long-term memory as a formatted string.
        
        Returns:
            Formatted long-term memory string
        """
        long_term_files = sorted(
            self.long_term_dir.glob("*.md"),
            key=lambda p: p.stem,
            reverse=True
        )
        
        if not long_term_files:
            return "No long-term memories yet."
        
        memory_parts = []
        for file_path in long_term_files:
            try:
                async with aiofiles.open(file_path, 'r') as f:
                    content = await f.read()
                    memory_parts.append(content)
            except Exception as e:
                print(f"Error reading long-term memory file {file_path}: {e}")
        
        return "\n\n".join(memory_parts) if memory_parts else "No long-term memories yet."
    
    async def add_long_term_memory(self, title: str, content: str):
        """Add or update a long-term memory entry.
        
        Args:
            title: Title/category of the memory (e.g., 'preferences', 'important_facts')
            content: Content to store
        """
        memory_file = self.long_term_dir / f"{title}.md"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # If file exists, append; otherwise create new
        if memory_file.exists():
            async with aiofiles.open(memory_file, 'a') as f:
                await f.write(f"\n\n## Updated: {timestamp}\n\n")
                await f.write(f"{content}\n")
        else:
            async with aiofiles.open(memory_file, 'w') as f:
                await f.write(f"# Long-Term Memory: {title}\n\n")
                await f.write(f"Created: {timestamp}\n\n")
                await f.write(f"{content}\n")
    
    async def get_short_term_files_for_consolidation(self, days_old: int = 7) -> List[Path]:
        """Get short-term memory files older than specified days for consolidation.
        
        Args:
            days_old: Get files older than this many days
            
        Returns:
            List of file paths that should be consolidated
        """
        from datetime import timedelta
        
        cutoff_date = datetime.now() - timedelta(days=days_old)
        cutoff_str = cutoff_date.strftime("%Y-%m-%d")
        
        all_files = sorted(
            self.short_term_dir.glob("*.md"),
            key=lambda p: p.stem
        )
        
        # Return files older than cutoff
        return [f for f in all_files if f.stem < cutoff_str]
    
    async def archive_short_term_memory(self, file_path: Path):
        """Archive a short-term memory file after consolidation.
        
        Args:
            file_path: Path to the short-term memory file to archive
        """
        # Move to archive folder within short_term
        archive_dir = self.short_term_dir / "archived"
        archive_dir.mkdir(exist_ok=True)
        
        archive_path = archive_dir / file_path.name
        
        # Move the file
        try:
            file_path.rename(archive_path)
        except Exception as e:
            print(f"Error archiving {file_path}: {e}")
    
    async def consolidate_memories(self, agent) -> str:
        """Consolidate old short-term memories into long-term insights.
        
        This method analyzes older short-term memories and extracts important
        information to store in long-term memory categories.
        
        Args:
            agent: ReACTAgent instance to use for analysis
            
        Returns:
            Summary of consolidation results
        """
        from datetime import datetime
        
        # Get files older than 7 days
        files_to_consolidate = await self.get_short_term_files_for_consolidation(days_old=7)
        
        if not files_to_consolidate:
            return "No short-term memories ready for consolidation."
        
        # Read all files to consolidate
        all_content = []
        for file_path in files_to_consolidate:
            try:
                async with aiofiles.open(file_path, 'r') as f:
                    content = await f.read()
                    all_content.append(f"## From {file_path.stem}\n{content}")
            except Exception as e:
                print(f"Error reading file {file_path}: {e}")
        
        if not all_content:
            return "No content to consolidate."
        
        combined_content = "\n\n".join(all_content)
        
        # Create prompt for AI to analyze and consolidate
        consolidation_prompt = f"""You are consolidating short-term memories into long-term memory storage.

Analyze the following conversation logs and extract important information that should be remembered long-term:

{combined_content}

Please identify and categorize important information into these categories:

1. **Personal Preferences** - User's likes, dislikes, preferences
2. **Important Facts** - Key facts about the user (name, location, job, family, etc.)
3. **Goals and Projects** - User's goals, ongoing projects, aspirations
4. **Relationships** - Important people in the user's life
5. **Recurring Topics** - Topics the user frequently discusses
6. **Key Insights** - Important insights or decisions made

For each category that has relevant information, provide:
- A clear, concise summary
- Specific details worth remembering

Format your response as:
CATEGORY: [category name]
CONTENT: [summary and details]

If a category has no relevant information, skip it.
"""
        
        try:
            # Use the agent to analyze
            consolidation_result = await agent.think(consolidation_prompt, [])
            
            # Parse the result and store in long-term memory
            await self._parse_and_store_consolidation(consolidation_result)
            
            # Archive the processed files
            for file_path in files_to_consolidate:
                await self.archive_short_term_memory(file_path)
            
            return f"Successfully consolidated {len(files_to_consolidate)} days of memories into long-term storage."
            
        except Exception as e:
            print(f"Error during consolidation: {e}")
            return f"Error consolidating memories: {e}"
    
    async def _parse_and_store_consolidation(self, consolidation_text: str):
        """Parse AI consolidation result and store in appropriate long-term memory files.
        
        Args:
            consolidation_text: Text from AI containing categorized memories
        """
        import re
        
        # Parse CATEGORY/CONTENT pairs
        pattern = r'CATEGORY:\s*(.+?)\s*\nCONTENT:\s*(.+?)(?=\nCATEGORY:|$)'
        matches = re.findall(pattern, consolidation_text, re.DOTALL)
        
        for category, content in matches:
            category_clean = category.strip().lower().replace(" ", "_")
            content_clean = content.strip()
            
            if content_clean:
                await self.add_long_term_memory(category_clean, content_clean)

    async def cleanup_long_term_memories(self, agent) -> str:
        """Clean up and reorganize long-term memories, removing duplicates and consolidating.
        
        This method uses AI to analyze each long-term memory file, remove duplicates,
        and reorganize the content in a clean, structured format.
        
        Args:
            agent: ReACTAgent instance to use for cleanup
            
        Returns:
            Summary of cleanup results
        """
        if not self.long_term_dir.exists():
            return "No long-term memory directory found."
        
        # Get all long-term memory files
        memory_files = list(self.long_term_dir.glob("*.md"))
        
        if not memory_files:
            return "No long-term memory files to clean up."
        
        cleaned_count = 0
        errors = []
        
        for file_path in memory_files:
            try:
                # Read current content
                async with aiofiles.open(file_path, 'r') as f:
                    content = await f.read()
                
                # Skip if file is already clean (no duplicate headers, etc.)
                if content.count("## Update [") <= 1:
                    continue
                
                # Create cleanup prompt
                cleanup_prompt = f"""You are cleaning up and organizing a long-term memory file.

Current content:
{content}

Please:
1. Remove all duplicate information
2. Consolidate related entries
3. Organize the content in a clear, structured format
4. Preserve all unique information
5. Keep the most recent/accurate version when duplicates exist
6. Maintain the original summary header but update it if needed

Format your response as a clean, organized markdown file with:
- A clear summary section at the top
- Well-organized details below
- No redundant information
- Clear, concise entries

Provide ONLY the cleaned content, no explanations."""

                # Use agent to clean up
                cleaned_content = await agent.think(cleanup_prompt, [])
                
                # Write back the cleaned content
                async with aiofiles.open(file_path, 'w') as f:
                    # Ensure it starts with proper header
                    if not cleaned_content.startswith("# Long-Term Memory:"):
                        category_name = file_path.stem.replace("_", " ").title()
                        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        cleaned_content = f"# Long-Term Memory: {file_path.stem}\n\nCreated: {timestamp}\n\n{cleaned_content}"
                    await f.write(cleaned_content)
                
                cleaned_count += 1
                
            except Exception as e:
                errors.append(f"{file_path.name}: {str(e)}")
        
        result = f"Cleaned {cleaned_count} long-term memory file(s)."
        if errors:
            result += f" Errors: {', '.join(errors)}"
        
        return result


