/*
 * Admin gate: asks for (and verifies) the admin token BEFORE the admin panel opens, wherever it is opened from
 * (the Admin & Proof table or the "Admin Action" link inside a map popup). Without this the panel opened freely
 * and the password was only requested when saving. The token is remembered for the browser session.
 */
(function () {
  'use strict';

  async function verifyAdmin() {
    let res;
    if (typeof window.adminFetch === 'function') {
      res = await window.adminFetch('/api/admin/check', { method: 'POST' });   // prompts if no token is stored yet
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
    } catch (err) {
      // prompt cancelled -> stay quiet
    }
    return false;
  }

  function install() {
    const original = window.openAdminModal;
    if (typeof original !== 'function' || original.__gated) return;
    const gated = async function () {
      if (!(await requireAdminLogin())) return;
      return original.apply(this, arguments);
    };
    gated.__gated = true;
    window.openAdminModal = gated;
  }

  window.requireAdminLogin = requireAdminLogin;
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', install);
  else install();
})();
