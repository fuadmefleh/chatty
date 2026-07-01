"""Unified Flask web server for all Mini Apps."""
import os
import sys
import json
import logging
from pathlib import Path

# Add current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

from skills.notes.notes_manager import NotesManager
from skills.walmart_orders.walmart_parser import WalmartOrderDB

logger = logging.getLogger('bot.mini_apps')

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Initialize managers for each mini app
notes_manager = NotesManager()
walmart_db = WalmartOrderDB()

# Base directory
BASE_DIR = Path(__file__).parent


# ============================================================================
# ROOT ROUTES
# ============================================================================

@app.route('/')
def index():
    """Root endpoint - list available mini apps."""
    return jsonify({
        'available_apps': [
            {'name': 'Walmart Orders', 'path': '/walmart'},
            {'name': 'Notes', 'path': '/notes'},
            # Add more mini apps here as they're developed
        ],
        'message': 'Chatty Mini Apps Server'
    })


@app.route('/health')
def health():
    """Health check endpoint."""
    return jsonify({'status': 'ok'})


# ============================================================================
# NOTES MINI APP
# ============================================================================

NOTES_WEBAPP_DIR = BASE_DIR / "skills" / "notes" / "webapp"


@app.route('/notes')
def notes_index():
    """Serve the Notes mini app main page."""
    return send_from_directory(NOTES_WEBAPP_DIR, 'index.html')


@app.route('/notes/styles.css')
def notes_styles():
    """Serve Notes CSS file."""
    return send_from_directory(NOTES_WEBAPP_DIR, 'styles.css')


@app.route('/notes/app.js')
def notes_app_js():
    """Serve Notes JavaScript file."""
    return send_from_directory(NOTES_WEBAPP_DIR, 'app.js')


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


# ============================================================================
# WALMART ORDERS MINI APP
# ============================================================================

WALMART_WEBAPP_DIR = BASE_DIR / "skills" / "walmart_orders" / "webapp"


@app.route('/walmart')
def walmart_index():
    """Serve the Walmart orders mini app main page."""
    return send_from_directory(WALMART_WEBAPP_DIR, 'index.html')


@app.route('/walmart/styles.css')
def walmart_styles():
    """Serve Walmart CSS file."""
    logger.info("  - Walmart Orders: /walmart")
    return send_from_directory(WALMART_WEBAPP_DIR, 'styles.css')


@app.route('/walmart/app.js')
def walmart_app_js():
    """Serve Walmart JavaScript file."""
    return send_from_directory(WALMART_WEBAPP_DIR, 'app.js')


@app.route('/api/walmart/orders', methods=['GET'])
def get_walmart_orders():
    """Get all Walmart orders."""
    try:
        limit = request.args.get('limit', 50, type=int)
        orders = walmart_db.get_all_orders(limit=limit)
        
        return jsonify({
            'success': True,
            'orders': orders,
            'count': len(orders)
        })
    except Exception as e:
        logger.error(f"Error getting Walmart orders: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/walmart/orders/<order_id>', methods=['GET'])
def get_walmart_order_details(order_id):
    """Get details for a specific Walmart order."""
    try:
        order = walmart_db.get_order_details(order_id)
        
        if not order:
            return jsonify({
                'success': False,
                'error': 'Order not found'
            }), 404
        
        return jsonify({
            'success': True,
            'order': order
        })
    except Exception as e:
        logger.error(f"Error getting order details: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/walmart/items/search', methods=['GET'])
def search_walmart_items():
    """Search for items in Walmart orders."""
    try:
        query = request.args.get('q', '')
        
        if not query:
            return jsonify({
                'success': False,
                'error': 'Search query is required'
            }), 400
        
        items = walmart_db.search_items(query)
        
        return jsonify({
            'success': True,
            'items': items,
            'count': len(items)
        })
    except Exception as e:
        logger.error(f"Error searching items: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/walmart/categories', methods=['GET'])
def get_walmart_categories():
    """Get spending breakdown by category."""
    try:
        categories = walmart_db.get_spending_by_category()
        
        return jsonify({
            'success': True,
            'categories': categories
        })
    except Exception as e:
        logger.error(f"Error getting categories: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/walmart/stats', methods=['GET'])
def get_walmart_stats():
    """Get overall statistics for Walmart orders."""
    try:
        orders = walmart_db.get_all_orders(limit=1000)
        
        if not orders:
            return jsonify({
                'success': True,
                'stats': {
                    'total_orders': 0,
                    'total_spent': 0,
                    'average_order': 0
                }
            })
        
        total_spent = sum(order['total_amount'] or 0 for order in orders)
        
        return jsonify({
            'success': True,
            'stats': {
                'total_orders': len(orders),
                'total_spent': round(total_spent, 2),
                'average_order': round(total_spent / len(orders), 2) if orders else 0
            }
        })
    except Exception as e:
        logger.error(f"Error getting stats: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================================
# OTHER FUTURE MINI APPS
# ============================================================================

# 
# Add routes for budget, reminders, or other mini apps here following the same pattern:
# @app.route('/budget')
# @app.route('/api/budget/...')
# etc.


# ============================================================================
# OPENCODE API
# ============================================================================


@app.route('/api/opencode/status', methods=['GET'])
def get_opencode_status():
    """Check if OpenCode agent is currently running."""
    try:
        from skills.opencode.runner import is_running
        return jsonify({
            'success': True,
            'running': is_running()
        })
    except Exception as e:
        logger.error(f"Error checking opencode status: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/opencode/restart', methods=['POST'])
def restart_services():
    """Restart chatty-bot (and optionally mini-apps) via pm2."""
    import subprocess
    import threading

    data = request.json or {}
    delay = data.get('delay', 5)
    services = data.get('services', ['chatty-bot'])

    # Validate service names to prevent command injection
    allowed = {'chatty-bot', 'chatty-mini-apps'}
    services = [s for s in services if s in allowed]

    if not services:
        return jsonify({'success': False, 'error': 'No valid services specified'}), 400

    def do_restart():
        import time
        time.sleep(delay)
        for svc in services:
            try:
                logger.info(f"Restarting {svc} via pm2...")
                subprocess.run(['pm2', 'restart', svc], capture_output=True, timeout=15)
                logger.info(f"{svc} restarted")
            except Exception as e:
                logger.error(f"Failed to restart {svc}: {e}")

    threading.Thread(target=do_restart, daemon=True).start()
    logger.info(f"Scheduled restart of {services} in {delay}s")

    return jsonify({
        'success': True,
        'message': f'Restart scheduled for {", ".join(services)} in {delay}s'
    })


# ============================================================================
# SERVER STARTUP
# ============================================================================

def run_server(host='0.0.0.0', port=5001):
    """Run the unified mini apps server."""
    logger.info(f"Starting Unified Mini Apps Server on {host}:{port}")
    logger.info("Available apps:")
    logger.info("  - Notes: /notes")
    app.run(host=host, port=port, debug=False)


if __name__ == '__main__':
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    run_server()
