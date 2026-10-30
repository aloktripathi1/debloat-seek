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
    header: 'data-seek-header',
    transcript: 'data-seek-transcript',
    answers: 'data-seek-answers',
    objectives: 'data-seek-objectives',
    announcements: 'data-seek-announcements',
    forum: 'data-seek-forum',
    calculator: 'data-seek-calculator'
  });

  const SEEK_THEME_ATTRIBUTE = 'data-theme';
  const SEEK_THEME_SETTING_ATTRIBUTE = 'data-seek-theme-setting';
  const SEEK_THEME_STATE_ATTRIBUTE = 'data-seek-theme';

  let currentSettings = null;
  let systemThemeMedia = null;
  let rootThemeObserver = null;
  let tabObserver = null;
  let tabScanScheduled = false;

  const OBJECTIVES_TAB_ATTRIBUTE = 'data-seek-objectives-tab';
  const OBJECTIVES_ONLY_ATTRIBUTE = 'data-seek-objectives-only';

  // SEEK's Objectives tab has no stable hook of its own, so identify it by its
  // visible label and tag it for the stylesheet. Only attributes are written:
  // the tab, its panel, and every handler stay in place.
  function markObjectivesTabs() {
    const bars = document.querySelectorAll('app-lesson-view .tab-bar-wrapper');

    for (const bar of bars) {
      const tabs = bar.querySelectorAll('button.tab-item');
      let otherTabs = 0;

      for (const tab of tabs) {
        const isObjectives = (tab.textContent || '').trim().toLowerCase() === 'objectives';

        if (isObjectives) {
          tab.setAttribute(OBJECTIVES_TAB_ATTRIBUTE, '');
        } else {
          tab.removeAttribute(OBJECTIVES_TAB_ATTRIBUTE);
          otherTabs += 1;
        }
      }

      const host = bar.closest('app-tab-bar') || bar;

      if (tabs.length > 0 && otherTabs === 0) {
        host.setAttribute(OBJECTIVES_ONLY_ATTRIBUTE, '');
      } else {
        host.removeAttribute(OBJECTIVES_ONLY_ATTRIBUTE);
      }
    }
  }

  function scheduleObjectivesScan() {
    if (tabScanScheduled) {
      return;
    }

    tabScanScheduled = true;

    const run = () => {
      tabScanScheduled = false;

      if (document.querySelector('app-lesson-view')) {
        markObjectivesTabs();
      }
    };

    if (typeof globalThis.requestAnimationFrame === 'function') {
      globalThis.requestAnimationFrame(run);
    } else {
      globalThis.setTimeout(run, 50);
    }
  }

  function watchLessonTabs() {
    if (tabObserver) {
      return;
    }

    if (!document.body) {
      document.addEventListener('DOMContentLoaded', watchLessonTabs, { once: true });
      return;
    }

    // Angular re-renders the lesson view; re-tag the tab whenever the tab bar
    // or a lesson view is inserted. Attribute writes are not observed, so this
    // cannot loop.
    tabObserver = new MutationObserver((mutations) => {
      for (const mutation of mutations) {
        if (mutation.type !== 'childList') {
          continue;
        }

        for (const node of [...mutation.addedNodes, ...mutation.removedNodes]) {
          if (node.nodeType !== 1) {
            continue;
          }

          if (
            node.matches('.tab-bar-wrapper, .tab-item, app-tab-bar, app-lesson-view')
            || node.querySelector('.tab-bar-wrapper, .tab-item, app-tab-bar, app-lesson-view')
          ) {
            scheduleObjectivesScan();
            return;
          }
        }
      }
    });

    tabObserver.observe(document.body, { childList: true, subtree: true });
  }

  /*
   * SEEK's outline component calls revealSelected() whenever the route query
   * params change. That helper scrolls .outline-nav to the selected lesson and
   * keeps re-scrolling for 1.5s through a ResizeObserver, so switching course
   * tabs yanks the sidebar back to the last lesson. Keep the learner's scroll
   * position and expanded units instead.
   *
   * Content scripts run in an isolated world, so patching Element.scrollTo here
   * would not intercept SEEK's own call. The guard therefore watches the
   * outline's scroll events, distinguishes learner intent from SEEK's reveal,
   * and restores the last learner position. It only touches .outline-nav.
   */
  const OUTLINE_STATE_PREFIX = 'debloatSeek.outline.';
  const OUTLINE_RESTORE_WINDOW_MS = 1800;
  const OUTLINE_SAVE_DELAY_MS = 120;
  const OUTLINE_SETTLE_DELAY_MS = 180;
  const OUTLINE_INTENT_MS = 1600;
  const OUTLINE_TOUCH_MS = 2500;
  const OUTLINE_POINTER_MS = 400;

  let outlineObserver = null;
  let outlinePointerGuardInstalled = false;
  const initializedOutlines = new WeakSet();
  const outlineStates = new WeakMap();
  const activeOutlines = new Set();

  function outlineStorageKey() {
    const match = globalThis.location
      && globalThis.location.pathname.match(/^\/courses\/([^/]+)/i);

    return match ? OUTLINE_STATE_PREFIX + match[1] : null;
  }

  function currentOutlineId() {
    try {
      return new URL(globalThis.location.href).searchParams.get('id');
    } catch (error) {
      return null;
    }
  }

  function readOutlineState() {
    const key = outlineStorageKey();

    if (!key) {
      return null;
    }

    try {
      const raw = globalThis.sessionStorage.getItem(key);

      if (!raw) {
        return null;
      }

      const state = JSON.parse(raw);

      if (
        !state
        || typeof state.scrollTop !== 'number'
        || !Array.isArray(state.units)
      ) {
        return null;
      }

      return state;
    } catch (error) {
      return null;
    }
  }

  function saveOutlineState(nav) {
    const key = outlineStorageKey();

    if (!key || !nav || !nav.isConnected) {
      return;
    }

    const units = Array.from(nav.querySelectorAll('.unit-container')).map((unit, index) => ({
      index,
      title: (unit.querySelector('.unit-title')?.textContent || '').trim(),
      open: unit.classList.contains('is-open')
    }));

    try {
      globalThis.sessionStorage.setItem(key, JSON.stringify({
        scrollTop: Math.round(nav.scrollTop),
        selectedId: currentOutlineId(),
        units,
        updatedAt: Date.now()
      }));
    } catch (error) {
      // sessionStorage can be unavailable in privacy modes. The sidebar still
      // works, it just falls back to SEEK's default reveal behaviour.
    }
  }

  function outlineStateFor(nav) {
    let state = outlineStates.get(nav);

    if (!state) {
      state = {
        guardTarget: null,
        lastId: currentOutlineId(),
        intentUntil: 0,
        pointerDown: false,
        settleTimer: 0,
        saveTimer: 0,
        restore: { cancelled: false }
      };
      outlineStates.set(nav, state);
    }

    return state;
  }

  function scheduleOutlineSave(nav) {
    const state = outlineStateFor(nav);

    if (state.saveTimer) {
      globalThis.clearTimeout(state.saveTimer);
    }

    state.saveTimer = globalThis.setTimeout(() => {
      state.saveTimer = 0;
      saveOutlineState(nav);
    }, OUTLINE_SAVE_DELAY_MS);
  }

  function scheduleOutlineSettle(nav) {
    const state = outlineStateFor(nav);

    if (state.settleTimer) {
      globalThis.clearTimeout(state.settleTimer);
    }

    state.settleTimer = globalThis.setTimeout(() => {
      state.settleTimer = 0;

      if (!nav.isConnected || state.pointerDown) {
        return;
      }

      state.guardTarget = nav.scrollTop;
      state.lastId = currentOutlineId();
      saveOutlineState(nav);
    }, OUTLINE_SETTLE_DELAY_MS);
  }

  function markOutlineIntent(nav, duration) {
    const state = outlineStateFor(nav);

    state.intentUntil = Math.max(state.intentUntil, Date.now() + duration);
    state.restore.cancelled = true;
  }

  function releaseOutlinePointer() {
    for (const nav of activeOutlines) {
      if (!nav.isConnected) {
        activeOutlines.delete(nav);
        continue;
      }

      const state = outlineStates.get(nav);

      if (!state || !state.pointerDown) {
        continue;
      }

      state.pointerDown = false;
      markOutlineIntent(nav, OUTLINE_POINTER_MS);
      scheduleOutlineSettle(nav);
    }
  }

  function installOutlinePointerGuard() {
    if (
      outlinePointerGuardInstalled
      || typeof globalThis.addEventListener !== 'function'
    ) {
      return;
    }

    outlinePointerGuardInstalled = true;
    globalThis.addEventListener('pointerup', releaseOutlinePointer, { passive: true });
    globalThis.addEventListener('pointercancel', releaseOutlinePointer, { passive: true });
    globalThis.addEventListener('touchend', releaseOutlinePointer, { passive: true });
  }

  function applyOutlineExpansion(nav, state) {
    const units = Array.from(nav.querySelectorAll('.unit-container'));
    const byTitle = new Map();

    for (const unit of units) {
      const title = (unit.querySelector('.unit-title')?.textContent || '').trim();

      if (title) {
        byTitle.set(title, unit);
      }
    }

    for (const saved of state.units) {
      const indexed = Number.isInteger(saved.index) ? units[saved.index] : null;
      const indexedTitle = indexed
        ? (indexed.querySelector('.unit-title')?.textContent || '').trim()
        : '';
      const unit = indexed && (!saved.title || indexedTitle === saved.title)
        ? indexed
        : byTitle.get(saved.title);

      if (!unit) {
        continue;
      }

      if (unit.classList.contains('is-open') !== Boolean(saved.open)) {
        unit.querySelector('.unit-header')?.click();
      }
    }
  }

  function restoreOutlineState(nav, saved) {
    const state = outlineStateFor(nav);
    const currentId = currentOutlineId();
    const sameSelection = currentId === null || saved.selectedId === currentId;

    // A different lesson is a deliberate navigation. Let SEEK expand its parent
    // unit and reveal it instead of restoring the previous position.
    if (!sameSelection) {
      state.guardTarget = null;
      state.lastId = currentId;
      return;
    }

    state.restore = { cancelled: false };
    state.guardTarget = saved.scrollTop;
    state.lastId = currentId;

    const apply = () => {
      if (state.restore.cancelled || !nav.isConnected) {
        return;
      }

      applyOutlineExpansion(nav, saved);
      nav.scrollTop = saved.scrollTop;
    };

    apply();

    if (typeof globalThis.requestAnimationFrame === 'function') {
      globalThis.requestAnimationFrame(apply);
    }

    // SEEK applies its own expansion and reveal after the first render. Run
    // again once those settle so the saved state wins.
    globalThis.setTimeout(apply, 300);
    globalThis.setTimeout(apply, OUTLINE_RESTORE_WINDOW_MS - 100);
  }

  function initOutlineNav(nav) {
    if (initializedOutlines.has(nav)) {
      return;
    }

    initializedOutlines.add(nav);
    activeOutlines.add(nav);
    installOutlinePointerGuard();

    const state = outlineStateFor(nav);
    const markIntent = (duration) => markOutlineIntent(nav, duration);

    nav.addEventListener('wheel', () => markIntent(OUTLINE_INTENT_MS), { passive: true });
    nav.addEventListener('touchstart', () => markIntent(OUTLINE_TOUCH_MS), { passive: true });
    nav.addEventListener('touchmove', () => markIntent(OUTLINE_TOUCH_MS), { passive: true });
    nav.addEventListener('keydown', () => markIntent(OUTLINE_INTENT_MS));

    nav.addEventListener('pointerdown', (event) => {
      if (event.target instanceof Element && event.target.closest('button')) {
        return;
      }

      state.pointerDown = true;
      markIntent(OUTLINE_INTENT_MS);
    }, { passive: true });

    nav.addEventListener('scroll', () => {
      const now = Date.now();
      const id = currentOutlineId();
      const userDriven = state.pointerDown || now < state.intentUntil;

      if (userDriven) {
        state.guardTarget = nav.scrollTop;
        state.lastId = id;
        scheduleOutlineSave(nav);
        scheduleOutlineSettle(nav);
        return;
      }

      if (id !== state.lastId) {
        // The learner moved to another lesson. Let SEEK reveal it, then protect
        // the new position.
        state.lastId = id;
        state.guardTarget = null;
        scheduleOutlineSettle(nav);
        return;
      }

      if (
        state.guardTarget !== null
        && Math.abs(nav.scrollTop - state.guardTarget) > 1
      ) {
        // Same lesson: this is SEEK's redundant re-reveal after a tab change.
        nav.scrollTop = state.guardTarget;
        return;
      }

      scheduleOutlineSettle(nav);
    }, { passive: true });

    nav.addEventListener('click', (event) => {
      if (!(event.target instanceof Element)) {
        return;
      }

      if (event.target.closest('.child-row')) {
        // Let SEEK reveal the chosen lesson. The new id also passes the guard.
        markIntent(OUTLINE_INTENT_MS * 2);
        state.guardTarget = null;
        state.lastId = null;
        scheduleOutlineSave(nav);
        return;
      }

      if (event.target.closest('.unit-header')) {
        // Programmatic clicks come from restoring saved expansion. They must
        // not cancel the rest of the restore sequence.
        if (!event.isTrusted) {
          return;
        }

        markIntent(OUTLINE_POINTER_MS);
        scheduleOutlineSave(nav);
      }
    });

    const saved = readOutlineState();

    if (saved) {
      restoreOutlineState(nav, saved);
    } else {
      state.guardTarget = null;
      state.lastId = currentOutlineId();
    }
  }

  function watchOutline() {
    if (outlineObserver) {
      return;
    }

    if (!document.body) {
      document.addEventListener('DOMContentLoaded', watchOutline, { once: true });
      return;
    }

    const scan = () => {
      for (const nav of activeOutlines) {
        if (!nav.isConnected) {
          activeOutlines.delete(nav);
        }
      }

      for (const nav of document.querySelectorAll('app-course-outline .outline-nav')) {
        initOutlineNav(nav);
      }
    };

    scan();

    outlineObserver = new MutationObserver((mutations) => {
      for (const mutation of mutations) {
        if (mutation.type !== 'childList') {
          continue;
        }

        for (const node of mutation.addedNodes) {
          if (node.nodeType !== 1) {
            continue;
          }

          if (
            node.matches?.('.outline-nav')
            || node.querySelector?.('.outline-nav')
          ) {
            scan();
            return;
          }
        }
      }
    });

    outlineObserver.observe(document.body, { childList: true, subtree: true });
  }

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
    watchLessonTabs();
    watchOutline();
    markObjectivesTabs();
    chrome.storage.onChanged.addListener(handleStorageChange);
  }

  init().catch(() => {
    // Keep the page usable even if the storage listener cannot be registered.
    if (!currentSettings) {
      applySettings(DEFAULT_SETTINGS);
    }

    watchSystemTheme();
    watchSeekTheme();
    watchLessonTabs();
    watchOutline();
    markObjectivesTabs();
  });
})();
