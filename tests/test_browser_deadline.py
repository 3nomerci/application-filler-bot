import asyncio
import time
from concurrent.futures import Future
from threading import Thread
from types import SimpleNamespace

import pytest

from application_filler.browser_deadline import BrowserUnresponsive, browser_deadline


def test_deadline_does_not_wait_for_a_stuck_cancellation():
    async def scenario():
        release = asyncio.Event()

        async def original(callback, *args, **kwargs):
            return await callback()

        connection = SimpleNamespace(wrap_api_call=original)
        playwright = SimpleNamespace(_impl_obj=SimpleNamespace(_connection=connection))

        async def stuck():
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                await release.wait()

        started = time.monotonic()
        try:
            with browser_deadline(playwright, seconds=0.02):
                with pytest.raises(BrowserUnresponsive, match="without retrying"):
                    await connection.wrap_api_call(stuck)
            assert time.monotonic() - started < 2
            assert connection.wrap_api_call is original
        finally:
            release.set()
            await asyncio.sleep(0)

    # The browser fixture may already own the main thread's asyncio loop.
    # This synthetic connection has no Playwright objects, so isolate its loop.
    outcome = Future()

    def run_scenario():
        try:
            asyncio.run(scenario())
            outcome.set_result(None)
        except BaseException as exc:
            outcome.set_exception(exc)

    worker = Thread(target=run_scenario, daemon=True)
    worker.start()
    outcome.result(timeout=5)
    worker.join(timeout=1)


def test_real_browser_read_has_an_outer_deadline_and_the_connection_remains_usable(application):
    with application() as agent:
        page = agent.browser.page
        started = time.monotonic()
        with browser_deadline(agent.browser.context.browser, seconds=0.25):
            with pytest.raises(BrowserUnresponsive, match="did not respond"):
                page.evaluate("() => new Promise(() => {})")
        assert time.monotonic() - started < 3
        assert page.evaluate("1 + 1") == 2


def test_unresponsive_tool_stops_the_application_without_model_or_action_retries(application):
    with application() as agent:
        attempted = []

        def message(*_args):
            agent.client.calls += 1
            return {
                "content": [
                    {
                        "type": "tool_use",
                        "id": "find",
                        "name": "find",
                        "toolset_name": "browser",
                        "input": {"query": "Name"},
                    },
                    {
                        "type": "tool_use",
                        "id": "click",
                        "name": "left_click",
                        "toolset_name": "browser",
                        "input": {},
                    },
                ],
                "stop_reason": "tool_use",
            }

        def execute(name, _args):
            attempted.append(name)
            raise BrowserUnresponsive("Browser did not respond; stopped without retrying")

        agent.client.message = message
        agent.native.execute = execute
        report = agent.run()
        assert report["browser_unresponsive"] is True
        assert report["status"] == "blocked"
        assert report["model_calls"] == 1
        assert attempted == ["find"]


def test_batch_stops_after_an_unresponsive_browser_without_opening_more_jobs(
    monkeypatch, tmp_path, capsys
):
    from contextlib import nullcontext

    from application_filler import cli
    from application_filler.demo import demo_settings

    opened = []
    browser = SimpleNamespace(new_context=lambda **_kwargs: SimpleNamespace(), close=lambda: None)
    playwright = SimpleNamespace(chromium=SimpleNamespace(launch=lambda **_kwargs: browser))
    monkeypatch.setattr(cli, "sync_playwright", lambda: nullcontext(playwright))
    monkeypatch.setattr(cli, "browser_deadline", lambda _pw: nullcontext())
    monkeypatch.setattr(cli, "NetworkGuard", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        cli, "BrowserSession", lambda *_args: SimpleNamespace(open=lambda url: opened.append(url))
    )
    monkeypatch.setattr(
        cli, "ClaudeClient", lambda _settings: SimpleNamespace(usage={}, estimated_usd=0)
    )

    class StalledAgent:
        def __init__(self, *_args, **_kwargs):
            self.report = {
                "status": "blocked",
                "browser_unresponsive": True,
                "reason": "Browser did not respond",
            }

        def run(self):
            return self.report

    monkeypatch.setattr(cli, "ApplicationAgent", StalledAgent)
    monkeypatch.chdir(tmp_path)
    args = SimpleNamespace(
        command="run",
        dev_local=True,
        urls=["https://example.org/one", "https://example.org/two"],
        links=None,
        demo=False,
        interactive=False,
        headless=True,
        ask_immediately=False,
        config=tmp_path / "private" / "instructions.yaml",
    )
    assert cli.run(args, demo_settings()) == 2
    assert opened == ["https://example.org/one"]
    assert "1 unprocessed link(s)" in capsys.readouterr().out
