"""Facial Recognition skill tools for LLM function calling.

These tools are dynamically loaded by the framework when the skill is activated.
"""
import json
import sys
import importlib.util
from pathlib import Path

# Add project root to path for src imports
project_root = str(Path(__file__).parent.parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.core.skill_tool import SkillTool

# Load the face_recognition_tool module from THIS skill folder explicitly
_face_path = Path(__file__).parent / "face_recognition_tool.py"
_spec = importlib.util.spec_from_file_location("face_recognition_module", _face_path)
_face_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_face_module)

FaceRecognitionManager = _face_module.FaceRecognitionManager

# Default user ID - in practice this should come from context
DEFAULT_USER_ID = "system"


def _get_manager(user_id: str = None) -> FaceRecognitionManager:
    """Get a face recognition manager for the user."""
    return FaceRecognitionManager(user_id or DEFAULT_USER_ID)


class DetectFaces(SkillTool):
    """Detect faces in an image."""
    
    name = "detect_faces"
    description = "Detect all faces in an image. Returns the number of faces found and their locations."
    parameters = {
        "type": "object",
        "properties": {
            "image_path": {
                "type": "string",
                "description": "Path to the image file to analyze"
            }
        },
        "required": ["image_path"]
    }
    
    async def execute(self, image_path: str) -> str:
        manager = _get_manager()
        result = manager.detect_faces(image_path)
        return json.dumps(result, indent=2)


class IdentifyFaces(SkillTool):
    """Identify known people in an image."""
    
    name = "identify_faces"
    description = "Identify known people in an image. Compares faces against previously stored known faces."
    parameters = {
        "type": "object",
        "properties": {
            "image_path": {
                "type": "string",
                "description": "Path to the image file to analyze"
            },
            "tolerance": {
                "type": "number",
                "description": "Face matching tolerance (0.0-1.0, default 0.6). Lower is stricter."
            }
        },
        "required": ["image_path"]
    }
    
    async def execute(self, image_path: str, tolerance: float = 0.6) -> str:
        manager = _get_manager()
        result = manager.identify_faces(image_path, tolerance)
        return json.dumps(result, indent=2, default=str)


class AddPerson(SkillTool):
    """Add a new person to the known faces database."""
    
    name = "add_known_person"
    description = "Add a new person to the known faces database. Stores their face encoding for future recognition."
    parameters = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Name of the person"
            },
            "image_path": {
                "type": "string",
                "description": "Path to an image containing their face"
            },
            "description": {
                "type": "string",
                "description": "Optional description or context about this person"
            }
        },
        "required": ["name", "image_path"]
    }
    
    async def execute(self, name: str, image_path: str, description: str = None) -> str:
        manager = _get_manager()
        result = manager.add_person(name, image_path, description)
        return json.dumps(result, indent=2)


class ListKnownPeople(SkillTool):
    """List all known people in the face database."""
    
    name = "list_known_people"
    description = "List all people that have been added to the known faces database."
    parameters = {
        "type": "object",
        "properties": {},
        "required": []
    }
    
    async def execute(self) -> str:
        manager = _get_manager()
        names = list(set(manager.known_faces.get("names", [])))
        metadata = manager.known_faces.get("metadata", {})
        
        people = []
        for name in names:
            info = {"name": name}
            if name in metadata:
                info["entries"] = len(metadata[name])
            people.append(info)
        
        return json.dumps({
            "success": True,
            "count": len(people),
            "people": people
        }, indent=2)
