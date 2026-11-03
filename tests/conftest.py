from contextlib import contextmanager

import pytest
from playwright.sync_api import sync_playwright

from application_filler.agent import ApplicationAgent
from application_filler.browser import BrowserSession, NetworkGuard
from application_filler.demo import ScriptedDemoClient, demo_server, demo_settings
from application_filler.documents import render_letter


@pytest.fixture(scope="session")
def chromium():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, chromium_sandbox=True)
        yield browser
        browser.close()


@pytest.fixture
def application(chromium, tmp_path):
    @contextmanager
    def make(pages=None, settings=None, interactive=False, ask=lambda _: ""):
        config = settings or demo_settings()
        private = tmp_path / "private"
        private.mkdir(exist_ok=True)
        _, pdf = render_letter("# Fictional CV\n\nPython services.", private)
        (private / "cv.pdf").write_bytes(pdf.read_bytes())
        with demo_server(pages) as url:
            context = chromium.new_context(accept_downloads=False, service_workers="block")
            session = BrowserSession(context, NetworkGuard(url, config, demo=True), config)
            session.open(url, initial=True)
            agent = ApplicationAgent(
                session,
                ScriptedDemoClient(),
                config,
                url,
                private,
                tmp_path / "artifacts",
                interactive,
                ask,
            )
            try:
                yield agent
            finally:
                context.close()

    return make


def reference(agent, label):
    return next(x["ref"] for x in agent.browser.inspect()["controls"] if x["label"] == label)
