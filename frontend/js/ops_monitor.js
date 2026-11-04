(function () {
  const API = window.location.origin + '/api';

  function $(id) { return document.getElementById(id); }

  function fmtBytes(n) {
    const v = Number(n) || 0;
    if (v < 1024) return v + ' B';
    if (v < 1024 * 1024) return (v / 1024).toFixed(1) + ' KB';
    return (v / (1024 * 1024)).toFixed(1) + ' MB';
  }

  function fmtUptime(sec) {
    const s = Math.max(0, Number(sec) || 0);
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    if (h > 0) return h + ' 小時 ' + m + ' 分';
    return m + ' 分';
  }

  function fmtAgo(sec) {
    if (sec == null || sec === '') return '';
    const s = Math.max(0, Number(sec) || 0);
    if (s < 60) return '剛剛';
    if (s < 3600) return Math.floor(s / 60) + ' 分鐘前';
    if (s < 86400) return Math.floor(s / 3600) + ' 小時前';
    return Math.floor(s / 86400) + ' 日前';
  }

  const OCR_MODE = {
    auto: '自動',
    quark_handwritten: '夸克手寫',
    quark_general: '夸克通用',
    quark_invoice: '夸克商業發票',
    local: '僅本地 RapidOCR',
  };

  function card(label, value, note) {
    const el = document.createElement('article');
    el.className = 'ops-card';
    el.innerHTML = '<div class="ops-k"></div><div class="ops-v"></div>';
    el.querySelector('.ops-k').textContent = label;
    el.querySelector('.ops-v').textContent = value;
    if (note) {
      const n = document.createElement('div');
      n.className = 'ops-note';
      n.textContent = note;
      el.appendChild(n);
    }
    return el;
  }

  function showDenied(text) {
    $('opsMsg').hidden = false;
    $('opsMsg').textContent = text;
    $('opsGrid').hidden = true;
    $('opsOcr').hidden = true;
    $('opsUploads').hidden = true;
    $('opsWrites').hidden = true;
    $('opsRefresh').hidden = true;
    $('opsAutoWrap').hidden = true;
    stopAuto();
  }

  async function loadStatus() {
    const r = await fetch(API + '/admin/ops-status', { credentials: 'include' });
    const json = await r.json().catch(() => ({}));
    if (r.status === 401) {
      window.location.replace('/login.html?next=/admin');
      return;
    }
    if (!r.ok || !json.success) {
      showDenied(json.error || '需要管理員');
      return;
    }
    const d = json.data || {};
    $('opsMsg').hidden = true;
    $('opsRefresh').hidden = false;
    $('opsAutoWrap').hidden = false;
    const grid = $('opsGrid');
    grid.hidden = false;
    const loginNote = d.auth_enabled
      ? '管理員閒置 ' + (d.idle_minutes_admin || '—') + ' 分鐘 · 其他 ' + (d.idle_minutes_user || '—') + ' 分鐘 · 登入保留 ' + (d.session_days || '—') + ' 天'
      : '';
    const dbNote = [
      d.journal_mode || '',
      d.busy_timeout_ms != null ? 'busy ' + d.busy_timeout_ms + ' ms' : '',
    ].filter(Boolean).join(' · ');
    grid.replaceChildren(
      card('版本', d.app_version || '—', d.deployment_label || d.deployment_tier || ''),
      card('登入', d.auth_enabled ? '已啟用' : '未啟用', loginNote),
      card('資料庫', d.db_exists ? fmtBytes(d.db_size_bytes) : '找不到', dbNote),
      card('資料庫最後修改', d.db_mtime || '—', d.db_mtime ? fmtAgo(d.db_age_sec) : ''),
      card('項目 / 付款', (d.project_count || 0) + ' / ' + (d.payment_count || 0), d.volume_mounted ? '資料目錄已掛載 /data' : (d.data_dir || '')),
      card('上傳檔', (d.upload_count || 0) + ' 個 · ' + fmtBytes(d.upload_bytes), '含子目錄'),
      card('還原權杖', d.restore_token_configured ? '已設定' : '未設定', '不顯示權杖內容'),
      card('本 worker 記憶體', d.worker_rss_mb != null ? d.worker_rss_mb + ' MB' : '—', '只代表處理此請求的行程，不是整機'),
      card('本 worker 已運行', fmtUptime(d.process_uptime_sec)),
    );
    const engines = d.ocr_engines || [];
    $('opsOcr').hidden = false;
    $('opsOcrMode').textContent = '模式：' + (OCR_MODE[d.ocr_mode] || d.ocr_mode || '—');
    const list = $('opsOcrList');
    list.replaceChildren();
    engines.forEach((eng) => {
      const span = document.createElement('span');
      span.className = 'ops-badge ' + (eng.ready ? 'ok' : 'bad');
      span.textContent = eng.name || '';
      list.appendChild(span);
    });
    const storage = d.upload_storage || [];
    $('opsUploads').hidden = false;
    const upBody = $('opsUploadBody');
    upBody.replaceChildren();
    storage.forEach((row) => {
      if (!row.files) return;
      const tr = document.createElement('tr');
      tr.innerHTML =
        '<td><code>' + (row.id || '') + '</code><br><span class="ops-sub">' + (row.label || '') + '</span></td>' +
        '<td>' + (row.feature || '') + '<br><span class="ops-sub">' + (row.path_hint || '') + '</span></td>' +
        '<td>' + row.files + '</td>' +
        '<td>' + fmtBytes(row.bytes) + '</td>';
      upBody.appendChild(tr);
    });
    if (!upBody.children.length) {
      const tr = document.createElement('tr');
      const td = document.createElement('td');
      td.colSpan = 4;
      td.textContent = '（尚無已分類檔案，或僅有舊版根目錄檔）';
      tr.appendChild(td);
      upBody.appendChild(tr);
    }
    const gen = d.generated_exports || [];
    $('opsGeneratedHint').textContent = gen.length
      ? '不寫 uploads 的匯出：' + gen.map((g) => g.label).join('、')
      : '';
    const rows = d.recent_writes || [];
    $('opsWrites').hidden = false;
    $('opsWriteHint').textContent = '最近 1 小時寫入 ' + (d.writes_last_hour || 0) + ' 筆，失敗 ' + (d.failed_writes_last_hour || 0) + ' 筆 · 下列為最近 ' + rows.length + ' 筆';
    const body = $('opsWriteBody');
    body.replaceChildren();
    if (!rows.length) {
      const tr = document.createElement('tr');
      const td = document.createElement('td');
      td.colSpan = 5;
      td.textContent = '尚無紀錄';
      tr.appendChild(td);
      body.appendChild(tr);
      return;
    }
    rows.forEach((row) => {
      const tr = document.createElement('tr');
      const code = Number(row.status_code);
      if (code >= 400) tr.className = 'ops-fail';
      [row.created_at, row.username, row.method, row.path, row.status_code].forEach((val) => {
        const td = document.createElement('td');
        td.textContent = val == null ? '' : String(val);
        tr.appendChild(td);
      });
      body.appendChild(tr);
    });
  }

  let autoTimer = null;
  const AUTO_KEY = 'qs_admin_autorefresh';

  function stopAuto() {
    if (autoTimer) {
      clearInterval(autoTimer);
      autoTimer = null;
    }
  }

  function startAuto() {
    stopAuto();
    autoTimer = setInterval(() => {
      if (document.hidden) return;
      loadStatus().catch(() => showDenied('載入失敗'));
    }, 30000);
  }

  $('opsAuto').checked = localStorage.getItem(AUTO_KEY) === '1';
  $('opsAuto').addEventListener('change', () => {
    if ($('opsAuto').checked) {
      localStorage.setItem(AUTO_KEY, '1');
      startAuto();
    } else {
      localStorage.removeItem(AUTO_KEY);
      stopAuto();
    }
  });

  $('opsTheme').addEventListener('click', () => {
    const cur = document.documentElement.getAttribute('data-theme') === 'light' ? 'light' : 'dark';
    const next = cur === 'light' ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('qs_theme', next);
  });
  $('opsRefresh').addEventListener('click', () => { loadStatus().catch(() => showDenied('載入失敗')); });

  (async function boot() {
    try {
      const r = await fetch(API + '/auth/me', { credentials: 'include' });
      const json = await r.json();
      const data = json.data || {};
      if (data.auth_required === false) {
        await loadStatus();
        if ($('opsAuto').checked) startAuto();
        return;
      }
      const user = data.user;
      if (!user) {
        window.location.replace('/login.html?next=/admin');
        return;
      }
      if (!user.is_admin && user.role !== 'admin') {
        showDenied('需要管理員');
        return;
      }
      await loadStatus();
      if ($('opsAuto').checked) startAuto();
    } catch (_) {
      showDenied('無法連線');
    }
  })();
})();
