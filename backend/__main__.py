"""Run the backend on its own:  python -m backend [--port 8765] [--token SECRET]"""
import argparse
import secrets

from .server import create_app

ap = argparse.ArgumentParser(description="HideIt backend API")
ap.add_argument("--host", default="127.0.0.1")
ap.add_argument("--port", type=int, default=8765)
ap.add_argument("--token", default=secrets.token_urlsafe(16))
a = ap.parse_args()
print(f"HideIt backend: http://{a.host}:{a.port}   token: {a.token}")
print(f"Frontend: python -m frontend --url http://{a.host}:{a.port} --token {a.token}")
create_app(a.token).run(host=a.host, port=a.port, threaded=True)
