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
    '[id*="admin" i]:not(html):not(body),[class*="admin" i]:not(html):not(body),[data-tab*="admin" i],[data-target*="admin" i],' +
    '[data-view*="admin" i],[data-page*="admin" i],[data-section*="admin" i],[href*="admin" i],[onclick*="openAdminModal"],[aria-controls*="admin" i]' +
    '{display:none !important;}';
  document.head.appendChild(css);

  const TEXT = /^\s*(admin(\s*(&|and)\s*proof|\s+(action|panel|dashboard|login|access))?|inspect\s*(&|and)\s*proof|admin action)\b/i;
  function hideByText(root) {
    (root.querySelectorAll ? root.querySelectorAll('a,button,li,[role="tab"],.tab,.nav-item,.nav-link') : []).forEach(function (el) {
      if (TEXT.test(el.textContent || '') && (el.textContent || '').length < 40) el.style.setProperty('display', 'none', 'important');
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
