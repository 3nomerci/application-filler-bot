import pytest
from conftest import reference

from application_filler.agent import Complete
from application_filler.browser import BrowserError

LABEL = "I agree to the Privacy Policy for processing this application"
PAGE = f"""<form>
<label><input type=checkbox name="candidate[consent_given]" required>{LABEL}</label>
<label><input type=checkbox name="candidate[consent_future_jobs]">
Contact me about future jobs</label>
<button>Submit application</button></form>"""


def request(agent, ref, value=True):
    return agent.execute(
        "request_input",
        {
            "ref": ref,
            "proposed_value": value,
            "question": "Two consents: required privacy and optional future jobs. "
            "Also an unrelated job note.",
        },
    )


def fill(agent, ref, value=True):
    return agent.native.execute(
        "form_input",
        {
            "target": {"type": "ref", "ref": ref},
            "value": value,
        },
    )


@pytest.mark.parametrize(
    "method,reply",
    [
        ("click", "yes"),
        ("form_input", "y"),
        ("keyboard", " YES "),
        ("answer_fields", "yes"),
    ],
)
def test_approved_consent_works_through_every_answer_path(application, method, reply):
    prompts = []

    def ask(prompt):
        prompts.append(prompt)
        return reply

    with application({"/": PAGE}, interactive=True, ask=ask) as a:
        a.settings.answers.topics["consent"] = "ask"
        ref = reference(a, LABEL)
        with pytest.raises(BrowserError, match="approval"):
            fill(a, ref)
        approved = request(a, ref)
        assert approved["answer"] is True
        assert len(prompts) == 1
        assert f"Checkbox (required): {LABEL}" in prompts[0]
        assert "Proposed choice: Check this checkbox." in prompts[0]
        assert "future jobs" not in prompts[0] and "unrelated job note" not in prompts[0]
        assert "True" not in prompts[0]
        a.browser.inspect()  # Reading again must preserve approval for the same control.
        if method == "click":
            a.native.execute("left_click", {"target": {"type": "ref", "ref": ref}})
        elif method == "form_input":
            fill(a, ref)
        elif method == "keyboard":
            a.browser.target(ref).element.focus()
            a.native.execute("key", {"text": "Space"})
        else:
            a.execute(
                "answer_fields",
                {
                    "answers": [
                        {
                            "ref": ref,
                            "value": True,
                            "basis": "user",
                            "category": "consent",
                            "reason": "User approved",
                            "approval_id": approved["approval_id"],
                        }
                    ]
                },
            )
        assert a.browser.page.locator("input").nth(0).is_checked()
        assert not a.browser.page.locator("input").nth(1).is_checked()
        assert not a.approvals and not a.unresolved
        with pytest.raises(BrowserError, match="approval"):
            fill(a, reference(a, "Contact me about future jobs"))
        with pytest.raises(BrowserError, match="approval"):
            fill(a, ref, False)  # Approval cannot be replayed for a different choice.


def test_approval_is_not_consumed_when_checkbox_action_fails(application, monkeypatch):
    with application({"/": PAGE}, interactive=True, ask=lambda _: "yes") as a:
        a.settings.answers.topics["consent"] = "ask"
        ref = reference(a, LABEL)
        approved = request(a, ref)
        original = a.browser.fill

        def fail(*_):
            raise BrowserError("Transient checkbox failure")

        monkeypatch.setattr(a.browser, "fill", fail)
        with pytest.raises(BrowserError, match="Transient"):
            a.native.execute("left_click", {"target": {"type": "ref", "ref": ref}})
        assert approved["approval_id"] in a.approvals
        monkeypatch.setattr(a.browser, "fill", original)
        fill(a, ref)
        assert a.browser.page.locator("input").first.is_checked()
        assert not a.approvals


def test_declining_new_proposal_revokes_old_unused_approval(application):
    replies = iter(["yes", "no"])
    with application({"/": PAGE}, interactive=True, ask=lambda _: next(replies)) as a:
        a.settings.answers.topics["consent"] = "ask"
        ref = reference(a, LABEL)
        request(a, ref)
        assert request(a, ref)["answer"] is None
        assert not a.approvals
        with pytest.raises(BrowserError, match="approval"):
            fill(a, ref)
        assert not a.browser.page.locator("input").first.is_checked()


def test_identical_labels_and_names_do_not_share_consent(application):
    checkbox = "<label>I agree<input type=checkbox name=consent></label>"
    with application({"/": checkbox * 2}, interactive=True, ask=lambda _: "yes") as a:
        a.settings.answers.topics["consent"] = "ask"
        controls = a.browser.inspect()["controls"]
        first, second = (control["ref"] for control in controls)
        request(a, first)
        with pytest.raises(BrowserError, match="approval"):
            fill(a, second)
        fill(a, first)
        assert a.browser.page.locator("input").nth(0).is_checked()
        assert not a.browser.page.locator("input").nth(1).is_checked()


def test_uncheck_proposal_and_invalid_response_are_unambiguous(application):
    replies = iter(["yes, no", "yes"])
    prompts = []

    def ask(prompt):
        prompts.append(prompt)
        return next(replies)

    with application(
        {"/": PAGE.replace("required>", "required checked>")}, interactive=True, ask=ask
    ) as a:
        a.settings.answers.topics["consent"] = "ask"
        ref = reference(a, LABEL)
        assert request(a, ref, False)["answer"] is False
        assert len(prompts) == 2 and "Uncheck this checkbox" in prompts[0]
        fill(a, ref, False)
        assert not a.browser.page.locator("input").first.is_checked()


def test_checkbox_question_without_proposal_accepts_no_and_quit(application):
    replies = iter(["no", "/quit"])
    with application({"/": PAGE}, interactive=True, ask=lambda _: next(replies)) as a:
        a.settings.answers.topics["consent"] = "ask"
        ref = reference(a, LABEL)
        decision = a.execute("request_input", {"ref": ref, "question": "Privacy?"})
        assert decision["answer"] is False
        fill(a, ref, False)
        with pytest.raises(KeyboardInterrupt):
            request(a, ref)
        assert not a.approvals


def test_unbound_proposal_cannot_grant_consent(application):
    with application({"/": PAGE}, interactive=True, ask=lambda _: "yes") as a:
        with pytest.raises(BrowserError, match="exact field ref"):
            a.execute("request_input", {"question": "Accept both?", "proposed_value": True})
        assert not a.approvals


@pytest.mark.parametrize("required", [False, True])
@pytest.mark.parametrize("kind", ["checkbox", "select"])
@pytest.mark.parametrize("propose", [False, True])
def test_skipping_optional_consent_allows_submission_but_required_still_blocks(
    application, required, kind, propose
):
    requirement = "required" if required else ""
    control = (
        f"<input type=checkbox {requirement}>"
        if kind == "checkbox"
        else f"<select {requirement}><option value=''>Choose</option>"
        "<option value=yes>Accept</option><option value=no>Decline</option></select>"
    )
    html = f"""<form onsubmit="event.preventDefault(); this.remove();
      document.querySelector('output').textContent='Application received'">
      <label>Talent database consent{control}</label>
      <button>Submit application</button></form><output></output>"""
    with application({"/": html}, interactive=True, ask=lambda _: "") as a:
        a.settings.answers.topics["consent"] = "ask"
        ref = reference(a, "Talent database consent")
        value = True if kind == "checkbox" else "yes"
        # An earlier rejected fill must not leave an optional consent stuck unresolved.
        with pytest.raises(BrowserError, match="approval"):
            fill(a, ref, value)
        args = {"ref": ref, "question": "Consent?"}
        if propose:
            args["proposed_value"] = value
        assert a.execute("request_input", args)["answer"] is None
        button = reference(a, "Submit application")
        if required:
            with pytest.raises(BrowserError, match="Talent database consent"):
                a.execute("submit_application", {"ref": button})
            assert not a.attempted
            assert not (a.artifacts / "submission-ledger").exists()
        else:
            assert not a.unresolved
            a.execute("submit_application", {"ref": button})
            a.complete(
                Complete(
                    status="submitted", reason="Accepted", confirmation_text="Application received"
                )
            )
            assert a.report["status"] == "submitted_confirmed"


def test_auto_cannot_finish_ready_without_submitting(application):
    with application({"/": "<label>Name<input></label>"}) as a:
        fill(a, reference(a, "Name"), "Alex Example")
        with pytest.raises(BrowserError, match="Automatic submission"):
            a.complete(Complete(status="ready_for_review", reason="Done"))
        assert not a.done and not a.attempted
