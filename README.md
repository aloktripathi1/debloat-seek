# Debloat SEEK

A small Manifest V3 Chrome extension that locally declutters and refines the IIT Madras SEEK course interface. It hides selected UI controls, applies a premium visual system to the course overview and assessment surfaces, adds System, Light, Dark, and Black themes to SEEK pages, and can hide assignment review answers so past-deadline work can be practised again. Everything happens in the browser only. It does not change SEEK, call SEEK APIs, send data anywhere, or alter course content, assignment behavior, submission controls, assessment logic, or the lesson player and video portal.

## Supported site

The extension is restricted to the two SEEK origins:

```text
https://seek.study.iitm.ac.in/*
https://seek.onlinedegree.iitm.ac.in/*
```

The `*` covers every course code and keeps the content script active during in-app navigation from the SEEK dashboard. It deliberately does **not** match all of `*.iitm.ac.in`. The content script also runs on non-course SEEK pages; the cleanup selectors match nothing there, while the theme still applies. If SEEK moves to another origin, update the `matches` entries in `manifest.json` and this document.

## Install

1. Open Chrome and go to `chrome://extensions`.
2. Turn on **Developer mode** (top-right).
3. Click **Load unpacked**.
4. Select the `debloat-seek` folder (the folder containing `manifest.json`).
4. Open or reload SEEK. The extension applies automatically.

There is no build step and no dependency to install for normal use.

## Project layout

```text
debloat-seek/
├── manifest.json
├── settings.js          # shared defaults, normalization, storage helpers
├── content.js           # applies root state attributes and listens for changes
├── styles.css           # scoped hiding, premium interface, and theme rules
├── background.js        # seeds defaults on first install
├── popup.html
├── popup.css
├── popup.js
├── icons/
├── tests/
│   ├── fixtures/seek-fixture.html
│   ├── fixtures/course-overview-fixture.html
│   ├── fixtures/assessment-fixture.html
│   ├── fixtures/assignment-fixture.html
│   ├── selector-check.py
│   ├── static-check.py
│   └── e2e_extension.py
└── README.md
```

## Configuration

Click the Debloat SEEK icon in the Chrome toolbar to open the popup.

### Appearance (on by default)

| Option | What it does |
| --- | --- |
| Theme | **System** follows your operating system, **Light** uses SEEK's light palette, **Dark** uses SEEK's soft dark palette, and **Black** replaces SEEK's dark surfaces with true black and near-black surfaces for low-glare reading. This setting changes SEEK pages only. |

The theme setting is stored with the other preferences and is applied to open SEEK tabs immediately. The extension sets SEEK's root `data-theme` attribute so SEEK's own components switch palettes, then layers Black-mode surface overrides on top. If you later change SEEK's own Appearance menu, the extension's saved theme remains authoritative. The extension popup itself keeps its own light/dark appearance based on your operating-system preference; the theme choice does not recolor the popup.

### Premium interface

While the extension is active, it also applies a shared visual system to SEEK course surfaces:

- Course overview cards with a clear title hierarchy, quiet metadata pills, a slim progress bar, a restrained primary **Continue learning** action, module cards with a subtle hover lift, and a single supporting upcoming-work rail. On desktop the empty left rail is removed so the course card and modules lead; below 992 px the rail moves below the course contents.
- Assessment start and submission surfaces with readable instructions, a focused score summary, a compact toolbar, and quiet test-case cards.

The system uses shared spacing, radius, typography, surface, shadow, and motion tokens. Interactive elements use 150–180 ms transitions, visible `:focus-visible` rings, and a reduced-motion fallback. It is CSS-only: no control, handler, navigation target, or submission action is added or removed. The single exception is the Objectives cleanup, where a tiny content-script pass writes a `data-seek-objectives-*` attribute on the tab so CSS can identify it; nothing is deleted or restyled inline. The course overview and assessment rules are scoped to `app-course-overview` and `app-assessments-view` so unrelated pages are not restyled. Lesson pages — including the video player, tab control, objectives, transcript panel, and course bar — keep SEEK's original layout and styling.

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
| Objectives | The Objectives tab in the lesson tab bar, its panel, and a tab bar that contains nothing but Objectives. Other tabs stay available. |
| Announcements | The announcements trigger, including the version with an unread badge such as `aria-label="Announcements, 1"`. |
| Forum | The Forum `app-button` in the course-actions navigation. |
| Calculator | The Calculator `app-button` in the course-actions navigation. |
| Hide assignment answers | On a reviewed assignment, hides the submitted-choice marker, the correct/expected answer reveal, per-choice feedback, and green/red correctness colours so the questions can be used for practice. It does not change submissions, scoring, or any SEEK data. |
| Course header bar | The entire `app-bar.course-bar` host, including the course title, Overview, and course action buttons. |

Each toggle is independent. Turning one option off does not change the others.

**Restore defaults** sets the three default cleanups back on, the seven optional cleanups back off, and the theme back to **System**. It does not uninstall or reset the extension.

## How settings are saved and restored

Settings are stored under one key, `debloatSeek.settings.v1`, using `chrome.storage.sync` as the primary store and `chrome.storage.local` as a fallback. The payload records a timestamp so the newest copy wins if sync and local ever disagree. The payload contains ten boolean preferences and one theme string (`system`, `light`, `dark`, or `black`).

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
  data-seek-answers="off"
  data-seek-announcements="off"
  data-seek-forum="off"
  data-seek-calculator="off"
  data-seek-header="off"
  data-seek-theme-setting="black"
  data-seek-theme="black"
  data-theme="dark">
```

`data-seek-theme-setting` is the saved choice, `data-seek-theme` is the resolved theme, and `data-theme` is the value SEEK's own components read. System mode resolves to `light` or `dark` from `prefers-color-scheme`. Black mode keeps `data-theme="dark"` and adds `data-seek-theme="black"`, which lets the extension override only SEEK's surface tokens.

`styles.css` contains rules gated by those attributes. For example:

```css
html[data-seek-unit-nav="on"] nav.unit-nav[aria-label="Previous and next unit"] {
  display: none !important;
}
```

This has several advantages:

- Elements are hidden with CSS, never deleted from the DOM.
- Turning a setting off removes the matching CSS rule; no stale inline styles are left behind.
- Angular can recreate course elements or navigate in-app without touching `<html>`. New nodes automatically match the same CSS rules, so no per-element tagging or polling is needed. A single root observer only reasserts the chosen theme if SEEK's theme service rewrites `data-theme`.
- Missing elements are harmless: the selector simply matches nothing.
- All changes are local to the browser.

## Selectors used

The selector evidence used for this build was the supplied `seek.html`, `course-page.html`, and assignment-review DOM snapshots plus the live `seek.study.iitm.ac.in` app bundle; no `SEEK_DOM_REFERENCE.md` file was present in the project. Angular-generated `_ngcontent-ng-c...` attributes are intentionally not used because they are build-specific and can change.

| Feature | Scoped selector | Notes |
| --- | --- | --- |
| Previous/Next | `nav.unit-nav[aria-label="Previous and next unit"]` | Exact accessible label. |
| Overview | `app-bar.course-bar .lead app-button[label="Overview"]`, `... button[aria-label="Overview"]`, and `:has(> button[aria-label="Overview"])` | Scoped to the course-bar lead area. |
| Target divider | `app-bar.course-bar .lead > span.divider` | Only the direct-child divider beside Overview. The separate `span.divider` in `nav.actions` is not matched. |
| Transcript | `app-lesson-view aside.transcript-panel.hidden-mobile` and `app-lesson-view aside.transcript-panel` | Scoped to the lesson view. |
| Objectives | `app-lesson-view .objectives`, `[data-seek-objectives-tab]`, and `[data-seek-objectives-only]` | The content script tags the Objectives tab by its visible label and a bar that only contains Objectives; no element is deleted and no handler changes. Scoped to the lesson view. |
| Announcements | `app-button[data-announcements-trigger]` plus label/`aria-label^="Announcements"` fallbacks scoped to `nav.actions[aria-label="Course actions"]` | The prefix matches `Announcements` and `Announcements, 1` without hardcoding a count. The panel's "Close announcements" button is not matched. |
| Forum | `app-button[label="Forum"]` and `:has(> button[aria-label="Forum"])` scoped to `nav.actions[aria-label="Course actions"]` | Does not match unrelated Forum controls elsewhere on the page. |
| Calculator | `app-button[label="Calculator"]` and `:has(> button[aria-label="Calculator"])` scoped to `nav.actions[aria-label="Course actions"]` | Does not match unrelated Calculator controls elsewhere on the page. |
| Hide assignment answers | `app-assessment-question-view .evaluated-answer` and its `.header`, `.reveal-badge`, `.choice.is-correct`, `.choice.is-expected`, `.choice.is-wrong`, `.choice.is-selected`, `.radio-dot`, `.checkbox`, `.short-answer .show-submission`, plus the question `.chip` states | Scoped to the reviewed-answer view, so taking an assignment is unaffected. Hides the selected-answer marker, expected answer, feedback, and green/red correctness styling. Optional and off by default. |
| Course header bar | `app-bar.course-bar` | Hides the whole course bar host. Optional and off by default. |
| Premium lesson surface | `.lesson-view`, `.content-column`, `.video-container`, `.tab-bar-wrapper`, `.objectives`, and `.transcript-panel` | Not restyled. The lesson player keeps SEEK's original layout and behavior. |
| Course overview | `app-course-overview .overview-page`, `.overview-card`, `.course-header`, `.module-card`, `.widget`, and `.due-item` | Scoped to the course overview component. Cards remain links or buttons with their original handlers. |
| Assessments | `app-assessments-view .pa-start-page`, `.assessment-instructions`, `.submission-overview`, `.submission-toolbar`, and `.test-case-card` | Styling only. Submission controls and assessment logic are untouched. |
| Theme | `html[data-seek-theme-setting]`, `html[data-seek-theme]`, and SEEK's `html[data-theme]` | The extension resolves System and Black, sets SEEK's light/dark palette, and adds Black surface overrides in `styles.css`. |

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
4. Reload the extension at `chrome://extensions` and reload SEEK.
5. In DevTools, confirm the root state attributes are present:
   ```js
   document.documentElement.dataset
   ```
6. Run the selector checks:
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

- `selector-check.py` checks every selector against a privacy-safe DOM fixture and, when present, the supplied `seek.html` snapshot. It covers off states, target identity, decoys, badge-count changes, calculator/header targeting, assignment review selectors, and missing elements.
- `static-check.py` checks the Manifest V3 configuration, permissions, origin/path restriction, popup structure, theme settings, JavaScript syntax, absence of remote code, CSS gating, shared design tokens, reduced-motion/focus rules, Black-mode tokens, and README requirements.
- `e2e_extension.py` loads the unpacked extension in Playwright with Chrome for Testing. It serves the lesson fixture from both real SEEK origins and separate course-overview, assessment, and assignment-review fixtures. It verifies defaults, all ten independent toggles, all four theme choices, live popup-to-content-script updates, badge changes, persistence after reload and browser restart, automatic application on newly opened course tabs, restoration, Angular-style node replacement, missing elements, origin restriction, that the stock lesson page keeps SEEK's original layout, course overview cards (including the primary action, module status/progress, and responsive supporting rail), assessment surfaces, assignment answer hiding, keyboard focus rings, hover lift, and the reduced-motion fallback.

Chrome for Testing is needed because branded Google Chrome 137+ ignores `--load-extension`:

```bash
npx --yes @puppeteer/browsers install chrome@stable --path /tmp/opencode/browsers
```

Set `SEEK_TEST_CHROME` to a specific Chrome for Testing executable if it is installed elsewhere.

### What was actually tested

Automated checks were run in this development environment:

- Manifest JSON parsing and all static checks passed, including the shared design tokens, scoped overview/assessment rules, focus states, and reduced-motion fallback.
- All selector checks passed against the fixture and the supplied `seek.html` snapshot.
- The Playwright browser test passed against the lesson fixture served at both `https://seek.study.iitm.ac.in` and `https://seek.onlinedegree.iitm.ac.in`, plus the course-overview, assessment, and assignment-review fixtures. It covered the default three elements, all ten toggles, all four themes, live storage updates, persistence after reload, restore defaults, badge-count changes, automatic application on newly opened course tabs, node replacement, missing elements, non-SEEK origin exclusion, the stock lesson layout, overview cards and their responsive supporting rail, assessment surfaces, assignment answer hiding, focus rings, hover lift, and reduced motion.
- A visual pass with the supplied lesson and course-overview snapshots was checked at desktop, tablet, and phone widths in Light and Black. Dark-mode tokens were injected into the local lesson snapshot for that check because it does not include SEEK's external palette stylesheet.
- A live-origin injection check confirmed the content script runs on both hosts and exposes the ten state attributes plus the resolved theme attributes. The check stopped at the login screen because no SEEK credentials were used.

The browser test uses a local fixture, not the live authenticated SEEK application. A final manual pass on a real SEEK account is still required.

## Manual test checklist

After loading the extension in Chrome:

1. Open a SEEK course lesson on each supported host.
2. Confirm the Previous/Next bar, Overview button, and the divider beside Overview are hidden.
3. Confirm the transcript panel, Announcements button, Forum button, Calculator button, and course header bar are still visible.
4. Confirm the course bar, lesson title bar, video frame, tab control, objectives card, and transcript panel look exactly as SEEK renders them — the extension does not restyle the lesson player. Check that the video still plays, tabs switch, and transcript cues still seek the video.
5. Open a course overview page and confirm the course card, module cards, and upcoming-work widget use the shared surfaces. Hover a module card and use Tab to confirm the subtle lift and visible focus ring.
6. Open an assessment start page and confirm the instructions, score summary, toolbar, and test cases are readable. Run or submit only in a test course where that is safe; confirm the controls still work.
7. Open a past-deadline assignment review. Confirm SEEK's selected answer, expected answer, score header, and green/red feedback are visible while **Hide assignment answers** is off. Enable it and confirm those reveals and colours disappear, while the question text, options, and question navigation remain usable.
8. Use Tab through the course bar, lesson tabs, module cards, and assessment controls. Every interactive element should show a visible focus ring.
9. Enable your operating system's reduced-motion setting and confirm SEEK's transitions become effectively instant.
10. Open the popup. Choose **Dark**. SEEK should switch to the soft dark palette without a reload. The popup should keep its own system light/dark appearance.
11. Choose **Black**. SEEK surfaces should become true black or near black. The popup should not turn black.
12. Choose **Light**. SEEK should switch to the light palette. Choose **System** and confirm SEEK follows the operating-system preference. The popup should continue to follow the operating system independently.
13. Enable **Video Transcript panel**. The transcript panel should disappear without a reload.
14. Enable **Announcements**. The announcements trigger, including a badge variant, should disappear. The announcements panel's close button should remain unaffected.
15. Enable **Forum**. Only the Forum button in the course actions should disappear.
16. Enable **Calculator**. Only the Calculator button in the course actions should disappear.
17. Enable **Course header bar**. The entire course bar should disappear.
18. Disable each optional toggle. The corresponding element should return.
19. Disable **Previous/Next navigation**, **Overview button**, and **Target divider** one at a time. Only the matching element should return.
20. Reload the page and confirm the settings and theme persist.
21. Navigate between units and courses, and between the two supported hosts. Confirm the settings continue to apply after Angular rerenders.
22. Click **Restore defaults** and confirm the three default cleanups return to on, the optional cleanups return to off, and the theme returns to System.
23. Reopen the course overview and assessment pages and confirm the redesigned surfaces, submission controls, content, and required navigation still work.

## Known limitations

- SEEK can change its DOM or accessible labels at any time. Selectors are intentionally narrow and may need maintenance.
- The divider selector relies on the current `app-bar.course-bar .lead` structure. That is the main selector most likely to need an update.
- The Announcements badge is matched by the stable `Announcements` prefix, not by a notification count. If SEEK changes that label entirely, update the fallback.
- The extension includes responsive rules for the overview and assessment surfaces. The Contents drawer on phones is still controlled by SEEK's own layout; if SEEK uses a different mobile component, the extension falls back to SEEK's styling.
- The course overview and assessment refinements depend on the current stable class names such as `.overview-card`, `.module-card`, and `.submission-overview`. If SEEK renames them, those surfaces keep SEEK's original styling rather than breaking. The lesson player is never restyled.
- Assignment answer hiding depends on the reviewed-answer classes `.evaluated-answer`, `.choice.is-correct`, `.choice.is-expected`, `.choice.is-wrong`, `.reveal-badge`, and `.chip`. If SEEK renames them, the toggle simply stops hiding those markers rather than changing the review page.
- Theme overrides cover SEEK's own surfaces and components. Embedded third-party content such as a YouTube player, PDF viewer, or external editor may keep its own light or dark appearance.
- The extension's theme takes precedence over SEEK's own Appearance menu. SEEK's menu may therefore show a different selected option until you choose a new one there. Set the SEEK theme to System if you want SEEK to follow the OS. The extension popup is not affected by this setting.
- It runs only in the top frame of the two exact SEEK origins. It does not modify embedded assignment iframes.
- Chrome sync availability depends on the browser profile. If sync is unavailable, settings still save to local storage.
- The automated browser test uses a fixture and the supplied snapshot, not a live authenticated SEEK session.
- Hiding the Overview button, Previous/Next bar, or entire course header bar removes those navigation shortcuts. Users can turn any option off at any time.
- The course header bar toggle hides the whole bar, including Contents, Grades, Forum, Calculator, Announcements, and Account. It is off by default.

## Privacy and permissions

- Permissions: `storage` only.
- Host access: limited by the content-script `matches` patterns to `https://seek.study.iitm.ac.in/*` and `https://seek.onlinedegree.iitm.ac.in/*`.
- No remote scripts, external dependencies, analytics, telemetry, `fetch`, or network requests.
- No SEEK data is read, stored, or transmitted by the extension. Only the ten boolean preferences and the theme choice are stored.
- The content script runs in the top frame only and does not change assignment content, submission behavior, assessment logic, or course data.
