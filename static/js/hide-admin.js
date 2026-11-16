/*
 * Removes every admin control from the PUBLIC page. Admin work now lives at /admin behind a login.
 * - hides the Admin tab/section, the admin table, "Inspect & Proof" and the "Admin Action" link in map popups
 *   (hidden rather than deleted, so the rest of the app's code that looks them up keeps working)
 * - if anything still calls openAdminModal(), it sends the visitor to the /admin login instead
 */
(function () {
  'use strict';
  const css = document.createElement('style');
  css.textContent =
    '[id*="reseed" i]:not([data-admin-login]),[id*="admin" i]:not(html):not(body):not([data-admin-login]),[class*="admin" i]:not(html):not(body):not([data-admin-login]),[data-tab*="admin" i]:not([data-admin-login]),[data-target*="admin" i]:not([data-admin-login]),[data-view*="admin" i]:not([data-admin-login]),[data-page*="admin" i]:not([data-admin-login]),[data-section*="admin" i]:not([data-admin-login]),[href*="admin" i]:not([data-admin-login]),[onclick*="openAdminModal"]:not([data-admin-login]),[aria-controls*="admin" i]:not([data-admin-login]){display:none !important;}';
  document.head.appendChild(css);

  const TEXT = /^\s*(reseed(\s+data)?|reset\s+(demo\s+)?data|admin(\s*(&|and)\s*proof|\s+(action|panel|dashboard|login|access))?|inspect\s*(&|and)\s*proof|admin action)\b/i;
  function hideByText(root) {
    (root.querySelectorAll ? root.querySelectorAll('a,button,li,[role="tab"],.tab,.nav-item,.nav-link') : []).forEach(function (el) {
      if (!el.hasAttribute('data-admin-login') && TEXT.test(el.textContent || '') && (el.textContent || '').length < 40) el.style.setProperty('display', 'none', 'important');
    });
  }
  hideByText(document);
  new MutationObserver(function (muts) {
    muts.forEach(function (m) { m.addedNodes.forEach(function (n) { if (n.nodeType === 1) hideByText(n); }); });
  }).observe(document.documentElement, { childList: true, subtree: true });

  function redirect() { window.location.href = '/admin'; }
  let tries = 0;
  const t = setInterval(function () { window.openAdminModal = redirect; if (++tries > 100) clearInterval(t); }, 200);
  window.openAdminModal = redirect;
  console.info('[hide-admin] public page: admin controls hidden');
})();
