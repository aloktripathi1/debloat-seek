/*
 * Debloat SEEK background service worker.
 *
 * Seeds safe defaults on first install. Updates never overwrite a user's
 * existing preferences.
 */
importScripts('settings.js');

chrome.runtime.onInstalled.addListener((details) => {
  if (details.reason !== 'install') {
    return;
  }

  (async () => {
    try {
      const hasStoredSettings = await DebloatSeekSettings.hasStoredSettings();

      if (!hasStoredSettings) {
        await DebloatSeekSettings.saveSettings(DebloatSeekSettings.DEFAULT_SETTINGS);
      }
    } catch (error) {
      console.warn('Debloat SEEK: could not initialize default settings.', error);
    }
  })();
});
