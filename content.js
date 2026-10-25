/*
 * Debloat SEEK content script.
 *
 * Visibility is controlled by data attributes on <html> and the scoped rules in
 * styles.css. Angular can recreate any course element without touching <html>,
 * so newly rendered nodes automatically match the same CSS rules. This avoids
 * per-element tagging, mutation loops, and stale inline styles.
 */
(function () {
  'use strict';

  const api = globalThis.DebloatSeekSettings;

  if (!api) {
    return;
  }

  const {
    BOOLEAN_SETTING_KEYS,
    DEFAULT_SETTINGS,
    SETTING_KEYS,
    STORAGE_KEY,
    THEME_VALUES,
    extractSettings,
    loadSettings,
    normalizeSettings
  } = api;

  const FEATURE_ATTRIBUTES = Object.freeze({
    unitNav: 'data-seek-unit-nav',
    overview: 'data-seek-overview',
    divider: 'data-seek-divider',
    transcript: 'data-seek-transcript',
    announcements: 'data-seek-announcements',
    forum: 'data-seek-forum',
    calculator: 'data-seek-calculator',
    header: 'data-seek-header',
    sidebar: 'data-seek-sidebar'
  });

  const SEEK_THEME_ATTRIBUTE = 'data-theme';
  const SEEK_THEME_SETTING_ATTRIBUTE = 'data-seek-theme-setting';
  const SEEK_THEME_STATE_ATTRIBUTE = 'data-seek-theme';

  let currentSettings = null;
  let systemThemeMedia = null;
  let rootThemeObserver = null;

  function resolveTheme(theme) {
    if (theme === 'system') {
      return globalThis.matchMedia
        && globalThis.matchMedia('(prefers-color-scheme: dark)').matches
        ? 'dark'
        : 'light';
    }

    return THEME_VALUES.includes(theme) ? theme : 'light';
  }

  function seekThemeFor(resolvedTheme) {
    return resolvedTheme === 'light' ? 'light' : 'dark';
  }

  function applyTheme(theme) {
    const root = document.documentElement;

    if (!root) {
      return;
    }

    const resolvedTheme = resolveTheme(theme);
    const seekTheme = seekThemeFor(resolvedTheme);

    root.setAttribute(SEEK_THEME_SETTING_ATTRIBUTE, theme);
    root.setAttribute(SEEK_THEME_STATE_ATTRIBUTE, resolvedTheme);

    // SEEK already ships a dark palette. Black mode builds on it and only
    // replaces the surface tokens in styles.css.
    if (root.getAttribute(SEEK_THEME_ATTRIBUTE) !== seekTheme) {
      root.setAttribute(SEEK_THEME_ATTRIBUTE, seekTheme);
    }
  }

  function watchSystemTheme() {
    if (systemThemeMedia || !globalThis.matchMedia) {
      return;
    }

    systemThemeMedia = globalThis.matchMedia('(prefers-color-scheme: dark)');

    const update = () => {
      if (currentSettings && currentSettings.theme === 'system') {
        applyTheme('system');
      }
    };

    if (typeof systemThemeMedia.addEventListener === 'function') {
      systemThemeMedia.addEventListener('change', update);
    } else if (typeof systemThemeMedia.addListener === 'function') {
      systemThemeMedia.addListener(update);
    }
  }

  function watchSeekTheme() {
    if (rootThemeObserver) {
      return;
    }

    const root = document.documentElement;

    if (!root) {
      return;
    }

    // SEEK's theme service can write data-theme after the app boots. Keep the
    // extension's explicit choice authoritative without touching SEEK storage.
    rootThemeObserver = new MutationObserver(() => {
      if (!currentSettings) {
        return;
      }

      const expected = seekThemeFor(resolveTheme(currentSettings.theme));

      if (root.getAttribute(SEEK_THEME_ATTRIBUTE) !== expected) {
        root.setAttribute(SEEK_THEME_ATTRIBUTE, expected);
      }
    });

    rootThemeObserver.observe(root, {
      attributes: true,
      attributeFilter: [SEEK_THEME_ATTRIBUTE]
    });
  }

  function applySettings(value) {
    const settings = normalizeSettings(value);

    if (currentSettings && SETTING_KEYS.every((key) => currentSettings[key] === settings[key])) {
      return;
    }

    const root = document.documentElement;

    if (!root) {
      return;
    }

    currentSettings = settings;
    root.setAttribute('data-seek-cleaner', 'active');

    for (const key of BOOLEAN_SETTING_KEYS) {
      root.setAttribute(FEATURE_ATTRIBUTES[key], settings[key] ? 'on' : 'off');
    }

    applyTheme(settings.theme);
  }

  function handleStorageChange(changes, areaName) {
    if (areaName !== 'sync' && areaName !== 'local') {
      return;
    }

    const change = changes[STORAGE_KEY];

    if (!change || change.newValue === undefined) {
      return;
    }

    applySettings(extractSettings(change.newValue));
  }

  async function init() {
    try {
      applySettings(await loadSettings());
    } catch (error) {
      // Storage should never prevent the page from working. Safe defaults are
      // still useful if a read unexpectedly fails.
      applySettings(DEFAULT_SETTINGS);
    }

    watchSystemTheme();
    watchSeekTheme();
    chrome.storage.onChanged.addListener(handleStorageChange);
  }

  init().catch(() => {
    // Keep the page usable even if the storage listener cannot be registered.
    if (!currentSettings) {
      applySettings(DEFAULT_SETTINGS);
    }

    watchSystemTheme();
    watchSeekTheme();
  });
})();
