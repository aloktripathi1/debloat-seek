/*
 * Debloat SEEK popup controller.
 *
 * Writes complete, normalized settings snapshots to shared storage. Saves are
 * chained so rapid toggling cannot write an older snapshot after a newer one.
 * The popup follows the operating-system light/dark preference; the saved theme
 * controls SEEK pages only.
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
    THEME_VALUES,
    loadSettings,
    saveSettings
  } = api;

  const controls = new Map();
  const themeButtons = new Map();
  const statusElement = document.getElementById('status');
  const summaryElement = document.getElementById('summary');
  const restoreButton = document.getElementById('restore-defaults');
  const showAllButton = document.getElementById('show-all-questions');

  let settings = { ...DEFAULT_SETTINGS };
  let saveChain = Promise.resolve();

  function setStatus(message, tone) {
    if (!statusElement) {
      return;
    }

    statusElement.textContent = message;
    statusElement.dataset.tone = tone || 'neutral';
  }

  function render() {
    for (const [key, input] of controls) {
      const enabled = Boolean(settings[key]);
      input.checked = enabled;

      const stateLabel = document.querySelector(`[data-state-for="${key}"]`);

      if (stateLabel) {
        stateLabel.textContent = enabled ? 'On' : 'Off';
      }
    }

    for (const [theme, button] of themeButtons) {
      const selected = settings.theme === theme;
      button.setAttribute('aria-checked', selected ? 'true' : 'false');
      button.tabIndex = selected ? 0 : -1;
    }

    if (summaryElement) {
      const enabled = BOOLEAN_SETTING_KEYS.filter((key) => settings[key]).length;
      const total = BOOLEAN_SETTING_KEYS.length;
      summaryElement.textContent = `${enabled} on · ${total - enabled} off`;
    }
  }

  function queueSave() {
    const snapshot = { ...settings };

    saveChain = saveChain.then(async () => {
      setStatus('Saving…', 'pending');

      try {
        const result = await saveSettings(snapshot);

        if (result.syncOk) {
          setStatus('Saved. Open SEEK tabs update automatically.', 'success');
        } else {
          setStatus('Saved locally. Chrome sync is unavailable.', 'warning');
        }
      } catch (error) {
        console.error('Debloat SEEK: failed to save settings.', error);
        setStatus('Could not save settings. Please try again.', 'error');
      }
    });
  }

  function handleToggle(key, input) {
    if (!BOOLEAN_SETTING_KEYS.includes(key)) {
      return;
    }

    settings = {
      ...settings,
      [key]: input.checked
    };

    render();
    queueSave();
  }

  function handleTheme(theme) {
    if (!THEME_VALUES.includes(theme) || settings.theme === theme) {
      return;
    }

    settings = {
      ...settings,
      theme
    };

    render();
    queueSave();
  }

  function handleThemeKeydown(event) {
    const navigationKeys = ['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Home', 'End'];

    if (!navigationKeys.includes(event.key)) {
      return;
    }

    event.preventDefault();

    const themes = [...themeButtons.keys()];
    const current = themes.indexOf(settings.theme);
    let next = current;

    if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') {
      next = (current - 1 + themes.length) % themes.length;
    } else if (event.key === 'ArrowRight' || event.key === 'ArrowDown') {
      next = (current + 1) % themes.length;
    } else if (event.key === 'Home') {
      next = 0;
    } else if (event.key === 'End') {
      next = themes.length - 1;
    }

    const nextTheme = themes[next];
    handleTheme(nextTheme);
    themeButtons.get(nextTheme)?.focus();
  }

  function restoreDefaults() {
    settings = { ...DEFAULT_SETTINGS };
    render();
    queueSave();
  }

  async function showAllQuestions() {
    if (!showAllButton || showAllButton.disabled) {
      return;
    }

    showAllButton.disabled = true;
    setStatus('Opening all questions…', 'pending');

    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

      if (!tab?.id) {
        throw new Error('No active tab');
      }

      const response = await chrome.tabs.sendMessage(tab.id, {
        type: 'debloat-seek:show-all-questions'
      });

      if (response?.ok) {
        setStatus('All questions opened.', 'success');
        window.close();
        return;
      }

      setStatus(response?.reason || 'Open a quiz page with numbered questions first.', 'warning');
    } catch (error) {
      console.error('Debloat SEEK: could not open all questions.', error);
      setStatus('Open a SEEK quiz tab first, then try again.', 'error');
    } finally {
      showAllButton.disabled = false;
    }
  }

  function bindThemeControls() {
    for (const button of document.querySelectorAll('[data-theme-option]')) {
      const theme = button.dataset.themeOption;

      if (!THEME_VALUES.includes(theme)) {
        continue;
      }

      themeButtons.set(theme, button);
      button.addEventListener('click', () => handleTheme(theme));
      button.addEventListener('keydown', handleThemeKeydown);
    }
  }

  async function init() {
    for (const input of document.querySelectorAll('input[data-setting]')) {
      const key = input.dataset.setting;

      if (!BOOLEAN_SETTING_KEYS.includes(key)) {
        continue;
      }

      controls.set(key, input);
      input.addEventListener('change', () => handleToggle(key, input));
    }

    bindThemeControls();

    if (restoreButton) {
      restoreButton.addEventListener('click', restoreDefaults);
    }

    if (showAllButton) {
      showAllButton.addEventListener('click', showAllQuestions);
    }

    try {
      settings = await loadSettings();
      render();
      setStatus('Settings loaded. Changes apply to open SEEK tabs.', 'neutral');
    } catch (error) {
      console.error('Debloat SEEK: failed to load settings.', error);
      settings = { ...DEFAULT_SETTINGS };
      render();
      setStatus('Using safe defaults because saved settings could not be loaded.', 'warning');
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, { once: true });
  } else {
    init();
  }
})();
