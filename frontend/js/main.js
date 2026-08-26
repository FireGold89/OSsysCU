/* ─── main.js — 核心應用邏輯 ───────────────────────────── */
const API = `${window.location.origin}/api`;

/** 所有 /api 請求帶 Session Cookie（登入後上傳／PDF 等） */
(function patchFetchCredentials() {
  const origFetch = window.fetch.bind(window);
  window.fetch = function (input, init) {
    const opts = init ? { ...init } : {};
    const url = typeof input === 'string' ? input : (input && input.url) || '';
    if (url.includes('/api/') && !opts.credentials) {
      opts.credentials = 'include';
    }
    return origFetch(input, opts);
  };
})();

// ─── 主題（Light / Dark）──────────────────────────────────
const Theme = {
  STORAGE_KEY: 'qs_theme',

  init() {
    this._syncToggleUI();
    document.querySelectorAll('.theme-toggle-btn').forEach((btn) => {
      btn.addEventListener('click', () => this.set(btn.getAttribute('data-theme-pick')));
    });
    if (window.matchMedia) {
      window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
        if (!localStorage.getItem(this.STORAGE_KEY)) {
          this.set(e.matches ? 'dark' : 'light', { animate: true, persist: false });
        }
      });
    }
  },

  get() {
    return document.documentElement.getAttribute('data-theme') === 'light' ? 'light' : 'dark';
  },

  set(theme, opts = {}) {
    const next = theme === 'light' ? 'light' : 'dark';
    const { animate = true, persist = true } = opts;
    if (animate) {
      document.documentElement.classList.add('theme-animate');
      setTimeout(() => document.documentElement.classList.remove('theme-animate'), 320);
    }
    document.documentElement.setAttribute('data-theme', next);
    if (persist) localStorage.setItem(this.STORAGE_KEY, next);
    this._syncToggleUI();
    if (typeof Dashboard !== 'undefined' && Dashboard.charts && App.currentProject) {
      const page = document.getElementById('page-dashboard');
      if (page?.classList.contains('active') && Dashboard._lastScStats) {
        Dashboard.renderCharts(Dashboard._lastScStats);
      }
    }
  },

  toggle() {
    this.set(this.get() === 'dark' ? 'light' : 'dark');
  },

  _syncToggleUI() {
    const current = this.get();
    document.querySelectorAll('.theme-toggle-btn').forEach((btn) => {
      const on = btn.getAttribute('data-theme-pick') === current;
      btn.classList.toggle('active', on);
      btn.setAttribute('aria-pressed', on ? 'true' : 'false');
    });
  },

  cssVar(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  },

  chartPalette() {
    return {
      paid: this.cssVar('--success') || '#10b981',
      unpaid: this.cssVar('--chart-unpaid') || '#374151',
      grid: this.cssVar('--chart-grid') || '#21262d',
      text: this.cssVar('--chart-text') || '#8b949e',
      label: this.cssVar('--chart-label') || '#e6edf3',
      segments: ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6'],
    };
  },
};

function uploadUrl(filename) {
  if (!filename) return null;
  const parts = String(filename).replace(/\\/g, '/').split('/').filter(Boolean).map(encodeURIComponent);
  return `${window.location.origin}/api/uploads/${parts.join('/')}`;
}

/** 應用內文件預覽（PDF / 圖片） */
const DocViewer = {
  PANEL_SIZE_KEY: 'qs_doc_viewer_size',
  _resizeInited: false,

  _initResize() {
    if (this._resizeInited) return;
    const panel = document.getElementById('docViewerPanel');
    const handleE = document.getElementById('docViewerResizeE');
    const handleS = document.getElementById('docViewerResizeS');
    const handleSE = document.getElementById('docViewerResizeSE');
    if (!panel) return;
    this._resizeInited = true;

    const startDrag = (mode, e, cursor) => {
      e.preventDefault();
      e.stopPropagation();
      const rect = panel.getBoundingClientRect();
      const startX = e.clientX;
      const startY = e.clientY;
      const startW = rect.width;
      const startH = rect.height;
      document.body.style.cursor = cursor;
      document.body.style.userSelect = 'none';

      const onMove = (ev) => {
        let w = startW;
        let h = startH;
        if (mode.includes('e')) w = startW + (ev.clientX - startX);
        if (mode.includes('s')) h = startH + (ev.clientY - startY);
        this._setPanelSize(w, h);
      };
      const onUp = () => {
        document.removeEventListener('mousemove', onMove);
        document.removeEventListener('mouseup', onUp);
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
        this._savePanelSize();
      };
      document.addEventListener('mousemove', onMove);
      document.addEventListener('mouseup', onUp);
    };

    handleE?.addEventListener('mousedown', (e) => startDrag('e', e, 'ew-resize'));
    handleS?.addEventListener('mousedown', (e) => startDrag('s', e, 'ns-resize'));
    handleSE?.addEventListener('mousedown', (e) => startDrag('es', e, 'nwse-resize'));
    handleSE?.addEventListener('dblclick', (e) => {
      e.preventDefault();
      e.stopPropagation();
      this._resetPanelSize();
    });
  },

  _panelLimits() {
    const pad = 32;
    return {
      minW: 480,
      minH: 320,
      maxW: window.innerWidth - pad,
      maxH: window.innerHeight - pad,
    };
  },

  _setPanelSize(w, h) {
    const panel = document.getElementById('docViewerPanel');
    if (!panel) return;
    const { minW, minH, maxW, maxH } = this._panelLimits();
    panel.style.width = `${Math.round(Math.max(minW, Math.min(w, maxW)))}px`;
    panel.style.height = `${Math.round(Math.max(minH, Math.min(h, maxH)))}px`;
    panel.style.maxWidth = 'none';
  },

  _applySavedPanelSize() {
    const panel = document.getElementById('docViewerPanel');
    if (!panel) return;
    try {
      const raw = localStorage.getItem(this.PANEL_SIZE_KEY);
      if (!raw) return;
      const { w, h } = JSON.parse(raw);
      if (w > 0 && h > 0) this._setPanelSize(w, h);
    } catch (e) { /* ignore */ }
  },

  _savePanelSize() {
    const panel = document.getElementById('docViewerPanel');
    if (!panel) return;
    const rect = panel.getBoundingClientRect();
    localStorage.setItem(this.PANEL_SIZE_KEY, JSON.stringify({
      w: Math.round(rect.width),
      h: Math.round(rect.height),
    }));
  },

  _resetPanelSize() {
    const panel = document.getElementById('docViewerPanel');
    if (!panel) return;
    panel.style.width = '';
    panel.style.height = '';
    panel.style.maxWidth = '';
    localStorage.removeItem(this.PANEL_SIZE_KEY);
  },

  async open(filePath, title = '文件預覽') {
    const url = uploadUrl(filePath);
    if (!url) {
      toast('此記錄沒有 PDF', 'warning');
      return;
    }
    const ext = (filePath.split('.').pop() || '').toLowerCase();
    const isImage = ['png', 'jpg', 'jpeg', 'gif', 'webp'].includes(ext);
    return this.openUrl(url, title, {
      kind: isImage ? 'image' : 'pdf',
      downloadName: filePath.split('/').pop(),
    });
  },

  async openBlob(blob, title = '文件預覽', opts = {}) {
    this._revokeBlob();
    const blobUrl = URL.createObjectURL(blob);
    this._blobUrl = blobUrl;
    return this.openUrl(blobUrl, title, { ...opts, skipHead: true });
  },

  _revokeBlob() {
    if (this._blobUrl) {
      URL.revokeObjectURL(this._blobUrl);
      this._blobUrl = null;
    }
  },

  async openUrl(url, title = '文件預覽', opts = {}) {
    const {
      kind = 'pdf', downloadUrl, downloadName, skipHead = false,
      themes, theme, onThemeChange, subtitle,
      appendixOptions, onAppendixChange,
    } = opts;
    const modal = document.getElementById('docViewerModal');
    const frame = document.getElementById('docViewerFrame');
    const img = document.getElementById('docViewerImg');
    const loading = document.getElementById('docViewerLoading');
    const errBox = document.getElementById('docViewerError');
    const errMsg = document.getElementById('docViewerErrorMsg');
    const errLink = document.getElementById('docViewerErrorLink');
    const openTab = document.getElementById('docViewerOpenTab');
    const download = document.getElementById('docViewerDownload');
    const printBtn = document.getElementById('docViewerPrint');

    document.getElementById('docViewerTitle').textContent = title;
    const subEl = document.getElementById('docViewerSubtitle');
    if (subEl) {
      if (subtitle) {
        subEl.textContent = subtitle;
        subEl.style.display = '';
      } else {
        subEl.textContent = '';
        subEl.style.display = 'none';
      }
    }
    const dlHref = downloadUrl || url;
    if (openTab) openTab.href = url;
    if (download) {
      download.href = dlHref;
      if (downloadName) download.download = downloadName;
      else download.removeAttribute('download');
    }
    if (errLink) errLink.href = url;
    if (printBtn) printBtn.style.display = kind === 'pdf' ? '' : 'none';
    this._syncThemePicker({
      themes, theme, onThemeChange, appendixOptions, onAppendixChange,
    });

    frame.style.display = 'none';
    frame.src = 'about:blank';
    img.style.display = 'none';
    img.removeAttribute('src');
    errBox.style.display = 'none';
    loading.style.display = '';
    this._initResize();
    this._applySavedPanelSize();
    modal.classList.add('open');
    this._onKey = (e) => { if (e.key === 'Escape') this.close(); };
    document.addEventListener('keydown', this._onKey);

    const showError = (msg) => {
      loading.style.display = 'none';
      if (errMsg) errMsg.textContent = msg;
      errBox.style.display = '';
    };

    if (kind === 'image') {
      img.onload = () => { loading.style.display = 'none'; };
      img.onerror = () => {
        img.style.display = 'none';
        showError('無法載入圖片，請用「新分頁開啟」或「下載」');
      };
      img.style.display = 'block';
      img.src = url;
      return;
    }

    frame.onload = () => { loading.style.display = 'none'; };
    frame.onerror = () => showError('無法載入 PDF，請用「新分頁開啟」');
    frame.style.display = 'block';
    frame.src = `${url}${url.includes('#') ? '' : '#view=FitH'}`;

    if (skipHead) return;

    try {
      const r = await fetch(url, { method: 'HEAD' });
      if (!r.ok) {
        loading.style.display = 'none';
        if (errMsg) {
          errMsg.textContent = r.status === 404
            ? '文件不在伺服器（Zeabur 需掛載 Volume）'
            : `伺服器回應 ${r.status}，可嘗試新分頁開啟`;
        }
        errBox.style.display = '';
      }
    } catch (e) { /* 仍嘗試 iframe 載入 */ }
  },

  setLoading(on) {
    const loading = document.getElementById('docViewerLoading');
    const frame = document.getElementById('docViewerFrame');
    if (loading) loading.style.display = on ? '' : 'none';
    if (frame && on) frame.style.display = 'none';
  },

  _syncThemePicker(opts) {
    const bar = document.getElementById('docViewerThemeBar');
    const sel = document.getElementById('docViewerTheme');
    const themeLabel = document.getElementById('docViewerThemeLabel');
    const apxSep = document.getElementById('docViewerAppendixSep');
    const apxLabel = document.getElementById('docViewerAppendixLabel');
    const voWrap = document.getElementById('docViewerAppendixVoWrap');
    const contraWrap = document.getElementById('docViewerAppendixContraWrap');
    const voChk = document.getElementById('docViewerAppendixVo');
    const contraChk = document.getElementById('docViewerAppendixContra');
    if (!bar || !sel) return;

    const themes = opts?.themes;
    const hasThemes = !!themes?.length;
    const apx = opts?.appendixOptions;
    const hasVoOpt = apx?.vo != null;
    const hasContraOpt = apx?.contra != null;
    const hasAppendix = hasVoOpt || hasContraOpt;

    if (!hasThemes && !hasAppendix) {
      bar.style.display = 'none';
      sel.onchange = null;
      this._themeChangeHandler = null;
      this._appendixChangeHandler = null;
      return;
    }

    bar.style.display = 'flex';
    if (themeLabel) themeLabel.style.display = hasThemes ? '' : 'none';
    sel.style.display = hasThemes ? '' : 'none';
    if (hasThemes) {
      sel.innerHTML = themes.map(t => {
        const id = escHtml(t.id);
        const label = escHtml(t.label);
        const on = t.id === opts.theme ? ' selected' : '';
        return `<option value="${id}"${on}>${label}</option>`;
      }).join('');
      this._themeChangeHandler = opts.onThemeChange || null;
      sel.onchange = () => {
        const fn = this._themeChangeHandler;
        if (fn) fn(sel.value);
      };
    } else {
      sel.onchange = null;
      this._themeChangeHandler = null;
    }

    if (apxSep) apxSep.style.display = hasThemes && hasAppendix ? '' : 'none';
    if (apxLabel) apxLabel.style.display = hasAppendix ? '' : 'none';
    if (voWrap) voWrap.style.display = hasVoOpt ? '' : 'none';
    if (contraWrap) contraWrap.style.display = hasContraOpt ? '' : 'none';
    if (voChk && hasVoOpt) {
      voChk.checked = !!apx.vo.checked;
      voChk.onchange = () => {
        const fn = this._appendixChangeHandler;
        if (fn) fn('vo', voChk.checked);
      };
    }
    if (contraChk && hasContraOpt) {
      contraChk.checked = !!apx.contra.checked;
      contraChk.onchange = () => {
        const fn = this._appendixChangeHandler;
        if (fn) fn('contra', contraChk.checked);
      };
    }
    this._appendixChangeHandler = opts.onAppendixChange || null;
  },

  print() {
    const frame = document.getElementById('docViewerFrame');
    if (!frame?.contentWindow) {
      toast('請先開啟 PDF 預覽', 'warning');
      return;
    }
    try {
      frame.contentWindow.focus();
      frame.contentWindow.print();
    } catch (e) {
      toast('無法直接打印，請用「新分頁開啟」後打印', 'warning');
    }
  },

  close() {
    if (this._onKey) document.removeEventListener('keydown', this._onKey);
    this._revokeBlob();
    this._syncThemePicker(null);
    const modal = document.getElementById('docViewerModal');
    if (modal) modal.classList.remove('open');
    const frame = document.getElementById('docViewerFrame');
    if (frame) frame.src = 'about:blank';
    const img = document.getElementById('docViewerImg');
    if (img) img.removeAttribute('src');
  },

  onBackdrop(e) {
    if (e.target.id === 'docViewerModal') this.close();
  },
};

// ─── 工具函數 ──────────────────────────────────────────────
const FMT_DECIMALS = 2;

function fmt(num, decimals = FMT_DECIMALS) {
  if (num == null || num === '') return '—';
  const n = parseFloat(num);
  if (isNaN(n)) return '—';
  return 'HK$' + n.toLocaleString('en-HK', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

/** Excel 會計格式：負數用括號 (1,500) */
function fmtAcct(num, decimals = FMT_DECIMALS) {
  if (num == null || num === '') return '—';
  const n = parseFloat(num);
  if (isNaN(n)) return '—';
  const abs = Math.abs(n).toLocaleString('en-HK', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
  return n < 0 ? `(HK$${abs})` : `HK$${abs}`;
}

function fmtPct(val) {
  if (val == null || val === '') return '—';
  const n = parseFloat(val);
  if (isNaN(n)) return '—';
  return n.toFixed(FMT_DECIMALS) + '%';
}

function fmtNumPlain(num, decimals = FMT_DECIMALS) {
  if (num == null || num === '') return '';
  const n = parseFloat(num);
  if (isNaN(n)) return '';
  return n.toLocaleString('en-HK', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

/** 表單輸入框用（無千分位） */
function fmtInputNum(num, decimals = FMT_DECIMALS) {
  if (num == null || num === '') return '';
  const n = parseFloat(num);
  if (isNaN(n)) return '';
  return n.toFixed(decimals);
}

/** 支出金額：會計括號格式 (HK$1,500.00)，零值不加括號 */
function fmtExpense(val, decimals = FMT_DECIMALS) {
  if (val == null || val === '') return '—';
  const n = parseFloat(val);
  if (isNaN(n)) return '—';
  if (n === 0) return fmtAcct(0);
  return fmtAcct(n < 0 ? n : -Math.abs(n));
}

function fmtIpExpenditure(val) {
  return fmtExpense(val);
}

/** 金額色調：負數 → 紅；role=expense 正值（支出）→ 紅；role=income 正值 → 綠 */
function amtClass(num, role = 'auto') {
  const n = parseFloat(num);
  if (isNaN(n) || num === '' || num == null) return '';
  if (n < 0) return 'negative';
  if (role === 'expense' && n > 0) return 'negative';
  if (role === 'income' && n > 0) return 'positive';
  return '';
}

function setAmtEl(el, num, role = 'auto') {
  if (!el) return;
  if (num == null || num === '') {
    el.textContent = '—';
  } else if (role === 'expense') {
    el.textContent = fmtExpense(num);
  } else {
    const n = parseFloat(num);
    el.textContent = !isNaN(n) && n < 0 ? fmtAcct(num) : fmt(num);
  }
  el.classList.remove('negative', 'positive');
  const cls = amtClass(num, role);
  if (cls) el.classList.add(cls);
}

/** 項目名稱中英欄位（兼容舊 project_name） */
function projectNameParts(p) {
  let en = (p?.project_name_en || '').trim();
  let zh = (p?.project_name_zh || '').trim();
  const legacy = (p?.project_name || '').trim();
  if (!en && !zh && legacy) {
    if (/[\u4e00-\u9fff]/.test(legacy)) {
      if (/[A-Za-z]/.test(legacy)) {
        for (const sep of [' / ', ' · ', '｜', ' | ']) {
          if (legacy.includes(sep)) {
            const i = legacy.indexOf(sep);
            en = legacy.slice(0, i).trim();
            zh = legacy.slice(i + sep.length).trim();
            break;
          }
        }
        if (!en && !zh) en = legacy;
      } else {
        zh = legacy;
      }
    } else {
      en = legacy;
    }
  }
  return { en, zh };
}

/** 單行項目名稱（中文優先，無中文則英文） */
function projectNameOneLine(p, maxLen) {
  const { en, zh } = projectNameParts(p);
  let s = zh || en || p?.project_code || '—';
  if (maxLen && s.length > maxLen) s = s.slice(0, maxLen) + '...';
  return s;
}

/** 項目名稱 HTML（中文主行，英文副行） */
function projectNameHtml(p) {
  const { en, zh } = projectNameParts(p);
  if (!en && !zh) return escHtml(p?.project_code || '—');
  const primary = zh || en;
  const secondary = zh && en && zh !== en ? en : '';
  if (!secondary) {
    return `<span class="proj-name-en">${escHtml(primary)}</span>`;
  }
  return `<span class="proj-name-en">${escHtml(primary)}</span><span class="proj-name-zh">${escHtml(secondary)}</span>`;
}

/** 表格公司名稱：中文優先，英文副行 */
function formatCompanyNameHtml(en, zh) {
  const e = (en || '').trim();
  const z = (zh || '').trim();
  if (!e && !z) return '—';
  const primary = z || e;
  const secondary = z && e && z !== e ? e : '';
  if (!secondary) {
    return `<div class="proj-name-block"><div class="proj-name-en">${escHtml(primary)}</div></div>`;
  }
  return `<div class="proj-name-block"><div class="proj-name-en">${escHtml(primary)}</div><div class="proj-name-zh">${escHtml(secondary)}</div></div>`;
}

/** 單行公司名稱（中文優先） */
function formatCompanyPrimary(en, zh) {
  const e = (en || '').trim();
  const z = (zh || '').trim();
  return z || e || '—';
}

/** 付款記錄公司名稱（缺中文時從分判商資料補） */
function paymentCompanyNameHtml(row) {
  let en = row?.company_name_en;
  let zh = row?.company_name_zh;
  if ((!zh || !en) && row?.sc_no && App.scList?.length) {
    const sc = App.scList.find(s => s.sc_no === row.sc_no);
    if (sc) {
      if (!en) en = sc.company_name_en;
      if (!zh) zh = sc.company_name_zh;
    }
  }
  return formatCompanyNameHtml(en, zh);
}

function escHtml(s) {
  return String(s || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function projectStatusInfo(status) {
  const map = {
    Active: { label: '進行中', badge: 'success', en: 'Active' },
    Completed: { label: '已完成', badge: 'info', en: 'Completed' },
    'On Hold': { label: '暫停', badge: 'warning', en: 'On Hold' },
  };
  return map[status] || { label: status || '—', badge: 'muted', en: status || '' };
}

function projectStatusBadgeHtml(status) {
  const m = projectStatusInfo(status);
  const pulse = status === 'Active' ? ' is-active' : '';
  return `<span class="badge badge-${m.badge} dash-hero-status-badge${pulse}"><span class="dash-status-dot"></span>${m.label}</span>`;
}

function updateDashProjectHero(project, ipPeriod) {
  const proj = project || {};
  const set = (id, val) => {
    const el = document.getElementById(id);
    if (el) el.textContent = val || '—';
  };
  const displayCode = proj.quotation_no || proj.project_code;
  set('dashProjCode', displayCode);
  const personEl = document.getElementById('dashProjPerson');
  if (personEl) {
    const personHtml = fmtProjectPerson(proj);
    personEl.innerHTML = personHtml && personHtml !== '—' ? personHtml : '—';
  }
  const nameEl = document.getElementById('dashProjName');
  if (nameEl) nameEl.innerHTML = projectNameHtml(proj);
  const period = ipPeriod?.site_period_text || proj.site_period_text;
  set('dashProjPeriod', period);
  set('dashProjMc', proj.main_contractor);
  const statusTop = document.getElementById('dashProjStatus');
  const statusMeta = document.getElementById('dashProjStatusMeta');
  if (statusTop) statusTop.innerHTML = proj.status ? projectStatusBadgeHtml(proj.status) : '';
  if (statusMeta) {
    statusMeta.innerHTML = proj.status
      ? `<div class="dash-hero-status-detail">${projectStatusBadgeHtml(proj.status)}<span class="dash-hero-status-detail-en">${projectStatusInfo(proj.status).en}</span></div>`
      : '—';
  }
  const amt = parseFloat(proj.contract_amount);
  const amtEl = document.getElementById('dashHeroContractAmt');
  if (amtEl) amtEl.textContent = !isNaN(amt) && amt !== 0 ? fmt(amt) : '—';
}

/** 工程項目負責人（顯示全名） */
function fmtProjectPerson(p) {
  if (!p) return '—';
  const name = (p.person_in_charge || '').trim();
  return name ? escHtml(name) : '—';
}

function updateDashIpTotals(ip) {
  const t = ip?.totals || {};
  const incomeEl = document.getElementById('dashIpIncome');
  const expEl = document.getElementById('dashIpExpenditure');
  const advEl = document.getElementById('dashIpAdvance');
  if (!incomeEl || !expEl || !advEl) return;
  const hasAny = ip && (
    ip.items?.length ||
    parseFloat(t.total_income) ||
    parseFloat(t.total_expenditure) ||
    parseFloat(t.advance)
  );
  if (!hasAny) {
    incomeEl.textContent = expEl.textContent = advEl.textContent = '—';
    [incomeEl, expEl, advEl].forEach(el => el.classList.remove('negative', 'positive'));
    return;
  }
  incomeEl.textContent = fmtAcct(t.total_income);
  incomeEl.classList.toggle('positive', parseFloat(t.total_income) > 0);
  expEl.textContent = fmtIpExpenditure(t.total_expenditure);
  expEl.classList.add('negative');
  advEl.textContent = fmtAcct(t.advance);
  advEl.classList.toggle('negative', parseFloat(t.advance) < 0);
  const advCard = advEl.closest('.stat-card');
  if (advCard) {
    advCard.classList.toggle('danger', parseFloat(t.advance) < 0);
    advCard.classList.toggle('warning', parseFloat(t.advance) >= 0);
  }
}

function contractCalcTableHtml(calc) {
  if (!calc) return '';
  const rateClass = calc.profit_rate < 0 ? 'negative' : 'positive';
  return `
    <table class="contract-calc-table">
      <tbody>
        <tr><td class="calc-label">(A) 承建金額</td><td class="calc-value">${fmtAcct(calc.main_contract_amount)}</td></tr>
        <tr><td class="calc-label">(B) 分判及代支小計</td><td class="calc-value ${amtClass(calc.sub_total_b, 'expense')}">${fmtExpense(calc.sub_total_b)}</td></tr>
        <tr><td class="calc-label">(C) 除外合約收費項目</td><td class="calc-value ${amtClass(calc.excluded_c, 'expense')}">${fmtExpense(calc.excluded_c)}</td></tr>
        <tr><td class="calc-label">財務會作調撥（人工分攤）</td><td class="calc-value ${amtClass(calc.labour_allocation, 'expense')}">${fmtExpense(calc.labour_allocation)}</td></tr>
        <tr class="calc-total"><td class="calc-label">(D) = (B)+(C)+調撥</td><td class="calc-value ${amtClass(calc.total_d, 'expense')}">${fmtExpense(calc.total_d)}</td></tr>
        <tr><td class="calc-label">(E) = (A) - (D) 預計利潤</td><td class="calc-value ${rateClass}">${fmtAcct(calc.profit_e)}</td></tr>
        <tr><td class="calc-label">預計利潤率</td><td class="calc-value ${rateClass}">${fmtPct(calc.profit_rate)}</td></tr>
      </tbody>
    </table>`;
}

function renderContractCalc(calc, containerId) {
  const el = document.getElementById(containerId);
  if (!el || !calc) return;
  el.innerHTML = contractCalcTableHtml(calc);
}

function fmtDate(str) {
  if (!str) return '—';
  const d = new Date(str);
  if (isNaN(d)) return str;
  return d.toLocaleDateString('zh-HK', { year: 'numeric', month: '2-digit', day: '2-digit' });
}

/** 推導父級判項編號（M-011.26 → M-011，SC-003A → SC-003） */
function deriveParentScNo(scNo) {
  if (!scNo) return scNo;
  const s = String(scNo).trim();
  if (s.includes('.')) return s.replace(/\.[^.]+$/, '');
  const m = s.match(/^(.+?)([A-Z]\d*)$/);
  if (m && m[1] !== s && m[2].length <= 3) return m[1];
  return s;
}

/** 解析工程描述（OCR 表格文字 → 明細列） */
function parseDescriptionItems(text) {
  if (!text || !String(text).trim()) {
    return { title: '', items: [], plain: '' };
  }
  const raw = String(text).replace(/\r\n/g, '\n');
  const norm = raw.replace(/项次/g, '項次').replace(/项目描述/g, '項目描述');
  const headerRe = /項次[\s\t]*項目描述[\s\t]*數量[\s\t]*單位[\s\t]*單價[\s\S]*?金額/;
  const headerMatch = norm.match(headerRe);
  if (headerMatch) {
    const headerStart = norm.indexOf(headerMatch[0]);
    const title = norm.slice(0, headerStart).replace(/\s+/g, ' ').trim();
    const after = norm.slice(headerStart + headerMatch[0].length).trim();
    const items = [];
    const rowRe = /(\d+)\s+([^\t\n]+?)\s+(\d+(?:\.\d+)?)\s+([^\t\n\d]+?)\s+([\d,]+(?:\.\d+)?)\s+([\d,]+(?:\.\d+)?)/g;
    let m;
    while ((m = rowRe.exec(after)) !== null) {
      items.push({
        no: m[1], description: m[2].trim(), qty: m[3], unit: m[4].trim(),
        unit_price: m[5].replace(/,/g, ''), amount: m[6].replace(/,/g, ''),
      });
    }
    if (!items.length) {
      after.split('\n').forEach((line, i) => {
        const parts = line.split('\t');
        if (parts.length >= 2 && parts[1]) {
          items.push({
            no: parts[0] || String(i + 1), description: parts[1],
            qty: parts[2] || '', unit: parts[3] || '',
            unit_price: parts[4] || '', amount: parts[5] || '',
          });
        }
      });
    }
    if (items.length) return { title, items, plain: '' };
  }
  const lines = norm.split('\n').map(l => l.trim()).filter(l => l !== '');
  const headerIdx = lines.findIndex(l => l.includes('項目描述') && l.includes('\t'));
  if (headerIdx >= 0) {
    const title = lines.slice(0, headerIdx).filter(Boolean).join(' ').trim();
    const items = [];
    for (let i = headerIdx + 1; i < lines.length; i++) {
      const parts = lines[i].split('\t');
      if (parts.length < 2 || !parts[1]) continue;
      items.push({
        no: parts[0] || String(items.length + 1), description: parts[1],
        qty: parts[2] || '', unit: parts[3] || '',
        unit_price: parts[4] || '', amount: parts[5] || '',
      });
    }
    return { title, items, plain: '' };
  }
  return { title: '', items: [], plain: raw.trim() };
}

/** 明細列 → 工程描述文字（與 OCR 格式一致） */
function buildDescriptionText(items, title) {
  const rows = (items || []).filter(it => it.description || it.amount);
  if (!rows.length) return (title || '').trim();
  const head = (title || '').trim()
    || (rows.length === 1 ? rows[0].description : `工程/服務項目（共 ${rows.length} 項）`);
  const lines = [head, '', '項次\t項目描述\t數量\t單位\t單價(HK$)\t金額(HK$)'];
  rows.forEach((it, i) => {
    lines.push([
      it.no || String(i + 1), it.description || '', it.qty || '', it.unit || '',
      fmtNumPlain(it.unit_price), fmtNumPlain(it.amount),
    ].join('\t'));
  });
  return lines.join('\n');
}

/** M-/SC-/O- 判項編號類型（對應 Excel 灰色提示） */
function refNoType(scNo) {
  const s = (scNo || '').toUpperCase().trim();
  if (/^M[-.]/.test(s) || s.startsWith('M')) return { label: '物料', badge: 'info' };
  if (/^SC[-.]/.test(s) || s.startsWith('SC')) return { label: '分判', badge: 'success' };
  if (/^O[-.]/.test(s) || s.startsWith('O')) return { label: '其他支出', badge: 'warning' };
  return { label: '', badge: 'muted' };
}

function fmtRefNo(scNo) {
  if (!scNo) return '—';
  const t = refNoType(scNo);
  const typeBadge = t.label
    ? `<span class="badge badge-${t.badge} ref-type-badge">${t.label}</span>`
    : '';
  return `<span class="ref-no-wrap"><span class="sc-no-chip">${scNo}</span>${typeBadge}</span>`;
}

function showLoading(text = '載入中...') {
  document.getElementById('loadingText').textContent = text;
  document.getElementById('loadingOverlay').classList.add('show');
}

function hideLoading() {
  document.getElementById('loadingOverlay').classList.remove('show');
}

function toast(msg, type = 'info') {
  const container = document.getElementById('toastContainer');
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  const icons = { success: '✅', error: '❌', warning: '⚠️', info: 'ℹ️' };
  el.innerHTML = `<span>${icons[type] || 'ℹ️'}</span><span>${msg}</span>`;
  container.appendChild(el);
  el.onclick = () => el.remove();
  setTimeout(() => el.remove(), 4000);
}

async function api(method, path, body, opts = {}) {
  const silent = opts.silent === true;
  try {
    const fetchOpts = {
      method,
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
    };
    if (body) fetchOpts.body = JSON.stringify(body);
    const r = await fetch(API + path, fetchOpts);
    if (r.status === 401 && !path.startsWith('/auth/')) {
      const next = encodeURIComponent(window.location.pathname + window.location.search);
      window.location.href = `/login.html?next=${next}`;
      throw new Error('請先登入');
    }
    const text = await r.text();
    let json;
    try {
      json = JSON.parse(text);
    } catch (e) {
      throw new Error(r.ok ? '伺服器回應格式錯誤' : `伺服器錯誤 (${r.status})，請重新啟動系統後再試`);
    }
    if (!json.success) throw new Error(json.error || '操作失敗');
    return json.data;
  } catch (e) {
    if (!silent) toast(e.message, 'error');
    throw e;
  }
}

// ─── 側欄收合 ───────────────────────────────────────────────
const Sidebar = {
  KEY: 'qs_sidebar_collapsed',

  init() {
    const collapsed = localStorage.getItem(this.KEY) === '1';
    this.apply(collapsed, false);
    document.getElementById('sidebarToggle')?.addEventListener('click', () => this.toggle());
    document.getElementById('sidebarToggleFoot')?.addEventListener('click', () => this.toggle());
  },

  toggle() {
    const sidebar = document.getElementById('sidebar');
    if (window.matchMedia('(max-width: 768px)').matches) {
      sidebar?.classList.toggle('open');
      return;
    }
    const collapsed = !document.documentElement.classList.contains('sidebar-collapsed');
    this.apply(collapsed, true);
  },

  closeMobile() {
    document.getElementById('sidebar')?.classList.remove('open');
  },

  apply(collapsed, persist) {
    document.documentElement.classList.toggle('sidebar-collapsed', collapsed);
    if (persist) {
      localStorage.setItem(this.KEY, collapsed ? '1' : '0');
    }
    const label = collapsed ? '展開側欄' : '收合側欄';
    ['sidebarToggle', 'sidebarToggleFoot'].forEach((id) => {
      const el = document.getElementById(id);
      if (!el) return;
      el.title = label;
      el.setAttribute('aria-label', label);
      el.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
    });
  },
};

// ─── 登入 ─────────────────────────────────────────────────
const Auth = {
  user: null,
  authRequired: false,

  async ensure() {
    try {
      const r = await fetch(`${API}/auth/me`, { credentials: 'include' });
      const json = await r.json();
      if (!json.success) throw new Error(json.error || '無法驗證登入狀態');
      const data = json.data || {};
      this.authRequired = !!data.auth_required;
      this.user = data.user || null;
      if (this.authRequired && !this.user) {
        const next = encodeURIComponent(window.location.pathname + window.location.search);
        window.location.href = `/login.html?next=${next}`;
        return false;
      }
      this.applyUi();
      return true;
    } catch (e) {
      toast(e.message || '登入驗證失敗', 'error');
      return false;
    }
  },

  isAdmin() {
    return this.user?.role === 'admin';
  },

  applyUi() {
    const badge = document.getElementById('authUserBadge');
    const logoutBtn = document.getElementById('authLogoutBtn');
    const authWrap = document.getElementById('authUserWrap');
    const settingsNav = document.querySelector('.nav-item[data-page="settings"]');
    const showAuth = this.authRequired && this.user;
    if (authWrap) authWrap.style.display = showAuth ? '' : 'none';
    if (logoutBtn) logoutBtn.style.display = showAuth ? '' : 'none';
    if (badge) {
      if (showAuth) {
        badge.textContent = this.user.username + (this.isAdmin() ? ' · 管理員' : '');
        badge.style.display = '';
      } else {
        badge.style.display = 'none';
      }
    }
    if (settingsNav) {
      settingsNav.style.display = this.authRequired && !this.isAdmin() ? 'none' : '';
    }
  },

  async logout() {
    try {
      await fetch(`${API}/auth/logout`, { method: 'POST', credentials: 'include' });
    } catch (e) {}
    window.location.href = '/login.html';
  },
};

// ─── App 主控制器 ───────────────────────────────────────────
const App = {
  currentProject: null,
  currentPage: 'dashboard',
  projects: [],
  scList: [],
  _projectSwitchSeq: 0,

  async init() {
    Theme.init();
    Sidebar.init();
    const ok = await Auth.ensure();
    if (!ok) return;
    document.addEventListener('click', (e) => {
      const btn = e.target.closest('.btn-view-pdf');
      if (!btn) return;
      e.preventDefault();
      e.stopPropagation();
      const path = btn.getAttribute('data-pdf-path');
      const title = btn.getAttribute('data-doc-title') || '文件預覽';
      if (path) DocViewer.open(path, title);
    });

    await this.loadProjects();
    document.getElementById('projectSelect').addEventListener('change', (e) => {
      this.selectProject(e.target.value);
    });
    const saved = localStorage.getItem('qs_project_id');
    if (saved && this.projects.find(p => p.id == saved)) {
      await this.selectProject(saved);
    } else if (this.projects.length > 0) {
      await this.selectProject(this.projects[0].id);
    }
    this._updateProjectSettlementNav();
    this.navigate('dashboard');
  },

  async loadProjects() {
    this.projects = await api('GET', '/projects') || [];
    const sel = document.getElementById('projectSelect');
    const curId = this.currentProject?.id;
    sel.innerHTML = '<option value="">— 請選擇項目 —</option>';
    this.projects.forEach(p => {
      const opt = document.createElement('option');
      opt.value = p.id;
      opt.textContent = `${p.project_code}${projectNameOneLine(p) !== p.project_code ? ' — ' + projectNameOneLine(p, 40) : ''}`;
      sel.appendChild(opt);
    });
    if (curId != null && curId !== '') {
      const fresh = this.projects.find(p => p.id == curId);
      if (fresh) {
        sel.value = String(curId);
        if (this.currentProject) Object.assign(this.currentProject, fresh);
        const badge = document.getElementById('currentProjectCode');
        if (badge) badge.textContent = fresh.project_code;
        document.getElementById('currentProjectBadge').style.display = '';
      }
    }
    // 更新工程項目頁
    Projects.render(this.projects);
  },

  async selectProject(id) {
    const switchSeq = ++this._projectSwitchSeq;
    showLoading('載入項目資料…');
    try {
      if (!id) {
        this.currentProject = null;
        this.scList = [];
        localStorage.removeItem('qs_project_id');
        document.getElementById('projectSelect').value = '';
        document.getElementById('currentProjectBadge').style.display = 'none';
        document.getElementById('btnQuickAdd').style.display = 'none';
        this._updateProjectSettlementNav();
        this._closeProjectModals();
        this._resetProjectFilters();
        await this._refreshProjectViews(switchSeq);
        return;
      }
      const fresh = await api('GET', `/projects/${id}`);
      if (!fresh || switchSeq !== this._projectSwitchSeq) return;
      this.currentProject = fresh;
      const idx = this.projects.findIndex(p => p.id == id);
      if (idx >= 0) this.projects[idx] = fresh;

      localStorage.setItem('qs_project_id', id);
      document.getElementById('projectSelect').value = String(id);
      document.getElementById('currentProjectCode').textContent = this.currentProject.project_code;
      document.getElementById('currentProjectBadge').style.display = '';
      document.getElementById('btnQuickAdd').style.display = 'none';

      this._updateProjectSettlementNav();
      this._closeProjectModals();
      this._resetProjectFilters();

      this.scList = await api('GET', `/projects/${id}/subcontractors`) || [];
      if (switchSeq !== this._projectSwitchSeq) return;

      await this._refreshProjectViews(switchSeq);
    } finally {
      if (switchSeq === this._projectSwitchSeq) hideLoading();
    }
  },

  _getActivePage() {
    return this.currentPage || document.querySelector('.nav-item.active')?.dataset.page || 'dashboard';
  },

  _updateProjectSettlementNav() {
    const el = document.getElementById('navProjectSettlement');
    if (!el) return;
    const p = this.currentProject;
    const has = !!p?.id;
    el.classList.toggle('nav-item-disabled', !has);
    el.title = has
      ? `註冊及更新 · ${p.project_code}`
      : '請先選擇項目';
  },

  openCurrentProjectSettlement() {
    const p = this.currentProject;
    if (!p?.id) {
      toast('請先在上方選擇項目', 'warn');
      return;
    }
    Projects.openSettlement(p.id);
  },

  _closeProjectModals() {
    Payments.closeModal?.();
    SC.closeModal?.();
    SC.closePayModal?.();
    IpPeriod.closeModal?.();
    IpPeriod.closeMetaModal?.();
    ScVoReg.closeModal?.();
    ScVoReg.closeTplManager?.();
  },

  _resetProjectFilters() {
    const payFilter = document.getElementById('payFilterSc');
    const paySearch = document.getElementById('paySearch');
    const scSearch = document.getElementById('scSearch');
    const svrSearch = document.getElementById('svrSearch');
    const svrFilterSc = document.getElementById('svrFilterSc');
    const svrFilterType = document.getElementById('svrFilterType');
    if (payFilter) payFilter.value = '';
    if (paySearch) paySearch.value = '';
    if (scSearch) scSearch.value = '';
    if (svrSearch) svrSearch.value = '';
    if (svrFilterSc) svrFilterSc.value = '';
    if (svrFilterType) svrFilterType.value = '';
  },

  async _refreshProjectViews(switchSeq) {
    Payments.populateScFilter();
    OCR.populateScOptions();

    await Promise.all([
      Dashboard.load(switchSeq),
      Payments.load(switchSeq),
      SC.load(switchSeq),
      IpPeriod.load(switchSeq),
      Reports.load(switchSeq),
    ]);
    if (switchSeq !== this._projectSwitchSeq) return;
    const active = this._getActivePage();
    if (active === 'iso-docs') IsoDocs.load();
    if (active === 'sc-vo-reg') { ScVoReg.populateScFilter(); ScVoReg.load(); }
    if (active === 'main-con-fac') MainConFac.load();
    if (active === 'sc-fac') ScFac.load();
    OCR.reset();
  },

  navigate(page, options = null) {
    Sidebar.closeMobile();
    if (page === 'settings' && Auth.authRequired && !Auth.isAdmin()) {
      toast('需要管理員權限', 'warning');
      return;
    }
    if (page === 'subcontractors') {
      options = options && typeof options === 'object' ? options : {};
      options.tab = options.tab || 'sc';
      page = 'payments';
    }
    if (page === 'ocr') {
      options = options && typeof options === 'object' ? options : {};
      options.tab = options.tab || 'ocr';
      page = 'payments';
    }
    if (page === 'sc-vo') page = 'sc-vo-reg';
    this.currentPage = page;
    // 隱藏所有頁面
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));

    // 顯示目標頁面
    document.getElementById(`page-${page}`)?.classList.add('active');
    document.querySelector(`[data-page="${page}"]`)?.classList.add('active');

    // 更新頁面標題
    const titles = {
      dashboard: ['項目概覽', '項目財務總覽'],
      'iso-docs': ['ISO文件登記', 'ISO 文件上傳 · 主合約及分判招標合約附件'],
      payments: ['分判付款登記', '發票／中期糧款計算書登記'],
      'sc-vo-reg': ['分判變更以及扣款登記', 'Sub-Con VO · 變更工程及扣款 · 模板快速新增'],
      'ip-period': ['糧期狀況', '地盤中期糧款手動編輯'],
      'main-con-fac': ['最終結算', 'Main Con Final Account · 工程帳目總結算'],
      'sc-fac': ['分判最終結算', 'SC Final Account · 每判項 PDF（3 頁）'],
      reports: ['財務報表', '付款統計分析'],
      projects: ['工程項目', '管理地盤工程項目 · Summary · 註冊及更新'],
      'project-settlement': ['註冊及更新', '項目金額結算（Cover Page 第5頁）'],
      'master-list': ['Master List', '公司報價／標書清單（Phase 1）'],
      'sc-contract-registry': ['分判合約編號', 'MS/C 分判工程合約編號表 · P1 PDF'],
      staff: ['項目負責人管理', 'Master List 項目負責人 · 工程項目選人'],
      settings: ['系統設定', 'OCR與系統配置'],
    };
    const [title, sub] = titles[page] || ['', ''];
    document.getElementById('pageTitle').textContent = title;
    document.getElementById('pageSubtitle').textContent = sub;

    const quickAdd = document.getElementById('btnQuickAdd');
    if (quickAdd) quickAdd.style.display = 'none';

    // 載入頁面數據
    if (page === 'dashboard') Dashboard.load();
    else if (page === 'iso-docs') IsoDocs.load();
    else if (page === 'payments') {
      if (options?.tab) Payments._pendingTab = options.tab;
      if (options?.openPaymentId) Payments._pendingOpenPaymentId = options.openPaymentId;
      Payments.load();
    }
    else if (page === 'sc-vo-reg') { ScVoReg.populateScFilter(); ScVoReg.load(); }
    else if (page === 'main-con-fac') MainConFac.load();
    else if (page === 'sc-fac') ScFac.load();
    else if (page === 'ip-period') IpPeriod.load();
    else if (page === 'reports') Reports.load();
    else if (page === 'projects') Projects.load();
    else if (page === 'master-list') MasterList.load();
    else if (page === 'sc-contract-registry') ScContractRegistry.load();
    else if (page === 'staff') StaffRoster.refresh();
    else if (page === 'settings') Settings.load();
    else if (page === 'project-settlement') Projects.loadSettlement();
  },

  quickAddPayment() {
    App.navigate('payments');
    setTimeout(() => Payments.openAdd(), 100);
  },

  importExcel() {
    document.getElementById('importModal').classList.add('open');
  },

  async onImportFileSelect(event) {
    const file = event.target.files[0];
    if (!file) return;

    document.getElementById('importStatus').style.display = '';
    const formData = new FormData();
    formData.append('file', file);

    try {
      const r = await fetch(`${API}/import/excel`, { method: 'POST', body: formData });
      const json = await r.json();
      if (json.success) {
        toast('Excel匯入成功！', 'success');
        document.getElementById('importModal').classList.remove('open');
        await App.loadProjects();
        if (json.data?.project_id) await App.selectProject(json.data.project_id);
      } else {
        toast('匯入失敗: ' + json.error, 'error');
      }
    } catch (e) {
      toast('匯入錯誤: ' + e.message, 'error');
    } finally {
      document.getElementById('importStatus').style.display = 'none';
      event.target.value = '';
    }
  },
};

// ─── Dashboard ─────────────────────────────────────────────
const Dashboard = {
  charts: {},

  async load(switchSeq) {
    const p = App.currentProject;
    if (!p) {
      document.getElementById('dashboardNoProject').style.display = '';
      document.getElementById('dashboardContent').style.display = 'none';
      return;
    }
    const projectId = p.id;
    document.getElementById('dashboardNoProject').style.display = 'none';
    document.getElementById('dashboardContent').style.display = '';

    const summary = await api('GET', `/reports/summary/${projectId}`);
    if (!summary || !App.currentProject || App.currentProject.id != projectId) return;
    if (switchSeq != null && switchSeq !== App._projectSwitchSeq) return;

    // 統計卡片
    const totalPaid = summary.total_paid || 0;
    const totalRem = summary.total_remainder || 0;
    const contractAmt = summary.project?.contract_amount || p.contract_amount || 0;
    const progress = contractAmt > 0 ? ((totalPaid / contractAmt) * 100).toFixed(FMT_DECIMALS) : '—';

    updateDashProjectHero(summary.project || p, summary.ip_period);

    setAmtEl(document.getElementById('dashTotalPaid'), totalPaid, 'expense');
    setAmtEl(document.getElementById('dashRemainder'), totalRem, 'expense');
    document.getElementById('dashProgress').textContent = progress !== '—' ? `${progress}%` : '—';

    updateDashIpTotals(summary.ip_period);

    // 付款登記統計
    const payments = await api('GET', `/projects/${projectId}/payments`);
    if (!App.currentProject || App.currentProject.id != projectId) return;
    if (switchSeq != null && switchSeq !== App._projectSwitchSeq) return;
    document.getElementById('dashPayCount').textContent = payments?.length || 0;
    document.getElementById('payBadge').textContent = payments?.length || 0;
    document.getElementById('dashScCount').textContent = App.scList?.length || 0;

    renderContractCalc(summary.contract_calc, 'dashContractCalc');
    renderSiteIpPeriod(summary.ip_period, 'dashSiteIp', { editable: false, hideProjectMeta: true });

    // 最近記錄
    const recent = (payments || []).slice(0, 8);
    const tbody = document.getElementById('dashRecentPayments');
    if (recent.length === 0) {
      tbody.innerHTML = `<tr><td colspan="6"><div class="empty-state" style="padding:24px">暫無付款登記</div></td></tr>`;
    } else {
      tbody.innerHTML = recent.map(r => `
        <tr onclick="App.navigate('payments')">
          <td class="td-muted">${fmtDate(r.invoice_date)}</td>
          <td>${fmtRefNo(r.sc_no)}</td>
          <td class="td-company-name">${paymentCompanyNameHtml(r)}</td>
          <td class="td-muted" style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${r.description || '—'}</td>
          <td class="td-amount ${amtClass(r.paid_amount, 'expense')}">${fmtExpense(r.paid_amount)}</td>
          <td class="td-mono td-muted">${r.invoice_no || '—'}</td>
        </tr>
      `).join('');
    }

    // 圖表
    this._lastScStats = summary.sc_stats || [];
    this.renderCharts(this._lastScStats);
  },

  renderCharts(scStats) {
    const stats = scStats.filter(s => s.contract_amount > 0).slice(0, 10);
    const labels = stats.map(s => s.sc_no || s.company_name_en?.substring(0, 15));
    const paid = stats.map(s => s.total_paid || 0);
    const remaining = stats.map(s => Math.max(0, (s.contract_amount || 0) - (s.total_paid || 0)));
    const pal = Theme.chartPalette();

    // 銷毀舊圖表
    Object.values(this.charts).forEach(c => c?.destroy());
    this.charts = {};

    // 橫條圖 - 付款狀況
    const ctx1 = document.getElementById('chartPayment').getContext('2d');
    this.charts.payment = new Chart(ctx1, {
      type: 'bar',
      data: {
        labels,
        datasets: [
          { label: '已付', data: paid, backgroundColor: pal.paid, borderRadius: 4 },
          { label: '未付', data: remaining, backgroundColor: pal.unpaid, borderRadius: 4 },
        ]
      },
      options: {
        indexAxis: 'y',
        responsive: true, maintainAspectRatio: false,
        plugins: {
          legend: { labels: { color: pal.text, font: { size: 11 } } },
          tooltip: {
            callbacks: {
              label: ctx => `${ctx.dataset.label}: HK$${fmtNumPlain(ctx.raw)}`
            }
          }
        },
        scales: {
          x: { stacked: true, ticks: { color: pal.text, font: { size: 10 }, callback: v => 'HK$' + (v / 1000).toFixed(FMT_DECIMALS) + 'K' }, grid: { color: pal.grid } },
          y: { stacked: true, ticks: { color: pal.label, font: { size: 11 } }, grid: { display: false } },
        }
      }
    });

    // 圓餅圖 - 類別分佈
    const categories = {};
    scStats.forEach(s => {
      const key = refNoType(s.sc_no).label || '其他';
      categories[key] = (categories[key] || 0) + (s.total_paid || 0);
    });

    const ctx2 = document.getElementById('chartCategory').getContext('2d');
    this.charts.category = new Chart(ctx2, {
      type: 'doughnut',
      data: {
        labels: Object.keys(categories),
        datasets: [{
          data: Object.values(categories),
          backgroundColor: pal.segments,
          borderWidth: 0, hoverOffset: 8
        }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: {
          legend: { position: 'bottom', labels: { color: pal.text, font: { size: 11 }, padding: 12 } },
          tooltip: {
            callbacks: { label: ctx => `${ctx.label}: HK$${fmtNumPlain(ctx.raw)}` }
          }
        }
      }
    });
  }
};

// ─── Settings ──────────────────────────────────────────────
const Settings = {
  _docProjects: [],
  _docProjectFilter: '',

  async load() {
    const data = await api('GET', '/settings');
    if (data) {
      document.getElementById('settingApiKey').value = data.gemini_api_key || '';
      document.getElementById('settingQuarkId').value = data.quark_client_id || '';
      document.getElementById('settingQuarkKey').value = data.quark_client_key || '';
      document.getElementById('settingQuarkApiKey').value = data.quark_api_key || '';
      document.getElementById('settingOcrMode').value = data.ocr_mode || 'auto';
      document.getElementById('settingCompany').value = data.company_name || '';
    }
    await this.loadDocLibrary();
    // 顯示OCR引擎狀態
    try {
      const engRes = await api('GET', '/ocr/engines');
      const engines = engRes?.engines || [];
      const el = document.getElementById('engineStatus');
      if (el) {
        if (engines.length === 0) {
          el.innerHTML = '<span class="badge badge-danger">⚠️ 無可用OCR引擎</span>';
        } else {
          el.innerHTML = engines.map(e => {
            const icon = e.includes('夸克') ? '🔮' :
                         e.includes('RapidOCR') ? '🐉' :
                         e.includes('pdfplumber') || e.includes('PyMuPDF') ? '📝' :
                         e.includes('Gemini') ? '🤖' : '👁️';
            const cls  = e.includes('夸克') && !e.includes('未設定') ? 'success' :
                         e.includes('RapidOCR') ? 'success' :
                         e.includes('Gemini') && e.includes('已設定') ? 'info' :
                         e.includes('未設定') || e.includes('未安裝') ? 'warning' : 'muted';
            return `<span class="badge badge-${cls}" style="margin:2px 4px 2px 0">${icon} ${e}</span>`;
          }).join('');
        }
      }
    } catch (e) {}
  },
  async save() {
    await api('POST', '/settings', {
      gemini_api_key: document.getElementById('settingApiKey').value,
      quark_client_id: document.getElementById('settingQuarkId').value.trim(),
      quark_client_key: document.getElementById('settingQuarkKey').value.trim(),
      quark_api_key: document.getElementById('settingQuarkApiKey').value.trim(),
      ocr_mode: document.getElementById('settingOcrMode').value,
      company_name: document.getElementById('settingCompany').value,
    });
    toast('設定已儲存', 'success');
  },

  async loadDocLibrary() {
    const search = document.getElementById('settingDocProjectSearch');
    if (search) search.value = '';
    this._docProjectFilter = '';
    try {
      const data = await api('GET', '/settings/doc-library');
      document.getElementById('settingDocLibraryUrl').value = data?.global_url || '';
      this._docProjects = data?.projects || [];
      this._renderDocProjectTable();
    } catch (e) {
      const tbody = document.getElementById('settingDocProjectBody');
      if (tbody) {
        tbody.innerHTML = '<tr><td colspan="4" class="td-muted" style="padding:20px;text-align:center">載入失敗</td></tr>';
      }
    }
  },

  filterDocProjects(q) {
    this._syncDocProjectInputs();
    this._docProjectFilter = (q || '').trim().toLowerCase();
    this._renderDocProjectTable();
  },

  _syncDocProjectInputs() {
    document.querySelectorAll('.setting-doc-proj-url').forEach(inp => {
      const id = parseInt(inp.dataset.projectId, 10);
      const p = (this._docProjects || []).find(x => x.id === id);
      if (p) p.doc_library_url = inp.value.trim();
    });
  },

  _renderDocProjectTable() {
    const tbody = document.getElementById('settingDocProjectBody');
    if (!tbody) return;
    const q = this._docProjectFilter;
    const rows = (this._docProjects || []).filter(p => {
      if (!q) return true;
      const hay = `${p.project_code || ''} ${p.project_name_zh || ''}`.toLowerCase();
      return hay.includes(q);
    });
    if (!rows.length) {
      tbody.innerHTML = '<tr><td colspan="4" class="td-muted" style="padding:20px;text-align:center">沒有符合的項目</td></tr>';
      return;
    }
    tbody.innerHTML = rows.map(p => {
      const code = escHtml(p.project_code || '—');
      const name = escHtml(p.project_name_zh || '—');
      const st = projectStatusInfo(p.status);
      const url = escHtml(p.doc_library_url || '');
      return `<tr data-project-id="${p.id}">
        <td class="settings-doc-code">${code}</td>
        <td class="settings-doc-name">${name}</td>
        <td><span class="badge badge-${st.badge}" style="font-size:10px">${st.label}</span></td>
        <td><input type="url" class="form-input setting-doc-proj-url" data-project-id="${p.id}"
          value="${url}" placeholder="https://.../${code}/ISO/"></td>
      </tr>`;
    }).join('');
  },

  _collectDocProjectUrls() {
    return (this._docProjects || []).map(p => ({
      id: p.id,
      doc_library_url: p.doc_library_url || '',
    }));
  },

  async saveDocLibrary() {
    this._syncDocProjectInputs();
    showLoading('儲存文件管理設定…');
    try {
      await api('POST', '/settings/doc-library', {
        global_url: document.getElementById('settingDocLibraryUrl').value.trim(),
        projects: this._collectDocProjectUrls(),
      });
      if (typeof IsoDocs !== 'undefined') IsoDocs._globalDocUrl = undefined;
      await App.loadProjects();
      const curId = App.currentProject?.id;
      if (curId) {
        const fresh = App.projects.find(p => p.id == curId);
        if (fresh) {
          App.currentProject = fresh;
          if (App._getActivePage?.() === 'iso-docs') IsoDocs.load();
        }
      }
      await this.loadDocLibrary();
      toast('文件管理設定已儲存', 'success');
    } catch (e) {
      toast(e.message || '儲存失敗', 'error');
    } finally {
      hideLoading();
    }
  },
};

// ─── 初始化 ────────────────────────────────────────────────
window.addEventListener('load', () => App.init());
