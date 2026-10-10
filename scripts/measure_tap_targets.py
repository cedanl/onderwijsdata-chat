#!/usr/bin/env -S uv run --quiet --python 3 --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["playwright==1.63.0"]
# ///
"""Measure the tap targets of the chat page, sidebar and dialogs in a headless browser (#490).

    uv run --python 3 scripts/measure_tap_targets.py http://127.0.0.1:8000
    uv run --python 3 scripts/measure_tap_targets.py <base-url> --viewport 390x844 --viewport 1440x900

Run it against a served app (no vite dev server needed). The /api/chat WebSocket is mocked with
one question and one answer, so it makes no LLM calls; the history list, the instellingen and the
app config are mocked too. Per viewport it measures every `button`, `a[href]` and `[role=button]`
on /chat, in the sidebar, in the data-sources dialog and in the settings dialog, and reports:

- every target under 24x24 (WCAG 2.2 AA 2.5.8). Excluded: numbers in a sentence
  (`.citatie-getal`), `.notfound-link`, and inline links in running text (the inline exception);
- at widths up to 1024 (the touch block in styles.css): every named target under 44x44. Named are
  the classes in NAMED and every button in the sidebar and the settings dialog;
- at widths up to 1024: targets whose boxes intersect within one layer (a scroll area or a popover;
  the floating scroll button aside). On wider screens the history actions show on hover, on top of the row;
- icons that grew (resend and copy 14px, history actions 13px) and horizontal overflow on /chat;
- the copied state of the copy button (#492): its "Gekopieerd" label must not be hidden under the
  touch frame, and the widened button keeps the minimum size.

A named class that is not on the page counts as a problem too, unless it is passed with
`--allow-absent` (for example `--allow-absent .scroll-to-bottom-btn` on a viewport so tall that
the answer fits without scrolling).

Exit code 1 if anything is reported. No browser yet:
`uv run --no-project --python 3 --with playwright==1.63.0 playwright install chromium`.
"""

import argparse
import json
import re
import sys

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError  # ty: ignore[unresolved-import]
from playwright.sync_api import sync_playwright  # ty: ignore[unresolved-import]

AA_MIN = 24
TOUCH_MIN = 44
TOUCH_MAX_WIDTH = 1024
NAMED = (
    ".resend-btn, .copy-btn, .modal-close, .modal-overlay-close, .answer-feedback-btn, "
    ".scroll-to-bottom-btn, .message-continue, .data-export-btn"
)
ICONS = {".resend-btn svg": 14, ".copy-btn svg": 14, ".history-action-icon svg": 13}

ANSWER = (
    "In 2024 stonden er 12.345 studenten ingeschreven.\n\n"
    "```python\nprint('reproduceerbaar')\n```\n\n"
    "De cijfers komen van DUO."
)
FIGURE = {"data": [{"type": "bar", "x": ["2023", "2024"], "y": [12000, 12345]}], "layout": {"title": "Studenten"}}
HISTORY = [
    {"id": f"gesprek-{i}", "title": f"Ingeschrevenen hbo, vraag {i}", "timestamp": 1_760_000_000 - i * 3600}
    for i in range(16)  # one more than a page, so "Meer laden" shows
]
INSTELLINGEN = [
    {"naam": "Hogeschool Utrecht", "type": "hbo", "aliassen": ["HU"]},
    {"naam": "Universiteit Utrecht", "type": "wo", "aliassen": ["UU"]},
    {"naam": "ROC Midden Nederland", "type": "mbo", "aliassen": []},
]

MEASURE = """({scope, skip, allNamed, named, overlaps: checkOverlaps}) => {
  const root = scope ? document.querySelector(scope) : document.body;
  if (!root) return null;
  const inRunningText = el => el.tagName === 'A' && getComputedStyle(el).display === 'inline'
    && [...el.parentElement.childNodes].some(n => n !== el && n.textContent.trim());
  // Targets only compete within one layer: a scroll area, or a popover that lies on top of the page.
  const layer = el => {
    for (let p = el.parentElement; p; p = p.parentElement) {
      const style = getComputedStyle(p);
      if (style.overflowY !== 'visible') return p;
      if (['absolute', 'fixed'].includes(style.position) && style.zIndex !== 'auto') return p;
    }
    return document.documentElement;
  };
  const describe = el => {
    const cls = [...el.classList].map(c => '.' + c).join('');
    const name = (el.getAttribute('aria-label') || el.getAttribute('title') || el.textContent || '').trim();
    return `${el.tagName.toLowerCase()}${cls} "${name.slice(0, 40)}"`;
  };
  const els = [...root.querySelectorAll('button, a[href], [role=button]')].filter(el =>
    !el.matches('.citatie-getal, .notfound-link') && !el.closest('[inert]') && !inRunningText(el)
    && !(skip && el.closest(skip)));
  const targets = els.map(el => ({ el, r: el.getBoundingClientRect() })).filter(t => t.r.width || t.r.height);
  const overlaps = [];
  for (let i = 0; checkOverlaps && i < targets.length; i++) {
    for (let j = i + 1; j < targets.length; j++) {
      const a = targets[i], b = targets[j];
      if (a.el.contains(b.el) || b.el.contains(a.el) || layer(a.el) !== layer(b.el)) continue;
      if (a.el.matches('.scroll-to-bottom-btn') || b.el.matches('.scroll-to-bottom-btn')) continue;
      const w = Math.min(a.r.right, b.r.right) - Math.max(a.r.left, b.r.left);
      const h = Math.min(a.r.bottom, b.r.bottom) - Math.max(a.r.top, b.r.top);
      if (w > 0.5 && h > 0.5) overlaps.push(`${describe(a.el)} and ${describe(b.el)}`);
    }
  }
  return {
    targets: targets.map(({ el, r }) => ({
      target: describe(el), w: Math.round(r.width * 10) / 10, h: Math.round(r.height * 10) / 10,
      named: allNamed || el.matches(named),
    })),
    overlaps,
  };
}"""

ICON_SIZES = """(icons) => Object.entries(icons).flatMap(([sel, size]) =>
  [...document.querySelectorAll(sel)].map(svg => svg.getBoundingClientRect())
    .filter(r => r.width && (Math.round(r.width) !== size || Math.round(r.height) !== size))
    .map(r => `${sel} is ${Math.round(r.width)}x${Math.round(r.height)}, expected ${size}x${size}`))"""

# After a copy (#492) the label must be the topmost element at its own centre: on touch the
# button's frame is a positioned ::before, which paints over children that are not positioned.
COPIED_LABEL = """() => {
  const button = document.querySelector('.copy-btn[data-copied]');
  const label = button && button.querySelector(':scope > span');
  if (!label) return { hidden: 'no "Gekopieerd" label in the copied button' };
  const r = label.getBoundingClientRect(), b = button.getBoundingClientRect();
  const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
  return {
    hidden: label.contains(hit) ? null : `"Gekopieerd" is hidden under ${hit ? hit.tagName.toLowerCase() : 'nothing'}`,
    w: Math.round(b.width * 10) / 10, h: Math.round(b.height * 10) / 10,
  };
}"""


def mock_chat(ws):
    """One answer with text, a code block, a data step, a figure and a cut-off end; then an error."""

    def on_message(message):
        if json.loads(message).get("action") != "message":
            return
        events = [
            {"type": "message_start"},
            {"type": "tool_start", "name": "query_data", "label": "Data opgehaald"},
            {"type": "tool_end", "name": "query_data", "export_key": "duo:meting:0:0", "snippet": "print(1)"},
            {"type": "figure", "label": "Studenten per jaar", "figure_json": json.dumps(FIGURE)},
            {"type": "text_delta", "content": ANSWER},
            {"type": "message_end", "content": ANSWER, "truncated": True},
            {"type": "error", "message": "Er ging iets mis bij het ophalen.", "modelafhankelijk": True},
        ]
        for event in events:
            ws.send(json.dumps(event))

    ws.on_message(on_message)


def mock_api(page):
    def history(route):
        if route.request.method != "GET":
            return route.continue_()
        return route.fulfill(json=HISTORY)

    page.route(re.compile(r"/api/conversations(\?.*)?$"), history)
    page.route(re.compile(r"/api/instellingen(\?.*)?$"), lambda route: route.fulfill(json=INSTELLINGEN))
    page.route(
        re.compile(r"/api/config$"),
        lambda route: route.fulfill(json={"dashboards_enabled": True, "feedback_enabled": True}),
    )
    page.route_web_socket(re.compile(r"/api/chat"), mock_chat)


def measure(page, label, scope, skip, all_named, overlaps):
    args = {"scope": scope, "skip": skip, "allNamed": all_named, "named": NAMED, "overlaps": overlaps}
    result = page.evaluate(MEASURE, args)
    if result is None:
        return [f"{label}: {scope} not found"], []
    return result["overlaps"], [dict(t, where=label) for t in result["targets"]]


def show_scroll_button(page, attempts=5):
    """Scroll the message list to the end and back to the top until the scroll-to-bottom button shows.

    The button follows an IntersectionObserver on the end of the list, which reports changes only.
    At 390px the list can stay at the top after the answer, so `scrollTop = 0` alone changes nothing:
    go to the end first. Both steps are asynchronous and a late re-render can pin the list to the
    bottom again, so scroll and wait, a few times.
    """
    for _ in range(attempts):
        page.evaluate("document.querySelector('.chat-messages').scrollTop = 1e6")
        page.wait_for_timeout(200)
        page.evaluate("document.querySelector('.chat-messages').scrollTop = 0")
        try:
            page.wait_for_selector(".scroll-to-bottom-btn", state="visible", timeout=2000)
            return
        except PlaywrightTimeoutError:
            continue


def check_copied_state(page, narrow):
    """Copy the user message; the copied button keeps its tap target and shows its label."""
    page.locator(".message.user .copy-btn-message").click()
    try:
        page.wait_for_selector(".copy-btn[data-copied]", timeout=3000)
    except PlaywrightTimeoutError:
        return ["copy button: no copied state after the click"]
    copied = page.evaluate(COPIED_LABEL)
    minimum = TOUCH_MIN if narrow else AA_MIN
    problems = [f"copy button: {copied['hidden']}"] if copied["hidden"] else []
    if copied.get("w", 0) < minimum or copied.get("h", 0) < minimum:
        problems.append(f"copy button: copied state is {copied.get('w')}x{copied.get('h')}, under {minimum}")
    return problems


def run_viewport(browser, base, width, height, allow_absent=()):
    """All findings for one viewport, plus every target measured."""
    context = browser.new_context(
        viewport={"width": width, "height": height}, permissions=["clipboard-read", "clipboard-write"]
    )
    page = context.new_page()
    page.add_init_script("localStorage.setItem('openEDUdata_onboarded', '1')")
    mock_api(page)
    page.goto(f"{base}/chat", wait_until="networkidle")
    page.locator("textarea.chat-input").fill("Hoeveel studenten stonden er in 2024 ingeschreven?")
    page.locator("textarea.chat-input").press("Enter")
    page.wait_for_selector(".answer-feedback-btn")
    page.wait_for_selector(".message-retry .message-continue")
    page.wait_for_timeout(800)  # plotly and the code highlighter render late
    show_scroll_button(page)

    problems, targets = [], []
    narrow = width <= TOUCH_MAX_WIDTH

    def collect(label, scope=None, all_named=False, skip=None):
        overlaps, found = measure(page, label, scope, skip, all_named, overlaps=narrow)
        problems.extend(f"overlap ({label}): {o}" for o in overlaps)
        targets.extend(found)

    collect("chat", skip=".chat-sidebar")
    problems.extend(page.evaluate(ICON_SIZES, ICONS))
    overflow = page.evaluate("[document.documentElement.scrollWidth, window.innerWidth]")
    if overflow[0] > overflow[1]:
        problems.append(f"horizontal overflow on /chat: scrollWidth {overflow[0]} > {overflow[1]}")
    problems.extend(check_copied_state(page, narrow))

    page.locator(".disclaimer-link").click()
    collect("data sources dialog", '[role="dialog"][aria-label="Databronnen"]')
    page.keyboard.press("Escape")

    page.locator(".navbar-profile-btn").click()
    dialog = page.locator('[role="dialog"][aria-label="Instellingen"]')
    dialog.get_by_role("button", name=re.compile(r"^WO")).click()
    dialog.locator("#settings-instelling").fill("zzzz")
    page.wait_for_selector(".instelling-clear-filter")
    collect("settings dialog", '[role="dialog"][aria-label="Instellingen"]', all_named=True)
    page.keyboard.press("Escape")

    if narrow:
        page.locator(".hamburger-btn").click()
        page.wait_for_timeout(400)  # the drawer slides in
    page.locator(".chat-sidebar .suggested-category-btn").first.click()
    page.locator(".chat-sidebar .history-btn").first.hover()
    page.wait_for_timeout(200)
    collect("sidebar", ".chat-sidebar", all_named=narrow)
    problems.extend(page.evaluate(ICON_SIZES, {".history-action-icon svg": 13}))

    for t in targets:
        if t["w"] < AA_MIN or t["h"] < AA_MIN:
            problems.append(f"under {AA_MIN}x{AA_MIN} ({t['where']}): {t['target']} {t['w']}x{t['h']}")
        elif narrow and t["named"] and (t["w"] < TOUCH_MIN or t["h"] < TOUCH_MIN):
            problems.append(f"under {TOUCH_MIN}x{TOUCH_MIN} ({t['where']}): {t['target']} {t['w']}x{t['h']}")
    absent = [c for c in NAMED.split(", ") if c not in allow_absent and not any(c in t["target"] for t in targets)]
    problems.extend(f"not on the page, so not measured: {c}" for c in absent)
    context.close()
    return problems, targets


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("base_url", help="for example http://127.0.0.1:5410")
    parser.add_argument("--viewport", action="append", help="WIDTHxHEIGHT; default 390x844 and 1440x900")
    parser.add_argument("--verbose", action="store_true", help="also list every target with its size")
    parser.add_argument(
        "--allow-absent", action="append", default=[], metavar="CLASS", help="a named class that may be missing"
    )
    args = parser.parse_args()
    viewports = [tuple(map(int, v.split("x"))) for v in args.viewport or ["390x844", "1440x900"]]

    failed = False
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for width, height in viewports:
            problems, targets = run_viewport(browser, args.base_url.rstrip("/"), width, height, args.allow_absent)
            print(f"{width}x{height}: {len(targets)} targets measured, {len(problems)} problems")
            for problem in problems:
                print(f"  {problem}")
            if args.verbose:
                for t in targets:
                    print(f"  {t['where']}: {t['target']} {t['w']}x{t['h']}{' (named)' if t['named'] else ''}")
            failed = failed or bool(problems)
        browser.close()
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
