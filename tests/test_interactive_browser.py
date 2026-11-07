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
            result = a.execute("request_input", {"question": "Complete the location field"})
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
