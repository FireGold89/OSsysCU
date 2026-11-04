/** /admin 共用：API、toast（不依賴 main.js） */
const API = `${window.location.origin}/api`;

function escHtml(s) {
  return String(s || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function toast(msg, type = 'info') {
  if (type === 'warn') type = 'warning';
  const container = document.getElementById('toastContainer');
  if (!container) return;
  const el = document.createElement('div');
  el.className = `admin-toast admin-toast-${type}`;
  const icons = { success: '✅', error: '❌', warning: '⚠️', info: 'ℹ️' };
  el.innerHTML = `<span>${icons[type] || 'ℹ️'}</span><span>${escHtml(msg)}</span>`;
  container.appendChild(el);
  el.onclick = () => el.remove();
  setTimeout(() => el.remove(), 4500);
}

async function api(method, path, body, opts = {}) {
  const silent = opts.silent === true;
  const fetchOpts = {
    method,
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
  };
  if (body) fetchOpts.body = JSON.stringify(body);
  const r = await fetch(API + path, fetchOpts);
  const text = await r.text();
  if (r.status === 401 && !path.startsWith('/auth/')) {
    const next = encodeURIComponent(window.location.pathname + window.location.search);
    window.location.href = `/login.html?next=${next}`;
    throw new Error('請先登入');
  }
  let json;
  try {
    json = JSON.parse(text);
  } catch (e) {
    throw new Error(r.ok ? '伺服器回應格式錯誤' : `伺服器錯誤 (${r.status})`);
  }
  if (!json.success) throw new Error(json.error || '操作失敗');
  return json.data;
}

window.Auth = { authRequired: true, isAdmin: () => true };

async function adminLogout() {
  try {
    await fetch(`${API}/auth/logout`, { method: 'POST', credentials: 'include' });
  } catch (e) { /* ignore */ }
  const next = encodeURIComponent('/admin' + (window.location.hash || ''));
  window.location.href = `/login.html?next=${next}`;
}
