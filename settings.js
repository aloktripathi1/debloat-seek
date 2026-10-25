/*
 * Shared settings model for Debloat SEEK.
 *
 * Loaded by the content script, the popup, and the background service worker.
 * Settings are written to chrome.storage.sync (primary) and chrome.storage.local
 * (fallback). The newest payload wins when the two areas disagree.
 */
(function (global) {
  'use strict';

  const STORAGE_KEY = 'debloatSeek.settings.v1';
  const STORAGE_VERSION = 1;

  const DEFAULT_SETTINGS = Object.freeze({
    unitNav: true,
    overview: true,
    divider: true,
    transcript: false,
    announcements: false,
    forum: false,
    calculator: false,
    header: false
  });

  const SETTING_KEYS = Object.freeze(Object.keys(DEFAULT_SETTINGS));

  function normalizeSettings(value) {
    const source = value && typeof value === 'object' ? value : {};
    const normalized = {};

    for (const key of SETTING_KEYS) {
      normalized[key] = typeof source[key] === 'boolean'
        ? source[key]
        : DEFAULT_SETTINGS[key];
    }

    return normalized;
  }

  function normalizePayload(value) {
    if (!value || typeof value !== 'object') {
      return {
        version: STORAGE_VERSION,
        updatedAt: 0,
        settings: { ...DEFAULT_SETTINGS }
      };
    }

    const hasSettingsObject = value.settings && typeof value.settings === 'object';

    return {
      version: Number.isInteger(value.version) ? value.version : 0,
      updatedAt: Number.isFinite(value.updatedAt) ? value.updatedAt : 0,
      settings: normalizeSettings(hasSettingsObject ? value.settings : value)
    };
  }

  function extractSettings(value) {
    return normalizePayload(value).settings;
  }

  function readArea(area) {
    try {
      return chrome.storage[area]
        .get(STORAGE_KEY)
        .then((result) => result ? result[STORAGE_KEY] : undefined)
        .catch(() => undefined);
    } catch (error) {
      return Promise.resolve(undefined);
    }
  }

  function writeArea(area, payload) {
    try {
      return chrome.storage[area].set({ [STORAGE_KEY]: payload });
    } catch (error) {
      return Promise.reject(error);
    }
  }

  async function loadSettings() {
    const [syncValue, localValue] = await Promise.all([
      readArea('sync'),
      readArea('local')
    ]);

    const candidates = [];

    if (syncValue !== undefined) {
      candidates.push({ area: 'sync', ...normalizePayload(syncValue) });
    }

    if (localValue !== undefined) {
      candidates.push({ area: 'local', ...normalizePayload(localValue) });
    }

    if (candidates.length === 0) {
      return { ...DEFAULT_SETTINGS };
    }

    candidates.sort((a, b) => {
      if (b.updatedAt !== a.updatedAt) {
        return b.updatedAt - a.updatedAt;
      }

      // Prefer sync when both copies are equally fresh.
      return a.area === 'sync' ? -1 : 1;
    });

    return candidates[0].settings;
  }

  async function hasStoredSettings() {
    const [syncValue, localValue] = await Promise.all([
      readArea('sync'),
      readArea('local')
    ]);

    return syncValue !== undefined || localValue !== undefined;
  }

  async function saveSettings(settings) {
    const payload = {
      version: STORAGE_VERSION,
      updatedAt: Date.now(),
      settings: normalizeSettings(settings)
    };

    const [syncResult, localResult] = await Promise.allSettled([
      writeArea('sync', payload),
      writeArea('local', payload)
    ]);

    const syncOk = syncResult.status === 'fulfilled';
    const localOk = localResult.status === 'fulfilled';

    if (!syncOk && !localOk) {
      throw syncResult.reason || localResult.reason || new Error('Could not save settings.');
    }

    return {
      settings: payload.settings,
      syncOk,
      localOk
    };
  }

  global.DebloatSeekSettings = Object.freeze({
    STORAGE_KEY,
    DEFAULT_SETTINGS,
    SETTING_KEYS,
    normalizeSettings,
    extractSettings,
    loadSettings,
    saveSettings,
    hasStoredSettings
  });
})(globalThis);
