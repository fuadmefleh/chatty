"""WhatsApp message parsing and data access implementation."""
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any


class WhatsAppParser:
    """Parser for WhatsApp message databases and exports."""
    
    def __init__(self):
        self.db_paths = self._find_whatsapp_databases()
        self.export_paths = self._find_whatsapp_exports()
    
    def _find_whatsapp_databases(self) -> List[Path]:
        """Find WhatsApp database files on the system."""
        possible_paths = [
            # Android WhatsApp databases
            Path.home() / "Android" / "data" / "com.whatsapp" / "databases",
            # Windows WhatsApp Web cache
            Path.home() / "AppData" / "Roaming" / "WhatsApp" / "databases",
            # macOS WhatsApp
            Path.home() / "Library" / "Containers" / "net.whatsapp.WhatsApp" / "Data" / "Library" / "Application Support" / "WhatsApp" / "Database",
            # Linux WhatsApp
            Path.home() / ".local" / "share" / "whatsapp-desktop" / "databases",
            # Common backup locations
            Path.home() / "Documents" / "WhatsApp Backups",
            Path.home() / "Downloads" / "WhatsApp",
        ]
        
        found_paths = []
        for path in possible_paths:
            if path.exists():
                # Look for database files
                for db_file in path.glob("*.db"):
                    if "whatsapp" in db_file.name.lower():
                        found_paths.append(db_file)
        
        return found_paths
    
    def _find_whatsapp_exports(self) -> List[Path]:
        """Find WhatsApp chat export files."""
        possible_paths = [
            Path.home() / "Downloads",
            Path.home() / "Documents",
            Path.home() / "Desktop",
            Path.home() / "WhatsApp Chats",
        ]
        
        found_exports = []
        for path in possible_paths:
            if path.exists():
                # Look for WhatsApp export files
                for export_file in path.glob("WhatsApp Chat*.txt"):
                    found_exports.append(export_file)
                for export_file in path.glob("_chat.txt"):
                    found_exports.append(export_file)
        
        return found_exports


async def get_recent_messages(limit: int = 20, days: int = 7) -> List[Dict[str, Any]]:
    """Get recent WhatsApp messages."""
    parser = WhatsAppParser()
    
    # Try database access first
    messages = await _get_messages_from_database(parser, limit, days)
    if messages:
        return messages
    
    # Fall back to export files
    messages = await _get_messages_from_exports(parser, limit, days)
    if messages:
        return messages
    
    # If no sources available, return helpful message
    return [{
        "timestamp": datetime.now().isoformat(),
        "contact": "System",
        "message": "WhatsApp messages not accessible. Please export your chats from WhatsApp (Settings > Chats > Chat History > Export Chat) and save them to your Downloads or Documents folder.",
        "type": "info"
    }]


async def search_messages(query: str, contact: str = None, days: int = 30, limit: int = 50) -> List[Dict[str, Any]]:
    """Search WhatsApp messages for specific content."""
    parser = WhatsAppParser()
    
    # Try database search first
    messages = await _search_database_messages(parser, query, contact, days, limit)
    if messages:
        return messages
    
    # Fall back to export file search
    messages = await _search_export_messages(parser, query, contact, days, limit)
    if messages:
        return messages
    
    return [{
        "timestamp": datetime.now().isoformat(),
        "contact": "System", 
        "message": f"No messages found for query: '{query}'. Please ensure WhatsApp chat exports are available.",
        "type": "info"
    }]


async def get_contact_messages(contact: str, limit: int = 30, days: int = 30) -> List[Dict[str, Any]]:
    """Get messages from a specific contact."""
    parser = WhatsAppParser()
    
    # Try database first
    messages = await _get_contact_from_database(parser, contact, limit, days)
    if messages:
        return messages
    
    # Fall back to exports
    messages = await _get_contact_from_exports(parser, contact, limit, days)
    if messages:
        return messages
    
    return [{
        "timestamp": datetime.now().isoformat(),
        "contact": "System",
        "message": f"No messages found from contact: '{contact}'. Please ensure WhatsApp chat exports are available.",
        "type": "info"
    }]


async def get_active_contacts(days: int = 30) -> List[Dict[str, Any]]:
    """Get list of active WhatsApp contacts."""
    parser = WhatsAppParser()
    
    # Try database first
    contacts = await _get_contacts_from_database(parser, days)
    if contacts:
        return contacts
    
    # Fall back to exports
    contacts = await _get_contacts_from_exports(parser, days)
    if contacts:
        return contacts
    
    return [{
        "contact": "System",
        "message_count": 0,
        "last_message_date": datetime.now().isoformat(),
        "type": "info"
    }]


async def _get_messages_from_database(parser: WhatsAppParser, limit: int, days: int) -> List[Dict[str, Any]]:
    """Try to get messages from WhatsApp databases."""
    if not parser.db_paths:
        return []
    
    try:
        # This is a placeholder - actual implementation would need to:
        # 1. Connect to WhatsApp's SQLite database
        # 2. Query the messages table
        # 3. Handle encryption/decryption if needed
        # 4. Parse contact names and message content
        
        # For now, return empty to fall back to export files
        return []
    except Exception:
        return []


async def _get_messages_from_exports(parser: WhatsAppParser, limit: int, days: int) -> List[Dict[str, Any]]:
    """Get messages from WhatsApp export files."""
    if not parser.export_paths:
        return []
    
    messages = []
    cutoff_date = datetime.now() - timedelta(days=days)
    
    try:
        for export_path in parser.export_paths[:3]:  # Limit to first 3 files
            file_messages = await _parse_export_file(export_path, cutoff_date)
            messages.extend(file_messages)
        
        # Sort by timestamp and limit
        messages.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        return messages[:limit]
    except Exception:
        return []


async def _parse_export_file(file_path: Path, cutoff_date: datetime) -> List[Dict[str, Any]]:
    """Parse a WhatsApp export text file."""
    messages = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # WhatsApp export format: [DD/MM/YYYY, HH:MM:SS] Contact Name: Message
        pattern = r'\[(\d{1,2}/\d{1,2}/\d{4}),\s*(\d{1,2}:\d{2}:\d{2})\]\s*([^:]+):\s*(.*)'
        
        for match in re.finditer(pattern, content, re.MULTILINE):
            date_str, time_str, contact, message = match.groups()
            
            try:
                # Parse timestamp
                timestamp = datetime.strptime(f"{date_str} {time_str}", "%d/%m/%Y %H:%M:%S")
                
                # Skip old messages
                if timestamp < cutoff_date:
                    continue
                
                messages.append({
                    "timestamp": timestamp.isoformat(),
                    "contact": contact.strip(),
                    "message": message.strip(),
                    "type": "chat",
                    "source": "export"
                })
            except ValueError:
                continue  # Skip malformed dates
        
        return messages
    except Exception:
        return []


async def _search_database_messages(parser: WhatsAppParser, query: str, contact: str, days: int, limit: int) -> List[Dict[str, Any]]:
    """Search messages in databases."""
    # Placeholder for database search
    return []


async def _search_export_messages(parser: WhatsAppParser, query: str, contact: str, days: int, limit: int) -> List[Dict[str, Any]]:
    """Search messages in export files."""
    all_messages = await _get_messages_from_exports(parser, limit * 3, days)  # Get more to search through
    
    query_lower = query.lower()
    matching_messages = []
    
    for message in all_messages:
        # Check if message contains query
        if query_lower in message.get('message', '').lower():
            # If contact specified, check contact name
            if contact and contact.lower() not in message.get('contact', '').lower():
                continue
            matching_messages.append(message)
    
    return matching_messages[:limit]


async def _get_contact_from_database(parser: WhatsAppParser, contact: str, limit: int, days: int) -> List[Dict[str, Any]]:
    """Get contact messages from database."""
    # Placeholder for database access
    return []


async def _get_contact_from_exports(parser: WhatsAppParser, contact: str, limit: int, days: int) -> List[Dict[str, Any]]:
    """Get contact messages from export files."""
    all_messages = await _get_messages_from_exports(parser, limit * 3, days)
    
    contact_lower = contact.lower()
    contact_messages = []
    
    for message in all_messages:
        if contact_lower in message.get('contact', '').lower():
            contact_messages.append(message)
    
    return contact_messages[:limit]


async def _get_contacts_from_database(parser: WhatsAppParser, days: int) -> List[Dict[str, Any]]:
    """Get contacts from database."""
    # Placeholder for database access
    return []


async def _get_contacts_from_exports(parser: WhatsAppParser, days: int) -> List[Dict[str, Any]]:
    """Get contacts from export files."""
    all_messages = await _get_messages_from_exports(parser, 1000, days)
    
    # Count messages per contact
    contact_counts = {}
    contact_last_message = {}
    
    for message in all_messages:
        contact = message.get('contact', 'Unknown')
        timestamp = message.get('timestamp', '')
        
        if contact not in contact_counts:
            contact_counts[contact] = 0
            contact_last_message[contact] = timestamp
        
        contact_counts[contact] += 1
        # Keep the most recent timestamp
        if timestamp > contact_last_message[contact]:
            contact_last_message[contact] = timestamp
    
    # Convert to list format
    contacts = []
    for contact, count in contact_counts.items():
        contacts.append({
            "contact": contact,
            "message_count": count,
            "last_message_date": contact_last_message[contact],
            "type": "contact"
        })
    
    # Sort by message count
    contacts.sort(key=lambda x: x['message_count'], reverse=True)
    return contacts