"""Only this container reads the API key. No browser, tools, or public listening port."""

import json
import os
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import httpx

from .config import MODEL_ID


def validate_request(body: dict) -> None:
    allowed = {"model", "max_tokens", "system", "messages", "tools", "thinking", "output_config"}
    if not isinstance(body, dict) or set(body) - allowed or body.get("model") != MODEL_ID:
        raise ValueError("Unsupported request")
    cap = body.get("max_tokens")
    if type(cap) is not int or not 1 <= cap <= 12000:
        raise ValueError("Output limit exceeded")
    if body.get("thinking") != {"type": "adaptive", "display": "omitted"}:
        raise ValueError("Unsupported thinking configuration")
    if not isinstance(body.get("tools", []), list):
        raise ValueError("Invalid tools")
    for tool in body.get("tools", []):
        if not isinstance(tool, dict):
            raise ValueError("Invalid tool")
        if tool.get("type") == "browser_toolset_20260801":
            from .native_browser import BROWSER_TOOL

            if tool != BROWSER_TOOL:
                raise ValueError("Unsupported browser configuration")
            continue
        if "type" in tool and tool["type"] not in {"web_search_20250305", "web_fetch_20250910"}:
            raise ValueError("Server tool is not allowed")
        if "type" in tool and not 1 <= tool.get("max_uses", 0) <= 2:
            raise ValueError("Search/fetch limit exceeded")


class Gateway:
    def __init__(self, key: str, transport=None, max_requests: int = 200):
        self._key = key
        self.transport = transport
        self.remaining = max_requests
        self.lock = threading.Lock()

    def forward(self, body: dict) -> tuple[int, dict]:
        try:
            validate_request(body)
        except (ValueError, TypeError):
            return 400, {"error": "request_rejected"}
        with self.lock:
            if self.remaining <= 0:
                return 429, {"error": "gateway_request_limit"}
            self.remaining -= 1
        try:
            with httpx.Client(timeout=180, transport=self.transport, trust_env=False) as client:
                response = client.post(
                    "https://api.anthropic.com/v1/messages",
                    json=body,
                    headers={"x-api-key": self._key, "anthropic-version": "2023-06-01"},
                )
            if response.status_code != 200:
                # Return only the API's diagnostic message, never headers or response dumps.
                # Redact credentials even if an upstream diagnostic unexpectedly echoes them.
                diagnostic = {"error": "provider_request_failed"}
                try:
                    error = response.json().get("error", {})
                    message = error.get("message") if isinstance(error, dict) else None
                    if isinstance(message, str):
                        message = message.replace(self._key, "[redacted]") if self._key else message
                        message = re.sub(r"sk-[A-Za-z0-9_-]+", "[redacted]", message)
                        diagnostic["detail"] = "".join(c for c in message if c.isprintable())[:800]
                except (ValueError, AttributeError):
                    pass
                return response.status_code, diagnostic
            data = response.json()
            if self._key and self._key in json.dumps(data):
                return 502, {"error": "invalid_provider_response"}
            return 200, data
        except (httpx.HTTPError, ValueError):
            return 502, {"error": "provider_connection_failed"}


def serve(gateway: Gateway, address=("0.0.0.0", 8765)):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def respond(self, status, data):
            payload = json.dumps(data).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self):
            self.respond(200 if self.path == "/health" else 404, {"ready": self.path == "/health"})

        def do_POST(self):
            if self.path != "/v1/messages":
                self.respond(404, {"error": "not_found"})
                return
            # Browser form/fetch requests must not turn this into a paid API relay.
            # The Python agent uses application/json and never supplies Origin.
            if self.headers.get("Origin") or self.headers.get_content_type() != "application/json":
                self.respond(403, {"error": "browser_requests_rejected"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 20000000:
                    raise ValueError
                self.connection.settimeout(15)
                body = json.loads(self.rfile.read(length))
            except (ValueError, OSError):
                self.respond(400, {"error": "invalid_request"})
                return
            self.respond(*gateway.forward(body))

    return ThreadingHTTPServer(address, Handler)


def main():
    # Not an environment variable containing the key: a container-only secret mount.
    path = Path("/run/secrets/anthropic_api_key")
    try:
        key = path.read_text(encoding="utf-8-sig").strip()
        if not key or len(key) > 500 or any(c.isspace() for c in key):
            raise ValueError
    except (OSError, ValueError):
        raise SystemExit("API secret is missing or invalid; see DOCUMENTATION.md.") from None
    server = serve(Gateway(key, max_requests=int(os.getenv("GATEWAY_MAX_REQUESTS", "200"))))
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
