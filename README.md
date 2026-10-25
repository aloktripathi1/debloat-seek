# Debloat SEEK

A small Manifest V3 Chrome extension that locally declutters the IIT Madras SEEK course interface. It hides selected UI controls in the browser only. It does not change SEEK, call SEEK APIs, send data anywhere, or touch assignments, submissions, assessments, or course content.

## Supported site

The extension is restricted to the two SEEK origins:

```text
https://seek.study.iitm.ac.in/*
https://seek.onlinedegree.iitm.ac.in/*
```

The `*` covers every course code and keeps the content script active during in-app navigation from the SEEK dashboard. It deliberately does **not** match all of `*.iitm.ac.in`. The content script also runs on non-course SEEK pages, but its CSS selectors match nothing there. If SEEK moves to another origin, update the `matches` entries in `manifest.json` and this document.

## Install

1. Open Chrome and go to `chrome://extensions`.
2. Turn on **Developer mode** (top-right).
3. Click **Load unpacked**.
4. Select the `debloat-seek` folder (the folder containing `manifest.json`).
5. Open or reload SEEK. The extension applies automatically.

There is no build step and no dependency to install for normal use.

## Project layout

```text
debloat-seek/
├── manifest.json
├── settings.js          # shared defaults, normalization, storage helpers
├── content.js           # applies root state attributes and listens for changes
├── styles.css           # scoped, reversible hiding rules
├── background.js        # seeds defaults on first install
├── popup.html
├── popup.css
├── popup.js
├── icons/
├── tests/
│   ├── fixtures/seek-fixture.html
│   ├── selector-check.py
│   ├── static-check.py
│   └── e2e_extension.py
└── README.md
```

## Configuration

Click the Debloat SEEK icon in the Chrome toolbar to open the popup.

### Default cleanup (on by default)

| Option | What it hides |
| --- | --- |
| Previous/Next navigation | The whole `nav.unit-nav[aria-label="Previous and next unit"]` bar. |
| Overview button | Only the Overview control in the course bar. |
| Target divider | Only the divider in `app-bar.course-bar .lead`, immediately after the Overview button. |

### Optional cleanup (off by default)

| Option | What it hides |
| --- | --- |
| Video Transcript panel | The `aside.transcript-panel` inside `app-lesson-view`. |
| Announcements | The announcements trigger, including the version with an unread badge such as `aria-label="Announcements, 1"`. |
| Forum | The Forum `app-button` in the course-actions navigation. |
| Calculator | The Calculator `app-button` in the course-actions navigation. |
| Course header bar | The entire `app-bar.course-bar` host, including the course title, Overview, and course action buttons. |

Each toggle is independent. Turning one option off does not change the others.

**Restore defaults** sets the three default cleanups back on and the five optional cleanups back off. It does not uninstall or reset the extension.

## How settings are saved and restored

Settings are stored under one key, `debloatSeek.settings.v1`, using `chrome.storage.sync` as the primary store and `chrome.storage.local` as a fallback. The payload records a timestamp so the newest copy wins if sync and local ever disagree.

- Safe defaults are used when no stored settings exist or a stored value is missing/invalid.
- The popup writes a complete settings snapshot on every change. Saves are chained so rapid toggling cannot write an older snapshot after a newer one.
- The content script listens to `chrome.storage.onChanged` and applies changes to open SEEK tabs immediately.
- `background.js` seeds the defaults on first install only. Extension updates do not overwrite existing preferences.
- **Restore defaults** writes the default snapshot through the same path.

Settings are read again on every full page load. In-app navigation and Angular rerenders do not need a storage read because the CSS state lives on the document root.

## How it works

The content script sets state attributes on `<html>`:

```html
<html
  data-seek-cleaner="active"
  data-seek-unit-nav="on"
  data-seek-overview="on"
  data-seek-divider="on"
  data-seek-transcript="off"
  data-seek-announcements="off"
  data-seek-forum="off"
  data-seek-calculator="off"
  data-seek-header="off">
```

`styles.css` contains rules gated by those attributes. For example:

```css
html[data-seek-unit-nav="on"] nav.unit-nav[aria-label="Previous and next unit"] {
  display: none !important;
}
```

This has several advantages:

- Elements are hidden with CSS, never deleted from the DOM.
- Turning a setting off removes the matching CSS rule; no stale inline styles are left behind.
- Angular can recreate course elements or navigate in-app without touching `<html>`. New nodes automatically match the same CSS rules, so no per-element tagging, polling, or MutationObserver loop is needed.
- Missing elements are harmless: the selector simply matches nothing.
- All changes are local to the browser.

## Selectors used

The selector evidence used for this build was the supplied `seek.html` DOM snapshot plus the live `seek.study.iitm.ac.in` app bundle; no `SEEK_DOM_REFERENCE.md` file was present in the project. Angular-generated `_ngcontent-ng-c...` attributes are intentionally not used because they are build-specific and can change.

| Feature | Scoped selector | Notes |
| --- | --- | --- |
| Previous/Next | `nav.unit-nav[aria-label="Previous and next unit"]` | Exact accessible label. |
| Overview | `app-bar.course-bar .lead app-button[label="Overview"]`, `... button[aria-label="Overview"]`, and `:has(> button[aria-label="Overview"])` | Scoped to the course-bar lead area. |
| Target divider | `app-bar.course-bar .lead > span.divider` | Only the direct-child divider beside Overview. The separate `span.divider` in `nav.actions` is not matched. |
| Transcript | `app-lesson-view aside.transcript-panel.hidden-mobile` and `app-lesson-view aside.transcript-panel` | Scoped to the lesson view. |
| Announcements | `app-button[data-announcements-trigger]` plus label/`aria-label^="Announcements"` fallbacks scoped to `nav.actions[aria-label="Course actions"]` | The prefix matches `Announcements` and `Announcements, 1` without hardcoding a count. The panel's "Close announcements" button is not matched. |
| Forum | `app-button[label="Forum"]` and `:has(> button[aria-label="Forum"])` scoped to `nav.actions[aria-label="Course actions"]` | Does not match unrelated Forum controls elsewhere on the page. |
| Calculator | `app-button[label="Calculator"]` and `:has(> button[aria-label="Calculator"])` scoped to `nav.actions[aria-label="Course actions"]` | Does not match unrelated Calculator controls elsewhere on the page. |
| Course header bar | `app-bar.course-bar` | Hides the whole course bar host. Optional and off by default. |

### Divider assumption

The supplied SEEK DOM snapshot showed two `span.divider` elements:

1. A direct child of `app-bar.course-bar .lead`, immediately after the Overview button.
2. A separate divider inside `nav.actions[aria-label="Course actions"]`.

The extension hides only the first one. If SEEK changes the course-bar structure, update the divider rule in `styles.css` and keep the selector scoped to the smallest stable parent available.

## Troubleshooting selectors

If SEEK changes its UI and an option stops working:

1. Open SEEK and inspect the element with Chrome DevTools.
2. Look for stable classes, accessible labels, semantic attributes, or a specific parent container. Avoid generated `_ngcontent-*` attributes.
3. Update the relevant rule in `styles.css`. Keep the `html[data-seek-*="on"]` gate so the popup toggle remains reversible.
4. Keep the selector narrow. Prefer a unique parent plus an accessible label or data attribute over a broad class selector.
5. Reload the extension at `chrome://extensions` and reload SEEK.
6. In DevTools, confirm the root state attributes are present:
   ```js
   document.documentElement.dataset
   ```
7. Run the selector checks:
   ```bash
   python3 tests/selector-check.py
   ```

If the popup saves but the page does not change, check that the page is on one of the supported SEEK course origins (`seek.study.iitm.ac.in` or `seek.onlinedegree.iitm.ac.in`) and reload the extension after editing files.

## Tests

The extension itself has no test dependency. Development checks are in `tests/`:

```bash
cd debloat-seek
python3 tests/selector-check.py
python3 tests/static-check.py
python3 tests/e2e_extension.py
```

- `selector-check.py` checks every selector against a privacy-safe DOM fixture and, when present, the supplied `seek.html` snapshot. It covers off states, target identity, decoys, badge-count changes, calculator/header targeting, and missing elements.
- `static-check.py` checks the Manifest V3 configuration, permissions, origin/path restriction, popup structure, JavaScript syntax, absence of remote code, CSS gating, and README requirements.
- `e2e_extension.py` loads the unpacked extension in Playwright with Chrome for Testing. It serves the fixture from both real SEEK origins, verifies defaults, all eight independent toggles, live popup-to-content-script updates, badge changes, persistence after reload, restoration, Angular-style node replacement, missing elements, and origin restriction.

Chrome for Testing is needed because branded Google Chrome 137+ ignores `--load-extension`:

```bash
npx --yes @puppeteer/browsers install chrome@stable --path /tmp/opencode/browsers
```

Set `SEEK_TEST_CHROME` to a specific Chrome for Testing executable if it is installed elsewhere.

### What was actually tested

Automated checks were run in this development environment:

- Manifest JSON parsing and all static checks passed.
- All selector checks passed against the fixture and the supplied `seek.html` snapshot.
- The Playwright browser test passed against the fixture served at both `https://seek.study.iitm.ac.in` and `https://seek.onlinedegree.iitm.ac.in`. It covered the default three elements, all eight toggles, live storage updates, persistence after reload, restore defaults, badge-count changes, node replacement, missing elements, and non-SEEK origin exclusion.
- A live-origin injection check confirmed the content script runs on both hosts and exposes all eight state attributes. The check stopped at the login screen because no SEEK credentials were used.

The browser test uses a local fixture, not the live authenticated SEEK application. A final manual pass on a real SEEK account is still required.

## Manual test checklist

After loading the extension in Chrome:

1. Open a SEEK course lesson on each supported host.
2. Confirm the Previous/Next bar, Overview button, and the divider beside Overview are hidden.
3. Confirm the transcript panel, Announcements button, Forum button, Calculator button, and course header bar are still visible.
4. Open the popup. Enable **Video Transcript panel**. The transcript panel should disappear without a reload.
5. Enable **Announcements**. The announcements trigger, including a badge variant, should disappear. The announcements panel's close button should remain unaffected.
6. Enable **Forum**. Only the Forum button in the course actions should disappear.
7. Enable **Calculator**. Only the Calculator button in the course actions should disappear.
8. Enable **Course header bar**. The entire course bar should disappear.
9. Disable each optional toggle. The corresponding element should return.
10. Disable **Previous/Next navigation**, **Overview button**, and **Target divider** one at a time. Only the matching element should return.
11. Reload the page and confirm the settings persist.
12. Navigate between units and courses, and between the two supported hosts. Confirm the settings continue to apply after Angular rerenders.
13. Click **Restore defaults** and confirm the three default cleanups return to on and the optional cleanups return to off.
14. Open an assignment or assessment page and confirm submission controls, content, and required navigation still work.

## Known limitations

- SEEK can change its DOM or accessible labels at any time. Selectors are intentionally narrow and may need maintenance.
- The divider selector relies on the current `app-bar.course-bar .lead` structure. That is the main selector most likely to need an update.
- The Announcements badge is matched by the stable `Announcements` prefix, not by a notification count. If SEEK changes that label entirely, update the fallback.
- The extension targets the desktop course UI. Mobile layouts or future SEEK surfaces may use different components.
- It runs only in the top frame of the two exact SEEK origins. It does not modify embedded assignment iframes.
- Chrome sync availability depends on the browser profile. If sync is unavailable, settings still save to local storage.
- The automated browser test uses a fixture and the supplied snapshot, not a live authenticated SEEK session.
- Hiding the Overview button, Previous/Next bar, or entire course header bar removes those navigation shortcuts. Users can turn any option off at any time.
- The course header bar toggle hides the whole bar, including Contents, Grades, Forum, Calculator, Announcements, and Account. It is off by default.

## Privacy and permissions

- Permissions: `storage` only.
- Host access: limited by the content-script `matches` patterns to `https://seek.study.iitm.ac.in/*` and `https://seek.onlinedegree.iitm.ac.in/*`.
- No remote scripts, external dependencies, analytics, telemetry, `fetch`, or network requests.
- No SEEK data is read, stored, or transmitted by the extension. Only the eight boolean preferences are stored.
- The content script runs in the top frame only and does not alter assignment content, submission controls, assessment functionality, or course data.
