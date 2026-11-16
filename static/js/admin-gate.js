/*
 * Admin gate v2: asks for (and verifies) the admin token BEFORE the admin panel opens, from anywhere it is opened
 * (Admin tab, or the "Admin Action" link inside a map popup).
 * Works three ways so it does not depend on how the app defines openAdminModal:
 *   1. wraps window.openAdminModal (waits for it to exist, polling for up to 20s)
 *   2. a capture-phase click guard on any element whose inline onclick mentions openAdminModal, or whose text is "Admin Action"
 *   3. exposes window.requireAdminLogin() for any other code to call.
 * The token is kept in sessionStorage ('gwr_admin_token') until the tab closes.
 */
(function () {
  'use strict';
  const LOG = '[admin-gate]';
  let bypass = false;

  async function verifyAdmin() {
    let res;
    if (typeof window.adminFetch === 'function') {
      res = await window.adminFetch('/api/admin/check', { method: 'POST' });
    } else {
      let token = sessionStorage.getItem('gwr_admin_token');
      if (!token) {
        token = window.prompt('Enter the admin token:');
        if (!token) throw new Error('Admin token required');
        token = token.trim();
        sessionStorage.setItem('gwr_admin_token', token);
      }
      res = await fetch('/api/admin/check', { method: 'POST', headers: { 'X-Admin-Token': token } });
      if (res.status === 401 || res.status === 503) sessionStorage.removeItem('gwr_admin_token');
    }
    return res;
  }

  function toast(msg, type) {
    if (typeof window.showToast === 'function') window.showToast(msg, type || 'error');
    else window.alert(msg);
  }

  async function requireAdminLogin() {
    try {
      const res = await verifyAdmin();
      if (res.ok) return true;
      if (res.status === 503) toast('Admin actions are disabled: ADMIN_TOKEN is not set on the server.');
      else if (res.status === 401) toast('Wrong admin token. Admin access denied.');
      else toast('Could not verify admin access (server error ' + res.status + ').');
    } catch (err) { /* prompt cancelled -> stay quiet */ }
    return false;
  }

  // 1. wrap the function once it exists
  function wrapFunction() {
    const original = window.openAdminModal;
    if (typeof original !== 'function') return false;
    if (original.__gated) return true;
    const gated = async function () {
      if (!bypass && !(await requireAdminLogin())) return;
      return original.apply(this, arguments);
    };
    gated.__gated = true;
    window.openAdminModal = gated;
    console.info(LOG, 'wrapped window.openAdminModal');
    return true;
  }

  // 2. click guard that works even if the function is not reachable from window
  function isAdminTrigger(el) {
    if (!el || !el.getAttribute) return false;
    const oc = el.getAttribute('onclick') || '';
    if (/openAdminModal/.test(oc)) return true;
    const txt = (el.textContent || '').trim();
    return /^admin action\b/i.test(txt) && /^(a|button)$/i.test(el.tagName);
  }

  document.addEventListener('click', function (e) {
    if (bypass) return;
    let el = e.target;
    while (el && el !== document && !isAdminTrigger(el)) el = el.parentNode;
    if (!el || el === document) return;
    e.preventDefault();
    e.stopImmediatePropagation();
    requireAdminLogin().then(function (ok) {
      if (!ok) return;
      bypass = true;
      try { el.click(); } finally { bypass = false; }
    });
  }, true);

  window.requireAdminLogin = requireAdminLogin;

  let tries = 0;
  const timer = setInterval(function () {
    tries += 1;
    if (wrapFunction() || tries > 100) {
      clearInterval(timer);
      if (tries > 100) console.warn(LOG, 'window.openAdminModal not found; relying on the click guard only');
    }
  }, 200);
  wrapFunction();
  console.info(LOG, 'loaded v2');
})();
