import copy
import json

import pytest
from conftest import reference

from application_filler.agent import Complete
from application_filler.browser import BrowserError

PAGE = """<form onsubmit="event.preventDefault(); this.remove();
document.querySelector('output').textContent='Application accepted'">
<label>Name<input required></label><label>City<input required></label>
<button>Submit application</button></form><output></output>"""


def tool(name, args, index):
    return {"type": "tool_use", "id": f"tool-{index}", "name": name, "input": args}


def test_batch_can_finish_independent_work_then_resume_with_bound_answer(application):
    asked = []

    def ask(question):
        asked.append(question)
        return "Paris"

    with application({"/": PAGE}, interactive=True, ask=ask) as a:
        a.defer_input = True
        city, name, submit = (
            reference(a, label) for label in ("City", "Name", "Submit application")
        )

        def message(system, messages, tools, searches):
            a.client.calls += 1
            if a.client.calls == 1:
                content = [
                    tool("request_input", {"question": "Which city?", "ref": city}, 1),
                    tool(
                        "answer_fields",
                        {
                            "answers": [
                                {
                                    "ref": name,
                                    "source": "full_name",
                                    "category": "general",
                                    "basis": "profile",
                                    "reason": "Known fact",
                                }
                            ]
                        },
                        2,
                    ),
                    tool("complete", {"status": "blocked", "reason": "City needed"}, 3),
                ]
            else:
                reply = json.loads(messages[-1]["content"])["review_answers"][0]["reply"]
                content = [
                    tool(
                        "answer_fields",
                        {
                            "answers": [
                                {
                                    "ref": city,
                                    "value": reply["answer"],
                                    "approval_id": reply["approval_id"],
                                    "category": "general",
                                    "basis": "user",
                                    "reason": "User supplied city",
                                }
                            ]
                        },
                        4,
                    ),
                    tool("submit_application", {"ref": submit}, 5),
                    tool(
                        "complete",
                        {
                            "status": "submitted",
                            "reason": "Accepted",
                            "confirmation_text": "Application accepted",
                        },
                        6,
                    ),
                ]
            return {"content": content, "stop_reason": "tool_use"}

        a.client.message = message
        assert a.run()["status"] == "needs_input"
        assert a.browser.page.get_by_label("Name").input_value() == "Alex Example"
        assert not asked and len(a.report["pending_questions"]) == 1
        prefix = copy.deepcopy(a.messages)
        # The batch can run another application before coming back to this one.
        with application() as b:
            assert b.run()["status"] == "submitted_confirmed"
        assert a.review_pending()["status"] == "submitted_confirmed"
        assert a.report["model_calls"] == 2
        assert a.messages[: len(prefix)] == prefix
        assert a.messages[-1]["role"] == "user"  # All final tool uses have results.
        assert len(asked) == 1 and not a.pending_inputs


def test_pending_context_blocks_submission_even_when_form_is_valid(application):
    with application({"/": "<button>Submit application</button>"}) as a:
        request = {"question": "Are you available for the required assessment?"}
        for _ in range(2):
            assert a.execute("request_input", request)["deferred"]
        assert len(a.pending_inputs) == 1
        with pytest.raises(BrowserError, match="Pending user"):
            a.execute("submit_application", {"ref": reference(a, "Submit application")})
        assert not a.attempted
        assert (
            a.complete(Complete(status="blocked", reason="Permission needed"))["status"]
            == "needs_input"
        )


def test_unbound_fact_question_accepts_text_instead_of_yes_no(application):
    with application(interactive=True, ask=lambda _: "Madrid, hybrid") as a:
        result = a.execute("request_input", {"kind": "answer", "question": "Preferred location?"})
        assert result["answer"] == "Madrid, hybrid"
        assert "approval_id" not in result and not a.approvals


def test_stale_deferred_consent_is_not_approved(application):
    asked = []
    with application(
        {"/": "<label>Privacy<input type=checkbox></label>"},
        interactive=True,
        ask=lambda q: asked.append(q) or "yes",
    ) as a:
        a.defer_input = True
        a.execute(
            "request_input",
            {"question": "Accept?", "ref": reference(a, "Privacy"), "proposed_value": True},
        )
        a.browser.page.locator("input").evaluate("el=>el.replaceWith(el.cloneNode(true))")
        a.settings.model.max_calls_per_application = 1
        a.report["model_calls"] = 1  # Review cannot reset the per-application call cap.
        a.review_pending()
        assert not asked and not a.approvals and a.client.calls == 0
        assert "changed" in a.messages[-1]["content"]
        assert a.report["reason"] == "Application model-call budget reached"


def test_manual_handoff_needs_explicit_kind_and_cannot_approve_fields(application):
    with application(interactive=True, ask=lambda _: "yes") as a:
        with pytest.raises(BrowserError, match="Manual browser help"):
            a.execute("request_input", {"kind": "manual", "question": "Log in", "ref": "ref_1"})
        result = a.execute("request_input", {"kind": "manual", "question": "Log in"})
        assert result["continue"] is True
        assert not a.approvals


@pytest.mark.parametrize("changed", [False, True])
def test_cover_letter_review_is_deferred_and_bound_to_document(application, changed):
    prompts = []
    with application(interactive=True, ask=lambda q: prompts.append(q) or "yes") as a:
        a.settings.documents.cover_letter = "review"
        a.defer_input = True
        result = a.execute(
            "create_cover_letter", {"markdown": "# Fictional letter\nPython services."}
        )
        assert not result["approved_for_upload"] and not prompts
        assert len(a.pending_inputs) == 1
        if changed:
            a.generated[0].write_text("A different letter", encoding="utf-8")
        a.settings.model.max_calls_per_application = 1
        a.report["model_calls"] = 1
        a.review_pending()
        assert a.letter_approved is (not changed)
        assert len(prompts) == (0 if changed else 1)
