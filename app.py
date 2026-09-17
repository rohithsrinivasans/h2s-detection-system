"""
Root entrypoint forwarder to backend/app.py.
Ensures both 'gunicorn app:app' and 'gunicorn --chdir backend app:app' work on Render.
"""

import os
import sys

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app import app, create_app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
