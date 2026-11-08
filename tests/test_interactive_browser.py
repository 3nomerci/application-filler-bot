from threading import Event

import pytest
from conftest import reference

from application_filler.agent import Answer
from application_filler.browser import BrowserError, browser_input


@pytest.mark.parametrize("final_review", [False, True])
def test_network_and_browser_edits_continue_while_terminal_waits(application, final_review):
    updated = Event()

    def ask(_):
        # Simulate the user waiting for the browser's async location lookup before
        # continuing. Plain input() on the Playwright thread would stall that lookup.
        assert updated.wait(5), "Browser network stalled during terminal input"
        return "yes"

    pages = {
        "/": "<label>Location<input></label><label>Language<input required></label>",
        "/locations": "Paris",
    }
    with application(pages, interactive=True, ask=ask) as a:
        a.settings.answers.mode = "review"
        for label in ("Location", "Language"):
            with pytest.raises(BrowserError, match="review"):
                a.answer(
                    Answer(
                        ref=reference(a, label),
                        value="Unknown",
                        category="general",
                        basis="inference",
                        reason="Test pending answer",
                    )
                )
        page = a.browser.page
        page.expose_function("edited", updated.set)
        page.evaluate("""() => setTimeout(async () => {
            const text = await (await fetch('/locations')).text();
            document.querySelector('input').value = text;
            await window.edited();
        }, 200)""")
        if final_review:
            # The final prompt must also service earlier applications' contexts.
            other = page.context.browser.new_context()
            other.new_page()
            try:
                browser_input(page.context.browser, "Review forms", ask)
            finally:
                other.close()
        else:
            result = a.execute(
                "request_input", {"kind": "manual", "question": "Complete the location field"}
            )
            assert result["continue"] is True
            assert any(c["value"] == "Paris" for c in result["page"]["controls"])
            assert a.identity(reference(a, "Location")) not in a.unresolved
            assert a.identity(reference(a, "Language")) in a.unresolved
        assert page.get_by_label("Location").input_value() == "Paris"


def test_terminal_eof_propagates_without_hanging(application):
    def closed_input(_):
        raise EOFError

    with application(interactive=True, ask=closed_input) as a:
        with pytest.raises(EOFError):
            a.approve("Continue?")


def test_manual_checkbox_fix_with_disabled_next_button(application):
    edited = Event()

    def ask(_):
        assert edited.wait(5)
        return "yes"

    html = "<label>Privacy<input type=checkbox required></label><button disabled>Next</button>"
    with application({"/": html}, interactive=True, ask=ask) as a:
        a.settings.answers.topics["consent"] = "ask"
        ref = reference(a, "Privacy")
        with pytest.raises(BrowserError, match="approval"):
            a.native.execute("form_input", {"target": {"type": "ref", "ref": ref}, "value": True})
        a.browser.page.expose_function("edited", edited.set)
        a.browser.page.evaluate("""() => setTimeout(async () => {
            document.querySelector('input').checked = true;
            await window.edited();
        }, 200)""")
        a.execute("request_input", {"kind": "manual", "question": "Complete the checkbox"})
        assert not a.unresolved
        assert a.browser.page.locator("input").is_checked()
