/* Small "Admin Login" link on the public page. It only opens /admin, where the login box is. */
(function () {
  'use strict';
  if (location.pathname.indexOf('/admin') === 0 || document.querySelector('[data-admin-login]')) return;
  const a = document.createElement('a');
  a.href = '/admin';
  a.textContent = 'Admin Login';
  a.setAttribute('data-admin-login', '1');
  a.style.cssText = 'position:fixed;left:12px;bottom:12px;z-index:9999;background:#1e3a2b;color:#fff;font:600 12px system-ui,sans-serif;' +
    'padding:7px 12px;border-radius:99px;text-decoration:none;opacity:.85;box-shadow:0 2px 8px rgba(0,0,0,.2)';
  a.onmouseenter = function () { a.style.opacity = '1'; };
  a.onmouseleave = function () { a.style.opacity = '.85'; };
  (document.body || document.documentElement).appendChild(a);
})();
