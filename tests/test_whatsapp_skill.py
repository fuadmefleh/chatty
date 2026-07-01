"""Tests for WhatsApp messages skill."""
import asyncio
import json
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
import sys

# Add project root to path
project_root = str(Path(__file__).parent.parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from skills.whatsapp_messages.tools import (
    ReadRecentWhatsAppMessagesTool,
    SearchWhatsAppMessagesTool,
    GetWhatsAppContactMessagesTool,
    ListWhatsAppContactsTool
)


class TestWhatsAppTools:
    """Test WhatsApp message tools."""
    
    @pytest.mark.asyncio
    async def test_read_recent_messages_tool(self):
        """Test reading recent WhatsApp messages."""
        tool = ReadRecentWhatsAppMessagesTool()
        
        # Test tool properties
        assert tool.name == "read_recent_whatsapp_messages"
        assert "recent" in tool.description.lower()
        assert "limit" in tool.parameters["properties"]
        assert "days" in tool.parameters["properties"]
        
        # Test execution with mocked data
        with patch('skills.whatsapp_messages.tools._parser.get_recent_messages') as mock_get:
            mock_get.return_value = [
                {
                    "timestamp": "2024-01-15T10:30:00",
                    "contact": "John Doe",
                    "message": "Hey, how are you?",
                    "type": "chat"
                }
            ]
            
            result = await tool.execute(limit=10, days=7)
            data = json.loads(result)
            
            assert data["success"] is True
            assert data["count"] == 1
            assert "John Doe" in str(data["messages"])
    
    @pytest.mark.asyncio
    async def test_search_messages_tool(self):
        """Test searching WhatsApp messages."""
        tool = SearchWhatsAppMessagesTool()
        
        # Test tool properties
        assert tool.name == "search_whatsapp_messages"
        assert "search" in tool.description.lower()
        assert "query" in tool.parameters["properties"]
        assert tool.parameters["required"] == ["query"]
        
        # Test execution
        with patch('skills.whatsapp_messages.tools._parser.search_messages') as mock_search:
            mock_search.return_value = [
                {
                    "timestamp": "2024-01-15T10:30:00",
                    "contact": "Jane Smith",
                    "message": "Let's meet for coffee tomorrow",
                    "type": "chat"
                }
            ]
            
            result = await tool.execute(query="coffee", contact="Jane", days=30)
            data = json.loads(result)
            
            assert data["success"] is True
            assert data["query"] == "coffee"
            assert data["contact"] == "Jane"
    
    @pytest.mark.asyncio
    async def test_get_contact_messages_tool(self):
        """Test getting messages from specific contact."""
        tool = GetWhatsAppContactMessagesTool()
        
        # Test tool properties
        assert tool.name == "get_whatsapp_contact_messages"
        assert "contact" in tool.description.lower()
        assert tool.parameters["required"] == ["contact"]
        
        # Test execution
        with patch('skills.whatsapp_messages.tools._parser.get_contact_messages') as mock_get:
            mock_get.return_value = [
                {
                    "timestamp": "2024-01-15T09:00:00",
                    "contact": "Mom",
                    "message": "Don't forget dinner tonight!",
                    "type": "chat"
                }
            ]
            
            result = await tool.execute(contact="Mom", limit=20)
            data = json.loads(result)
            
            assert data["success"] is True
            assert data["contact"] == "Mom"
            assert "Mom" in str(data["messages"])
    
    @pytest.mark.asyncio
    async def test_list_contacts_tool(self):
        """Test listing WhatsApp contacts."""
        tool = ListWhatsAppContactsTool()
        
        # Test tool properties
        assert tool.name == "list_whatsapp_contacts"
        assert "contacts" in tool.description.lower()
        
        # Test execution
        with patch('skills.whatsapp_messages.tools._parser.get_active_contacts') as mock_list:
            mock_list.return_value = [
                {
                    "contact": "John Doe",
                    "message_count": 25,
                    "last_message_date": "2024-01-15T10:30:00",
                    "type": "contact"
                },
                {
                    "contact": "Work Group",
                    "message_count": 15,
                    "last_message_date": "2024-01-15T09:15:00",
                    "type": "contact"
                }
            ]
            
            result = await tool.execute(days=30)
            data = json.loads(result)
            
            assert data["success"] is True
            assert data["count"] == 2
            assert any("John Doe" in str(contact) for contact in data["contacts"])
    
    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test error handling in tools."""
        tool = ReadRecentWhatsAppMessagesTool()
        
        with patch('skills.whatsapp_messages.tools._parser.get_recent_messages') as mock_get:
            mock_get.side_effect = Exception("Database error")
            
            result = await tool.execute()
            data = json.loads(result)
            
            assert data["success"] is False
            assert "error" in data
            assert "Database error" in data["error"]


def test_tool_names_unique():
    """Test that all tool names are unique."""
    tools = [
        ReadRecentWhatsAppMessagesTool(),
        SearchWhatsAppMessagesTool(),
        GetWhatsAppContactMessagesTool(),
        ListWhatsAppContactsTool()
    ]
    
    names = [tool.name for tool in tools]
    assert len(names) == len(set(names)), "Tool names must be unique"


def test_all_tools_have_required_attributes():
    """Test that all tools have required attributes."""
    tools = [
        ReadRecentWhatsAppMessagesTool(),
        SearchWhatsAppMessagesTool(), 
        GetWhatsAppContactMessagesTool(),
        ListWhatsAppContactsTool()
    ]
    
    for tool in tools:
        assert hasattr(tool, 'name'), f"{tool.__class__} missing name"
        assert hasattr(tool, 'description'), f"{tool.__class__} missing description"
        assert hasattr(tool, 'parameters'), f"{tool.__class__} missing parameters"
        assert hasattr(tool, 'execute'), f"{tool.__class__} missing execute method"
        
        # Validate parameter structure
        assert "type" in tool.parameters
        assert tool.parameters["type"] == "object"
        assert "properties" in tool.parameters


if __name__ == "__main__":
    # Run a simple test
    async def main():
        tool = ReadRecentWhatsAppMessagesTool()
        print(f"Tool: {tool.name}")
        print(f"Description: {tool.description}")
        
        # Test with mock data
        with patch('skills.whatsapp_messages.whatsapp_parser.get_recent_messages') as mock_get:
            mock_get.return_value = [{"test": "data"}]
            result = await tool.execute()
            print(f"Result: {result}")
    
    asyncio.run(main())