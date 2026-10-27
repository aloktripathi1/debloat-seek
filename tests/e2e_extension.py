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
EXTENSION = ROOT / "extension"
FIXTURE = (ROOT / "tests" / "fixtures" / "seek-fixture.html").read_text(encoding="utf-8")
OVERVIEW_FIXTURE = (ROOT / "tests" / "fixtures" / "course-overview-fixture.html").read_text(encoding="utf-8")
ASSESSMENT_FIXTURE = (ROOT / "tests" / "fixtures" / "assessment-fixture.html").read_text(encoding="utf-8")
ASSIGNMENT_FIXTURE = (ROOT / "tests" / "fixtures" / "assignment-fixture.html").read_text(encoding="utf-8")
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
    "header": False,
    "transcript": False,
    "answers": False,
    "objectives": False,
    "announcements": False,
    "forum": False,
    "calculator": False,
    "theme": "system"
}

BOOLEAN_SETTINGS = {
    key: value for key, value in DEFAULT_SETTINGS.items() if key != "theme"
}

ATTRIBUTES = {
    "unitNav": "data-seek-unit-nav",
    "overview": "data-seek-overview",
    "divider": "data-seek-divider",
    "header": "data-seek-header",
    "transcript": "data-seek-transcript",
    "answers": "data-seek-answers",
    "objectives": "data-seek-objectives",
    "announcements": "data-seek-announcements",
    "forum": "data-seek-forum",
    "calculator": "data-seek-calculator"
}

TARGETS = {
    "unitNav": 'nav.unit-nav[aria-label="Previous and next unit"]',
    "overview": '.lead button[aria-label="Overview"]',
    "overviewHost": '.lead app-button[label="Overview"]',
    "divider": '.lead > span.divider',
    "transcript": 'app-lesson-view aside.transcript-panel',
    "objectives": 'app-lesson-view .objectives',
    "objectivesTab": 'app-lesson-view [data-seek-objectives-tab]',
    "objectivesOnlyBar": 'app-lesson-view [data-seek-objectives-only]',
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

    url = request.url.rstrip("/")

    if url.endswith("/courses/empty"):
        body = MINIMAL
    elif url.endswith("/courses/overview"):
        body = OVERVIEW_FIXTURE
    elif url.endswith("/courses/assessment"):
        body = ASSESSMENT_FIXTURE
    elif url.endswith("/courses/assignment"):
        body = ASSIGNMENT_FIXTURE
    else:
        body = FIXTURE

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


def computed_style(page, selector, property_name):
    return page.locator(selector).first.evaluate(
        "(element, propertyName) => getComputedStyle(element).getPropertyValue(propertyName).trim()",
        property_name
    )


def theme_surface(page):
    return page.evaluate(
        "() => getComputedStyle(document.documentElement).getPropertyValue('--color-background-surface-base').trim()"
    )


def popup_surface(popup):
    return popup.evaluate(
        "() => getComputedStyle(document.documentElement).getPropertyValue('--bg').trim()"
    )


def expected_theme_surface(resolved_theme):
    return {
        "light": "#ffffff",
        "dark": "#1b1d29",
        "black": "#000000"
    }[resolved_theme]


def expected_popup_surface(popup):
    return popup.evaluate(
        "() => matchMedia('(prefers-color-scheme: dark)').matches ? '#131417' : '#f2f3f4'"
    )


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


def check_theme(page, expected_setting):
    expected_resolved = page.evaluate(
        """(theme) => theme === 'system'
            ? (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
            : theme""",
        expected_setting
    )
    actual_setting = page.evaluate("() => document.documentElement.getAttribute('data-seek-theme-setting')")
    actual_resolved = page.evaluate("() => document.documentElement.getAttribute('data-seek-theme')")
    actual_seek = page.evaluate("() => document.documentElement.getAttribute('data-theme')")

    check(actual_setting == expected_setting,
          f"theme setting is {expected_setting} (got {actual_setting})")
    check(actual_resolved == expected_resolved,
          f"theme resolves to {expected_resolved} (got {actual_resolved})")
    check(actual_seek == ("light" if expected_resolved == "light" else "dark"),
          f"SEEK data-theme matches {expected_resolved}")

    return expected_resolved


def check_default_page(page, theme="system"):
    resolved_theme = check_theme(page, theme)
    check(theme_surface(page) == expected_theme_surface(resolved_theme),
          f"page surface matches {resolved_theme} theme")

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


def check_stock_lesson(page):
    checks = [
        ('.lesson-view', 'padding', '16px', "lesson surface keeps SEEK's original padding"),
        ('.lesson-view', 'gap', '8px', "lesson surface keeps SEEK's original column gap"),
        ('.unit-view .title-bar .title', 'font-size', '14px',
         "lesson title keeps SEEK's original type scale"),
        ('.lesson-view .video-container', 'border-radius', '0px',
         "video player keeps SEEK's original shape")
    ]

    for selector, property_name, expected, label in checks:
        actual = computed_style(page, selector, property_name)
        check(actual == expected, f"{label} ({property_name}: {actual})")

    check_hidden(page, TARGETS["objectives"], False, "objectives panel stays visible by default")
    check_hidden(page, TARGETS["objectivesTab"], False, "objectives tab stays visible by default")
    check_hidden(page, TARGETS["objectivesOnlyBar"], False,
                 "objectives-only tab bar stays visible by default")
    check_hidden(page, "#decoy-objectives", False, "unrelated objectives panel")


def check_assignment_review(page, hidden):
    header = 'app-assessment-question-view .evaluated-answer > .header'
    badge = 'app-assessment-question-view .evaluated-answer .reveal-badge'
    feedback = 'app-assessment-question-view .evaluated-answer .choice-feedback'
    wrong_choice = 'app-assessment-question-view .evaluated-answer .choice.is-wrong'
    expected_choice = 'app-assessment-question-view .evaluated-answer .choice.is-expected'
    selected_radio = 'app-assessment-question-view .evaluated-answer .choice .radio.is-checked'
    radio_dot = 'app-assessment-question-view .evaluated-answer .choice .radio-dot'
    checkbox_icon = 'app-assessment-question-view .evaluated-answer .choice .checkbox.is-checked svg'
    answer_label = 'app-assessment-question-view .evaluated-answer .short-answer .answer-label'
    short_answer = 'app-assessment-question-view .evaluated-answer .short-answer .show-submission'
    chip_badge = 'app-assessment-question-view .chip.correct .badge'
    instructions_badge = 'app-assessment-question-view .chip.instructions .badge'
    instructions_circle = 'app-assessment-question-view .chip.instructions .circle'
    chip_circle = 'app-assessment-question-view .chip.correct.current .circle'
    chip_current = 'app-assessment-question-view .chip.correct.current'
    success_cell = 'app-assessment-question-view .cell.has-success'
    incorrect_panel = 'app-assessment-question-view .evaluated-answer.incorrect'
    linear_header = ('app-assessment-question-view app-assessment-linear-view '
                     '.linear-view .evaluated-answer .eval-header')
    linear_text = ('app-assessment-question-view app-assessment-linear-view '
                   '.linear-view .evaluated-answer .eval-text')
    linear_feedback = 'app-assessment-question-view app-assessment-linear-view .linear-view .feedback'
    linear_incorrect = ('app-assessment-question-view app-assessment-linear-view '
                        '.linear-view .evaluated-answer.incorrect')

    if hidden:
        check_hidden(page, header, True, "reviewed answer header is hidden")
        check_hidden(page, badge, True, "correct/expected badges are hidden")
        check_hidden(page, feedback, True, "per-choice feedback is hidden")
        check_hidden(page, radio_dot, True, "selected radio marker is hidden")
        check_hidden(page, checkbox_icon, True, "checked checkbox marker is hidden")
        check_hidden(page, answer_label, True, "short-answer label is hidden")
        check_hidden(page, short_answer, True, "submitted and expected short answers are hidden")
        check_hidden(page, chip_badge, True, "question correctness badges are hidden")
        check_hidden(page, linear_header, True, "list-view verdict header is hidden")
        check_hidden(page, linear_text, True, "list-view verdict text is hidden")
        check_hidden(page, linear_feedback, True, "list-view feedback is hidden")
        check(computed_style(page, linear_incorrect, 'border-color') == 'rgb(223, 228, 237)',
              "list-view answer panel border is neutralised")
        check_hidden(page, instructions_badge, False, "instructions chip badge stays visible")
        check(computed_style(page, instructions_circle, 'background-color') == 'rgb(224, 242, 254)',
              "instructions chip keeps its own colour")

        check(computed_style(page, wrong_choice, 'background-color') == 'rgb(249, 249, 250)',
              "wrong choice uses the neutral surface")
        check(computed_style(page, expected_choice, 'background-color') == 'rgb(249, 249, 250)',
              "expected choice uses the neutral surface")
        check(computed_style(page, wrong_choice, 'border-color') == 'rgba(0, 0, 0, 0)',
              "wrong choice border is neutralised")
        check(computed_style(page, expected_choice, 'border-style') == 'solid',
              "expected choice dashed border is neutralised")
        check(computed_style(page, selected_radio, 'border-color') == 'rgb(223, 228, 237)',
              "selected radio border is neutralised")
        check(computed_style(page, success_cell, 'border-color') == 'rgb(223, 228, 237)',
              "review cell border is neutralised")
        check(computed_style(page, incorrect_panel, 'border-color') == 'rgb(223, 228, 237)',
              "review panel border is neutralised")
        check(computed_style(page, chip_circle, 'background-color') == 'rgb(246, 246, 246)',
              "question chips lose correctness colour")
        check(computed_style(page, chip_circle, 'color') == 'rgb(36, 36, 36)',
              "question chip numbers use the default text colour")
        check(computed_style(page, chip_current, 'border-color') == 'rgb(36, 36, 36)',
              "current question keeps a neutral marker")
    else:
        check_hidden(page, header, False, "reviewed answer header is visible")
        check_hidden(page, badge, False, "correct/expected badges are visible")
        check_hidden(page, feedback, False, "per-choice feedback is visible")
        check_hidden(page, radio_dot, False, "selected radio marker is visible")
        check_hidden(page, checkbox_icon, False, "checked checkbox marker is visible")
        check_hidden(page, answer_label, False, "short-answer label is visible")
        check_hidden(page, short_answer, False, "submitted and expected short answers are visible")
        check_hidden(page, chip_badge, False, "question correctness badges are visible")
        check_hidden(page, linear_header, False, "list-view verdict header is visible")
        check_hidden(page, linear_text, False, "list-view verdict text is visible")
        check_hidden(page, linear_feedback, False, "list-view feedback is visible")
        check(computed_style(page, linear_incorrect, 'border-color') == 'rgb(217, 45, 32)',
              "list-view answer panel keeps SEEK's error border")
        check_hidden(page, instructions_badge, False, "instructions chip badge is visible by default")

        check(computed_style(page, wrong_choice, 'background-color') == 'rgb(254, 243, 242)',
              "wrong choice keeps SEEK's error tint")
        check(computed_style(page, expected_choice, 'background-color') == 'rgb(255, 250, 235)',
              "expected choice keeps SEEK's warning tint")
        check(computed_style(page, success_cell, 'border-color') == 'rgb(3, 152, 85)',
              "review cell keeps SEEK's success border")
        check(computed_style(page, incorrect_panel, 'border-color') == 'rgb(217, 45, 32)',
              "review panel keeps SEEK's error border")
        check(computed_style(page, chip_circle, 'background-color') == 'rgb(3, 152, 85)',
              "current question keeps its correctness colour")
        check(computed_style(page, chip_current, 'border-color') == 'rgb(3, 152, 85)',
              "current question keeps its correctness border")


def check_overview_redesign(page):
    checks = [
        ('.overview-page', 'padding', '24px', 'course overview uses the page rhythm'),
        ('.overview-page', 'gap', '24px', 'course overview uses consistent spacing'),
        ('.overview-card', 'border-radius', '14px', 'course overview card uses the shared radius'),
        ('.course-header', 'padding', '24px', 'course header has generous padding'),
        ('.course-header', 'background-color', 'rgb(249, 249, 250)', 'course header uses the subtle surface'),
        ('.course-title', 'font-size', '22px', 'course title has clear hierarchy'),
        ('.course-title', 'font-weight', '700', 'course title has strong emphasis'),
        ('.module-card', 'border-radius', '14px', 'module cards use the shared radius'),
        ('.module-card', 'padding', '16px', 'module cards use consistent padding'),
        ('.widget', 'border-radius', '14px', 'side widgets use the shared radius'),
        ('.due-item', 'padding', '12px 8px', 'upcoming items use compact spacing')
    ]

    for selector, property_name, expected, label in checks:
        actual = computed_style(page, selector, property_name)
        check(actual == expected, f"{label} ({property_name}: {actual})")

    columns = computed_style(page, '.overview-page', 'grid-template-columns')
    check(len(columns.split()) == 2, f"course overview removes the empty left rail ({columns})")
    check(computed_style(page, '.overview-side', 'width') == '300px',
          "course overview keeps one supporting rail")

    page.locator('.module-card').first.hover()
    page.wait_for_timeout(220)
    check(computed_style(page, '.module-card', 'transform') == 'matrix(1, 0, 0, 1, 0, -1)',
          "module cards lift subtly on hover")

    page.locator('.module-card').first.focus()
    check(computed_style(page, '.module-card', 'outline-width') == '2px',
          "module cards have a visible keyboard focus ring")

    page.emulate_media(reduced_motion='reduce')
    page.wait_for_timeout(50)
    durations = computed_style(page, '.module-card', 'transition-duration')
    check(
        all(float(part.strip().rstrip('s')) <= 0.001 for part in durations.split(',') if part.strip()),
        f"reduced motion removes long transitions ({durations})"
    )
    page.emulate_media(reduced_motion='no-preference', color_scheme='light')

    check(computed_style(page, '.continue-learning .btn', 'border-radius') == '8px',
          "course overview primary action uses the compact radius")
    check(computed_style(page, '.continue-learning .btn', 'background-color') not in ('rgba(0, 0, 0, 0)', 'transparent'),
          "course overview primary action has a filled primary surface")
    check(computed_style(page, '.module-status', 'border-radius') == '999px',
          "module status uses a quiet pill")
    check(computed_style(page, '.module-progress', 'height') == '4px',
          "module progress uses a slim track")

    original_viewport = page.viewport_size

    for width, height, label in [(768, 900, 'tablet'), (390, 844, 'phone')]:
        page.set_viewport_size({'width': width, 'height': height})
        page.wait_for_timeout(150)
        overflow = page.evaluate("() => document.documentElement.scrollWidth > window.innerWidth")
        check(not overflow, f"course overview has no horizontal overflow at {label} width")

        side_top = page.evaluate("() => document.querySelector('.overview-side').getBoundingClientRect().top")
        modules_top = page.evaluate("() => document.querySelector('.modules').getBoundingClientRect().top")
        check(side_top > modules_top, f"supporting rail follows course contents at {label} width")

    page.set_viewport_size(original_viewport)
    page.wait_for_timeout(100)


def check_assessment_redesign(page):
    checks = [
        ('.pa-start-page', 'padding', '24px', 'assessment start page uses the page rhythm'),
        ('.assessment-instructions', 'border-radius', '14px', 'assessment instructions use the shared radius'),
        ('.submission-overview', 'border-radius', '14px', 'submission overview uses the shared radius'),
        ('.submission-overview', 'padding', '24px', 'submission overview has generous padding'),
        ('.submission-overview', 'background-color', 'rgb(249, 249, 250)',
         'submission overview uses the subtle surface'),
        ('.card-title', 'font-size', '11px', 'submission label uses the compact type scale'),
        ('.card-title', 'font-weight', '600', 'submission label has clear emphasis'),
        ('.earned', 'font-size', '32px', 'submission score has strong hierarchy'),
        ('.earned', 'font-weight', '700', 'submission score has strong emphasis'),
        ('.submission-toolbar', 'border-radius', '10px', 'submission toolbar uses the compact radius'),
        ('.test-case-card', 'border-radius', '10px', 'test cases use the compact radius'),
        ('.test-case-card', 'background-color', 'rgb(249, 249, 250)',
         'test cases use the subtle surface')
    ]

    for selector, property_name, expected, label in checks:
        actual = computed_style(page, selector, property_name)
        check(actual == expected, f"{label} ({property_name}: {actual})")


def get_popup_states(popup):
    return popup.eval_on_selector_all(
        "input[data-setting]",
        """elements => Object.fromEntries(
            elements.map(element => [element.dataset.setting, element.checked])
        )"""
    )


def get_popup_theme(popup):
    return popup.eval_on_selector(
        '[data-theme-option][aria-checked="true"]',
        "element => element.dataset.themeOption"
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


def set_theme(popup, page, theme):
    button = popup.locator(f'[data-theme-option="{theme}"]')
    changed = button.get_attribute("aria-checked") != "true"

    if changed:
        button.click()

    page.wait_for_function(
        "(theme) => document.documentElement.getAttribute('data-seek-theme-setting') === theme",
        arg=theme,
        timeout=5000
    )

    expected_resolved = page.evaluate(
        """(theme) => theme === 'system'
            ? (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
            : theme""",
        theme
    )

    page.wait_for_function(
        """([theme, resolved]) => {
            const root = document.documentElement;
            return root.getAttribute('data-seek-theme-setting') === theme
                && root.getAttribute('data-seek-theme') === resolved
                && root.getAttribute('data-theme') === (resolved === 'light' ? 'light' : 'dark');
        }""",
        arg=[theme, expected_resolved],
        timeout=5000
    )

    if changed:
        popup.wait_for_function(
            "() => document.querySelector('#status')?.textContent.startsWith('Saved')",
            timeout=5000
        )
        status = popup.locator("#status").inner_text()
        check(status.startswith("Saved"), f"{theme} theme saved (status: {status})")

    check(button.get_attribute("aria-checked") == "true", f"{theme} theme is selected in the popup")
    check_theme(page, theme)


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
                    f"--disable-extensions-except={EXTENSION}",
                    f"--load-extension={EXTENSION}",
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
                page.emulate_media(color_scheme="light")
                page.goto("https://seek.study.iitm.ac.in/courses/test", wait_until="domcontentloaded")
                wait_for_root(page, BOOLEAN_SETTINGS)

                print("\nInitial defaults")
                check_default_page(page)

                print("\nStock lesson page")
                check_stock_lesson(page)

                page.goto("https://seek.study.iitm.ac.in/courses/overview", wait_until="domcontentloaded")
                wait_for_root(page, BOOLEAN_SETTINGS)
                check_overview_redesign(page)

                page.goto("https://seek.study.iitm.ac.in/courses/assessment", wait_until="domcontentloaded")
                wait_for_root(page, BOOLEAN_SETTINGS)
                check_assessment_redesign(page)

                page.goto("https://seek.study.iitm.ac.in/courses/test", wait_until="domcontentloaded")
                wait_for_root(page, BOOLEAN_SETTINGS)

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

                check(get_popup_states(popup) == BOOLEAN_SETTINGS, "popup starts with safe boolean defaults")
                check(popup.locator("#summary").inner_text() == "3 on · 7 off",
                      "popup summary reports three on and seven off")
                check(popup.locator("a.source-link").get_attribute("href")
                      == "https://github.com/aloktripathi1/debloat-seek",
                      "popup links to the public source repository")
                check(get_popup_theme(popup) == "system", "popup starts in System theme")
                check(get_stored_settings(popup) == DEFAULT_SETTINGS, "defaults are persisted in chrome.storage.sync")

                print("\nTheme modes")
                popup_system_surface = expected_popup_surface(popup)

                set_theme(popup, page, "dark")
                check(theme_surface(page) == expected_theme_surface("dark"),
                      "SEEK uses the soft dark surface")
                check(popup_surface(popup) == popup_system_surface,
                      "extension panel keeps its own system theme")
                check(popup.evaluate("() => document.documentElement.getAttribute('data-theme')") == "system",
                      "extension panel is not recolored by the SEEK theme")

                set_theme(popup, page, "black")
                check(theme_surface(page) == "#000000", "SEEK uses a true black surface")
                check(popup_surface(popup) == popup_system_surface,
                      "extension panel stays unchanged in Black mode")

                set_theme(popup, page, "light")
                check(theme_surface(page) == "#ffffff", "SEEK uses the light surface")
                check(popup_surface(popup) == popup_system_surface,
                      "extension panel stays unchanged in Light mode")

                set_theme(popup, page, "system")
                resolved_system = page.evaluate(
                    "() => matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'"
                )
                check(theme_surface(page) == expected_theme_surface(resolved_system),
                      f"SEEK follows system theme ({resolved_system})")
                check(popup_surface(popup) == popup_system_surface,
                      "extension panel still follows the operating system")

                print("\nOptional toggles are independent")
                set_toggle(popup, page, "transcript", True)
                check_hidden(page, TARGETS["transcript"], True, "transcript panel after enabling")
                check_hidden(page, TARGETS["announcements"], False, "announcements unaffected by transcript")
                check_hidden(page, TARGETS["forum"], False, "forum unaffected by transcript")
                check_hidden(page, TARGETS["unitNav"], True, "unit navigation unaffected by transcript")

                set_toggle(popup, page, "objectives", True)
                check_hidden(page, TARGETS["objectives"], True, "objectives panel after enabling")
                check_hidden(page, TARGETS["objectivesTab"], True, "objectives tab after enabling")
                check_hidden(page, TARGETS["objectivesOnlyBar"], True,
                             "objectives-only tab bar after enabling")
                check_hidden(page, "#decoy-objectives", False, "unrelated objectives panel unaffected")
                check_hidden(page, TARGETS["announcements"], False, "announcements unaffected by objectives")
                check_hidden(page, TARGETS["forum"], False, "forum unaffected by objectives")

                set_toggle(popup, page, "objectives", False)
                check_hidden(page, TARGETS["objectives"], False, "objectives panel restored")
                check_hidden(page, TARGETS["objectivesTab"], False, "objectives tab restored")

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

                print("\nAssignment answer practice mode")
                page.goto("https://seek.study.iitm.ac.in/courses/assignment", wait_until="domcontentloaded")
                page.wait_for_function(
                    """() => document.documentElement.getAttribute('data-seek-cleaner') === 'active'
                        && document.documentElement.getAttribute('data-seek-answers') === 'off'""",
                    timeout=5000
                )
                check_assignment_review(page, False)
                set_toggle(popup, page, "answers", True)
                check_assignment_review(page, True)

                fresh_assignment = context.new_page()
                fresh_assignment.on("pageerror", lambda error: page_errors.append(f"fresh assignment: {error}"))
                fresh_assignment.emulate_media(color_scheme="light")
                fresh_assignment.goto(
                    "https://seek.study.iitm.ac.in/courses/assignment",
                    wait_until="domcontentloaded"
                )
                fresh_assignment.wait_for_function(
                    """() => document.documentElement.getAttribute('data-seek-cleaner') === 'active'
                        && document.documentElement.getAttribute('data-seek-answers') === 'on'""",
                    timeout=5000
                )
                check_assignment_review(fresh_assignment, True)
                fresh_assignment.close()

                set_toggle(popup, page, "answers", False)
                check_assignment_review(page, False)

                page.goto("https://seek.study.iitm.ac.in/courses/test", wait_until="domcontentloaded")
                wait_for_root(page, {
                    **BOOLEAN_SETTINGS,
                    "transcript": True,
                    "announcements": True
                })

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
                all_off = {key: False for key in BOOLEAN_SETTINGS}
                wait_for_root(page, all_off)
                check_hidden(page, TARGETS["unitNav"], False, "unit navigation visible after all-off reload")
                check_hidden(page, TARGETS["overview"], False, "Overview visible after all-off reload")
                check_hidden(page, TARGETS["divider"], False, "divider visible after all-off reload")
                check_hidden(page, TARGETS["calculator"], False, "calculator visible after all-off reload")
                check_hidden(page, TARGETS["header"], False, "course header visible after all-off reload")
                check_theme(page, "system")

                fresh = context.new_page()
                fresh.on("pageerror", lambda error: page_errors.append(f"fresh: {error}"))
                fresh.emulate_media(color_scheme="light")
                fresh.goto("https://seek.study.iitm.ac.in/courses/test", wait_until="domcontentloaded")
                wait_for_root(fresh, all_off)
                check_hidden(fresh, TARGETS["unitNav"], False,
                             "saved settings apply on a newly opened course tab")
                check_hidden(fresh, TARGETS["divider"], False,
                             "saved cleanup settings apply without opening the popup")
                check_theme(fresh, "system")
                fresh.close()

                popup.close()
                popup = open_popup(context, extension_id)
                check(get_popup_states(popup) == all_off,
                      "popup restores the all-off state")

                popup.locator("#restore-defaults").click()
                wait_for_root(page, BOOLEAN_SETTINGS)
                popup.wait_for_function(
                    "() => !document.querySelector('#status')?.textContent.startsWith('Saving')",
                    timeout=5000
                )

                check(get_popup_states(popup) == BOOLEAN_SETTINGS, "Restore defaults resets every toggle")
                check(get_popup_theme(popup) == "system", "Restore defaults resets the theme")
                check(get_stored_settings(popup) == DEFAULT_SETTINGS, "Restore defaults is persisted")
                check_default_page(page)

                print("\nMissing elements and origin coverage")
                page.goto("https://seek.study.iitm.ac.in/courses/empty", wait_until="domcontentloaded")
                wait_for_root(page, BOOLEAN_SETTINGS)
                check(page.locator(TARGETS["unitNav"]).count() == 0, "minimal SEEK course page has no target elements")

                page.goto("https://seek.onlinedegree.iitm.ac.in/courses/test", wait_until="domcontentloaded")
                wait_for_root(page, BOOLEAN_SETTINGS)
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
