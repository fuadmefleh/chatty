#!/bin/bash
# Start the Unified Mini Apps Server

echo "Starting Unified Mini Apps Server..."
echo "Server will run on http://localhost:5001"
echo ""
echo "Available Mini Apps:"
echo "  - Notes: http://localhost:5001/notes"
echo "  - Walmart: http://localhost:5001/walmart"
echo ""
echo "To access from Telegram:"
echo "1. Make sure your bot is running"
echo "2. Type /notes or /walmart in your chat"
echo "3. Click the mini app button"
echo ""
echo "Press Ctrl+C to stop"
echo ""

cd "$(dirname "$0")"
python3 mini_app_server.py
