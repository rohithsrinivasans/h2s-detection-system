"""
Local runner for SentryH2S Platform.
Launches the Flask application from the backend package with frontend assets connected.
"""

import os
import sys

# Add backend directory to sys.path
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("=" * 65)
    print("  SENTRYH2S INDUSTRIAL SAFETY OPERATIONS CONSOLE")
    print(f"  Web Server Active at : http://localhost:{port}")
    print("  Default Credentials  : admin / admin123")
    print("=" * 65)
    app.run(debug=True, host="0.0.0.0", port=port)
