"""HTTP client for the HideIt backend (stdlib only)."""
from __future__ import annotations

import json
import urllib.error
import urllib.request


class BackendError(Exception):
    """Raised with a user-readable message when the backend rejects a request."""


class Client:
    def __init__(self, base_url: str, token: str):
        self.base = base_url.rstrip("/")
        self.token = token

    def _call(self, path: str, payload: dict | None = None, timeout: float = 900) -> dict:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(self.base + path, data=data, method="GET" if data is None else "POST",
                                     headers={"Content-Type": "application/json", "X-HideIt-Token": self.token})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            try:
                msg = json.loads(exc.read().decode("utf-8")).get("error", str(exc))
            except Exception:
                msg = str(exc)
            raise BackendError(msg) from None
        except (urllib.error.URLError, ConnectionError, TimeoutError) as exc:
            raise BackendError(f"Cannot reach the HideIt backend: {exc}") from None

    def health(self):
        return self._call("/api/health", timeout=5)

    def load_carrier(self, path, kind):
        return self._call("/api/carrier/load", {"path": path, "kind": kind})

    def clear_carrier(self, cid):
        return self._call("/api/carrier/clear", {"id": cid}, timeout=10)

    def encode(self, **kw):
        return self._call("/api/encode", kw)

    def decode(self, cid, passphrase=""):
        return self._call("/api/decode", {"id": cid, "passphrase": passphrase})

    def save_result(self, result_id, output_path):
        return self._call("/api/decode/save", {"result_id": result_id, "output_path": output_path})

    def inspect(self, cid, mode):
        return self._call("/api/inspect", {"id": cid, "mode": mode})
