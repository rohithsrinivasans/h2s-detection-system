"""
Root WSGI entrypoint forwarder to backend/app.py.
Ensures 'gunicorn app:app' and 'gunicorn --chdir backend app:app' work seamlessly on Render and locally.
"""

import os
import sys
import importlib.util

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

backend_app_path = os.path.join(BACKEND_DIR, "app.py")
spec = importlib.util.spec_from_file_location("backend_app", backend_app_path)
backend_app_module = importlib.util.module_from_spec(spec)
sys.modules["backend_app"] = backend_app_module
spec.loader.exec_module(backend_app_module)

app = backend_app_module.app
create_app = backend_app_module.create_app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("=" * 65)
    print("  SENTRYH2S INDUSTRIAL SAFETY OPERATIONS CONSOLE")
    print(f"  Web Server Active at : http://localhost:{port}")
    print("  Default Credentials  : admin / admin123")
    print("=" * 65)
    app.run(debug=True, host="0.0.0.0", port=port)
