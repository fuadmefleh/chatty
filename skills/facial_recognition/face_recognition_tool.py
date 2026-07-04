"""Facial recognition tool for detecting and identifying faces in images."""
import importlib.util
import json
import pickle
from pathlib import Path
from typing import Dict, Optional

# Lazy import - only import when needed to avoid startup crashes
FACE_RECOGNITION_AVAILABLE = None

def _check_face_recognition():
    """Check if face_recognition is available and cache the result."""
    global FACE_RECOGNITION_AVAILABLE
    if FACE_RECOGNITION_AVAILABLE is None:
        FACE_RECOGNITION_AVAILABLE = all(
            importlib.util.find_spec(module) is not None
            for module in ("face_recognition", "PIL", "numpy")
        )
    return FACE_RECOGNITION_AVAILABLE


class FaceRecognitionManager:
    """Manages face encodings and recognition for users."""
    
    def __init__(self, user_id: str):
        """Initialize face recognition manager for a user.
        
        Args:
            user_id: User ID for storing face data
        """
        self.user_id = user_id
        # Store face data in memory/{user_id}/face_data/
        base_dir = Path(__file__).parent.parent.parent / "memory" / str(user_id)
        self.face_data_dir = base_dir / "face_data"
        self.face_data_dir.mkdir(parents=True, exist_ok=True)
        
        # Files for storing known faces
        self.encodings_file = self.face_data_dir / "face_encodings.pkl"
        self.metadata_file = self.face_data_dir / "face_metadata.json"
        
        # Load known faces
        self.known_faces = self._load_known_faces()
    
    def _load_known_faces(self) -> Dict:
        """Load known face encodings and metadata.
        
        Returns:
            Dictionary with face data
        """
        if not self.encodings_file.exists():
            return {"encodings": [], "names": [], "metadata": {}}
        
        try:
            # Load encodings
            with open(self.encodings_file, 'rb') as f:
                data = pickle.load(f)
            
            # Load metadata
            if self.metadata_file.exists():
                with open(self.metadata_file, 'r') as f:
                    metadata = json.load(f)
                data["metadata"] = metadata
            else:
                data["metadata"] = {}
            
            return data
        except Exception as e:
            print(f"Error loading face data: {e}")
            return {"encodings": [], "names": [], "metadata": {}}
    
    def _save_known_faces(self):
        """Save known face encodings and metadata to disk."""
        try:
            # Save encodings
            with open(self.encodings_file, 'wb') as f:
                pickle.dump({
                    "encodings": self.known_faces["encodings"],
                    "names": self.known_faces["names"]
                }, f)
            
            # Save metadata
            with open(self.metadata_file, 'w') as f:
                json.dump(self.known_faces["metadata"], f, indent=2)
        except Exception as e:
            print(f"Error saving face data: {e}")
    
    def detect_faces(self, image_path: str) -> Dict:
        """Detect all faces in an image.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Dictionary with detection results
        """
        if not _check_face_recognition():
            return {"error": "face_recognition library not installed"}
        
        try:
            import face_recognition
            
            # Load image
            image = face_recognition.load_image_file(image_path)
            
            # Detect faces
            face_locations = face_recognition.face_locations(image)
            
            return {
                "num_faces": len(face_locations),
                "locations": [
                    {
                        "top": loc[0],
                        "right": loc[1],
                        "bottom": loc[2],
                        "left": loc[3]
                    }
                    for loc in face_locations
                ],
                "image_size": image.shape
            }
        except Exception as e:
            return {"error": str(e)}
    
    def encode_faces(self, image_path: str) -> Dict:
        """Create face encodings for all faces in an image.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Dictionary with face encodings
        """
        if not _check_face_recognition():
            return {"error": "face_recognition library not installed"}
        
        try:
            import face_recognition
            
            # Load image
            image = face_recognition.load_image_file(image_path)
            
            # Get face locations and encodings
            face_locations = face_recognition.face_locations(image)
            face_encodings = face_recognition.face_encodings(image, face_locations)
            
            return {
                "num_faces": len(face_encodings),
                "encodings": face_encodings,
                "locations": face_locations
            }
        except Exception as e:
            return {"error": str(e)}
    
    def add_person(self, name: str, image_path: str, description: Optional[str] = None) -> Dict:
        """Add a new person with their face encoding.
        
        Args:
            name: Name of the person
            image_path: Path to image containing their face
            description: Optional description/context
            
        Returns:
            Result dictionary
        """
        if not _check_face_recognition():
            return {"error": "face_recognition library not installed"}
        
        try:
            import numpy as np
            
            # Encode the face
            result = self.encode_faces(image_path)
            
            if "error" in result:
                return result
            
            if result["num_faces"] == 0:
                return {"error": "No faces detected in the image"}
            
            if result["num_faces"] > 1:
                return {
                    "warning": f"Multiple faces detected ({result['num_faces']}). Using the first face.",
                    "suggestion": "Please provide an image with only one face for better accuracy"
                }
            
            # Add the encoding
            encoding = result["encodings"][0]
            self.known_faces["encodings"].append(encoding)
            self.known_faces["names"].append(name)
            
            # Add metadata
            if name not in self.known_faces["metadata"]:
                self.known_faces["metadata"][name] = []
            
            self.known_faces["metadata"][name].append({
                "image_path": image_path,
                "description": description,
                "added_date": str(np.datetime64('now'))
            })
            
            # Save to disk
            self._save_known_faces()
            
            return {
                "success": True,
                "name": name,
                "message": f"Successfully added {name} to known faces"
            }
        except Exception as e:
            return {"error": str(e)}
    
    def identify_faces(self, image_path: str, tolerance: float = 0.6) -> Dict:
        """Identify all faces in an image.
        
        Args:
            image_path: Path to the image file
            tolerance: Face matching tolerance (lower = stricter, default 0.6)
            
        Returns:
            Dictionary with identification results
        """
        if not _check_face_recognition():
            return {"error": "face_recognition library not installed"}
        
        if not self.known_faces["encodings"]:
            return {
                "error": "No known faces in database. Add people first using add_person."
            }
        
        try:
            import face_recognition
            import numpy as np
            
            # Load and encode faces in the image
            image = face_recognition.load_image_file(image_path)
            face_locations = face_recognition.face_locations(image)
            face_encodings = face_recognition.face_encodings(image, face_locations)
            
            if not face_encodings:
                return {
                    "num_faces": 0,
                    "faces": [],
                    "message": "No faces detected in the image"
                }
            
            # Identify each face
            identified_faces = []
            
            for (encoding, location) in zip(face_encodings, face_locations):
                # Compare with known faces
                matches = face_recognition.compare_faces(
                    self.known_faces["encodings"],
                    encoding,
                    tolerance=tolerance
                )
                
                # Find best match by distance
                face_distances = face_recognition.face_distance(
                    self.known_faces["encodings"],
                    encoding
                )
                
                best_match_index = None
                if True in matches:
                    best_match_index = np.argmin(face_distances)
                
                if best_match_index is not None:
                    name = self.known_faces["names"][best_match_index]
                    confidence = 1 - face_distances[best_match_index]
                else:
                    name = "Unknown"
                    confidence = 0.0
                
                identified_faces.append({
                    "name": name,
                    "confidence": float(confidence),
                    "location": {
                        "top": location[0],
                        "right": location[1],
                        "bottom": location[2],
                        "left": location[3]
                    }
                })
            
            return {
                "num_faces": len(identified_faces),
                "faces": identified_faces
            }
        except Exception as e:
            return {"error": str(e)}
    
    def list_known_people(self) -> Dict:
        """List all known people in the database.
        
        Returns:
            Dictionary with known people info
        """
        if not self.known_faces["names"]:
            return {
                "num_people": 0,
                "people": [],
                "message": "No known people in database"
            }
        
        # Count occurrences of each name (multiple encodings per person)
        from collections import Counter
        name_counts = Counter(self.known_faces["names"])
        
        people = []
        for name, count in name_counts.items():
            metadata = self.known_faces["metadata"].get(name, [])
            people.append({
                "name": name,
                "num_samples": count,
                "metadata": metadata
            })
        
        return {
            "num_people": len(people),
            "people": people
        }


# Singleton manager instances per user
_managers = {}

def get_manager(user_id: str) -> FaceRecognitionManager:
    """Get or create face recognition manager for a user."""
    if user_id not in _managers:
        _managers[user_id] = FaceRecognitionManager(user_id)
    return _managers[user_id]


# Tool functions that the agent can call

async def detect_faces(image_path: str, user_id: str) -> str:
    """Detect faces in an image.
    
    Args:
        image_path: Path to the image file
        user_id: User ID
        
    Returns:
        Detection results as string
    """
    if not _check_face_recognition():
        return "❌ Face recognition library is not installed. Please install: pip install face-recognition"
    
    manager = get_manager(user_id)
    result = manager.detect_faces(image_path)
    
    if "error" in result:
        return f"❌ Error: {result['error']}"
    
    num_faces = result["num_faces"]
    if num_faces == 0:
        return "No faces detected in the image."
    elif num_faces == 1:
        return "✅ Detected 1 face in the image."
    else:
        return f"✅ Detected {num_faces} faces in the image."


async def add_person(name: str, image_path: str, user_id: str, description: str = None) -> str:
    """Add a person to the known faces database.
    
    Args:
        name: Name of the person
        image_path: Path to image containing their face
        user_id: User ID
        description: Optional description
        
    Returns:
        Result message
    """
    if not _check_face_recognition():
        return "❌ Face recognition library is not installed. Please install: pip install face-recognition"
    
    manager = get_manager(user_id)
    result = manager.add_person(name, image_path, description)
    
    if "error" in result:
        return f"❌ Error: {result['error']}"
    
    if "warning" in result:
        return f"⚠️ {result['warning']}\n{result['suggestion']}\n\n✅ Added {name} to known faces."
    
    return f"✅ {result['message']}"


async def identify_faces(image_path: str, user_id: str) -> str:
    """Identify all faces in an image.
    
    Args:
        image_path: Path to the image file
        user_id: User ID
        
    Returns:
        Identification results as string
    """
    if not _check_face_recognition():
        return "❌ Face recognition library is not installed. Please install: pip install face-recognition"
    
    manager = get_manager(user_id)
    result = manager.identify_faces(image_path)
    
    if "error" in result:
        return f"❌ Error: {result['error']}"
    
    if result["num_faces"] == 0:
        return "No faces detected in the image."
    
    # Format the results
    output = [f"✅ Found {result['num_faces']} face(s):\n"]
    
    for i, face in enumerate(result["faces"], 1):
        confidence_percent = face["confidence"] * 100
        if face["name"] == "Unknown":
            output.append(f"{i}. Unknown person")
        else:
            output.append(f"{i}. {face['name']} (confidence: {confidence_percent:.1f}%)")
    
    return "\n".join(output)


async def list_known_people(user_id: str) -> str:
    """List all known people.
    
    Args:
        user_id: User ID
        
    Returns:
        List of known people
    """
    if not _check_face_recognition():
        return "❌ Face recognition library is not installed. Please install: pip install face-recognition"
    
    manager = get_manager(user_id)
    result = manager.list_known_people()
    
    if result["num_people"] == 0:
        return "No known people in the database yet. Add people using photos with their names."
    
    output = [f"👥 Known people ({result['num_people']}):\n"]
    
    for person in result["people"]:
        output.append(f"• {person['name']} ({person['num_samples']} sample(s))")
    
    return "\n".join(output)


# Main execute function for the skill
async def execute(action: str, **kwargs) -> str:
    """Execute a facial recognition action.
    
    Args:
        action: Action to perform (detect_faces, add_person, identify_faces, list_known_people)
        **kwargs: Action-specific parameters
        
    Returns:
        Result string
    """
    if action == "detect_faces":
        return await detect_faces(kwargs["image_path"], kwargs["user_id"])
    elif action == "add_person":
        return await add_person(
            kwargs["name"],
            kwargs["image_path"],
            kwargs["user_id"],
            kwargs.get("description")
        )
    elif action == "identify_faces":
        return await identify_faces(kwargs["image_path"], kwargs["user_id"])
    elif action == "list_known_people":
        return await list_known_people(kwargs["user_id"])
    else:
        return f"❌ Unknown action: {action}"
