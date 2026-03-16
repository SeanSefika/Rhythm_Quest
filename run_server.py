"""
Entry point for PyInstaller - starts Flask and auto-initializes the database.
"""
import sys
import os
import threading
import webbrowser

# Determine base directory (pyinstaller sets sys.frozen)
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Change CWD so Flask finds templates, static, and db files
os.chdir(BASE_DIR)

# Add BASE_DIR to path so forms.py is found
sys.path.insert(0, BASE_DIR)

from app import app

def init_database():
    """Initialize the database tables if they don't exist."""
    with app.test_client() as client:
        client.get('/init_db')

if __name__ == '__main__':
    # Initialize db first
    init_database()

    # Start Flask server on port 5000
    app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)
