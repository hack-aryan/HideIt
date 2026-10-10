"""Local REST API (Flask). Every route is POST/GET JSON and requires the session token."""
from __future__ import annotations

import hmac
import threading

from flask import Flask, jsonify, request

from .service import HideItService

API_VERSION = 1


def create_app(token: str, service: HideItService | None = None) -> Flask:
    app = Flask(__name__)
    svc = service or HideItService()

    @app.before_request
    def _auth():
        sent = request.headers.get("X-HideIt-Token", "")
        if not hmac.compare_digest(sent, token):
            return jsonify(error="Unauthorized"), 401

    @app.errorhandler(ValueError)
    def _value_error(exc):
        return jsonify(error=str(exc)), 400

    @app.errorhandler(Exception)
    def _unexpected(exc):  # never leak a traceback to the client
        app.logger.exception("Unhandled error")
        return jsonify(error=f"Internal error: {exc}"), 500

    def body() -> dict:
        return request.get_json(silent=True) or {}

    @app.get("/api/health")
    def health():
        return jsonify(ok=True, version=API_VERSION)

    @app.post("/api/carrier/load")
    def load():
        b = body()
        return jsonify(svc.load_carrier(b.get("path", ""), b.get("kind", "")))

    @app.post("/api/carrier/clear")
    def clear():
        return jsonify(ok=svc.clear_carrier(body().get("id", "")))

    @app.post("/api/encode")
    def encode():
        b = body()
        return jsonify(svc.encode(
            b.get("id", ""), b.get("output_path", ""), bool(b.get("is_file")), b.get("text", ""),
            b.get("secret_path", ""), bool(b.get("aes")), b.get("passphrase", ""), int(b.get("depth", 1))))

    @app.post("/api/decode")
    def decode():
        b = body()
        return jsonify(svc.decode(b.get("id", ""), b.get("passphrase", "")))

    @app.post("/api/decode/save")
    def save():
        b = body()
        return jsonify(svc.save_result(b.get("result_id", ""), b.get("output_path", "")))

    @app.post("/api/inspect")
    def inspect():
        b = body()
        return jsonify(svc.inspect(b.get("id", ""), b.get("mode", "rgb")))

    return app


def start_in_thread(token: str, host: str = "127.0.0.1", port: int = 0):
    """Start the API in a daemon thread. Returns (server, port)."""
    from werkzeug.serving import make_server
    srv = make_server(host, port, create_app(token), threaded=True)
    threading.Thread(target=srv.serve_forever, daemon=True, name="hideit-backend").start()
    return srv, srv.server_port
