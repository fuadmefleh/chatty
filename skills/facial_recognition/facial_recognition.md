# Facial Recognition

## Description
Detect, identify, and label faces in photos using facial recognition technology. This skill can learn who people are from labeled photos and then automatically identify them in future images.

## Usage
Use this skill when:
- User shares a photo and you need to identify who's in it
- User wants to label/teach you who someone is in a photo
- You need to detect how many people are in an image
- User asks about people in their uploaded photos

## Examples
- "Who is in this photo?"
- "This is my sister Sarah" (when sharing a photo)
- "Do you recognize anyone in this picture?"
- "Label the faces in this image"

## Tools
- `detect_faces` - Detect all faces in an image and return face locations
- `encode_face` - Create a face encoding for a person (for learning/storing identity)
- `identify_faces` - Identify all faces in an image by matching against known faces
- `add_person` - Add a new person with their face encoding and name
- `list_known_people` - List all people the system knows
