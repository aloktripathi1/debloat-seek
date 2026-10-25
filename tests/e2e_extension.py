#!/usr/bin/env python3
"""End-to-end browser checks for Debloat SEEK.

Uses Playwright with an unbranded Chrome for Testing build because branded
Google Chrome 137+ ignores --load-extension. The test serves a privacy-safe DOM
fixture from the real SEEK origin and loads the unpacked extension.

Install a test browser once:
    npx --yes @puppeteer/browsers install chrome@stable --path /tmp/opencode/browsers

Run:
    python3 tests/e2e_extension.py
"""

from pathlib import Path
import os
import sys
import tempfile
import time

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = (ROOT / "tests" / "fixtures" / "seek-fixture.html").read_text(encoding="utf-8")
MINIMAL = "<!doctype html><html lang='en'><body><h1>SEEK</h1></body></html>"
SEEK_PATTERNS = [
    "https://seek.study.iitm.ac.in/**",
    "https://seek.onlinedegree.iitm.ac.in/**"
]
STORAGE_KEY = "debloatSeek.settings.v1"

DEFAULT_SETTINGS = {
    "unitNav": True,
    "overview": True,
    "divider": True,
    "transcript": False,
    "announcements": False,
    "forum": False,
    "calculator": False,
    "header": False
}

ATTRIBUTES = {
    "unitNav": "data-seek-unit-nav",
    "overview": "data-seek-overview",
    "divider": "data-seek-divider",
    "transcript": "data-seek-transcript",
    "announcements": "data-seek-announcements",
    "forum": "data-seek-forum",
    "calculator": "data-seek-calculator",
    "header": "data-seek-header"
}

TARGETS = {
    "unitNav": 'nav.unit-nav[aria-label="Previous and next unit"]',
    "overview": '.lead button[aria-label="Overview"]',
    "overviewHost": '.lead app-button[label="Overview"]',
    "divider": '.lead > span.divider',
    "transcript": 'app-lesson-view aside.transcript-panel',
    "announcements": 'nav.actions app-button[data-announcements-trigger]',
    "forum": 'nav.actions app-button[label="Forum"]',
    "calculator": 'nav.actions app-button[label="Calculator"]',
    "header": 'app-bar.course-bar'
}

failures = []
page_errors = []


def check(condition, message):
    if condition:
        print(f"  PASS  {message}")
    else:
        print(f"  FAIL  {message}")
        failures.append(message)


def find_chrome():
    candidates = []

    configured = os.environ.get("SEEK_TEST_CHROME")

    if configured:
        candidates.append(Path(configured))

    candidates.extend(sorted(Path("/tmp/opencode/browsers/chrome").glob("*/chrome-linux64/chrome")))
    candidates.extend(sorted(Path.home().glob(".cache/ms-playwright/chromium-*/chrome-linux64/chrome")))

    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    return None


def route_handler(route):
    request = route.request

    if request.resource_type != "document":
        route.abort()
        return

    body = MINIMAL if request.url.rstrip("/").endswith("/courses/empty") else FIXTURE
    route.fulfill(status=200, content_type="text/html; charset=utf-8", body=body)


def display_of(page, selector):
    return page.locator(selector).first.evaluate("element => getComputedStyle(element).display")


def check_hidden(page, selector, should_be_hidden, label):
    try:
        actual = display_of(page, selector)
    except Exception as error:
        check(False, f"{label}: selector {selector!r} is missing ({error})")
        return

    if should_be_hidden:
        check(actual == "none", f"{label} is hidden (display: {actual})")
    else:
        check(actual != "none", f"{label} is visible (display: {actual})")


def wait_for_root(page, settings):
    expected = {
        ATTRIBUTES[key]: "on" if settings[key] else "off"
        for key in ATTRIBUTES
    }

    page.wait_for_function(
        """(expected) => {
            const root = document.documentElement;
            return root.getAttribute('data-seek-cleaner') === 'active'
                && Object.entries(expected).every(([name, value]) => root.getAttribute(name) === value);
        }""",
        arg=expected,
        timeout=5000
    )


def check_default_page(page):
    check_hidden(page, TARGETS["unitNav"], True, "unit navigation")
    check_hidden(page, TARGETS["overview"], True, "Overview button")
    check_hidden(page, TARGETS["overviewHost"], True, "Overview component host")
    check_hidden(page, TARGETS["divider"], True, "course-bar divider")
    check_hidden(page, TARGETS["transcript"], False, "transcript panel")
    check_hidden(page, TARGETS["announcements"], False, "announcements trigger")
    check_hidden(page, TARGETS["forum"], False, "forum trigger")
    check_hidden(page, TARGETS["calculator"], False, "calculator trigger")
    check_hidden(page, TARGETS["header"], False, "course header bar")

    # These must never be caught by the scoped selectors.
    check_hidden(page, "nav.actions > span.divider", False, "course-actions divider decoy")
    check_hidden(page, "#decoy-overview", False, "unrelated Overview button")
    check_hidden(page, "#decoy-divider", False, "unrelated divider")
    check_hidden(page, "#decoy-unit-nav", False, "unrelated unit navigation")
    check_hidden(page, "#decoy-announcements", False, "unrelated announcements button")
    check_hidden(page, "#decoy-forum", False, "unrelated forum button")
    check_hidden(page, "#decoy-calculator", False, "unrelated calculator button")
    check_hidden(page, "#decoy-app-bar", False, "unrelated app bar")
    check_hidden(page, "#decoy-transcript", False, "unrelated transcript panel")
    check_hidden(page, 'button[aria-label="Close announcements"]', False, "announcements panel close button")


def get_popup_states(popup):
    return popup.eval_on_selector_all(
        "input[data-setting]",
        """elements => Object.fromEntries(
            elements.map(element => [element.dataset.setting, element.checked])
        )"""
    )


def open_popup(context, extension_id):
    popup = context.new_page()
    popup.on("pageerror", lambda error: page_errors.append(f"popup: {error}"))
    popup.goto(f"chrome-extension://{extension_id}/popup.html", wait_until="domcontentloaded")
    popup.wait_for_function(
        "() => document.querySelector('#status')?.textContent.includes('Settings loaded')",
        timeout=5000
    )
    return popup


def set_toggle(popup, page, key, enabled):
    input_locator = popup.locator(f'input[data-setting="{key}"]')

    if input_locator.is_checked() != enabled:
        input_locator.click(force=True)

    page.wait_for_function(
        """([name, value]) => document.documentElement.getAttribute(name) === value""",
        arg=[ATTRIBUTES[key], "on" if enabled else "off"],
        timeout=5000
    )

    popup.wait_for_function(
        "() => !document.querySelector('#status')?.textContent.startsWith('Saving')",
        timeout=5000
    )

    status = popup.locator("#status").inner_text()
    check(status.startswith("Saved"), f"{key} toggle saved (status: {status})")


def get_stored_settings(popup):
    result = popup.evaluate(
        "async (key) => await chrome.storage.sync.get(key)",
        STORAGE_KEY
    )
    payload = result.get(STORAGE_KEY)

    if not payload:
        return None

    return payload.get("settings")


def get_extension_id(context):
    for _ in range(50):
        if context.service_workers:
            return context.service_workers[0].url.split("/")[2]
        time.sleep(0.1)

    return None


def main():
    chrome = find_chrome()

    if not chrome:
        print("SKIP: no Chrome for Testing binary found.", file=sys.stderr)
        print("Install one with: npx --yes @puppeteer/browsers install chrome@stable --path /tmp/opencode/browsers",
              file=sys.stderr)
        return 0

    print(f"Using browser: {chrome}")

    with tempfile.TemporaryDirectory(prefix="debloat-seek-") as user_data:
        with sync_playwright() as playwright:
            context = playwright.chromium.launch_persistent_context(
                user_data,
                headless=True,
                executable_path=chrome,
                args=[
                    f"--disable-extensions-except={ROOT}",
                    f"--load-extension={ROOT}",
                    "--no-first-run",
                    "--no-default-browser-check"
                ]
            )

            try:
                extension_id = get_extension_id(context)
                check(extension_id is not None, "extension service worker loaded")

                if not extension_id:
                    return 1

                for pattern in SEEK_PATTERNS:
                    context.route(pattern, route_handler)

                page = context.new_page()
                page.on("pageerror", lambda error: page_errors.append(f"page: {error}"))
                page.goto("https://seek.study.iitm.ac.in/courses/test", wait_until="domcontentloaded")
                wait_for_root(page, DEFAULT_SETTINGS)

                print("\nInitial defaults")
                check_default_page(page)

                print("\nAngular-style rerender and in-app navigation")
                page.evaluate(
                    """() => {
                        const selectors = [
                            'nav.unit-nav[aria-label="Previous and next unit"]',
                            '.lead app-button[label="Overview"]',
                            '.lead > span.divider',
                            'app-lesson-view aside.transcript-panel',
                            'nav.actions app-button[data-announcements-trigger]',
                            'nav.actions app-button[label="Forum"]',
                            'nav.actions app-button[label="Calculator"]',
                            'app-bar.course-bar'
                        ];

                        for (const selector of selectors) {
                            const element = document.querySelector(selector);
                            if (element) {
                                element.replaceWith(element.cloneNode(true));
                            }
                        }

                        history.pushState({}, '', '/courses/rerendered');
                    }"""
                )
                check_default_page(page)

                print("\nPopup defaults and storage")
                popup = open_popup(context, extension_id)
                popup.wait_for_function(
                    """async (key) => {
                        const result = await chrome.storage.sync.get(key);
                        return Boolean(result[key]);
                    }""",
                    arg=STORAGE_KEY,
                    timeout=5000
                )

                check(get_popup_states(popup) == DEFAULT_SETTINGS, "popup starts with safe defaults")
                check(get_stored_settings(popup) == DEFAULT_SETTINGS, "defaults are persisted in chrome.storage.sync")

                print("\nOptional toggles are independent")
                set_toggle(popup, page, "transcript", True)
                check_hidden(page, TARGETS["transcript"], True, "transcript panel after enabling")
                check_hidden(page, TARGETS["announcements"], False, "announcements unaffected by transcript")
                check_hidden(page, TARGETS["forum"], False, "forum unaffected by transcript")
                check_hidden(page, TARGETS["unitNav"], True, "unit navigation unaffected by transcript")

                set_toggle(popup, page, "announcements", True)
                check_hidden(page, TARGETS["announcements"], True, "announcements after enabling")
                check_hidden(page, TARGETS["transcript"], True, "transcript remains hidden")
                check_hidden(page, TARGETS["forum"], False, "forum unaffected by announcements")

                print("\nAnnouncements badge fallback")
                page.evaluate(
                    """() => {
                        const host = document.querySelector('nav.actions app-button[data-announcements-trigger]');
                        const button = host.querySelector('button');
                        host.removeAttribute('data-announcements-trigger');
                        host.removeAttribute('label');
                        button.setAttribute('aria-label', 'Announcements, 7');
                    }"""
                )
                check_hidden(page, 'nav.actions app-button:has(button[aria-label^="Announcements"])', True,
                             "announcements badge variant with a changed count")

                print("\nCalculator and course header toggles")
                set_toggle(popup, page, "calculator", True)
                check_hidden(page, TARGETS["calculator"], True, "calculator after enabling")
                check_hidden(page, TARGETS["header"], False, "course header unaffected by calculator")
                check_hidden(page, TARGETS["forum"], False, "forum unaffected by calculator")
                check_hidden(page, "#decoy-calculator", False, "unrelated calculator button")

                set_toggle(popup, page, "header", True)
                check_hidden(page, TARGETS["header"], True, "course header after enabling")
                check_hidden(page, TARGETS["unitNav"], True, "unit navigation unaffected by header")
                check_hidden(page, TARGETS["transcript"], True, "transcript unaffected by header")

                set_toggle(popup, page, "header", False)
                check_hidden(page, TARGETS["header"], False, "course header restored")
                check_hidden(page, TARGETS["calculator"], True, "calculator remains hidden")
                check_hidden(page, "#decoy-app-bar", False, "unrelated app bar")

                set_toggle(popup, page, "calculator", False)
                check_hidden(page, TARGETS["calculator"], False, "calculator restored")

                print("\nPersistence after reload")
                set_toggle(popup, page, "calculator", True)
                set_toggle(popup, page, "header", True)
                page.reload(wait_until="domcontentloaded")
                wait_for_root(page, {
                    **DEFAULT_SETTINGS,
                    "transcript": True,
                    "announcements": True,
                    "calculator": True,
                    "header": True
                })
                check_hidden(page, TARGETS["header"], True, "course header persists after reload")
                check_hidden(page, TARGETS["calculator"], True, "calculator persists after reload")
                set_toggle(popup, page, "header", False)
                set_toggle(popup, page, "calculator", False)
                check_hidden(page, TARGETS["header"], False, "course header restored after reload")
                check_hidden(page, TARGETS["calculator"], False, "calculator restored after reload")
                check_hidden(page, TARGETS["transcript"], True, "transcript persists after reload")
                check_hidden(page, TARGETS["announcements"], True, "announcements persists after reload")
                check_hidden(page, TARGETS["forum"], False, "forum still visible after reload")

                set_toggle(popup, page, "forum", True)
                check_hidden(page, TARGETS["forum"], True, "forum after enabling")
                check_hidden(page, TARGETS["transcript"], True, "transcript remains hidden")
                check_hidden(page, TARGETS["announcements"], True, "announcements remains hidden")

                print("\nDisabling optional toggles restores elements")
                set_toggle(popup, page, "transcript", False)
                check_hidden(page, TARGETS["transcript"], False, "transcript restored")
                check_hidden(page, TARGETS["announcements"], True, "announcements still hidden")
                check_hidden(page, TARGETS["forum"], True, "forum still hidden")

                set_toggle(popup, page, "announcements", False)
                check_hidden(page, TARGETS["announcements"], False, "announcements restored")
                check_hidden(page, TARGETS["forum"], True, "forum still hidden")

                set_toggle(popup, page, "forum", False)
                check_hidden(page, TARGETS["forum"], False, "forum restored")

                print("\nDefault toggles are independent")
                set_toggle(popup, page, "unitNav", False)
                check_hidden(page, TARGETS["unitNav"], False, "unit navigation restored")
                check_hidden(page, TARGETS["overview"], True, "Overview still hidden")
                check_hidden(page, TARGETS["divider"], True, "divider still hidden")

                set_toggle(popup, page, "overview", False)
                check_hidden(page, TARGETS["overview"], False, "Overview restored")
                check_hidden(page, TARGETS["divider"], True, "divider still hidden")

                set_toggle(popup, page, "divider", False)
                check_hidden(page, TARGETS["divider"], False, "divider restored")

                print("\nAll-off persistence and Restore defaults")
                page.reload(wait_until="domcontentloaded")
                wait_for_root(page, {key: False for key in DEFAULT_SETTINGS})
                check_hidden(page, TARGETS["unitNav"], False, "unit navigation visible after all-off reload")
                check_hidden(page, TARGETS["overview"], False, "Overview visible after all-off reload")
                check_hidden(page, TARGETS["divider"], False, "divider visible after all-off reload")
                check_hidden(page, TARGETS["calculator"], False, "calculator visible after all-off reload")
                check_hidden(page, TARGETS["header"], False, "course header visible after all-off reload")

                popup.close()
                popup = open_popup(context, extension_id)
                check(get_popup_states(popup) == {key: False for key in DEFAULT_SETTINGS},
                      "popup restores the all-off state")

                popup.locator("#restore-defaults").click()
                wait_for_root(page, DEFAULT_SETTINGS)
                popup.wait_for_function(
                    "() => !document.querySelector('#status')?.textContent.startsWith('Saving')",
                    timeout=5000
                )

                check(get_popup_states(popup) == DEFAULT_SETTINGS, "Restore defaults resets every toggle")
                check(get_stored_settings(popup) == DEFAULT_SETTINGS, "Restore defaults is persisted")
                check_default_page(page)

                print("\nMissing elements and origin coverage")
                page.goto("https://seek.study.iitm.ac.in/courses/empty", wait_until="domcontentloaded")
                wait_for_root(page, DEFAULT_SETTINGS)
                check(page.locator(TARGETS["unitNav"]).count() == 0, "minimal SEEK course page has no target elements")

                page.goto("https://seek.onlinedegree.iitm.ac.in/courses/test", wait_until="domcontentloaded")
                wait_for_root(page, DEFAULT_SETTINGS)
                check_default_page(page)

                context.route(
                    "https://example.com/**",
                    lambda route: route.fulfill(
                        status=200,
                        content_type="text/html; charset=utf-8",
                        body=MINIMAL
                    )
                )
                other = context.new_page()
                other.goto("https://example.com/", wait_until="domcontentloaded")
                other.wait_for_timeout(400)
                check(other.evaluate("document.documentElement.hasAttribute('data-seek-cleaner')") is False,
                      "content script does not run on non-SEEK origins")

                print("\nRuntime errors")
                check(len(page_errors) == 0, f"no page errors were reported ({page_errors})")

            finally:
                context.close()

    if failures:
        print(f"\n{len(failures)} browser check(s) failed.")
        return 1

    print("\nAll browser checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
