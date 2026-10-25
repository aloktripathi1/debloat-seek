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
    DEFAULT_SETTINGS,
    SETTING_KEYS,
    STORAGE_KEY,
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
    header: 'data-seek-header'
  });

  let currentSettings = null;

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

    for (const key of SETTING_KEYS) {
      root.setAttribute(FEATURE_ATTRIBUTES[key], settings[key] ? 'on' : 'off');
    }
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

    chrome.storage.onChanged.addListener(handleStorageChange);
  }

  init().catch(() => {
    // Keep the page usable even if the storage listener cannot be registered.
    if (!currentSettings) {
      applySettings(DEFAULT_SETTINGS);
    }
  });
})();
