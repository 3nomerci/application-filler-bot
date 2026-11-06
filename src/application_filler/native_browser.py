"""Local executor for Anthropic's browser_toolset_20260801.

The API defines the tools; Playwright executes them inside the existing sandbox.
No generated JavaScript, shell commands, arbitrary uploads or desktop access.
"""

import base64
import json
import re
from urllib.parse import urlsplit

from .browser import META, SELECTOR, BrowserError

DISABLED = {
    "right_click",
    "middle_click",
    "left_click_drag",
    "left_mouse_down",
    "left_mouse_up",
    "hold_key",
    "zoom",
    "javascript_exec",
    "read_console",
    "read_network",
}
BROWSER_TOOL = {
    "type": "browser_toolset_20260801",
    "configs": {
        **{name: {"enabled": False} for name in sorted(DISABLED)},
        "file_upload": {"enabled": True},
    },
}

GUIDANCE = """
Use the native browser tools to operate pages. Read the page, click Apply, wait for delayed
content, scroll, and use screenshots/coordinates or keyboard interaction when needed. Zoom is
disabled. find ranks rendered labels and control types; rephrase if no match. Element refs
survive re-reads but not replaced elements/navigation. After an empty page, wait a few seconds
and inspect/screenshot before declaring it unavailable. Recover within a reasonable call budget.
Use browser.form_input for ordinary fields. answer_fields remains an optional shortcut to copy
profile keys and is required for research-backed salary/visa answers and explicit field approvals.
Use browser.type for focused text and browser.key for dropdowns and date widgets. Browser clicks
on submit buttons and Enter in forms are guarded: use submit_application for final submission.
Browser file_upload accepts document_ids=['cv'] or ['cover_letter'] only; no filesystem paths.
For cover-letter textboxes use answer_fields(category='cover_letter') with the actual tailored text.
'Tell us about yourself/why join' is a cover letter, not a protected personal disclosure.
Copy date facts in the format the field requests; native date inputs require YYYY-MM-DD.
Education end dates supplied by the user are facts about dates, not proof of an awarded degree.
Protected employment categories (e.g. Italian categorie protette/Law 68) have a separate policy:
negative_or_skip answers No only when candidate.protected_category_member is explicitly false;
when true, leave that question blank; if unknown ask. Do not generalize this to gender, ethnicity,
veteran status or disability questions. For optional skipped questions continue other fields.
If a site asks for an unspecified job preference, fill independent fields before requesting input.
Do not invent consent. answers.cookies=accept_when_needed explicitly authorizes accepting cookies
required to access the application, including marketing cookies when the site gates its job content
behind them. It does not authorize other declarations. When cookies are not needed, prefer rejecting
optional cookies. answers.cookies=ask requires approval. Other consents follow
answers.topics.consent.
For complete(ready_for_review), pass ref of the application's final button/form so unrelated footer
contact/newsletter forms do not block completion. Never fill unrelated forms to satisfy validation.
When a batch action fails, subsequent calls are not executed; inspect and recover next turn.
"""


def text_block(value):
    return {
        "type": "text",
        "text": value if isinstance(value, str) else json.dumps(value, ensure_ascii=False),
    }


class NativeBrowser:
    def __init__(self, agent):
        self.agent = agent
        self.browser = agent.browser
        self.tabs = {}
        self.tab_counter = 0
        self.reported_tabs = set()

    def state(self):
        for page in self.browser.context.pages:
            if not page.is_closed() and page not in self.tabs.values():
                self.tab_counter += 1
                self.tabs[f"tab-{self.tab_counter}"] = page
        self.tabs = {key: page for key, page in self.tabs.items() if not page.is_closed()}
        if self.tabs and self.browser.page.is_closed():
            self.browser.page = next(iter(self.tabs.values()))

        def clean(value):
            return "".join(c if c.isprintable() else " " for c in value)[:4096]

        result = {
            "type": "browser_state",
            "tabs": [
                {
                    "tab_id": key,
                    "url": clean(page.url),
                    "title": clean(page.title()),
                    "active": page == self.browser.page,
                }
                for key, page in self.tabs.items()
            ],
        }
        opened = set(self.tabs) - self.reported_tabs
        if opened:
            result["state_changes"] = [
                {"type": "tab_opened", "tab_id": key} for key in sorted(opened)
            ]
        self.reported_tabs = set(self.tabs)
        return result

    def select_tab(self, args):
        # Inventory without consuming the pending tab-open events.
        reported = self.reported_tabs.copy()
        self.state()
        self.reported_tabs = reported
        if "tab_id" in args:
            if args["tab_id"] not in self.tabs:
                raise BrowserError("Unknown tab_id; use list_tabs")
            self.browser.page = self.tabs[args["tab_id"]]
        if self.browser.page.is_closed():
            raise BrowserError("No active tab; use new_tab")

    def coordinate(self, target):
        if target.get("type") != "coordinate":
            raise BrowserError("Expected a viewport coordinate target")
        x, y = target.get("x"), target.get("y")
        size = self.browser.page.evaluate("({width:innerWidth,height:innerHeight})")
        if any(type(n) not in {int, float} for n in (x, y)) or not (
            0 <= x < size["width"] and 0 <= y < size["height"]
        ):
            raise BrowserError("Coordinate is outside the viewport")
        return x, y

    def ref(self, target):
        if target.get("type") == "ref":
            ref = target["ref"]
            element = self.browser.target(ref).element
            if element.owner_frame() not in self.browser.page.frames:
                raise BrowserError("Reference belongs to a different tab")
            return ref
        x, y = self.coordinate(target)
        frame = self.browser.page.main_frame
        while True:
            if not self.browser.allowed_frame(frame):
                raise BrowserError("Frame requires approval")
            handle = frame.evaluate_handle(
                """([x,y]) => {
                let el=document.elementFromPoint(x,y), inner;
                while(el?.shadowRoot && (inner=el.shadowRoot.elementFromPoint(x,y)) && inner!==el)
                    el=inner;
                return el;
            }""",
                [x, y],
            ).as_element()
            if handle is None:
                raise BrowserError("No element at coordinate; inspect again")
            child = handle.content_frame()
            if child:
                box = handle.bounding_box()
                if not box:
                    raise BrowserError("Frame is no longer visible")
                # bounding_box uses top-level viewport coordinates, including nested frames.
                x, y = target["x"] - box["x"], target["y"] - box["y"]
                frame = child
                continue
            control = handle.evaluate_handle(
                "(el, selector)=>el.closest(selector)||el", SELECTOR
            ).as_element()
            return self.browser.register(control)

    def focused_ref(self):
        for frame in reversed(self.browser.page.frames):
            if not self.browser.allowed_frame(frame):
                continue
            handle = frame.evaluate_handle("""() => {
                let el=document.activeElement;
                while(el?.shadowRoot?.activeElement) el=el.shadowRoot.activeElement;
                return el;
            }""").as_element()
            if handle and handle.evaluate("el=>!['BODY','HTML','IFRAME'].includes(el.tagName)"):
                return self.browser.register(handle)
        raise BrowserError("Focus a form control before typing or pressing keys")

    def fill(self, ref, value):
        from .agent import TOPICS, Answer

        target = self.browser.target(ref)
        text = " ".join(target.metadata[k] for k in ("label", "group", "name")).casefold()
        categories = [key for key, pattern in TOPICS.items() if re.search(pattern, text)]
        category = categories[0] if categories else "general"
        if category in {"salary", "work_authorization"}:
            raise BrowserError("Use answer_fields with source or research evidence for this field")
        if type(value) in {int, float}:
            value = str(value)

        # Exact facts can pass review mode without the model recreating source annotations.
        def facts(node, prefix=""):
            if isinstance(node, dict):
                for key, item in node.items():
                    yield from facts(item, f"{prefix}.{key}".lstrip("."))
            elif type(node) in {str, int, float, bool} and node != "":
                yield prefix, node

        source = next(
            (
                key
                for key, fact in facts(self.agent.settings.candidate)
                if type(value) is type(fact) and value == fact
            ),
            None,
        )
        return self.agent.answer(
            Answer(
                ref=ref,
                value=value,
                source=source,
                category=category,
                basis="profile" if source else "inference",
                reason="Native browser field entry",
            )
        )

    def check_click(self, ref):
        target = self.browser.target(ref)
        if self.browser.is_submission(target):
            raise BrowserError("Use submit_application for final or ambiguous submit controls")
        meta = target.metadata
        label = (meta["label"] + " " + meta["group"]).casefold()
        # Cookie consent buttons are actions too, not just checkbox fields.
        if re.search(r"\b(accept|allow|agree|consent|accetta)\b", label):
            cookie_permission = (
                self.agent.settings.answers.cookies == "accept_when_needed"
                and self.is_cookie_control(ref)
            )
            if (
                not cookie_permission
                and self.agent.settings.answers.topics.get("consent", "ask") != "infer"
            ):
                identity = self.agent.identity(ref)
                approval = next(
                    (
                        key
                        for key, value in self.agent.approvals.items()
                        if value == (identity, True)
                    ),
                    None,
                )
                if approval is None:
                    raise BrowserError(
                        "Use request_input with this ref and proposed_value=true, then retry click"
                    )
                self.agent.approvals.pop(approval)
        if meta["kind"] in {"checkbox", "radio", "option"}:
            value = (
                not bool(meta["checked"] in {True, "true"}) if meta["kind"] == "checkbox" else True
            )
            return self.fill(ref, value)
        return None

    def is_cookie_control(self, ref):
        return self.browser.target(ref).element.evaluate(r"""el => {
            if (/cookies?/i.test(el.getAttribute('aria-label') || el.innerText || '')) return true;
            for(let n=el, level=0; n && level<8; n=n.parentElement, level++) {
                if (/^(BODY|HTML)$/.test(n.tagName)) break;
                const marker=(n.id||'')+' '+(typeof n.className==='string'?n.className:'');
                if (/cookie|onetrust|consent-banner/i.test(marker) &&
                    /cookies?/i.test(n.innerText||''))
                    return true;
            }
            return false;
        }""")

    def read_page(self, args):
        depth = args.get("depth", 15)
        if (
            type(depth) is not int
            or depth < 1
            or args.get("filter") not in {None, "all", "interactive"}
        ):
            raise BrowserError("Invalid read_page filter or depth")
        scope = self.browser.target(args["ref"]).element if args.get("ref") else None
        lines = []
        for frame in self.browser.page.frames:
            if not self.browser.allowed_frame(frame):
                lines.append("[frame requires host approval]")
                continue
            if frame != self.browser.page.main_frame and not frame.frame_element().is_visible():
                continue
            if scope and scope.owner_frame() != frame:
                continue
            root = scope or frame.query_selector("body")
            if not root:
                continue
            selector = (
                SELECTOR
                if args.get("filter") == "interactive"
                else (
                    SELECTOR + ",body,main,section,article,nav,header,footer,form,[role=form],"
                    "fieldset,legend,"
                    "label,h1,h2,h3,h4,h5,h6,p,li,[role=dialog],[role=group],[role=radiogroup]"
                )
            )
            elements = [root, *root.query_selector_all(selector)]
            for element in elements:
                meta = element.evaluate(META)
                if not element.is_visible() and meta["kind"] != "file":
                    continue
                layout = element.evaluate(
                    """(el, root) => {
                    let level=0, node=el;
                    while(node && node!==root) {level++; node=node.parentElement;}
                    const b=el.getBoundingClientRect();
                    return {level,
                            onscreen:b.bottom>0 && b.right>0 &&
                                b.top<innerHeight && b.left<innerWidth,
                            text:(el.innerText||'').trim().slice(0,1000)};
                }""",
                    root,
                )
                if layout["level"] > depth:
                    continue
                if args.get("filter") is None and not layout["onscreen"] and meta["kind"] != "file":
                    continue
                ref = self.browser.register(element, meta)
                if not meta["label"] and meta["tag"] in {
                    "p",
                    "li",
                    "legend",
                    "h1",
                    "h2",
                    "h3",
                    "h4",
                }:
                    meta = {**meta, "label": layout["text"]}
                description = {
                    key: meta[key]
                    for key in (
                        "label",
                        "group",
                        "kind",
                        "name",
                        "required",
                        "value",
                        "options",
                        "files",
                        "checked",
                        "href",
                    )
                    if meta[key]
                }
                lines.append(
                    " " * min(layout["level"], 15)
                    + f"[{ref}] "
                    + json.dumps(description, ensure_ascii=False)
                )
        result = "\n".join(lines) or "(empty page; wait, then inspect or screenshot)"
        return result[:49500] + (
            "\n[TRUNCATED: narrow with ref/filter/depth]" if len(result) > 49500 else ""
        )

    def find(self, query):
        if not isinstance(query, str) or not query.strip():
            raise BrowserError("Find requires a description")
        words = set(re.findall(r"\w+", query.casefold())) - {"the", "a", "an", "for", "with"}
        synonyms = {
            "dropdown": {"select", "combobox"},
            "field": {"input", "textbox", "textarea"},
            "upload": {"file"},
            "checkbox": {"checkbox"},
            "button": {"button", "submit"},
        }
        matches = []
        for frame in self.browser.page.frames:
            if not self.browser.allowed_frame(frame) or (
                frame != self.browser.page.main_frame and not frame.frame_element().is_visible()
            ):
                continue
            for element in frame.locator(SELECTOR).element_handles():
                meta = element.evaluate(META)
                if not element.is_visible() and meta["kind"] != "file":
                    continue
                label = (meta["label"] + " " + meta["group"] + " " + meta["name"]).casefold()
                score = sum(
                    3 if word in label else int(meta["kind"] in synonyms.get(word, {word}))
                    for word in words
                )
                if score:
                    ref = self.browser.register(element, meta)
                    matches.append(
                        (
                            score,
                            {
                                "ref": ref,
                                "kind": meta["kind"],
                                "label": meta["label"],
                                "group": meta["group"],
                            },
                        )
                    )
        matches.sort(key=lambda item: item[0], reverse=True)
        return (
            "\n".join(f"[{m['ref']}] " + json.dumps(m, ensure_ascii=False) for _, m in matches[:20])
            or "No matching visible controls."
        )

    def execute(self, name, args):
        if name in DISABLED:
            raise BrowserError("Browser member is disabled")
        if name == "new_tab":
            if len(self.browser.context.pages) >= 10:
                raise BrowserError("Tab limit reached")
            self.browser.context.new_page()
            return [self.state()]
        if name == "list_tabs":
            return [self.state()]
        self.select_tab(args)
        page = self.browser.page
        if name in {"list_tabs", "switch_tab", "close_tab"}:
            if name in {"switch_tab", "close_tab"} and "tab_id" not in args:
                raise BrowserError("tab_id is required")
            if name == "close_tab":
                page.close()
            elif name == "switch_tab":
                page.bring_to_front()
            return [self.state()]
        if name == "navigate":
            self.browser.count_action()
            url = args["url"]
            if url in {"back", "forward", "reload"}:
                response = {
                    "back": page.go_back,
                    "forward": page.go_forward,
                    "reload": page.reload,
                }[url](wait_until="domcontentloaded", timeout=30000)
                if response and response.status in {401, 403, 429}:
                    raise BrowserError("Website denied access; hand off without retries")
            else:
                if not urlsplit(url).scheme:
                    url = "https://" + url
                self.browser.open(url)
            return [text_block("Navigated"), self.state()]
        if name == "screenshot":
            data = page.screenshot(type="jpeg", quality=70, full_page=False)
            return [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": base64.b64encode(data).decode(),
                    },
                },
                self.state(),
            ]
        if name == "read_page":
            return [text_block(self.read_page(args)), self.state()]
        if name == "find":
            return [text_block(self.find(args["query"])), self.state()]
        if name == "get_page_text":
            texts = []
            for frame in page.frames:
                if self.browser.allowed_frame(frame) and (
                    frame == page.main_frame or frame.frame_element().is_visible()
                ):
                    texts.append(frame.locator("body").inner_text(timeout=5000))
            return [text_block("\n".join(texts)[:50000] or "(empty)"), self.state()]
        if name == "wait":
            duration = args.get("duration")
            if type(duration) not in {float, int} or not 0 <= duration <= 30:
                raise BrowserError("Wait duration must be 0 to 30 seconds")
            self.browser.count_action()
            page.wait_for_timeout(duration * 1000)
        elif name == "form_input":
            return [text_block(self.fill(self.ref(args["target"]), args["value"])), self.state()]
        elif name == "file_upload":
            if args.get("paths") or args.get("document_ids") not in [["cv"], ["cover_letter"]]:
                raise BrowserError(
                    "Use document_ids ['cv'] or ['cover_letter']; paths are disabled"
                )
            self.agent.execute(
                "upload_document",
                {"ref": self.ref(args["target"]), "kind": args["document_ids"][0]},
            )
        elif name in {"left_click", "double_click", "triple_click"}:
            if args.get("modifiers"):
                raise BrowserError("Modified clicks are not permitted; use new_tab and navigate")
            ref = self.ref(args["target"])
            result = self.check_click(ref)
            if result is None:
                self.browser.count_action()
                count = {"left_click": 1, "double_click": 2, "triple_click": 3}[name]
                if args["target"]["type"] == "coordinate":
                    page.mouse.click(*self.coordinate(args["target"]), click_count=count)
                else:
                    self.browser.target(ref).element.click(click_count=count)
            else:
                return [text_block(result), self.state()]
        elif name in {"hover", "mouse_move", "scroll_to"}:
            self.browser.count_action()
            if name == "mouse_move":
                page.mouse.move(*self.coordinate(args["target"]))
            else:
                element = self.browser.target(self.ref(args["target"])).element
                if name == "hover":
                    element.hover()
                else:
                    element.scroll_into_view_if_needed()
        elif name == "scroll":
            amount = args.get("scroll_amount", 3)
            direction = args.get("scroll_direction")
            if (
                type(amount) is not int
                or not 1 <= amount <= 10
                or direction not in {"up", "down", "left", "right"}
            ):
                raise BrowserError("Invalid scroll direction or amount")
            self.browser.count_action()
            page.mouse.move(*self.coordinate(args["target"]))
            distance = amount * 100 * (-1 if direction in {"up", "left"} else 1)
            page.mouse.wheel(
                distance if direction in {"left", "right"} else 0,
                distance if direction in {"up", "down"} else 0,
            )
        elif name == "type":
            ref = self.focused_ref()
            target = self.browser.target(ref)
            value = args.get("text")
            if not isinstance(value, str):
                raise BrowserError("Text must be a string")
            # Compute insertion at the current selection and validate the entire resulting answer.
            resulting = target.element.evaluate(
                """(el,text)=> {
                const value=el.value;
                if(typeof value!=='string') return null;
                const start=el.selectionStart ?? value.length, end=el.selectionEnd ?? value.length;
                return value.slice(0,start)+text+value.slice(end);
            }""",
                value,
            )
            if resulting is None:
                raise BrowserError("Use form_input/answer_fields for this editor")
            return [text_block(self.fill(ref, resulting)), self.state()]
        elif name == "key":
            self.key(args)
        else:
            raise BrowserError("Unknown browser member")
        self.browser.settle()
        self.agent.report["actions"].append({"tool": "browser." + name})
        return [text_block("Action completed. Inspect the result."), self.state()]

    def key(self, args):
        repeat = args.get("repeat", 1)
        if type(repeat) is not int or not 1 <= repeat <= 100:
            raise BrowserError("Key repeat must be 1 to 100")
        aliases = {
            "ctrl": "Control",
            "alt": "Alt",
            "shift": "Shift",
            "cmd": "Meta",
            "escape": "Escape",
            "esc": "Escape",
            "enter": "Enter",
            "tab": "Tab",
            "space": "Space",
            "arrowdown": "ArrowDown",
            "arrowup": "ArrowUp",
            "arrowleft": "ArrowLeft",
            "arrowright": "ArrowRight",
        }
        for chord in args["text"].split():
            key = "+".join(aliases.get(part.lower(), part) for part in chord.split("+"))
            if key not in {
                "Tab",
                "Shift+Tab",
                "Escape",
                "Control+a",
                "Meta+a",
                "ArrowDown",
                "ArrowUp",
                "ArrowLeft",
                "ArrowRight",
                "Enter",
                "Space",
            }:
                raise BrowserError("Use type/form_input to edit answers; this key is not permitted")
            if key in {"ArrowDown", "ArrowUp", "ArrowLeft", "ArrowRight", "Enter", "Space"}:
                ref = self.focused_ref()
                target = self.browser.target(ref)
                if key in {"Enter", "Space"}:
                    # Never allow implicit HTML form submission or toggles past the answer policy.
                    if target.metadata["kind"] in {
                        "button",
                        "submit",
                        "a",
                        "checkbox",
                        "radio",
                        "option",
                    }:
                        result = self.check_click(ref)
                        if result is not None:
                            continue
                    elif key == "Enter" and target.metadata["form"]:
                        raise BrowserError(
                            "Enter may submit this form; click the observed next button "
                            "or use submit_application"
                        )
                if target.metadata["kind"] in {"select", "combobox", "date", "month", "number"}:
                    from .agent import PROTECTED_CATEGORY, TOPICS

                    label = " ".join(
                        target.metadata[k] for k in ("label", "group", "name")
                    ).casefold()
                    if self.agent.settings.answers.mode == "review" or any(
                        re.search(p, label) for p in [*TOPICS.values(), PROTECTED_CATEGORY]
                    ):
                        raise BrowserError(
                            "Use answer_fields/form_input so this answer can be checked"
                        )
            self.browser.count_action()
            for _ in range(repeat):
                self.browser.page.keyboard.press(key)
