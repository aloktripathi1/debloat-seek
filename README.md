# Debloat SEEK

Debloat SEEK is a free, local-only Chrome extension that makes the IIT Madras SEEK course site cleaner and easier to use. It hides clutter, improves the course overview and assessment pages, adds themes, and can hide assignment answers so you can practise past questions.

Everything happens in your browser. The extension does not call SEEK APIs, send data anywhere, or change course content, submissions, scores, or the lesson/video player.

[Download ZIP](https://github.com/aloktripathi1/debloat-seek/archive/refs/heads/main.zip) · [View source on GitHub](https://github.com/aloktripathi1/debloat-seek)

## Install in Chrome

1. **Download the ZIP** using the link above, or open the [GitHub repository](https://github.com/aloktripathi1/debloat-seek), click **Code**, then **Download ZIP**.
2. **Extract the ZIP** to a folder you can keep. On Windows, right-click the ZIP and choose **Extract All**. On macOS, double-click the ZIP. You should see `manifest.json` inside the extracted folder.
3. Open Chrome and go to `chrome://extensions`.
4. Turn on **Developer mode** in the top-right corner.
5. Click **Load unpacked**.
6. Select the extracted folder that contains `manifest.json`.
7. Pin **Debloat SEEK** from the Chrome extensions menu, open SEEK, and reload the tab.

The extension is now active and applies automatically whenever you open SEEK.

> Works in Chrome and other Chromium browsers such as Edge and Brave. It is not a Firefox extension.

## Features

### Default cleanup (on by default)

- **Previous/Next navigation** — hides the unit navigation bar.
- **Overview button** — hides the Overview button in the course bar.
- **Target divider** — hides the small divider next to the Overview button.

### Optional cleanup (off by default)

- **Course header bar** — hides the entire course header bar.
- **Video Transcript panel** — hides the transcript panel on lesson pages.
- **Hide assignment answers** — hides selected answers, expected answers, verdict headers, feedback, and correctness colours in reviewed assignments. Submissions and scoring are untouched.
- **Objectives** — hides the Objectives tab and panel while leaving other lesson tabs usable.
- **Announcements** — hides the announcements button.
- **Forum** — hides the Forum button.
- **Calculator** — hides the Calculator button.

### Themes and layout

- **System**, **Light**, **Dark**, and **Black** themes for SEEK pages.
- A cleaner course overview and assessment layout.
- Lesson pages, including the video player, tabs, objectives, transcript, and course bar, keep SEEK's original layout and behaviour.

## How to use it

Click the Debloat SEEK icon in the Chrome toolbar to open the popup.

- **Default cleanup** options are already on.
- **Optional cleanup** options are off until you switch them on.
- Changes apply to open SEEK tabs immediately.
- **Restore defaults** turns the default cleanups back on, turns the optional cleanups off, and sets the theme back to **System**.

Settings are saved with `chrome.storage.sync`, so they apply automatically the next time you open SEEK, even if you never open the popup.

## Troubleshooting

- **The extension icon is not visible:** click the puzzle-piece icon in Chrome's toolbar and pin **Debloat SEEK**.
- **Changes are not showing:** reload the SEEK tab. If you just installed or updated the extension, reload the tab once.
- **The extension is disabled:** open `chrome://extensions` and make sure Debloat SEEK is switched on.
- **A SEEK update broke an option:** turn that option off and reload the page. SEEK changes its page structure occasionally, so selectors may need updating.
- **You want a clean reset:** click **Restore defaults** in the popup. To remove the extension completely, open `chrome://extensions` and click **Remove**.

## Known limitations

- The extension only runs on these SEEK origins:
  - `https://seek.study.iitm.ac.in/*`
  - `https://seek.onlinedegree.iitm.ac.in/*`
- It is designed for Chromium browsers, not Firefox.
- SEEK can change its page structure at any time. If an option stops working, the extension may need an update.
- All changes are visual and local. The extension does not modify SEEK data or submissions.

## For developers

The extension has no build step. Load the repository folder directly with **Load unpacked**.

Run the checks from the project folder:

```bash
python3 tests/static-check.py
python3 tests/selector-check.py
python3 tests/e2e_extension.py
```

The browser test uses Playwright with Chrome for Testing. See the test file for the one-time browser install command.
