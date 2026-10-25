/*
 * Debloat SEEK popup controller.
 *
 * Writes complete, normalized settings snapshots to shared storage. Saves are
 * chained so rapid toggling cannot write an older snapshot after a newer one.
 */
(function () {
  'use strict';

  const api = globalThis.DebloatSeekSettings;

  if (!api) {
    return;
  }

  const {
    DEFAULT_SETTINGS,
    loadSettings,
    saveSettings
  } = api;

  const controls = new Map();
  const statusElement = document.getElementById('status');
  const summaryElement = document.getElementById('summary');
  const restoreButton = document.getElementById('restore-defaults');

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

    if (summaryElement) {
      const enabledDefaults = ['unitNav', 'overview', 'divider']
        .filter((key) => settings[key]).length;
      const enabledOptional = ['transcript', 'announcements', 'forum', 'calculator', 'header']
        .filter((key) => settings[key]).length;

      summaryElement.textContent = `${enabledDefaults}/3 default · ${enabledOptional}/5 optional`;
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
    if (!Object.prototype.hasOwnProperty.call(DEFAULT_SETTINGS, key)) {
      return;
    }

    settings = {
      ...settings,
      [key]: input.checked
    };

    render();
    queueSave();
  }

  function restoreDefaults() {
    settings = { ...DEFAULT_SETTINGS };
    render();
    queueSave();
  }

  async function init() {
    for (const input of document.querySelectorAll('input[data-setting]')) {
      const key = input.dataset.setting;

      if (!Object.prototype.hasOwnProperty.call(DEFAULT_SETTINGS, key)) {
        continue;
      }

      controls.set(key, input);
      input.addEventListener('change', () => handleToggle(key, input));
    }

    if (restoreButton) {
      restoreButton.addEventListener('click', restoreDefaults);
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
