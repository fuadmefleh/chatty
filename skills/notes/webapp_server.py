"""Flask web server for Notes Mini App."""
import sys
import logging
from pathlib import Path

# Add parent directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

from skills.notes.notes_manager import NotesManager

logger = logging.getLogger('bot.webapp')

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Initialize notes manager
notes_manager = NotesManager()

# Path to webapp files
WEBAPP_DIR = Path(__file__).parent / "webapp"


@app.route('/')
def index():
    """Serve the mini app main page."""
    return send_from_directory(WEBAPP_DIR, 'index.html')


@app.route('/styles.css')
def styles():
    """Serve CSS file."""
    return send_from_directory(WEBAPP_DIR, 'styles.css')


@app.route('/app.js')
def app_js():
    """Serve JavaScript file."""
    return send_from_directory(WEBAPP_DIR, 'app.js')


@app.route('/api/notes', methods=['GET'])
def get_notes():
    """Get all notes for a user."""
    try:
        user_id = request.args.get('user_id')
        
        if not user_id:
            return jsonify({
                'success': False,
                'error': 'user_id is required'
            }), 400
        
        notes = notes_manager.get_notes(user_id)
        
        return jsonify({
            'success': True,
            'notes': [
                {
                    'id': note.id,
                    'content': note.content,
                    'created_at': note.created_at
                }
                for note in notes
            ]
        })
    except Exception as e:
        logger.error(f"Error getting notes: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/notes', methods=['POST'])
def create_note():
    """Create a new note."""
    try:
        data = request.json
        user_id = data.get('user_id')
        note_content = data.get('note_content')
        
        if not user_id or not note_content:
            return jsonify({
                'success': False,
                'error': 'user_id and note_content are required'
            }), 400
        
        note = notes_manager.add_note(user_id, note_content)
        
        return jsonify({
            'success': True,
            'note': {
                'id': note.id,
                'content': note.content,
                'created_at': note.created_at
            }
        })
    except Exception as e:
        logger.error(f"Error creating note: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/notes/<note_id>', methods=['PUT'])
def update_note(note_id):
    """Update an existing note."""
    try:
        data = request.json
        user_id = data.get('user_id')
        note_content = data.get('note_content')
        
        if not user_id or not note_content:
            return jsonify({
                'success': False,
                'error': 'user_id and note_content are required'
            }), 400
        
        note = notes_manager.update_note(user_id, note_id, note_content)
        
        if not note:
            return jsonify({
                'success': False,
                'error': 'Note not found'
            }), 404
        
        return jsonify({
            'success': True,
            'note': {
                'id': note.id,
                'content': note.content,
                'created_at': note.created_at
            }
        })
    except Exception as e:
        logger.error(f"Error updating note: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/notes/<note_id>', methods=['DELETE'])
def delete_note(note_id):
    """Delete a note."""
    try:
        data = request.json
        user_id = data.get('user_id')
        
        if not user_id:
            return jsonify({
                'success': False,
                'error': 'user_id is required'
            }), 400
        
        success = notes_manager.delete_note(user_id, note_id)
        
        if not success:
            return jsonify({
                'success': False,
                'error': 'Note not found'
            }), 404
        
        return jsonify({
            'success': True,
            'message': 'Note deleted successfully'
        })
    except Exception as e:
        logger.error(f"Error deleting note: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def run_webapp_server(host='0.0.0.0', port=5001):
    """Run the Flask webapp server."""
    logger.info(f"Starting Notes Mini App server on {host}:{port}")
    app.run(host=host, port=port, debug=False)


if __name__ == '__main__':
    run_webapp_server()
