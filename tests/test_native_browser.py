import json

import pytest
from conftest import reference

from application_filler.agent import Answer, Complete
from application_filler.browser import BrowserError
from application_filler.config import MODEL_ID
from application_filler.native_browser import BROWSER_TOOL


def field(ref, value):
    return {"target": {"type": "ref", "ref": ref}, "value": value}


def test_native_tools_stable_refs_dates_and_text_letter(application):
    html = """<label>Birth date<input type=date></label>
    <label>Tell us about yourself and why you'd like to join Sortrace
    <textarea name=sortrace_intro></textarea></label>"""
    with application({"/": html}) as a:
        a.settings.candidate["date_of_birth"] = "1994-06-12"
        a.settings.documents.cover_letter = "trusted"
        a.native.execute("read_page", {"filter": "all"})
        ref = reference(a, "Birth date")
        a.native.execute("read_page", {})
        a.native.execute("form_input", field(ref, "1994-06-12"))
        a.execute(
            "answer_fields",
            {
                "answers": [
                    Answer(
                        ref=reference(
                            a, "Tell us about yourself and why you'd like to join Sortrace"
                        ),
                        value="A factual tailored letter.",
                        category="cover_letter",
                        basis="inference",
                        reason="Based on candidate background",
                    ).model_dump()
                ]
            },
        )
        assert a.browser.page.locator("input").input_value() == "1994-06-12"
        assert a.browser.page.locator("textarea").input_value() == "A factual tailored letter."
        assert not a.unresolved


@pytest.mark.parametrize("member,expected", [(False, "n"), (True, "")])
def test_protected_category_explicit_negative_or_skip(application, member, expected):
    html = """<label>Appartenenza alle categorie protette (Legge 68)
    <select><option value="">Choose</option><option value=y>Sì</option>
    <option value=n>No, non appartengo</option></select></label>"""
    with application({"/": html}) as a:
        a.settings.candidate["protected_category_member"] = member
        a.native.execute("read_page", {})
        ref = reference(a, "Appartenenza alle categorie protette (Legge 68)")
        a.native.execute("form_input", field(ref, "n"))
        assert a.browser.page.locator("select").input_value() == expected
        if not member:
            with pytest.raises(BrowserError, match="negative answer"):
                a.native.execute("form_input", field(ref, "y"))


def test_native_coordinates_cannot_submit_and_keyboard_cannot_bypass_policy(application):
    html = """<form onsubmit="window.sent=true;return false">
    <label>Gender<input></label><button>Submit application</button></form>"""
    with application({"/": html}) as a:
        a.settings.submission = "manual"
        a.native.execute("read_page", {})
        box = a.browser.page.locator("button").bounding_box()
        with pytest.raises(BrowserError, match="submit_application"):
            a.native.execute(
                "left_click",
                {"target": {"type": "coordinate", "x": box["x"] + 5, "y": box["y"] + 5}},
            )
        a.browser.page.locator("input").focus()
        with pytest.raises(BrowserError, match="approval"):
            a.native.execute("type", {"text": "Male"})
        with pytest.raises(BrowserError, match="submit"):
            a.native.execute("key", {"text": "Enter"})
        assert a.browser.page.evaluate("Boolean(window.sent)") is False


def test_native_iframe_coordinates_tabs_and_upload_restrictions(application):
    html = """<iframe srcdoc="<label>City<input></label>"></iframe>"""
    with application({"/": html}) as a:
        a.native.execute("read_page", {"filter": "all"})
        element = a.browser.page.frames[1].locator("input")
        box = element.bounding_box()
        a.native.execute(
            "left_click", {"target": {"type": "coordinate", "x": box["x"] + 5, "y": box["y"] + 5}}
        )
        a.native.execute("type", {"text": "Rome"})
        assert element.input_value() == "Rome"
        original = a.native.execute("list_tabs", {})[0]["tabs"][0]["tab_id"]
        created = a.native.execute("new_tab", {})
        assert len(created) == 1 and created[0]["type"] == "browser_state"
        assert len(created[0]["state_changes"]) == 1
        new = next(tab["tab_id"] for tab in created[0]["tabs"] if tab["active"])
        a.native.execute("switch_tab", {"tab_id": original})
        assert len(a.native.execute("close_tab", {"tab_id": new})[0]["tabs"]) == 1
        with pytest.raises(BrowserError, match="paths are disabled"):
            a.native.execute(
                "file_upload",
                {
                    "target": {"type": "ref", "ref": "unknown"},
                    "paths": ["/run/secrets/anthropic_api_key"],
                },
            )


def test_native_loop_echoes_toolset_and_halts_batch_after_error(application):
    with application({"/": "<p>Example</p>"}) as a:
        a.settings.model.max_calls_per_application = 2

        def message(system, messages, tools, searches):
            assert BROWSER_TOOL in tools
            a.client.calls += 1
            if a.client.calls == 1:
                calls = [
                    ("read_page", {}),
                    ("javascript_exec", {"text": "bad"}),
                    ("navigate", {"url": "https://must-not-visit.example"}),
                ]
                content = [
                    {
                        "type": "tool_use",
                        "id": str(i),
                        "toolset_name": "browser",
                        "name": name,
                        "input": args,
                    }
                    for i, (name, args) in enumerate(calls)
                ]
            else:
                results = messages[-1]["content"]
                assert all(r["toolset_name"] == "browser" for r in results)
                assert not results[0]["is_error"]
                assert results[1]["is_error"] and results[2]["is_error"]
                assert "Not executed" in results[2]["content"]
                content = [
                    {
                        "type": "tool_use",
                        "id": "done",
                        "name": "complete",
                        "input": {"status": "blocked", "reason": "Test complete"},
                    }
                ]
            return {"model": MODEL_ID, "content": content, "stop_reason": "tool_use"}

        a.client.message = message
        assert a.run()["reason"] == "Test complete"
        assert "must-not-visit" not in a.browser.page.url
        assert json.dumps(a.messages)


def test_cookie_permission_does_not_authorize_other_consents(application):
    html = """<div id=cookie-banner>We use cookies.
    <button type=button onclick="this.dataset.clicked='yes'">Allow all</button></div>
    <button type=button>Accept legal declaration</button>"""
    with application({"/": html}) as a:
        a.settings.answers.cookies = "accept_when_needed"
        a.settings.answers.topics["consent"] = "ask"
        a.native.execute(
            "left_click", {"target": {"type": "ref", "ref": reference(a, "Allow all")}}
        )
        assert (
            a.browser.page.locator("#cookie-banner button").get_attribute("data-clicked") == "yes"
        )
        with pytest.raises(BrowserError, match="request_input"):
            a.native.execute(
                "left_click",
                {"target": {"type": "ref", "ref": reference(a, "Accept legal declaration")}},
            )


def test_completion_ignores_unrelated_newsletter_form(application):
    html = """<form id=application><label>Name<input required></label><button>Submit</button></form>
    <form><label>Newsletter email<input type=email required></label>
    <button>Subscribe</button></form>"""
    with application({"/": html}) as a:
        a.native.execute("form_input", field(reference(a, "Name"), "Alex Example"))
        a.complete(
            Complete(
                status="ready_for_review", reason="Application filled", ref=reference(a, "Submit")
            )
        )
        assert a.report["status"] == "ready_for_review"
        assert a.browser.page.locator("input[type=email]").input_value() == ""


def test_supplied_date_corrects_default_and_education_dates_copy(application):
    html = """<label>Birth date<input type=date value=2026-11-06></label>
    <label>Study start date<input></label><label>Study end date<input></label>"""
    with application({"/": html}) as a:
        a.settings.candidate.update(
            date_of_birth="1994-06-12",
            education={"bachelors": {"start_date": "2013-09-01", "end_date": "2017-06-30"}},
        )
        a.native.execute("form_input", field(reference(a, "Birth date"), "1994-06-12"))
        for label, key, value in [
            ("Study start date", "start_date", "01/09/2013"),
            ("Study end date", "end_date", "30/06/2017"),
        ]:
            a.answer(
                Answer(
                    ref=reference(a, label),
                    source="education.bachelors." + key,
                    value=value,
                    category="general",
                    basis="profile",
                    reason="Format supplied date",
                )
            )
        assert a.browser.page.locator("input").evaluate_all("nodes=>nodes.map(el=>el.value)") == [
            "1994-06-12",
            "01/09/2013",
            "30/06/2017",
        ]


def test_native_find_ranks_control_description_and_keeps_ref(application):
    html = """<label>Position<select><option value=free>Free Application</option></select></label>
    <label>Unrelated<input></label>"""
    with application({"/": html}) as a:
        result = a.native.execute("find", {"query": "the Position dropdown"})
        assert "Position" in result[0]["text"] and "Unrelated" not in result[0]["text"]
        ref = reference(a, "Position")
        a.native.execute("read_page", {"filter": "all"})
        a.native.execute("form_input", field(ref, "Free Application"))
        assert a.browser.page.locator("select").input_value() == "free"


def test_phone_prefix_default_is_completed_but_full_existing_number_is_protected(application):
    html = '<label>Phone<input type=tel value="+39"></label>'
    with application({"/": html}) as a:
        a.settings.candidate["phone"] = "+390001234567"
        a.native.execute("form_input", field(reference(a, "Phone"), "+390001234567"))
        assert a.browser.page.locator("input").input_value() == "+390001234567"
    with application({"/": html.replace('value="+39"', 'value="+390007654321"')}) as a:
        a.settings.candidate["phone"] = "+390001234567"
        with pytest.raises(BrowserError, match="Existing answer"):
            a.native.execute("form_input", field(reference(a, "Phone"), "+390001234567"))
