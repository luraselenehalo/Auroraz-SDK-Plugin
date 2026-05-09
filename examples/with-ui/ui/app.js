// with-ui — example postMessage protocol consumer.
//
// AURORAZ desktop sends `auroraz/init` once on iframe load with this
// plugin's settings + permissions. Plugin replies via `plugin/notify`
// to surface a toast in AURORAZ.

(function () {
  const TRUSTED_ORIGINS = new Set([
    window.location.origin,
    'http://localhost:5173',
    'http://127.0.0.1:5173',
  ]);

  const status = document.getElementById('status');
  const output = document.getElementById('output');
  const pingBtn = document.getElementById('ping');

  window.addEventListener('message', (e) => {
    if (!TRUSTED_ORIGINS.has(e.origin)) return;
    const data = e.data || {};
    if (data.type === 'auroraz/init') {
      status.textContent = `Init OK · plugin_id=${data.plugin_id} · ${(data.permissions || []).length} permissions`;
      output.textContent = JSON.stringify({
        settings: data.settings,
        permissions: data.permissions,
      }, null, 2);
    } else if (data.type === 'auroraz/settings-changed') {
      output.textContent = JSON.stringify({ settings: data.settings, _ts: Date.now() }, null, 2);
    }
  });

  pingBtn.addEventListener('click', () => {
    window.parent.postMessage(
      { type: 'plugin/notify', message: 'Hi from with-ui iframe', level: 'info' },
      '*',
    );
  });

  // Tell AURORAZ we're ready to receive auroraz/init.
  window.parent.postMessage({ type: 'plugin/ready' }, '*');
})();
