import json
import os

import httpx

from .config import MODEL_ID, Model


class ModelError(RuntimeError):
    pass


class ClaudeClient:
    """Messages API tool loop client. It never reads an API key or .env file."""

    def __init__(self, settings: Model, transport=None, endpoint=None):
        self.settings = settings
        self.endpoint = endpoint or os.getenv("MODEL_GATEWAY_URL", "http://gateway:8765")
        self.transport = transport
        self.calls = 0
        self.estimated_usd = 0.0
        self.usage: list[dict] = []

    def message(self, system: str, messages: list, tools: list, searches: int = 0) -> dict:
        body = {
            "model": MODEL_ID,
            "max_tokens": self.settings.max_output_tokens,
            "thinking": {"type": "adaptive", "display": "omitted"},
            "output_config": {"effort": self.settings.effort},
            "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            "messages": messages,
            "tools": list(tools),
        }
        if searches > 0:
            body["tools"] += [
                {"type": "web_search_20250305", "name": "web_search", "max_uses": min(searches, 2)},
                {
                    "type": "web_fetch_20250910",
                    "name": "web_fetch",
                    "max_uses": 2,
                    "max_content_tokens": 6000,
                    "citations": {"enabled": True},
                },
            ]
        serialized = json.dumps(body, ensure_ascii=False)
        if len(serialized) > self.settings.max_request_chars:
            raise ModelError("Context limit reached; no instructions were silently discarded")
        if self.calls >= self.settings.max_calls_per_run:
            raise ModelError("Run model-call limit reached")
        # Conservative local allowance, not a provider-enforced billing guarantee.
        reservation = (len(serialized.encode()) * 0.625 + body["max_tokens"] * 2.5) / 1e6
        reservation += min(searches, 2) * 0.01
        if self.estimated_usd + reservation > self.settings.estimated_budget_usd:
            raise ModelError("Local estimated cost budget reached")
        self.calls += 1
        status = None
        provider_detail = ""
        try:
            with httpx.Client(timeout=190, transport=self.transport, trust_env=False) as client:
                response = client.post(self.endpoint + "/v1/messages", json=body)
                status = response.status_code
                if response.is_error:
                    try:
                        detail = response.json().get("detail", "")
                        if isinstance(detail, str):
                            provider_detail = "".join(c for c in detail if c.isprintable())[:800]
                    except (ValueError, AttributeError):
                        pass
                response.raise_for_status()
                data = response.json()
            if data.get("model") != MODEL_ID or not isinstance(data.get("content"), list):
                raise ValueError
        except (httpx.HTTPError, ValueError):
            self.estimated_usd += reservation
            detail = f" (HTTP {status})" if status is not None else ""
            hint = provider_detail or "Check gateway status and provider access."
            raise ModelError(
                f"Model request failed{detail}. {hint} No automatic API retry was made."
            ) from None
        usage = data.get("usage", {})
        inputs = sum(
            usage.get(k, 0)
            for k in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
        )
        multiplier = 5 if inputs > 100000 else 1
        cost = (
            (
                usage.get("input_tokens", 0) * 0.1
                + usage.get("cache_read_input_tokens", 0) * 0.01
                + usage.get("cache_creation_input_tokens", 0) * 0.125
                + usage.get("output_tokens", 0) * 0.5
            )
            * multiplier
            / 1e6
        )
        cost += usage.get("server_tool_use", {}).get("web_search_requests", 0) * 0.01
        self.estimated_usd += cost
        self.usage.append({"model": MODEL_ID, "usage": usage, "estimated_usd": round(cost, 6)})
        if data.get("stop_reason") in {"max_tokens", "refusal"}:
            raise ModelError("Model output was incomplete or refused; no partial actions executed")
        return data
