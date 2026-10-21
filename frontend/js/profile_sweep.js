/**
 * 登入前清理本機舊資料。
 * 只動這個網站的 Cache Storage、Service Worker，以及會讓再次登入去拉整個項目的記住值。
 * 不碰 Cookie、主題、側欄、字級、開門動畫偏好。
 */
(function () {
  var BUILD_KEY = 'qs_app_build';
  var PROJECT_KEY = 'qs_project_id';
  var RESTORE_KEY = 'qs_auto_restore_project';
  var SWEEP_FLAG = 'qs_profile_sweep_v1';
  var RELOAD_KEY = 'qs_html_reload_for';
  var NOTE_KEY = 'qs_profile_cleaned';
  var STATUS_MS = 4000;

  function metaBuild() {
    var el = document.querySelector('meta[name="ossyscu-build"]');
    var value = el ? (el.getAttribute('content') || '') : '';
    if (!value || value === '__APP_BUILD__') return '';
    return value;
  }

  function markCleaned() {
    try { sessionStorage.setItem(NOTE_KEY, '1'); } catch (_) { /* private mode */ }
  }

  function dropRememberedProject() {
    try {
      localStorage.removeItem(PROJECT_KEY);
      localStorage.setItem(RESTORE_KEY, '0');
    } catch (_) { /* ignore */ }
  }

  /** 這個 Profile 尚未清過，或記住的版本和現在的頁面不一致。 */
  function clearStaleMemory(ver) {
    var cleaned = false;
    try {
      if (localStorage.getItem(SWEEP_FLAG) !== '1') {
        var hadProject = !!localStorage.getItem(PROJECT_KEY);
        var hadRestore = localStorage.getItem(RESTORE_KEY) === '1';
        dropRememberedProject();
        localStorage.setItem(SWEEP_FLAG, '1');
        if (hadProject || hadRestore) {
          markCleaned();
          cleaned = true;
        }
      }
      if (!ver) return cleaned;
      var prev = localStorage.getItem(BUILD_KEY);
      if (prev && prev !== ver) {
        dropRememberedProject();
        markCleaned();
        cleaned = true;
      }
      localStorage.setItem(BUILD_KEY, ver);
    } catch (_) { /* ignore */ }
    return cleaned;
  }

  clearStaleMemory(metaBuild());

  function purgeCaches() {
    var jobs = [];
    var removed = 0;
    if (window.caches && caches.keys) {
      jobs.push(caches.keys().then(function (keys) {
        removed += keys.length;
        return Promise.all(keys.map(function (key) { return caches.delete(key); }));
      }).catch(function () {}));
    }
    if (navigator.serviceWorker && navigator.serviceWorker.getRegistrations) {
      jobs.push(navigator.serviceWorker.getRegistrations().then(function (regs) {
        removed += regs.length;
        return Promise.all(regs.map(function (reg) { return reg.unregister(); }));
      }).catch(function () {}));
    }
    return Promise.all(jobs).then(function () { return removed; }).catch(function () { return 0; });
  }

  function reloadOnce(ver) {
    try {
      if (sessionStorage.getItem(RELOAD_KEY) === ver) return false;
      sessionStorage.setItem(RELOAD_KEY, ver);
    } catch (_) {
      return false;
    }
    var url = new URL(window.location.href);
    url.searchParams.set('_cb', String(Date.now()));
    window.location.replace(url.toString());
    return true;
  }

  function prepare() {
    return purgeCaches().then(function (removed) {
      if (removed > 0) markCleaned();
      var ctrl = new AbortController();
      var timer = setTimeout(function () { ctrl.abort(); }, STATUS_MS);
      return fetch('/api/system/status', {
        credentials: 'include',
        cache: 'no-store',
        signal: ctrl.signal,
      }).finally(function () { clearTimeout(timer); }).then(function (r) {
        return r.json();
      }).then(function (json) {
        var ver = json && json.data && json.data.app_version;
        if (!ver) return { cleaned: false };
        var meta = metaBuild();
        clearStaleMemory(ver);
        if (meta && meta !== ver && reloadOnce(ver)) {
          return { reloading: true, cleaned: true };
        }
        return { cleaned: false };
      });
    }).catch(function () {
      return { cleaned: false };
    });
  }

  window.qsProfileSweep = {
    prepare: prepare,
    consumeNote: function () {
      try {
        if (sessionStorage.getItem(NOTE_KEY) !== '1') return false;
        sessionStorage.removeItem(NOTE_KEY);
        return true;
      } catch (_) {
        return false;
      }
    },
  };
})();
