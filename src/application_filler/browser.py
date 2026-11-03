import ipaddress
import re
import socket
from dataclasses import dataclass
from urllib.parse import urlsplit

from playwright.sync_api import BrowserContext, ElementHandle, Page

from .config import Settings


class BrowserError(RuntimeError):
    pass


def public_url(url: str) -> str:
    p = urlsplit(url)
    if (
        p.scheme != "https"
        or not p.hostname
        or p.username
        or p.password
        or p.port not in (None, 443)
    ):
        raise BrowserError("Only public HTTPS URLs without credentials are permitted")
    addresses = socket.getaddrinfo(p.hostname, 443, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(x[4][0]).is_global for x in addresses):
        raise BrowserError("Private and reserved network destinations are blocked")
    return p.hostname.lower()


class NetworkGuard:
    def __init__(self, url: str, settings: Settings, demo: bool = False):
        self.demo_origin = self.origin(url) if demo else None
        self.settings = settings
        self.hosts = {urlsplit(url).hostname} if demo else {public_url(url)}
        for host in settings.navigation.allowed_hosts:
            self.hosts.add(public_url("https://" + host))
        self.checked: set[tuple] = set()
        self.blocked_host: str | None = None

    @staticmethod
    def origin(url: str):
        p = urlsplit(url)
        return p.scheme, p.hostname, p.port

    def allowed(self, url: str, navigation: bool = True) -> bool:
        if self.demo_origin:
            return self.origin(url) == self.demo_origin
        origin = self.origin(url)
        if origin not in self.checked:
            public_url(url)
            self.checked.add(origin)
        p = urlsplit(url)
        if p.username or p.password:
            return False
        if (
            navigation
            and self.settings.navigation.handoffs == "ask"
            and p.hostname not in self.hosts
        ):
            self.blocked_host = p.hostname
            return False
        return True

    def route(self, route):
        try:
            url = route.request.url
            if url.startswith("data:") and not route.request.is_navigation_request():
                route.continue_()
            elif self.allowed(url, route.request.is_navigation_request()):
                route.continue_()
            else:
                route.abort("blockedbyclient")
        except (ValueError, OSError, BrowserError):
            route.abort("blockedbyclient")


SELECTOR = (
    'input,textarea,select,button,a[href],[role="button"],[role="combobox"],'
    '[role="option"],[role="checkbox"],[role="radio"],[role="textbox"],'
    '[contenteditable="true"]'
)
META = r"""el => {
  const text = node => {
    if (!node) return '';
    const clone = node.cloneNode(true);
    clone.querySelectorAll('input,textarea,select,script,style').forEach(x=>x.remove());
    return (clone.textContent||'').replace(/\s+/g,' ').trim();
  };
  const root = el.getRootNode();
  const aria = (el.getAttribute('aria-labelledby')||'').split(/\s+/)
    .map(id=>text(root.getElementById?.(id))).join(' ').trim();
  const tag = el.tagName.toLowerCase();
  const role = el.getAttribute('role') || '';
  const kind = tag === 'input' ? el.type : tag === 'select' ? 'select' :
    tag === 'textarea' ? 'textarea' : role || tag;
  const label = aria || el.getAttribute('aria-label') ||
    Array.from(el.labels||[]).map(text).join(' ') ||
    (['a','button'].includes(tag)||role ? text(el) : '') || el.placeholder || '';
  const group = text(el.closest('fieldset')?.querySelector('legend')) ||
    el.closest('[role=group],[role=radiogroup]')?.getAttribute('aria-label') || '';
  return {label:label.slice(0,700),group:group.slice(0,700),kind,tag,
    name:(el.name||'').slice(0,200),type:el.type||'',href:el.href||'',
    required:Boolean(el.required || el.getAttribute('aria-required')==='true'),
    disabled:Boolean(el.disabled || el.readOnly || el.getAttribute('aria-disabled')==='true'),
    value:kind==='password'?'[redacted]':String(el.value??'').slice(0,1500),
    checked:el.checked??el.getAttribute('aria-checked'),
    form:Boolean(el.form||el.closest('form')),
    options:tag==='select'?Array.from(el.options).filter(x=>!x.disabled)
      .map(x=>({label:x.label,value:x.value})):[],
    files:kind==='file'?Array.from(el.files).map(x=>x.name):[]};
}"""


@dataclass
class Target:
    element: ElementHandle
    metadata: dict
    frame_url: str


class BrowserSession:
    def __init__(self, context: BrowserContext, guard: NetworkGuard, settings: Settings):
        self.context, self.guard, self.settings = context, guard, settings
        self.page: Page = context.new_page()
        self.targets: dict[str, Target] = {}
        self.links: set[str] = set()
        self.generation = 0
        self.actions = 0
        self.events: list[dict] = []
        context.route("**/*", guard.route)
        # Applications may use sockets, but exposing the model gateway is not acceptable.
        context.route_web_socket("**/*", lambda socket: socket.close())
        context.on("page", self._new_page)
        self._new_page(self.page)

    def _new_page(self, page):
        page.set_default_timeout(7000)
        page.on("dialog", lambda dialog: dialog.dismiss())
        self.page = page  # Popups opened by Apply become the active application page.

    def open(self, url: str, initial=False):
        if not initial and url not in self.links:
            raise BrowserError("Navigate only to a link observed on the current page")
        if not self.guard.allowed(url):
            raise BrowserError("Destination needs host approval")
        response = self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
        if response and response.status in {401, 403, 429}:
            raise BrowserError("Website denied or rate-limited access; hand off without retries")
        self.settle()

    def settle(self):
        self.page.wait_for_timeout(self.settings.browser.delay_ms)

    def allowed_frame(self, frame):
        # srcdoc/about:blank embedded documents inherit their parent's origin.
        while frame and frame.url in {"about:blank", "about:srcdoc"}:
            frame = frame.parent_frame
        return bool(frame and self.guard.allowed(frame.url))

    def inspect(self, offset: int = 0) -> dict:
        if self.page.is_closed():
            raise BrowserError("Browser tab was closed")
        if not self.guard.allowed(self.page.url):
            raise BrowserError("Page is outside permitted destinations")
        self.generation += 1
        self.targets = {}
        self.links = set()
        controls = []
        texts = []
        excluded = []
        for index, frame in enumerate(self.page.frames):
            if frame != self.page.main_frame and not frame.frame_element().is_visible():
                continue
            try:
                if not self.allowed_frame(frame):
                    excluded.append("unapproved_frame")
                    continue
            except (BrowserError, ValueError, OSError):
                excluded.append("unapproved_frame")
                continue
            texts.append(
                frame.locator("body").inner_text(timeout=5000)[
                    : self.settings.browser.snapshot_chars
                ]
            )
            for element in frame.locator(SELECTOR).element_handles():
                if not element.is_visible() and element.get_attribute("type") != "file":
                    continue
                meta = element.evaluate(META)
                if meta["kind"] == "hidden":
                    continue
                ref = f"s{self.generation}-e{len(controls)}"
                self.targets[ref] = Target(element, meta, frame.url)
                controls.append({"ref": ref, "frame": index, **meta})
                if meta["href"]:
                    self.links.add(meta["href"])
        text = "\n".join(texts)
        return {
            "url": self.page.url,
            "title": self.page.title(),
            "text": text[: self.settings.browser.snapshot_chars],
            "text_truncated": len(text) > self.settings.browser.snapshot_chars,
            "controls": controls[offset : offset + 100],
            "total_controls": len(controls),
            "next_offset": offset + 100 if len(controls) > offset + 100 else None,
            "uninspected": excluded,
            "blocked_host": self.guard.blocked_host,
        }

    def target(self, ref: str) -> Target:
        target = self.targets.get(ref)
        if not target:
            raise BrowserError("Stale reference: inspect the current page again")
        frame = target.element.owner_frame()
        if frame is None or frame.url != target.frame_url or not self.allowed_frame(frame):
            raise BrowserError("Frame changed; inspect again")
        current = target.element.evaluate(META)
        keys = ("label", "group", "kind", "name", "href", "options")
        if any(current[k] != target.metadata[k] for k in keys) or (
            not target.element.is_visible() and current["kind"] != "file"
        ):
            raise BrowserError("Control changed; inspect again")
        if current["disabled"]:
            raise BrowserError("Control is disabled or read-only")
        target.metadata = current
        return target

    def count_action(self):
        if self.actions >= self.settings.browser.max_actions:
            raise BrowserError("Browser action budget reached")
        self.actions += 1

    def is_submission(self, target: Target, purpose: str) -> bool:
        m = target.metadata
        if purpose == "submit":
            return True
        label = m["label"].casefold()
        next_step = bool(re.search(r"\b(next|continue|back|previous|avanti|indietro)\b", label))
        final = bool(re.search(r"\b(submit|send|finish|invia|conferma)\b", label))
        return final or (m["form"] and m["type"] == "submit" and not next_step)

    def click(self, ref: str, purpose: str, submitting: bool = False):
        target = self.target(ref)
        if self.is_submission(target, purpose) and not submitting:
            raise BrowserError("Use submit_application for final or ambiguous submit controls")
        if target.metadata["kind"] in {"checkbox", "radio", "option"}:
            raise BrowserError("Use answer_fields for answer choices")
        self.count_action()
        target.element.click(timeout=7000, no_wait_after=True)
        self.settle()

    def fill(self, ref: str, value: str | bool):
        target = self.target(ref)
        e, m = target.element, target.metadata
        self.count_action()
        kind = m["kind"]
        if kind in {"password", "file", "submit", "button", "a"}:
            raise BrowserError("This field needs a different tool or human input")
        if kind == "select":
            matches = [o for o in m["options"] if str(value) in {o["label"], o["value"]}]
            if len(matches) != 1:
                raise BrowserError("Choose exactly one option from the observation")
            e.select_option(value=matches[0]["value"], timeout=7000)
            if e.input_value() != matches[0]["value"]:
                raise BrowserError("Selection did not persist")
        elif kind in {"radio", "checkbox"}:
            if type(value) is not bool:
                raise BrowserError("Use a boolean for radio/checkbox controls")
            if m["tag"] == "input":
                e.set_checked(value, timeout=7000)
                if e.is_checked() != value:
                    raise BrowserError("Checked state did not persist")
            else:
                current = e.get_attribute("aria-checked") == "true"
                if current != value:
                    e.click(timeout=7000)
                if (e.get_attribute("aria-checked") == "true") != value:
                    raise BrowserError("Custom checked state did not persist")
        elif kind == "option":
            if value is not True:
                raise BrowserError("Use true to select an observed option")
            e.click(timeout=7000)
        elif isinstance(value, str):
            e.fill(value, timeout=7000)
            actual = e.evaluate("el=>el.isContentEditable?el.innerText:el.value")
            if actual != value:
                raise BrowserError("Entered answer did not persist")
        else:
            raise BrowserError("Text controls need a string")
        self.settle()

    def upload(self, ref: str, path):
        target = self.target(ref)
        if target.metadata["kind"] != "file":
            raise BrowserError("Upload requires a file input")
        self.count_action()
        target.element.set_input_files(str(path), timeout=10000)
        self.settle()
        if target.element.evaluate("el=>el.files[0]?.name") != path.name:
            raise BrowserError("Attachment was not accepted")

    def invalid_fields(self) -> list[str]:
        invalid = []
        for target in self.targets.values():
            e = target.element
            if not e.evaluate("""el => {
                if (el.disabled || el.getAttribute('aria-disabled') === 'true') return true;
                if (el.validity && !el.validity.valid) return false;
                if (el.getAttribute('aria-invalid') === 'true') return false;
                if (el.getAttribute('aria-required') === 'true') {
                    const role = el.getAttribute('role');
                    if (role === 'checkbox') return el.getAttribute('aria-checked') === 'true';
                    if (role === 'textbox' || role === 'combobox')
                        return Boolean((el.value || el.textContent || '').trim());
                }
                return true;
            }"""):
                invalid.append(target.metadata["label"])
        return invalid
