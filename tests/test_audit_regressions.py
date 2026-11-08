import pytest
from conftest import reference
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Frame

from application_filler.agent import Answer
from application_filler.browser import BrowserError


def field(ref, value):
    return {"target": {"type": "ref", "ref": ref}, "value": value}


def test_input_next_advances_without_reserving_final_submission(application):
    html = """<form onsubmit="event.preventDefault(); window.advanced=true">
    <input type=submit value=Next></form><button>Submit application</button>"""
    with application({"/": html}) as a:
        a.native.execute("left_click", {"target": {"type": "ref", "ref": reference(a, "Next")}})
        assert a.browser.page.evaluate("window.advanced") is True
        assert not a.attempted
        assert not (a.artifacts / "submission-ledger").exists()
        with pytest.raises(BrowserError, match="submit_application"):
            a.native.execute(
                "left_click", {"target": {"type": "ref", "ref": reference(a, "Submit application")}}
            )


def test_disappearing_frame_during_inspection_does_not_lose_main_form(application, monkeypatch):
    html = '<label>Name<input></label><iframe srcdoc="<p>Transient frame</p>"></iframe>'
    with application({"/": html}) as a:
        child = a.browser.page.frames[1]
        original = Frame.frame_element

        def detach(frame):
            if frame == child:
                a.browser.page.locator("iframe").evaluate("el=>el.remove()")
            return original(frame)

        monkeypatch.setattr(Frame, "frame_element", detach)
        observation = a.browser.inspect()
        assert any(c["label"] == "Name" for c in observation["controls"])
        assert not observation["uninspected"]


def test_unreadable_present_frame_still_blocks_submission(application, monkeypatch):
    html = '<iframe srcdoc="<p>Form</p>"></iframe><button>Submit application</button>'
    with application({"/": html}) as a:
        ref = reference(a, "Submit application")

        def fail(_):
            raise PlaywrightError("Frame is changing")

        monkeypatch.setattr(Frame, "frame_element", fail)
        with pytest.raises(BrowserError, match="uninspected_frames"):
            a.execute("submit_application", {"ref": ref})
        assert not a.attempted


@pytest.mark.parametrize(
    "value,accepted", [("+39 123 456 7890", True), ("+39 123 456 7899", False)]
)
def test_phone_formatting_is_accepted_but_changed_digits_are_rejected(application, value, accepted):
    with application({"/": "<label>Phone<input type=tel></label>"}) as a:
        a.browser.page.locator("input").evaluate(
            "(el,value)=>el.addEventListener('input',()=>el.value=value)", value
        )

        def call():
            return a.native.execute("form_input", field(reference(a, "Phone"), "+391234567890"))

        if accepted:
            call()
            assert a.browser.page.locator("input").input_value() == value
        else:
            with pytest.raises(BrowserError, match="did not persist"):
                call()


def test_dropdown_query_can_be_replaced_without_approving_a_choice(application):
    html = """<label>Degree<input role=combobox aria-controls=choices></label>
    <div id=choices role=listbox><div role=option>Master's Degree</div></div>
    <label>Statement<input></label>"""
    with application({"/": html}) as a:
        a.settings.answers.mode = "review"
        ref = reference(a, "Degree")
        a.native.execute("form_input", field(ref, "Master of Science"))
        a.native.execute("key", {"text": "Control+a"})
        a.native.execute("key", {"text": "BackSpace"})
        assert a.browser.page.get_by_label("Degree").input_value() == ""
        a.native.execute("form_input", field(ref, "Master"))
        a.native.execute("form_input", field(ref, ""))
        assert not a.answered and not any(x["tool"] == "answer" for x in a.report["actions"])
        with pytest.raises(BrowserError, match="review"):
            a.native.execute("form_input", field(reference(a, "Master's Degree"), True))
        with pytest.raises(BrowserError, match="missing"):
            a.native.execute("form_input", field(reference(a, "Statement"), ""))
        a.browser.page.get_by_label("Statement").focus()
        with pytest.raises(BrowserError, match="dropdown search only"):
            a.native.execute("key", {"text": "Backspace"})


def test_value_match_cannot_turn_an_unrelated_fact_into_approval(application):
    with application({"/": "<label>Optional membership<input type=checkbox></label>"}) as a:
        a.settings.answers.mode = "review"
        a.settings.candidate["relocation"] = True
        with pytest.raises(BrowserError, match="review"):
            a.native.execute("form_input", field(reference(a, "Optional membership"), True))
        assert not a.browser.page.locator("input").is_checked()


def test_retention_acknowledgement_is_consent(application):
    label = "I understand my personal data will be kept for four years"
    with application({"/": f"<label>{label}<input type=checkbox name=accept_gdpr></label>"}) as a:
        a.settings.answers.topics["consent"] = "ask"
        with pytest.raises(BrowserError, match="approval"):
            a.native.execute("form_input", field(reference(a, label), True))


def test_snapshot_contains_fields_beyond_first_hundred(application):
    html = "".join(f"<label>Field {i}<input></label>" for i in range(125))
    with application({"/": html}) as a:
        page = a.browser.inspect()
        assert len(page["controls"]) == 125 and not page["controls_truncated"]
        a.answer(
            Answer(
                ref=reference(a, "Field 124"),
                source="full_name",
                category="general",
                basis="profile",
                reason="Explicit fact",
            )
        )
        assert a.browser.page.get_by_label("Field 124", exact=True).input_value() == "Alex Example"
