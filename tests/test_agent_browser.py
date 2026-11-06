import json

import httpx
import pytest
from conftest import reference

from application_filler.agent import Answer, Complete, reserve_submission
from application_filler.browser import BrowserError, NetworkGuard, public_url
from application_filler.demo import demo_settings
from application_filler.gateway import Gateway
from application_filler.llm import ClaudeClient


def answer(ref, **kwargs):
    return Answer(ref=ref, category="general", basis="inference", reason="Test", **kwargs)


def test_listing_redirect_multistep_attachments_confirmation(application):
    with application() as agent:
        report = agent.run()
        assert report["status"] == "submitted_confirmed", report
        assert agent.browser.page.evaluate("window.submissions") == 1
        assert len(agent.generated) == 2
        assert agent.generated[1].read_bytes().startswith(b"%PDF-")
        assert "alex@example.com" not in json.dumps(report)
        assert report["model_calls"] >= 8
        assert not reserve_submission(agent.artifacts / "submission-ledger", agent.url)


def test_inline_cover_letter_no_longer_blocks_before_first_model_call(application):
    with application() as a:
        letter = "Dear fictional team,\n\n" + "Example style sentence. " * 40
        a.settings.documents.examples = [letter]
        prompt = a.prompt()
        assert prompt.count("Dear fictional team,") == 1
        assert "UNTRUSTED STYLE EXAMPLES" in prompt
        report = a.run()
        assert report["status"] == "submitted_confirmed", report
        assert report["model_calls"] > 0


def test_missing_example_reports_configuration_problem_before_model_call(application):
    with application() as a:
        a.settings.documents.examples = ["missing-letter.md"]
        report = a.run()
        assert report["status"] == "blocked"
        assert report["model_calls"] == 0
        assert "documents.examples[0]" in report["reason"]
        assert "missing-letter.md" not in report["reason"]


@pytest.mark.parametrize("thinking_starts_at", [1, 3])
@pytest.mark.parametrize("exhaust_search_budget", [False, True])
def test_full_messages_client_gateway_and_browser_loop(
    application, thinking_starts_at, exhaust_search_budget
):
    with application() as a:
        scripted = a.client
        signed_prefixes = {}
        if exhaust_search_budget:
            a.settings.model.web_searches_per_application = 3

        def upstream(req):
            body = json.loads(req.content)
            assert req.headers["x-api-key"] == "FAKE-INTEGRATION-KEY"
            # Enforce Haiku 5.5's prefix binding, not just unchanged signature text.
            # Starting at turn 3 reproduces the timing in the user's failed demo.
            for index, message in enumerate(body["messages"]):
                if message["role"] != "assistant":
                    continue
                for block in message["content"]:
                    if block["type"] != "thinking":
                        continue
                    prefix = {
                        "system": body["system"],
                        "tools": body["tools"],
                        "messages": body["messages"][:index],
                    }
                    if prefix != signed_prefixes[block["signature"]]:
                        return httpx.Response(
                            400,
                            json={
                                "error": {
                                    "type": "invalid_request_error",
                                    "message": "Invalid signature in thinking block: "
                                    "the preceding conversation was modified.",
                                }
                            },
                        )
            response = scripted.message(body["system"], body["messages"], body["tools"])
            if scripted.calls >= thinking_starts_at:
                signature = f"opaque-test-signature-{scripted.calls}"
                signed_prefixes[signature] = {
                    "system": body["system"],
                    "tools": body["tools"],
                    "messages": body["messages"],
                }
                response["content"].insert(
                    0, {"type": "thinking", "thinking": "", "signature": signature}
                )
            if exhaust_search_budget and scripted.calls <= 3:
                assert any(t.get("name") == "web_search" for t in body["tools"])
                response["usage"] = {"server_tool_use": {"web_search_requests": 1}}
            elif exhaust_search_budget:
                assert not any(t.get("name") == "web_search" for t in body["tools"])
            return httpx.Response(200, json=response)

        gateway = Gateway("FAKE-INTEGRATION-KEY", transport=httpx.MockTransport(upstream))

        def local(req):
            assert "x-api-key" not in req.headers
            status, body = gateway.forward(json.loads(req.content))
            return httpx.Response(status, json=body)

        a.client = ClaudeClient(a.settings.model, transport=httpx.MockTransport(local))
        report = a.run()
        assert report["status"] == "submitted_confirmed", report
        assert a.client.calls == scripted.calls
        assert all(
            block["signature"] in signed_prefixes
            for m in a.messages
            if m["role"] == "assistant"
            for block in m["content"]
            if block["type"] == "thinking"
        )


def test_model_can_recover_from_invalid_arguments_without_leaking_values(application):
    with application() as a:
        scripted = a.client.message
        rejected = False

        def message(system, messages, tools, searches):
            nonlocal rejected
            response = scripted(system, messages, tools, searches)
            tool = next(b for b in response["content"] if b["type"] == "tool_use")
            if tool["name"] == "answer_fields" and not rejected:
                rejected = True
                tool["input"]["answers"][0]["basis"] = "PRIVATE-INVALID-VALUE"
            elif rejected and a.client.calls == 3:
                result = messages[-1]["content"][0]
                assert result["is_error"] is True
                data = json.loads(result["content"])
                assert data["issues"] == [{"field": "answers.0.basis", "problem": "literal_error"}]
                assert "PRIVATE-INVALID-VALUE" not in result["content"]
            return response

        a.client.message = message
        report = a.run()
        assert report["status"] == "submitted_confirmed", report
        assert report["tool_errors"][0]["issues"][0]["field"] == "answers.0.basis"
        assert "PRIVATE-INVALID-VALUE" not in json.dumps(report)


@pytest.mark.parametrize("source", ["full_name", "candidate.full_name"])
def test_candidate_source_paths_are_unambiguous(application, source):
    with application({"/": "<label>Name<input></label>"}) as a:
        a.answer(
            Answer(
                ref=reference(a, "Name"),
                source=source,
                basis="profile",
                category="general",
                reason="Copy fact",
            )
        )
        assert a.browser.page.locator("input").input_value() == "Alex Example"


def test_iframe_srcdoc_and_apply_popup(application):
    pages = {
        "/": "<a target='_blank' href='/form'>Apply</a>",
        "/form": '<iframe srcdoc="<label>City<input name=city></label>"></iframe>',
    }
    with application(pages) as a:
        a.native.execute("left_click", {"target": {"type": "ref", "ref": reference(a, "Apply")}})
        a.answer(answer(reference(a, "City"), value="Rome"))
        assert a.browser.page.url.endswith("/form")
        assert a.browser.page.frames[1].locator("input").input_value() == "Rome"


def test_failed_optional_answer_blocks_premature_completion(application):
    with application({"/": "<label>Name<input value='Existing'></label>"}) as a:
        result = a.execute(
            "answer_fields",
            {"answers": [answer(reference(a, "Name"), value="Changed").model_dump()]},
        )
        assert "error" in result["results"][0]
        assert a.unresolved
        with pytest.raises(BrowserError):
            a.complete(Complete(status="ready_for_review", reason="done"))


def test_omitted_sensitive_policy_still_requires_approval(application):
    settings = demo_settings()
    settings.answers.topics = {"salary": "infer"}
    with application({"/": "<label>Gender<input></label>"}, settings) as a:
        with pytest.raises(BrowserError, match="requires request_input"):
            a.answer(answer(reference(a, "Gender"), value="Prefer not to say"))


def test_manual_submission_cannot_be_clicked_via_generic_tool(application):
    config = demo_settings()
    config.submission = "manual"
    with application({"/": "<form><button>Send application</button></form>"}, config) as a:
        ref = reference(a, "Send application")
        with pytest.raises(BrowserError, match="submit_application"):
            a.native.execute("left_click", {"target": {"type": "ref", "ref": ref}})
        with pytest.raises(BrowserError, match="Manual submission"):
            a.execute("submit_application", {"ref": ref})
        assert not a.attempted


def test_unknown_submission_never_retried_or_falsely_confirmed(application):
    page = "<button onclick='window.n=(window.n||0)+1'>Send application</button>"
    with application({"/": page}) as a:
        a.execute("submit_application", {"ref": reference(a, "Send application")})
        with pytest.raises(BrowserError, match="already attempted"):
            a.execute("submit_application", {"ref": reference(a, "Send application")})
        with pytest.raises(BrowserError, match="acceptance statement"):
            a.complete(Complete(status="submitted", reason="done", confirmation_text="Thank you"))
        a.complete(Complete(status="blocked", reason="No confirmation"))
        assert a.report["status"] == "submission_unverified"
        assert a.browser.page.evaluate("window.n") == 1


def test_sensitive_ask_survives_incorrect_model_category_and_approval_is_bound(application):
    page = "<label>Gender<input name='gender'></label><label>Email<input name='email'></label>"
    with application({"/": page}, interactive=True, ask=lambda _: "Prefer not to say") as a:
        ref = reference(a, "Gender")
        with pytest.raises(BrowserError, match="requires request_input"):
            a.answer(answer(ref, value="Prefer not to say"))
        approval = a.execute("request_input", {"ref": ref, "question": "Gender response?"})
        other = reference(a, "Email")
        with pytest.raises(BrowserError, match="approval token"):
            a.answer(
                Answer(
                    ref=other,
                    value=approval["answer"],
                    basis="user",
                    category="general",
                    reason="Test",
                    approval_id=approval["approval_id"],
                )
            )
        ref = reference(a, "Gender")
        a.answer(
            Answer(
                ref=ref,
                value=approval["answer"],
                basis="user",
                category="personal_disclosure",
                reason="Approved",
                approval_id=approval["approval_id"],
            )
        )
        assert not a.unresolved
        assert a.browser.page.locator("[name=gender]").input_value() == "Prefer not to say"


def test_unattended_question_flags_application(application):
    with application({"/": "<label>Question<input></label>"}) as a:
        a.execute("request_input", {"question": "Missing candidate information"})
        assert a.done and a.report["reason"] == "user_input_required"


def test_select_semantics_and_profile_text_cannot_be_rewritten(application):
    page = """<label>Relocation<select><option value=''>Choose</option>
    <option value='y'>Yes, happy to relocate</option></select></label>
    <label>Name<input></label>"""
    with application({"/": page}) as a:
        a.answer(
            Answer(
                ref=reference(a, "Relocation"),
                value="y",
                source="relocation",
                basis="profile",
                category="general",
                reason="Equivalent wording",
            )
        )
        assert a.browser.page.locator("select").input_value() == "y"
        with pytest.raises(BrowserError, match="Copy profile text exactly"):
            a.answer(
                Answer(
                    ref=reference(a, "Name"),
                    value="Invented",
                    source="full_name",
                    basis="profile",
                    category="general",
                    reason="Test",
                )
            )


def test_salary_requires_actual_research_and_pay_units(application):
    with application({"/": "<label>Expected salary<input></label>"}) as a:
        ref = reference(a, "Expected salary")
        with pytest.raises(BrowserError, match="Research first"):
            a.answer(answer(ref, value="60000", sources=["https://fake.example/salary"]))
        a.collect_sources(
            [
                {
                    "type": "web_search_tool_result",
                    "content": [
                        {
                            "type": "web_search_result",
                            "url": "https://example.com/pay",
                            "title": "Pay",
                        }
                    ],
                }
            ]
        )
        with pytest.raises(BrowserError, match="Salary inference needs"):
            a.answer(answer(ref, value="60000", sources=["https://example.com/pay"]))
        a.answer(
            answer(
                ref,
                value="60000",
                sources=["https://example.com/pay"],
                salary_evidence={
                    "amount": 60000.0,
                    "currency": "EUR",
                    "period": "annual",
                    "basis": "gross_base",
                },
            )
        )
        assert a.report["actions"][-1]["salary"]["currency"] == "EUR"


def test_stale_refs_and_hidden_required_file_block_actions(application):
    page = "<input type='file' required hidden><label>Name<input></label><button>Send</button>"
    with application({"/": page}) as a:
        old = reference(a, "Name")
        a.browser.page.locator("input:not([type=file])").evaluate(
            "el=>el.replaceWith(el.cloneNode(true))"
        )
        a.browser.inspect()
        with pytest.raises(BrowserError, match="Stale reference"):
            a.answer(answer(old, value="Alex"))
        with pytest.raises(BrowserError, match="invalid fields"):
            a.execute("submit_application", {"ref": reference(a, "Send")})
        assert not a.attempted


def test_custom_dropdown_and_shadow_dom(application):
    page = """<button role='combobox'
    onclick="document.querySelector('[role=option]').hidden=false">
    Country</button><div role='option' hidden onclick="document.querySelector('output').textContent=
    'Italy'">Italy</div><output></output><div id='host'></div><script>
    document.getElementById('host').attachShadow({mode:'open'}).innerHTML=
    '<label>Portfolio<input></label>';</script>"""
    with application({"/": page}) as a:
        a.native.execute("left_click", {"target": {"type": "ref", "ref": reference(a, "Country")}})
        a.answer(answer(reference(a, "Italy"), value=True))
        a.answer(answer(reference(a, "Portfolio"), value="https://example.com"))
        assert a.browser.page.locator("output").inner_text() == "Italy"
        assert a.browser.page.locator("#host input").input_value() == "https://example.com"


def test_approved_false_checkbox_and_prior_values(application):
    config = demo_settings()
    config.answers.topics["consent"] = "ask"
    page = (
        "<label>Consent<input type='checkbox' checked></label>"
        "<label>Name<input value='Old'></label>"
    )
    with application({"/": page}, config, True, lambda _: "y") as a:
        ref = reference(a, "Consent")
        approval = a.execute(
            "request_input", {"ref": ref, "question": "Decline?", "proposed_value": False}
        )
        a.answer(
            Answer(
                ref=ref,
                value=False,
                category="consent",
                basis="user",
                reason="Decline",
                approval_id=approval["approval_id"],
            )
        )
        assert not a.browser.page.locator("[type=checkbox]").is_checked()
        with pytest.raises(BrowserError, match="Existing answer"):
            a.answer(answer(reference(a, "Name"), value="New"))


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com",
        "https://127.0.0.1",
        "https://[::1]",
        "https://user:password@example.com",
        "file:///tmp/key",
    ],
)
def test_nonpublic_destinations_rejected(url):
    with pytest.raises(BrowserError):
        public_url(url)


def test_cross_host_policy_and_private_gateway(monkeypatch):
    monkeypatch.setattr(
        "application_filler.browser.socket.getaddrinfo",
        lambda *a, **kw: [(2, 1, 6, "", ("93.184.215.14", 443))],
    )
    settings = demo_settings()
    guard = NetworkGuard("https://employer.example/job", settings)
    assert guard.allowed("https://ats.example/apply")
    settings.navigation.handoffs = "ask"
    assert not guard.allowed("https://ats.example/apply")
    assert guard.blocked_host == "ats.example"
    with pytest.raises(BrowserError):
        guard.allowed("http://gateway:8765/v1/messages")
