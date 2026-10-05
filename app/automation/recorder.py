"""Learn Mode recorder.

The injected script reports clicks, typing, and key presses. Sensitive input
is replaced with a placeholder before it ever reaches Python. Navigation is
observed from Playwright. The script does not interact with CAPTCHAs.
"""

from __future__ import annotations

import os
import threading
import time

from app.automation.browser_manager import BrowserManager
from app.automation.errors import AutomationError, ProfileInUse
from app.automation.secrets import sanitize_type_value, sensitive_kind
from app.database import repositories
from app.models.profile import Profile
from app.models.workflow import ElementTarget, WorkflowStep
from app.utils.constants import ActionType, LockKind, VerificationType
from app.utils.logger import get_logger
from app.utils.redact import redact_text


logger = get_logger("recorder")

DEFAULT_NEW_TAB_URLS = (
    "chrome://new-tab-page/",
    "chrome://newtab/",
    "https://www.google.com/",
)


def normalize_start_url(start_url: str) -> str:
    text = (start_url or "").strip()
    if not text:
        return ""
    if "://" not in text:
        return "https://" + text
    return text


def open_learn_start_page(page, start_url: str = "") -> None:
    """Open the user's New Tab page, or a URL they typed in Learn Mode."""
    targets = []
    normalized = normalize_start_url(start_url)
    if normalized:
        targets.append(normalized)
    else:
        targets.extend(DEFAULT_NEW_TAB_URLS)
    for url in targets:
        try:
            page.goto(url, wait_until="domcontentloaded")
            body = ""
            try:
                body = page.inner_text("body")
            except Exception:
                body = page.url or ""
            if "incorrect profile type" in body.lower():
                continue
            return
        except Exception:
            logger.debug("Could not open Learn Mode start page %s", url, exc_info=True)
    try:
        page.bring_to_front()
    except Exception:
        logger.exception("Could not focus the Learn Mode window")

# Playwright evaluates an init script as a program. A bare arrow function would
# be created and discarded, so this source calls itself.
RECORDER_SCRIPT = r"""
(() => {
  if (window.__btaInstalled) return;
  window.__btaInstalled = true;

  function cssEscapeIdent(value) {
    if (window.CSS && CSS.escape) return CSS.escape(value);
    return String(value).replace(/[^a-zA-Z0-9_-]/g, "\\$&");
  }

  function labelText(el) {
    if (el.id) {
      const label = document.querySelector(`label[for="${cssEscapeIdent(el.id)}"]`);
      if (label && label.innerText) return label.innerText.trim();
    }
    const parentLabel = el.closest("label");
    if (parentLabel) {
      const clone = parentLabel.cloneNode(true);
      clone.querySelectorAll("input,textarea,select,button").forEach((node) => node.remove());
      return (clone.innerText || "").trim();
    }
    return "";
  }

  function accessibleName(el) {
    const aria = el.getAttribute("aria-label");
    if (aria) return aria.trim();
    const labelledby = el.getAttribute("aria-labelledby");
    if (labelledby) {
      const text = labelledby.split(/\s+/).map((id) => {
        const node = document.getElementById(id);
        return node ? node.innerText : "";
      }).join(" ").trim();
      if (text) return text;
    }
    const fromLabel = labelText(el);
    if (fromLabel) return fromLabel.slice(0, 200);
    const title = el.getAttribute("title");
    if (title) return title.trim();
    if (el.innerText && el.innerText.trim() && el.innerText.trim().length <= 120) {
      return el.innerText.trim();
    }
    return "";
  }

  function implicitRole(el) {
    const explicit = el.getAttribute("role");
    if (explicit) return explicit;
    const tag = el.tagName.toLowerCase();
    const type = (el.getAttribute("type") || "").toLowerCase();
    if (tag === "a" && el.hasAttribute("href")) return "link";
    if (tag === "button") return "button";
    if (tag === "textarea") return "textbox";
    if (tag === "select") return "combobox";
    if (tag === "input") {
      if (["submit", "button", "reset"].includes(type)) return "button";
      if (type === "checkbox") return "checkbox";
      if (type === "radio") return "radio";
      return "textbox";
    }
    return "";
  }

  function cssPath(el) {
    if (el.id) return `#${cssEscapeIdent(el.id)}`;
    const testId = el.getAttribute("data-testid");
    if (testId) return `[data-testid="${String(testId).replace(/"/g, '\\"')}"]`;
    const parts = [];
    let node = el;
    while (node && node.nodeType === 1 && parts.length < 6) {
      let part = node.tagName.toLowerCase();
      if (node.id) {
        parts.unshift(`#${cssEscapeIdent(node.id)}`);
        break;
      }
      const parent = node.parentElement;
      if (parent) {
        const same = Array.from(parent.children).filter((child) => child.tagName === node.tagName);
        if (same.length > 1) part += `:nth-of-type(${same.indexOf(node) + 1})`;
      }
      parts.unshift(part);
      node = parent;
    }
    return parts.join(" > ");
  }

  function xpath(el) {
    if (el.id) return `//*[@id="${el.id}"]`;
    const parts = [];
    let node = el;
    while (node && node.nodeType === 1) {
      let index = 1;
      let sibling = node.previousElementSibling;
      while (sibling) {
        if (sibling.tagName === node.tagName) index += 1;
        sibling = sibling.previousElementSibling;
      }
      parts.unshift(`${node.tagName.toLowerCase()}[${index}]`);
      node = node.parentElement;
    }
    return "/" + parts.join("/");
  }

  function describe(el) {
    const rect = el.getBoundingClientRect();
    const attrs = {};
    for (const name of ["id", "name", "type", "placeholder", "href", "data-testid", "aria-label", "autocomplete"]) {
      const value = el.getAttribute(name);
      if (value) attrs[name] = value;
    }
    return {
      role: implicitRole(el),
      name: accessibleName(el).slice(0, 200),
      text: (el.innerText || "").trim().slice(0, 200),
      tag: el.tagName.toLowerCase(),
      label: labelText(el).slice(0, 200),
      placeholder: el.getAttribute("placeholder") || "",
      input_type: el.getAttribute("type") || "",
      attributes: attrs,
      selector: cssPath(el),
      fallback_selector: xpath(el),
      test_id: el.getAttribute("data-testid") || "",
      x: rect.x + rect.width / 2,
      y: rect.y + rect.height / 2
    };
  }

  function sensitiveKind(el, desc) {
    const type = (el.getAttribute("type") || "").toLowerCase();
    const auto = (el.getAttribute("autocomplete") || "").toLowerCase();
    const blob = [desc.name, desc.label, desc.placeholder, desc.attributes.name, desc.attributes.id, auto]
      .join(" ").toLowerCase();
    if (type === "password" || auto.includes("password")) return "PASSWORD";
    if (/seed|mnemonic|recovery phrase/.test(blob)) return "SEED_PHRASE";
    if (/private.?key/.test(blob)) return "PRIVATE_KEY";
    if (/api[-_ ]?key|secret/.test(blob)) return "API_KEY";
    if (/\bpin\b|one[-_ ]?time|\botp\b/.test(blob)) return "PIN";
    if (/\btoken\b/.test(blob)) return "TOKEN";
    if (/password|passwd/.test(blob)) return "PASSWORD";
    return "";
  }

  function send(payload) {
    if (typeof window.__btaRecord === "function") window.__btaRecord(payload);
  }

  let pending = null;
  function flushInput() {
    if (!pending) return;
    const item = pending;
    pending = null;
    send(item);
  }

  document.addEventListener("click", (event) => {
    const el = event.target && event.target.closest
      ? (event.target.closest("button, a, input, select, textarea, label, [role='button'], [role='link']") || event.target)
      : event.target;
    if (!el || el === document.body || el === document.documentElement) return;
    flushInput();
    send({ kind: "click", target: describe(el) });
  }, true);

  function isField(el) {
    return el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement;
  }

  function commitField(el) {
    const desc = describe(el);
    const kind = sensitiveKind(el, desc);
    pending = {
      kind: "type",
      target: desc,
      value: kind ? "" : (el.value ?? ""),
      placeholder: kind ? `{{${kind}}}` : "",
      sensitive: Boolean(kind)
    };
  }

  document.addEventListener("input", (event) => {
    if (isField(event.target)) commitField(event.target);
  }, true);
  document.addEventListener("change", (event) => {
    if (!isField(event.target)) return;
    commitField(event.target);
    flushInput();
  }, true);
  document.addEventListener("focusout", (event) => {
    if (isField(event.target)) flushInput();
  }, true);

  document.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" && event.key !== "Escape") return;
    flushInput();
    const target = event.target instanceof Element ? describe(event.target) : {};
    send({ kind: "key", key: event.key, target });
  }, true);
})();
"""


def _float_or_none(value) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class Recorder:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._steps: list[WorkflowStep] = []
        self._last_url: str | None = None
        self._history: list[str] = []
        self._last_click = 0.0
        self._last_click_signature: tuple[str, str, str] | None = None

    def attach(self, context) -> None:
        context.expose_binding("__btaRecord", self._on_binding)
        context.add_init_script(RECORDER_SCRIPT)
        context.on("framenavigated", self._on_frame)
        context.on("page", self._prime)
        for page in context.pages:
            self._prime(page)

    def steps(self) -> list[WorkflowStep]:
        with self._lock:
            return [step.model_copy(deep=True) for step in self._steps]

    def _prime(self, page) -> None:
        try:
            page.evaluate(RECORDER_SCRIPT)
        except Exception:
            logger.debug("Recorder script was not injected into the current page yet", exc_info=True)

    def _add(self, action: str, target: ElementTarget | None = None, value: str = "") -> None:
        from app.services.settings_service import get_int

        verification = VerificationType.PAGE_LOADED if action == ActionType.OPEN_URL else VerificationType.NONE
        with self._lock:
            logger.info("Recorded %s %s", action, redact_text(value)[:120])
            self._steps.append(
                WorkflowStep(
                    step_number=len(self._steps) + 1,
                    action_type=action,
                    target=target or ElementTarget(),
                    value=value,
                    timeout_ms=get_int("default_timeout_ms"),
                    retry_count=get_int("default_retry_count"),
                    retry_delay_ms=get_int("default_retry_delay_ms"),
                    verification_type=verification,
                )
            )

    def _target_from(self, data: dict) -> ElementTarget:
        raw_attributes = data.get("attributes") or {}
        attributes = {}
        if isinstance(raw_attributes, dict):
            attributes = {
                str(key): str(item)
                for key, item in raw_attributes.items()
                if key != "value" and item is not None
            }
        target = ElementTarget(
            role=str(data.get("role") or ""),
            name=str(data.get("name") or ""),
            text=str(data.get("text") or ""),
            tag=str(data.get("tag") or ""),
            label=str(data.get("label") or ""),
            placeholder=str(data.get("placeholder") or ""),
            input_type=str(data.get("input_type") or ""),
            attributes=attributes,
            selector=str(data.get("selector") or ""),
            fallback_selector=str(data.get("fallback_selector") or ""),
            test_id=str(data.get("test_id") or ""),
            x=_float_or_none(data.get("x")),
            y=_float_or_none(data.get("y")),
        )
        if sensitive_kind(target):
            target.text = ""
        return target

    def _on_binding(self, _source, payload) -> None:
        if not isinstance(payload, dict):
            return
        kind = payload.get("kind")
        if kind == "click":
            target = self._target_from(payload.get("target") or {})
            if target.tag in {"html", "body"}:
                return
            signature = (target.selector, target.name, target.role)
            now = time.monotonic()
            if signature == self._last_click_signature and now - self._last_click < 0.35:
                return
            self._last_click = now
            self._last_click_signature = signature
            self._add(ActionType.CLICK, target)
            return
        if kind == "type":
            target = self._target_from(payload.get("target") or {})
            raw_value = "" if payload.get("sensitive") else str(payload.get("value") or "")
            value = sanitize_type_value(
                target,
                raw_value,
                sensitive=bool(payload.get("sensitive")),
                placeholder=str(payload.get("placeholder") or ""),
            )
            if not value and not payload.get("sensitive"):
                return
            self._add(ActionType.TYPE, target, value)
            return
        if kind == "key":
            key = str(payload.get("key") or "")
            if key not in {"Enter", "Escape"}:
                return
            target = self._target_from(payload.get("target") or {})
            self._add(ActionType.PRESS_KEY, target, key)

    def _remember(self, url: str) -> None:
        self._last_url = url
        if not self._history or self._history[-1] != url:
            self._history.append(url)

    def _on_frame(self, frame) -> None:
        try:
            if frame.parent_frame is not None:
                return
            url = frame.url or ""
            self._prime(frame.page)
        except Exception:
            return
        if not url or url.startswith(("about:", "chrome:", "chrome-extension:", "devtools:")):
            return
        if url == self._last_url:
            return
        if time.monotonic() - self._last_click < 1.0:
            self._remember(url)
            return
        nav_type = ""
        try:
            nav_type = frame.page.evaluate(
                "() => { const entry = performance.getEntriesByType('navigation')[0]; return entry ? entry.type : ''; }"
            )
        except Exception:
            nav_type = ""
        if nav_type == "reload":
            self._add(ActionType.RELOAD, value=url)
            self._remember(url)
            return
        if nav_type == "back_forward":
            if len(self._history) >= 2 and url == self._history[-2]:
                self._history.pop()
                self._last_url = url
                self._add(ActionType.NAVIGATE_BACK, value=url)
                return
            self._add(ActionType.NAVIGATE_FORWARD, value=url)
            self._remember(url)
            return
        self._add(ActionType.OPEN_URL, value=url)
        self._remember(url)


class LearnSession:
    """Owns one visible Chrome window while the user demonstrates a task."""

    def __init__(self) -> None:
        self.recorder = Recorder()
        self.error: str | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._browser: BrowserManager | None = None
        self.profile_id: int | None = None

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def snapshot(self) -> list[WorkflowStep]:
        return self.recorder.steps()

    def start(self, profile: Profile, start_url: str = "") -> None:
        if self.running:
            raise AutomationError("Learn Mode is already running")
        if profile.id is None:
            raise AutomationError("Save the profile before Learn Mode")
        if not repositories.acquire_lock(
            profile.id,
            owner_pid=os.getpid(),
            run_id=None,
            kind=LockKind.LEARN,
        ):
            raise ProfileInUse("Profile currently in use")
        self.error = None
        self.recorder = Recorder()
        self._stop.clear()
        self.profile_id = profile.id
        self._thread = threading.Thread(
            target=self._run,
            args=(profile, start_url.strip()),
            name="bta-learn",
            daemon=True,
        )
        self._thread.start()

    def _run(self, profile: Profile, start_url: str = "") -> None:
        browser = BrowserManager()
        self._browser = browser
        try:
            context = browser.launch(profile)
            self.recorder.attach(context)
            pid = browser.find_pid(profile)
            if profile.id is not None and pid:
                repositories.set_lock_browser_pid(profile.id, pid)
            page = context.pages[-1] if context.pages else context.new_page()
            open_learn_start_page(page, start_url)
            self._stop.wait()
        except Exception as exc:
            self.error = redact_text(str(exc))
            logger.exception("Learn Mode failed")
        finally:
            try:
                browser.close()
            except Exception:
                logger.exception("Learn Mode could not close Chrome")
            if profile.id is not None:
                repositories.release_lock(profile.id, kind=LockKind.LEARN)
            self._browser = None

    def stop(self) -> list[WorkflowStep]:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=20)
        if self.error:
            raise AutomationError(self.error)
        return self.recorder.steps()
