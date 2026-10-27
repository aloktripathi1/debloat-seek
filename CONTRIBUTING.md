# Contributing to Debloat SEEK

Thanks for helping improve Debloat SEEK. This is an unofficial, local-only Chrome extension for the IIT Madras SEEK portal.

## Before you start

- Keep the extension local-only. Do not add remote code, analytics, tracking, or calls to SEEK APIs.
- Do not commit real SEEK HTML snapshots, account details, screenshots containing personal data, cookies, or other private material.
- Keep SEEK's lesson and video portal stock unless the change is explicitly about a cleanup option.
- Prefer CSS-only changes. If JavaScript is required, keep it small and scoped.

Private DOM snapshots belong in the gitignored `local/` folder, for example `local/seek.html`.

## Local setup

1. Fork and clone the repository.
2. Open `chrome://extensions`.
3. Turn on **Developer mode**.
4. Click **Load unpacked** and select the repository folder.
5. Open or reload SEEK after changing files.

There is no build step. The extension runtime, tests, and documentation live together at the repository root.

## Tests

Run the checks from the repository root:

```bash
python3 tests/static-check.py
python3 tests/selector-check.py
python3 tests/e2e_extension.py
```

The browser test needs Playwright and an unbranded Chrome for Testing build. The install command is documented at the top of `tests/e2e_extension.py`.

Please run the relevant checks before opening a pull request. If you change a selector or popup behavior, update the fixtures and tests too.

## Making a change

- Keep selectors scoped to SEEK's stable page structure.
- Avoid generated Angular attributes such as `_ngcontent-*`.
- Do not delete SEEK elements from the DOM.
- Keep the popup keyboard-accessible and use visible focus states.
- Update `README.md` when a user-facing feature or install step changes.
- Keep the manifest version current when preparing a release.

## Pull requests

1. Create a branch from `main`.
2. Make a focused change with a clear commit message.
3. Run the relevant tests.
4. Open a pull request describing the problem, the change, and how you tested it.
5. Include a screenshot for popup or visual changes.

Small, focused pull requests are easier to review than large rewrites.

## Reporting bugs

Open an issue with:

- Chrome version
- Debloat SEEK version
- The SEEK page where the problem occurs
- Steps to reproduce
- Expected and actual behavior
- A screenshot or console message if useful

Remove names, email addresses, answers, and other personal data before posting.

## License

By contributing, you agree that your changes are released under the MIT License in `LICENSE`.
