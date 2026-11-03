"""Local integration fixture and explicitly scripted model double. Never used for real URLs."""

import json
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .config import MODEL_ID, Settings

STYLE = """<meta charset='utf-8'><title>Fictional application</title><style>
body{font:18px system-ui;max-width:700px;margin:40px auto}label{display:block;margin:18px 0}
input,select,textarea,button{font:inherit;padding:9px}input:not([type=checkbox]){display:block}
button,a{cursor:pointer}h1{color:#173f87}</style>"""
PAGES = {
    "/": STYLE
    + """<h1>Backend Engineer — Example Company</h1>
    <p>Fictional role in Berlin. Build Python services.
    This local practice site sends no application.</p>
    <a href='/redirect'>Apply for this role</a>""",
    "/apply": STYLE
    + """<h1>Contact information</h1><form action='/details'>
    <label>Your full name<input name='q1' required></label>
    <label>Contact email<input name='q2' type='email' required></label>
    <label>Are you open to moving for this role?<select name='q3' required>
    <option value=''>Choose</option><option value='yes'>Yes, I am open to relocating</option>
    <option value='no'>No, I need to stay where I am</option></select></label>
    <button type='submit'>Next</button></form>""",
    "/details": STYLE
    + """<h1>Documents</h1><form id='application'>
    <label>Resume PDF<input type='file' name='cv' required></label>
    <label>Cover letter PDF<input type='file' name='letter' required></label>
    <label><input type='checkbox' name='consent' required>
    I agree to the fictional privacy terms</label>
    <button type='submit'>Send application</button></form>
    <script>window.submissions=0;document.querySelector('form').onsubmit=e=>{
      e.preventDefault();window.submissions++;document.querySelector('form').remove();
      document.body.insertAdjacentHTML('beforeend',
        '<h2>Application received. Thank you!</h2>');};</script>""",
}


@contextmanager
def demo_server(pages=None):
    pages = pages or PAGES

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            route = self.path.split("?")[0]
            if route == "/redirect":
                self.send_response(302)
                self.send_header("Location", "/apply")
                self.end_headers()
                return
            body = pages.get(route, "Not found").encode()
            self.send_response(200 if route in pages else 404)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def demo_settings() -> Settings:
    settings = Settings(
        candidate={
            "full_name": "Alex Example",
            "email": "alex@example.com",
            "relocation": "Yes",
            "citizenships": ["IT"],
        }
    )
    settings.documents.background = "I build Python services. This is fictional demo information."
    settings.answers.topics["consent"] = "infer"
    settings.submission = "auto"
    settings.browser.delay_ms = 100
    return settings


class ScriptedDemoClient:
    """Tests the real executor/protocol without claiming to measure model intelligence."""

    def __init__(self):
        self.calls = 0
        self.estimated_usd = 0.0
        self.usage = []
        self.letter_created = False

    def message(self, system, messages, tools, searches=0):
        self.calls += 1
        page = None
        for message in messages:
            if message["role"] != "user":
                continue
            items = (
                message["content"]
                if isinstance(message["content"], list)
                else [{"content": message["content"]}]
            )
            for item in items:
                try:
                    data = json.loads(item["content"])
                except (KeyError, ValueError, TypeError):
                    continue
                candidate = data.get("page", data)
                if isinstance(candidate, dict) and "controls" in candidate:
                    page = candidate
        if page is None:
            raise AssertionError("Test double requires a real browser observation")
        controls = page["controls"]
        tool, args = "read_page", {}
        if "Application received. Thank you!" in page["text"]:
            tool, args = (
                "complete",
                {
                    "status": "submitted",
                    "reason": "Local fixture accepted",
                    "confirmation_text": "Application received. Thank you!",
                },
            )
        elif any("Apply for" in x["label"] for x in controls):
            target = next(x for x in controls if "Apply for" in x["label"])
            tool, args = "click", {"ref": target["ref"], "purpose": "apply"}
        elif any(x["name"] == "q1" for x in controls):
            fields = {x["name"]: x for x in controls if x["name"]}
            if not fields["q1"]["value"]:
                tool, args = (
                    "answer_fields",
                    {
                        "answers": [
                            {
                                "ref": fields["q1"]["ref"],
                                "source": "full_name",
                                "category": "general",
                                "basis": "profile",
                                "reason": "Supplied name",
                            },
                            {
                                "ref": fields["q2"]["ref"],
                                "source": "email",
                                "category": "general",
                                "basis": "profile",
                                "reason": "Supplied email",
                            },
                            {
                                "ref": fields["q3"]["ref"],
                                "value": "yes",
                                "source": "relocation",
                                "category": "general",
                                "basis": "profile",
                                "reason": "Equivalent page option",
                            },
                        ]
                    },
                )
            else:
                target = next(x for x in controls if x["label"] == "Next")
                tool, args = "click", {"ref": target["ref"], "purpose": "next"}
        else:
            files = {x["name"]: x for x in controls if x["kind"] == "file"}
            if not files["cv"]["files"]:
                tool, args = "upload_document", {"ref": files["cv"]["ref"], "kind": "cv"}
            elif not self.letter_created:
                tool, args = (
                    "create_cover_letter",
                    {
                        "markdown": "Dear Example Company,\n\n"
                        "I build Python services and am interested in your "
                        "Backend Engineer role in Berlin.\n\nAlex Example"
                    },
                )
                self.letter_created = True
            elif not files["letter"]["files"]:
                tool, args = (
                    "upload_document",
                    {"ref": files["letter"]["ref"], "kind": "cover_letter"},
                )
            else:
                consent = next(x for x in controls if x["kind"] == "checkbox")
                if not consent["checked"]:
                    tool, args = (
                        "answer_fields",
                        {
                            "answers": [
                                {
                                    "ref": consent["ref"],
                                    "value": True,
                                    "category": "consent",
                                    "basis": "inference",
                                    "reason": "Demo policy allows",
                                }
                            ]
                        },
                    )
                else:
                    target = next(x for x in controls if x["label"] == "Send application")
                    tool, args = "submit_application", {"ref": target["ref"]}
        return {
            "model": MODEL_ID,
            "stop_reason": "tool_use",
            "usage": {},
            "content": [
                {"type": "tool_use", "id": f"fixture-{self.calls}", "name": tool, "input": args}
            ],
        }
