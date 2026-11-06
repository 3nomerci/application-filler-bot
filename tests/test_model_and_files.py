import json
import threading

import httpx
import pytest
from pydantic import ValidationError
from pypdf import PdfReader

from application_filler.cli import initialize
from application_filler.config import (
    MODEL_ID,
    ConfigurationError,
    Documents,
    Model,
    Settings,
    load_cover_letter_examples,
    load_settings,
    private_file,
)
from application_filler.documents import remove_generated, render_letter
from application_filler.gateway import Gateway, serve
from application_filler.llm import ClaudeClient, ModelError


def request():
    return {
        "model": MODEL_ID,
        "max_tokens": 8192,
        "thinking": {"type": "adaptive", "display": "omitted"},
        "messages": [],
        "tools": [],
    }


def test_gateway_contains_key_and_sanitizes_errors():
    sentinel = "FAKE-TEST-KEY-never-a-real-secret"

    def provider(req):
        assert req.url == "https://api.anthropic.com/v1/messages"
        assert req.headers["x-api-key"] == sentinel
        return httpx.Response(401, json={"error": sentinel})

    gateway = Gateway(sentinel, transport=httpx.MockTransport(provider), max_requests=1)
    status, body = gateway.forward(request())
    assert status == 401 and sentinel not in json.dumps(body)
    assert gateway.forward(request())[0] == 429


def test_provider_error_reaches_report_without_credential_or_headers():
    secret = "FAKE-SECRET-ONLY-FOR-TEST"

    def provider(req):
        return httpx.Response(
            400,
            headers={"x-secret": secret},
            json={
                "error": {
                    "type": "invalid_request_error",
                    "message": f"Invalid signature. Echoed credential: {secret}; "
                    "sk-ant-fake-other-key",
                },
                "unrelated_private_body": secret,
            },
        )

    gateway = Gateway(secret, transport=httpx.MockTransport(provider))

    def relay(req):
        status, body = gateway.forward(json.loads(req.content))
        assert secret not in json.dumps(body) and "sk-ant" not in json.dumps(body)
        assert "unrelated_private_body" not in body
        return httpx.Response(status, json=body)

    client = ClaudeClient(Model(), transport=httpx.MockTransport(relay))
    with pytest.raises(ModelError, match=r"HTTP 400.*Invalid signature") as failure:
        client.message("system", [], [])
    assert secret not in str(failure.value)


@pytest.mark.parametrize(
    "change",
    [
        {"model": "rolling-model"},
        {"max_tokens": 20000},
        {"tools": [None]},
        {"tools": [{"type": "bash_20250124"}]},
        {"stream": True},
    ],
)
def test_gateway_rejects_unapproved_protocol(change):
    gateway = Gateway("FAKE-TEST-KEY")
    assert gateway.forward(request() | change)[0] == 400
    assert gateway.remaining == 200


def test_gateway_rejects_browser_origin_and_plaintext():
    server = serve(Gateway("FAKE-TEST-KEY"), ("127.0.0.1", 0))
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        with httpx.Client(trust_env=False) as client:
            url = f"http://127.0.0.1:{server.server_port}/v1/messages"
            assert (
                client.post(
                    url, json=request(), headers={"Origin": "https://evil.example"}
                ).status_code
                == 403
            )
            assert (
                client.post(
                    url, content=json.dumps(request()), headers={"Content-Type": "text/plain"}
                ).status_code
                == 403
            )
    finally:
        server.shutdown()
        server.server_close()
        worker.join()


def test_client_fixed_snapshot_thinking_signatures_tools_and_no_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "FAKE-SHOULD-NOT-BE-READ")
    blocks = [
        {"type": "thinking", "thinking": "", "signature": "opaque-signature"},
        {"type": "tool_use", "id": "one", "name": "read_page", "input": {}},
    ]
    calls = []

    def gateway(req):
        body = json.loads(req.content)
        calls.append(body)
        assert "x-api-key" not in req.headers
        assert b"FAKE-SHOULD-NOT-BE-READ" not in req.content
        assert body["model"] == MODEL_ID
        assert body["thinking"] == {"type": "adaptive", "display": "omitted"}
        assert body["output_config"] == {"effort": "medium"}
        assert "temperature" not in body
        return httpx.Response(
            200,
            json={
                "model": MODEL_ID,
                "content": blocks,
                "stop_reason": "tool_use",
                "usage": {
                    "input_tokens": 2000,
                    "output_tokens": 100,
                    "server_tool_use": {"web_search_requests": 1},
                },
            },
        )

    client = ClaudeClient(Model(), transport=httpx.MockTransport(gateway))
    result = client.message("instructions", [{"role": "user", "content": "Start"}], [], 2)
    client.message("instructions", [{"role": "assistant", "content": result["content"]}], [], 1)
    assert calls[1]["messages"][0]["content"] == blocks
    assert calls[0]["tools"][0]["max_uses"] == 2
    assert client.estimated_usd == pytest.approx(0.0205)


@pytest.mark.parametrize("stop", ["max_tokens", "refusal"])
def test_partial_model_actions_never_executed(stop):
    transport = httpx.MockTransport(
        lambda _: httpx.Response(
            200,
            json={
                "model": MODEL_ID,
                "stop_reason": stop,
                "content": [{"type": "tool_use"}],
                "usage": {},
            },
        )
    )
    with pytest.raises(ModelError, match="no partial actions"):
        ClaudeClient(Model(), transport=transport).message("system", [], [])


def test_budget_prevents_request_and_http_failure_has_no_retry():
    calls = []

    def failure(req):
        calls.append(req)
        return httpx.Response(503)

    transport = httpx.MockTransport(failure)
    client = ClaudeClient(Model(estimated_budget_usd=0.001), transport=transport)
    with pytest.raises(ModelError, match="cost budget"):
        client.message("system", [], [])
    assert not calls
    client = ClaudeClient(Model(), transport=transport)
    with pytest.raises(ModelError, match="No automatic API retry"):
        client.message("system", [], [])
    assert len(calls) == 1 and client.estimated_usd > 0


def test_yaml_comments_duplicates_and_unknown_options(tmp_path):
    path = tmp_path / "instructions.yaml"
    path.write_text("version: 2\n# This is not a model instruction\ninstructions: Use facts\n")
    assert load_settings(path).instructions == "Use facts"
    path.write_text("version: 2\nversion: 2\n")
    with pytest.raises(ValueError, match="Invalid YAML"):
        load_settings(path)
    with pytest.raises(ValidationError):
        Settings.model_validate({"answers": {"topics": {"sallary": "infer"}}})


def test_private_paths_pdf_unicode_and_cleanup(tmp_path):
    private = tmp_path / "private"
    private.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("must remain")
    with pytest.raises(ValueError, match="inside the private"):
        private_file(private, "../outside.txt")
    md, pdf = render_letter("# Nicolò\n\nEsperienza, perché €50.000 — <b>literal</b>", private)
    text = "".join(page.extract_text() for page in PdfReader(pdf).pages)
    assert "Nicolò" in text and "€50.000" in text and "<b>literal</b>" in text
    with pytest.raises(ValueError, match="escaped"):
        remove_generated([outside], private)
    remove_generated([md, pdf], private)
    assert outside.exists() and not pdf.exists()


def test_initialization_copies_neutral_template_and_preserves_personal_files(tmp_path, monkeypatch):
    from pathlib import Path

    template = Path("examples/instructions.yaml").read_text(encoding="utf-8")
    (tmp_path / "examples").mkdir()
    (tmp_path / "examples/instructions.yaml").write_text(template, encoding="utf-8")
    target = tmp_path / "private/instructions.yaml"
    monkeypatch.chdir(tmp_path)
    initialize()
    config = load_settings(target)
    assert config.candidate["citizenships"] == []
    assert config.candidate["full_name"] == ""
    assert config.submission == "manual"
    target.write_text("# Personal instructions\nversion: 2\ninstructions: Ask about salary\n")
    links = tmp_path / "private/links.txt"
    links.write_text("https://example.com/job\n")
    before = target.read_bytes(), links.read_bytes()
    initialize()
    assert (target.read_bytes(), links.read_bytes()) == before


def test_examples_accept_yaml_letters_and_existing_files(tmp_path):
    (tmp_path / "style.md").write_text("Example from file", encoding="utf-8")
    path = tmp_path / "instructions.yaml"
    path.write_text(
        "version: 2\ndocuments:\n  examples:\n    - style.md\n    - |\n"
        "      Dear Team,\n\n      A fictional example letter.\n",
        encoding="utf-8",
    )
    settings = load_settings(path)
    result = load_cover_letter_examples(tmp_path, settings.documents)
    assert result == ["Example from file", "Dear Team,\n\nA fictional example letter.\n"]


@pytest.mark.parametrize(
    "entry", ["missing.md", "../outside.md", "X" * 5000, "\n" + "X" * 20001, "\n  \n"]
)
def test_bad_example_errors_do_not_echo_private_contents(tmp_path, entry):
    with pytest.raises(ConfigurationError) as error:
        load_cover_letter_examples(tmp_path, Documents(examples=[entry]))
    assert "documents.examples[0]" in str(error.value)
    assert "YAML '- |'" in str(error.value)
    assert entry not in str(error.value)
