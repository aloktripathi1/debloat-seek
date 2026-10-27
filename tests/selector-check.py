#!/usr/bin/env python3
"""Verify Debloat SEEK selectors against the privacy-safe DOM fixture.

Run from the extension directory:
    python3 tests/selector-check.py
"""

from pathlib import Path
import sys

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "seek-fixture.html"
ASSIGNMENT_FIXTURE = ROOT / "tests" / "fixtures" / "assignment-fixture.html"
REAL_DOM = ROOT / "seek.html"

SELECTORS = {
    "unitNav": 'html[data-seek-unit-nav="on"] nav.unit-nav[aria-label="Previous and next unit"]',
    "overview": (
        'html[data-seek-overview="on"] app-bar.course-bar .lead app-button[label="Overview"], '
        'html[data-seek-overview="on"] app-bar.course-bar .lead button[aria-label="Overview"], '
        'html[data-seek-overview="on"] app-bar.course-bar .lead app-button:has(> button[aria-label="Overview"])'
    ),
    "divider": 'html[data-seek-divider="on"] app-bar.course-bar .lead > span.divider',
    "transcript": (
        'html[data-seek-transcript="on"] app-lesson-view aside.transcript-panel.hidden-mobile, '
        'html[data-seek-transcript="on"] app-lesson-view aside.transcript-panel'
    ),
    "objectives": 'html[data-seek-objectives="on"] app-lesson-view .objectives',
    "announcements": (
        'html[data-seek-announcements="on"] app-button[data-announcements-trigger], '
        'html[data-seek-announcements="on"] nav.actions[aria-label="Course actions"] app-button[label="Announcements"], '
        'html[data-seek-announcements="on"] nav.actions[aria-label="Course actions"] app-button:has(button[aria-label^="Announcements"]), '
        'html[data-seek-announcements="on"] nav.actions[aria-label="Course actions"] > button[aria-label^="Announcements"]'
    ),
    "forum": (
        'html[data-seek-forum="on"] nav.actions[aria-label="Course actions"] app-button[label="Forum"], '
        'html[data-seek-forum="on"] nav.actions[aria-label="Course actions"] app-button:has(> button[aria-label="Forum"]), '
        'html[data-seek-forum="on"] nav.actions[aria-label="Course actions"] > button[aria-label="Forum"]'
    ),
    "calculator": (
        'html[data-seek-calculator="on"] nav.actions[aria-label="Course actions"] app-button[label="Calculator"], '
        'html[data-seek-calculator="on"] nav.actions[aria-label="Course actions"] app-button:has(> button[aria-label="Calculator"]), '
        'html[data-seek-calculator="on"] nav.actions[aria-label="Course actions"] > button[aria-label="Calculator"]'
    ),
    "header": 'html[data-seek-header="on"] app-bar.course-bar'
}

ATTRIBUTES = {
    "unitNav": "data-seek-unit-nav",
    "overview": "data-seek-overview",
    "divider": "data-seek-divider",
    "transcript": "data-seek-transcript",
    "objectives": "data-seek-objectives",
    "answers": "data-seek-answers",
    "announcements": "data-seek-announcements",
    "forum": "data-seek-forum",
    "calculator": "data-seek-calculator",
    "header": "data-seek-header"
}

ASSIGNMENT_SELECTORS = {
    "header": (
        'html[data-seek-answers="on"] app-assessment-question-view .evaluated-answer > .header',
        2
    ),
    "revealBadges": (
        'html[data-seek-answers="on"] app-assessment-question-view .evaluated-answer .reveal-badge',
        3
    ),
    "choices": (
        'html[data-seek-answers="on"] app-assessment-question-view .evaluated-answer .choice.is-correct, '
        'html[data-seek-answers="on"] app-assessment-question-view .evaluated-answer .choice.is-expected, '
        'html[data-seek-answers="on"] app-assessment-question-view .evaluated-answer .choice.is-wrong, '
        'html[data-seek-answers="on"] app-assessment-question-view .evaluated-answer .choice.is-selected',
        3
    ),
    "radioDots": (
        'html[data-seek-answers="on"] app-assessment-question-view .evaluated-answer .choice .radio-dot',
        2
    ),
    "checkboxIcons": (
        'html[data-seek-answers="on"] app-assessment-question-view .evaluated-answer '
        '.choice .checkbox.is-checked svg',
        1
    ),
    "shortAnswer": (
        'html[data-seek-answers="on"] app-assessment-question-view .evaluated-answer '
        '.short-answer .answer-label, '
        'html[data-seek-answers="on"] app-assessment-question-view .evaluated-answer '
        '.short-answer .show-submission',
        2
    ),
    "feedback": (
        'html[data-seek-answers="on"] app-assessment-question-view .evaluated-answer .choice-feedback',
        2
    ),
    "chipBadges": (
        'html[data-seek-answers="on"] app-assessment-question-view .chip.correct .badge, '
        'html[data-seek-answers="on"] app-assessment-question-view .chip.incorrect .badge, '
        'html[data-seek-answers="on"] app-assessment-question-view .chip.partial .badge, '
        'html[data-seek-answers="on"] app-assessment-question-view .chip.eval-unanswered .badge',
        4
    ),
    "cellBorders": (
        'html[data-seek-answers="on"] app-assessment-question-view .cell.has-success, '
        'html[data-seek-answers="on"] app-assessment-question-view .cell.has-error, '
        'html[data-seek-answers="on"] app-assessment-question-view .cell.has-warning',
        2
    ),
    "evaluatedBorders": (
        'html[data-seek-answers="on"] app-assessment-question-view '
        '.evaluated-answer.correct, '
        'html[data-seek-answers="on"] app-assessment-question-view '
        '.evaluated-answer.incorrect',
        2
    )
}

failures = []


def check(condition, message):
    if condition:
        print(f"  PASS  {message}")
    else:
        print(f"  FAIL  {message}")
        failures.append(message)


def load_fixture():
    return BeautifulSoup(FIXTURE.read_text(encoding="utf-8"), "html.parser")


def set_states(soup, **states):
    for key, attribute in ATTRIBUTES.items():
        soup.html[attribute] = "on" if states.get(key, False) else "off"


def test_off_states(soup):
    print("\nOff states")
    set_states(soup)
    for key, selector in SELECTORS.items():
        check(len(soup.select(selector)) == 0, f"{key} selector matches nothing when off")


def test_on_states(soup):
    print("\nOn states and target identity")
    set_states(soup, unitNav=True, overview=True, divider=True,
               transcript=True, objectives=True, announcements=True, forum=True,
               calculator=True, header=True)

    unit_navs = soup.select(SELECTORS["unitNav"])
    check(len(unit_navs) == 1, "unitNav matches exactly one navigation")
    check(unit_navs[0].get("aria-label") == "Previous and next unit",
          "unitNav target has the expected accessible label")

    overviews = soup.select(SELECTORS["overview"])
    check(len(overviews) == 2, "overview matches only the host and its button")
    check(any(element.name == "button" and element.get("aria-label") == "Overview"
              for element in overviews), "overview target button is present")
    check(all("decoy" not in (element.get("id") or "") for element in overviews),
          "overview selector does not match the unrelated Overview button")

    dividers = soup.select(SELECTORS["divider"])
    check(len(dividers) == 1, "divider matches exactly one element")
    check(dividers[0].parent.get("class") == ["lead"],
          "divider is scoped to the course-bar .lead container")
    actions_divider = soup.select_one("nav.actions > span.divider")
    check(actions_divider not in dividers,
          "divider selector does not match the course-actions divider")

    transcripts = soup.select(SELECTORS["transcript"])
    check(len(transcripts) == 1, "transcript matches exactly one panel")
    check(transcripts[0].find_parent("app-lesson-view") is not None,
          "transcript is scoped inside app-lesson-view")
    check(soup.select_one("#decoy-transcript") not in transcripts,
          "transcript selector does not match an unrelated transcript panel")

    objectives = soup.select(SELECTORS["objectives"])
    check(len(objectives) == 1, "objectives matches exactly one panel")
    check(objectives[0].find_parent("app-lesson-view") is not None,
          "objectives panel is scoped inside app-lesson-view")
    check(soup.select_one("#decoy-objectives") not in objectives,
          "objectives selector does not match an unrelated objectives panel")

    announcements = soup.select(SELECTORS["announcements"])
    check(len(announcements) == 1, "announcements matches exactly one trigger")
    check(announcements[0].get("data-announcements-trigger") is not None,
          "announcements target has data-announcements-trigger")
    close_button = soup.select_one('button[aria-label="Close announcements"]')
    check(close_button not in announcements,
          "announcements selector does not match the panel close button")
    check(soup.select_one("#decoy-announcements") not in announcements,
          "announcements selector does not match an unrelated button")

    forums = soup.select(SELECTORS["forum"])
    check(len(forums) == 1, "forum matches exactly one trigger")
    check(forums[0].get("label") == "Forum", "forum target is the Forum component")
    check(soup.select_one("#decoy-forum") not in forums,
          "forum selector does not match an unrelated Forum button")

    calculators = soup.select(SELECTORS["calculator"])
    check(len(calculators) == 1, "calculator matches exactly one trigger")
    check(calculators[0].get("label") == "Calculator",
          "calculator target is the Calculator component")
    check(soup.select_one("#decoy-calculator") not in calculators,
          "calculator selector does not match an unrelated Calculator button")

    headers = soup.select(SELECTORS["header"])
    check(len(headers) == 1, "header matches exactly one course bar")
    check(headers[0].get("class") == ["course-bar"],
          "header target is the course-bar host")
    check(soup.select_one("#decoy-app-bar") not in headers,
          "header selector does not match an unrelated app bar")


def test_badge_variant():
    print("\nAnnouncements badge variants")
    soup = load_fixture()
    set_states(soup, announcements=True)
    trigger = soup.select_one("nav.actions[aria-label='Course actions'] app-button[data-announcements-trigger]")
    trigger.button["aria-label"] = "Announcements, 1"
    del trigger["data-announcements-trigger"]
    del trigger["label"]

    check(len(soup.select(SELECTORS["announcements"])) == 1,
          "badge label 'Announcements, 1' still matches without the data attribute")

    trigger.button["aria-label"] = "Announcements, 42"
    check(len(soup.select(SELECTORS["announcements"])) == 1,
          "badge label with a different count still matches")

    trigger.button["aria-label"] = "Announcements"
    check(len(soup.select(SELECTORS["announcements"])) == 1,
          "label without a badge still matches")

    trigger.decompose()
    check(len(soup.select(SELECTORS["announcements"])) == 0,
          "missing announcements trigger is handled gracefully")


def test_assignment_answers():
    print("\nAssignment answer practice mode")
    soup = BeautifulSoup(ASSIGNMENT_FIXTURE.read_text(encoding="utf-8"), "html.parser")
    set_states(soup, answers=True)

    for key, (selector, expected) in ASSIGNMENT_SELECTORS.items():
        check(len(soup.select(selector)) == expected,
              f"assignment {key} matches {expected} element(s) when enabled")

    instructions = soup.select_one("app-assessment-question-view .chip.instructions")
    check(instructions is not None, "instructions chip is present in the review fixture")
    check(instructions not in soup.select(ASSIGNMENT_SELECTORS["chipBadges"][0]),
          "correctness badge selector does not match the instructions chip")

    set_states(soup)
    for key, (selector, _) in ASSIGNMENT_SELECTORS.items():
        check(len(soup.select(selector)) == 0,
              f"assignment {key} selector matches nothing when disabled")

    lesson = load_fixture()
    set_states(lesson, answers=True)
    for key, (selector, _) in ASSIGNMENT_SELECTORS.items():
        check(len(lesson.select(selector)) == 0,
              f"assignment {key} selector does not match lesson markup")


def test_missing_elements():
    print("\nMissing elements")
    soup = BeautifulSoup("<html><body><h1>SEEK</h1></body></html>", "html.parser")
    set_states(soup, unitNav=True, overview=True, divider=True,
               transcript=True, objectives=True, announcements=True, forum=True,
               calculator=True, header=True)
    for key, selector in SELECTORS.items():
        check(len(soup.select(selector)) == 0, f"{key} selector is safe on a page without targets")


def test_real_dom():
    if not REAL_DOM.exists():
        print("\nReal DOM: skipped (seek.html not found)")
        return

    print("\nReal DOM evidence")
    soup = BeautifulSoup(REAL_DOM.read_text(encoding="utf-8"), "html.parser")
    set_states(soup, unitNav=True, overview=True, divider=True,
               transcript=True, objectives=True, announcements=True, forum=True,
               calculator=True, header=True)

    expected = {
        "unitNav": 1,
        "overview": 2,
        "divider": 1,
        "transcript": 1,
        "objectives": 1,
        "announcements": 1,
        "forum": 1,
        "calculator": 1,
        "header": 1
    }

    for key, selector in SELECTORS.items():
        check(len(soup.select(selector)) == expected[key],
              f"real DOM: {key} matches {expected[key]} element(s)")

    divider = soup.select_one(SELECTORS["divider"])
    check(divider is not None and divider.parent.get("class") == ["lead"],
          "real DOM: divider is the course-bar .lead divider")

def main():
    if not FIXTURE.exists():
        print(f"Fixture not found: {FIXTURE}", file=sys.stderr)
        return 1

    soup = load_fixture()
    test_off_states(soup)
    test_on_states(soup)
    test_badge_variant()
    test_assignment_answers()
    test_missing_elements()
    test_real_dom()

    if failures:
        print(f"\n{len(failures)} check(s) failed.")
        return 1

    print("\nAll selector checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
