/*
 * Live sync for the PUBLIC site: when an admin (or another citizen) changes a report, show a small
 * "Updates available - Refresh" bar so visitors see it without guessing to reload.
 * Polls /api/reports every 20 s while the tab is visible. It never reloads by itself, so a half-filled
 * report form is never lost.
 */
(function () {
  'use strict';
  if (location.pathname.indexOf('/admin') === 0) return;          // the admin page has its own refresh
  const EVERY_MS = 20000;
  let baseline = null, banner = null, busy = false;

  function fingerprint(list) {
    return list.length + '|' + list.map(function (r) {
      return [r.id, r.status, r.upvotes || 0, r.after_image_url || ''].join(':');
    }).sort().join(',');
  }

  async function snapshot() {
    const res = await fetch('/api/reports', { cache: 'no-store' });
    if (!res.ok) throw new Error('HTTP ' + res.status);
    return fingerprint((await res.json()).reports || []);
  }

  function showBanner() {
    if (banner) return;
    banner = document.createElement('div');
    banner.setAttribute('role', 'status');
    banner.style.cssText = 'position:fixed;left:50%;bottom:18px;transform:translateX(-50%);z-index:99999;background:#1e3a2b;color:#fff;' +
      'padding:10px 16px;border-radius:10px;font:600 14px system-ui,sans-serif;box-shadow:0 6px 20px rgba(0,0,0,.25);display:flex;gap:12px;align-items:center';
    banner.innerHTML = '<span>Updates available</span>';
    const btn = document.createElement('button');
    btn.textContent = 'Refresh';
    btn.style.cssText = 'background:#b8963e;color:#fff;border:0;border-radius:8px;padding:6px 12px;font:inherit;cursor:pointer';
    btn.onclick = function () { location.reload(); };
    const x = document.createElement('button');
    x.textContent = '\u00d7'; x.setAttribute('aria-label', 'Dismiss');
    x.style.cssText = 'background:transparent;color:#fff;border:0;font-size:18px;cursor:pointer;line-height:1';
    x.onclick = function () { banner.remove(); banner = null; rebaseline(); };
    banner.appendChild(btn); banner.appendChild(x);
    document.body.appendChild(banner);
  }

  async function rebaseline() { try { baseline = await snapshot(); } catch (e) { /* keep old */ } }

  async function check() {
    if (busy || document.hidden) return;
    busy = true;
    try {
      const now = await snapshot();
      if (baseline === null) baseline = now;
      else if (now !== baseline) showBanner();
    } catch (e) { /* offline or server busy: try again next time */ }
    busy = false;
  }

  // A change made by THIS visitor (new report, upvote) should not trigger the banner for themselves.
  const origFetch = window.fetch;
  window.fetch = function (input, init) {
    const p = origFetch.apply(this, arguments);
    const method = ((init && init.method) || (input && input.method) || 'GET').toUpperCase();
    const url = typeof input === 'string' ? input : (input && input.url) || '';
    if (method !== 'GET' && /\/api\/reports/.test(url)) p.then(function () { setTimeout(rebaseline, 2500); }, function () {});
    return p;
  };

  rebaseline();
  setInterval(check, EVERY_MS);
  document.addEventListener('visibilitychange', function () { if (!document.hidden) check(); });
  console.info('[live-sync] watching for updates');
})();
