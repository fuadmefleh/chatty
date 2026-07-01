#!/bin/bash
# Wrapper script to import Walmart orders with venv activated

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
VENV_PYTHON="$PROJECT_ROOT/venv/bin/python3"

# Check if venv exists
if [ ! -f "$VENV_PYTHON" ]; then
    echo "Error: Virtual environment not found at $VENV_PYTHON"
    exit 1
fi

# Run the import script with venv python (don't change directory)
exec "$VENV_PYTHON" "$SCRIPT_DIR/import_orders.py" "$@"
