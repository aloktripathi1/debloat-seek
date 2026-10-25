#!/usr/bin/env python3
"""Static checks for the Debloat SEEK extension.

Run from the extension directory:
    python3 tests/static-check.py
"""

from pathlib import Path
import json
import re
import shutil
import subprocess
import sys

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
SEEK_ORIGINS = [
    "https://seek.study.iitm.ac.in/*",
    "https://seek.onlinedegree.iitm.ac.in/*"
]

failures = []


def check(condition, message):
    if condition:
        print(f"  PASS  {message}")
    else:
        print(f"  FAIL  {message}")
        failures.append(message)


def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def check_manifest():
    print("\nManifest")
    manifest = json.loads(read("manifest.json"))

    check(manifest.get("manifest_version") == 3, "Manifest V3 is used")
    check(manifest.get("permissions") == ["storage"], "Only the storage permission is requested")
    check("host_permissions" not in manifest, "No extra host permissions are requested")

    scripts = manifest.get("content_scripts", [])
    check(len(scripts) == 1, "Exactly one content script entry is declared")

    if scripts:
        entry = scripts[0]
        check(entry.get("matches") == SEEK_ORIGINS,
              "Content script is restricted to the two supported SEEK origins")
        check(entry.get("all_frames") is False, "Content script runs in the top frame only")
        check(entry.get("run_at") == "document_start", "Content script starts before the page renders")
        check(entry.get("css") == ["styles.css"], "Dedicated stylesheet is injected")
        check(entry.get("js") == ["settings.js", "content.js"], "Settings helper loads before the content script")

    check(manifest.get("action", {}).get("default_popup") == "popup.html", "Popup is declared")
    check(manifest.get("background", {}).get("service_worker") == "background.js",
          "Background service worker is declared")
    check(manifest.get("minimum_chrome_version") == "105", "Minimum Chrome version covers :has() support")

    required_files = [
        "manifest.json", "settings.js", "content.js", "styles.css",
        "popup.html", "popup.css", "popup.js", "background.js",
        "icons/icon16.png", "icons/icon32.png", "icons/icon48.png", "icons/icon128.png",
        "README.md"
    ]

    for name in required_files:
        check((ROOT / name).exists(), f"{name} exists")


def check_syntax():
    print("\nJavaScript syntax")
    node = shutil.which("node")

    if not node:
        print("  SKIP  node is not installed")
        return

    for name in ["settings.js", "content.js", "popup.js", "background.js"]:
        result = subprocess.run(
            [node, "--check", str(ROOT / name)],
            capture_output=True,
            text=True
        )
        check(result.returncode == 0, f"{name} parses successfully")


def check_popup():
    print("\nPopup structure")
    soup = BeautifulSoup(read("popup.html"), "html.parser")
    inputs = soup.select("input[data-setting]")
    keys = [element.get("data-setting") for element in inputs]

    check(keys == [
        "unitNav", "overview", "divider",
        "transcript", "announcements", "forum", "calculator", "header"
    ], "Eight independent settings are present in the expected order")

    default_keys = {"unitNav", "overview", "divider"}
    for element in inputs:
        key = element.get("data-setting")
        checked = element.has_attr("checked")
        expected = key in default_keys
        check(checked is expected, f"{key} HTML fallback default is {'on' if expected else 'off'}")

    check(soup.select_one("#restore-defaults") is not None, "Restore defaults control is present")
    check(soup.select_one("#status[role='status'][aria-live='polite']") is not None,
          "Accessible live status message is present")
    check(len(soup.select("label.setting-row")) == 8, "Every setting has a clickable label row")
    check(soup.select_one("script[src='settings.js']") is not None,
          "Popup loads the shared settings helper")
    check(soup.select_one("script[src='popup.js']") is not None,
          "Popup loads its local controller")


def check_no_remote_code():
    print("\nNo remote code or telemetry")
    scanned = [
        "settings.js", "content.js", "styles.css", "popup.html",
        "popup.css", "popup.js", "background.js"
    ]

    forbidden = [
        r"https?://",
        r"\bfetch\s*\(",
        r"XMLHttpRequest",
        r"new\s+Function",
        r"\beval\s*\(",
        r"google-analytics",
        r"gtag\s*\(",
        r"sendBeacon"
    ]

    for name in scanned:
        text = read(name)
        for pattern in forbidden:
            check(re.search(pattern, text) is None, f"{name} has no match for {pattern}")

    check("_ngcontent" not in read("styles.css"), "Generated _ngcontent attributes are not used in CSS")
    check("_ngcontent" not in read("content.js"), "Generated _ngcontent attributes are not used in JS")
    check(".remove(" not in read("content.js"), "Content script does not delete SEEK elements")
    check("style.setProperty" not in read("content.js"), "Content script does not write inline styles")


def check_css():
    print("\nStylesheet")
    css = read("styles.css")

    check(css.count("{") == css.count("}"), "CSS braces are balanced")
    check(css.count('html[data-seek-unit-nav="on"]') == 1, "Unit navigation is gated by its own state")
    check(css.count('html[data-seek-overview="on"]') == 3, "Overview selectors are gated by their own state")
    check(css.count('html[data-seek-divider="on"]') == 1, "Divider is gated by its own state")
    check(css.count('html[data-seek-transcript="on"]') == 2, "Transcript selectors are gated by their own state")
    check(css.count('html[data-seek-announcements="on"]') == 4,
          "Announcements selectors are gated by their own state")
    check(css.count('html[data-seek-forum="on"]') == 3, "Forum selectors are gated by their own state")
    check(css.count('html[data-seek-calculator="on"]') == 3,
          "Calculator selectors are gated by their own state")
    check(css.count('html[data-seek-header="on"]') == 1,
          "Course header is gated by its own state")
    check("app-bar.course-bar .lead > span.divider" in css,
          "Divider selector is scoped to the course-bar lead container")
    check("app-bar.course-bar" in css,
          "Course header selector targets the course bar host")
    check('aria-label^="Announcements"' in css,
          "Announcements label fallback uses a stable prefix, not a hardcoded count")
    check("display: none !important;" in css, "Targets are hidden through CSS rather than deletion")


def check_readme():
    print("\nREADME")
    readme = read("README.md")
    required_phrases = [
        "chrome://extensions",
        "Developer mode",
        "Load unpacked",
        "chrome.storage.sync",
        "Troubleshooting",
        "Known limitations",
        "Calculator",
        "Course header bar"
    ]

    for phrase in required_phrases:
        check(phrase.lower() in readme.lower(), f"README mentions {phrase}")


def main():
    check_manifest()
    check_syntax()
    check_popup()
    check_no_remote_code()
    check_css()
    check_readme()

    if failures:
        print(f"\n{len(failures)} check(s) failed.")
        return 1

    print("\nAll static checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
