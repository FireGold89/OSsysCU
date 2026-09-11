/* portfolio_progress.js — 進行中項目（On Progress Projects） */
const PortfolioCommon = {
  STATUS_OPTIONS: [
    { value: 'On Progress', label: '進行中' },
    { value: 'Completed', label: '已完成' },
  ],
  CLIENT_FA_OPTIONS: [
    { value: 'On Progress', label: '進行中' },
    { value: 'Completed', label: '已完成' },
    { value: '待簽', label: '待簽' },
  ],

  statusLabel(val) {
    const found = this.STATUS_OPTIONS.find((x) => x.value === val);
    return found ? found.label : (val || '—');
  },

  clientFaLabel(val) {
    const found = this.CLIENT_FA_OPTIONS.find((x) => x.value === val);
    return found ? found.label : (val || '—');
  },

  statusClass(val) {
    if (val === 'Completed') return 'portfolio-chip done';
    if (val === '待簽') return 'portfolio-chip pending';
    return 'portfolio-chip progress';
  },

  statusSelectClass(val) {
    const v = (val || '').trim();
    if (v === 'Completed') return 'pf-status-done';
    if (v === '待簽') return 'pf-status-pending';
    if (v === 'On Progress') return 'pf-status-progress';
    return 'pf-status-empty';
  },

  onStatusSelectChange(el) {
    el.classList.remove('pf-status-done', 'pf-status-progress', 'pf-status-pending', 'pf-status-empty');
    el.classList.add(this.statusSelectClass(el.value));
    if (el.dataset.scField === 'fac_status') this.saveScField(el);
    else this.saveField(el);
  },

  dash(val) {
    const s = (val ?? '').toString().trim();
    return s ? escHtml(s) : '<span class="td-muted">—</span>';
  },

  descCell(val) {
    const s = (val ?? '').toString().trim();
    if (!s) return '<span class="td-muted">—</span>';
    return `<span class="pf-desc" title="${escHtml(s)}">${escHtml(s)}</span>`;
  },

  clientCell(val) {
    const s = (val ?? '').toString().trim();
    if (!s) return '<span class="td-muted">—</span>';
    return `<span class="pf-client-cell" title="${escHtml(s)}">${escHtml(s)}</span>`;
  },

  daysUntil(dateStr) {
    const s = (dateStr || '').toString().trim();
    if (!s) return null;
    const t = Date.parse(s);
    if (Number.isNaN(t)) return null;
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    return Math.round((t - today.getTime()) / 86400000);
  },

  dlpStatus(dateStr) {
    const d = this.daysUntil(dateStr);
    if (d == null) return null;
    if (d < 0) return { kind: 'overdue', label: `已過期 ${Math.abs(d)} 天` };
    if (d <= 90) return { kind: 'soon', label: `${d} 天內` };
    return null;
  },

  dlpChipHtml(dateStr) {
    const st = this.dlpStatus(dateStr);
    if (!st) return '';
    return `<span class="portfolio-chip portfolio-chip-dlp ${st.kind}">${escHtml(st.label)}</span>`;
  },

  dlpExpiryCell(id, val) {
    const chip = this.dlpChipHtml(val);
    return `<div class="pf-dlp-expiry-cell">${this.dateInput(id, val, 'dlp_expiry_date')}${chip}</div>`;
  },

  hasScPending(item) {
    const slots = item?.subcontractors || [];
    return slots.some((sc) => PortfolioCommon.slotHasData(sc) && (sc.fac_status || '').trim() !== 'Completed');
  },

  slotHasData(sc) {
    return !!(sc?.name || '').trim() || !!(sc?.fac_status || '').trim();
  },

  dateCell(val) {
    return this.dash(val);
  },

  checkCell(done) {
    return done ? '<span class="portfolio-check">✔</span>' : '<span class="td-muted">—</span>';
  },

  statusSelect(id, val, field) {
    const cur = val || 'On Progress';
    const opts = this.STATUS_OPTIONS.map((o) => (
      `<option value="${o.value}" ${o.value === cur ? 'selected' : ''}>${o.label}</option>`
    )).join('');
    return `<select class="form-input portfolio-select portfolio-status-select ${this.statusSelectClass(cur)}" data-id="${id}" data-field="${field}" onchange="PortfolioCommon.onStatusSelectChange(this)">${opts}</select>`;
  },

  clientFaSelect(id, val) {
    const cur = val || 'On Progress';
    const opts = this.CLIENT_FA_OPTIONS.map((o) => (
      `<option value="${o.value}" ${o.value === cur ? 'selected' : ''}>${o.label}</option>`
    )).join('');
    return `<select class="form-input portfolio-select portfolio-status-select ${this.statusSelectClass(cur)}" data-id="${id}" data-field="client_fac_status" onchange="PortfolioCommon.onStatusSelectChange(this)">${opts}</select>`;
  },

  dateInput(id, val, field) {
    return `<input type="date" class="form-input portfolio-date" data-id="${id}" data-field="${field}" value="${escHtml(val || '')}" onchange="PortfolioCommon.saveField(this)">`;
  },

  textInput(id, val, field, placeholder) {
    return `<input type="text" class="form-input portfolio-text" data-id="${id}" data-field="${field}" value="${escHtml(val || '')}" placeholder="${escHtml(placeholder || '')}" onchange="PortfolioCommon.saveField(this)" onkeydown="if(event.key==='Enter')this.blur()">`;
  },

  projectLink(item) {
    const code = item.project_code || '—';
    if (!item.project_id) return escHtml(code);
    return `<button type="button" class="btn-link portfolio-code-link" onclick="PortfolioCommon.openProject(${item.project_id})">${escHtml(code)}</button>`;
  },

  async openProject(projectId) {
    await App.selectProject(projectId);
    App.navigate('dashboard');
  },

  _saveTimer: {},

  saveField(el) {
    const id = Number(el.dataset.id);
    const field = el.dataset.field;
    const value = el.value;
    const key = `${id}:${field}`;
    clearTimeout(this._saveTimer[key]);
    const delay = (field === 'portfolio_remark' || field === 'n_code') ? 400 : 0;
    this._saveTimer[key] = setTimeout(() => this._put(id, field, value, el), delay);
  },

  async _put(id, field, value, el) {
    try {
      const body = {};
      body[field] = value;
      const item = await api('PUT', `/portfolio/projects/${id}`, body);
      el.classList.remove('portfolio-save-err');
      el.classList.add('portfolio-save-ok');
      setTimeout(() => el.classList.remove('portfolio-save-ok'), 800);
      if (typeof PortfolioProgress !== 'undefined') PortfolioProgress.patchItem(item);
      if (typeof PortfolioFac !== 'undefined') PortfolioFac.patchItem(item);
    } catch (e) {
      el.classList.add('portfolio-save-err');
    }
  },

  checkInput(id, done, field) {
    const on = done ? ' checked' : '';
    return `<label class="portfolio-check-wrap"><input type="checkbox" data-id="${id}" data-field="${field}"${on} onchange="PortfolioCommon.saveCheck(this)"></label>`;
  },

  numberInput(id, val, field) {
    const v = val == null || val === '' ? '' : escHtml(String(val));
    return `<input type="number" class="form-input portfolio-num" data-id="${id}" data-field="${field}" value="${v}" min="0" step="1" onchange="PortfolioCommon.saveField(this)">`;
  },

  saveCheck(el) {
    this._put(Number(el.dataset.id), el.dataset.field, el.checked ? 1 : 0, el);
  },

  SC_FAC_OPTIONS: [
    { value: 'On Progress', label: '進行中' },
    { value: 'Completed', label: '已完成' },
    { value: '待簽', label: '待簽' },
  ],

  slotAt(item, slotNo) {
    const slots = item?.subcontractors || [];
    const hit = slots.find((s) => Number(s.slot) === Number(slotNo));
    return hit || { slot: slotNo, name: '', fac_status: '', subcontractor_id: null };
  },

  scFacSelect(portfolioId, slot, val) {
    const cur = val || '';
    const opts = ['<option value="">—</option>'].concat(this.SC_FAC_OPTIONS.map((o) => (
      `<option value="${o.value}" ${o.value === cur ? 'selected' : ''}>${o.label}</option>`
    ))).join('');
    return `<select class="form-input portfolio-select portfolio-status-select pf-sc-status ${this.statusSelectClass(cur)}" data-id="${portfolioId}" data-slot="${slot}" data-sc-field="fac_status" onchange="PortfolioCommon.onStatusSelectChange(this)">${opts}</select>`;
  },

  _scNameMatch(sub, curName) {
    const name = this.scCompanyName(sub);
    const cur = (curName || '').trim();
    if (!cur || !name) return false;
    if (name === cur) return true;
    const norm = (s) => s.replace(/\s+/g, '').toLowerCase();
    const a = norm(name);
    const b = norm(cur);
    return a === b || a.includes(b) || b.includes(a);
  },

  _lastScClear: null,

  _restoreScSelect(el, sc) {
    if (sc?.subcontractor_id) el.value = String(sc.subcontractor_id);
    else if ((sc?.name || '').trim()) el.value = '__keep__';
    else el.value = '';
  },

  _showScClearUndoToast() {
    const container = document.getElementById('toastContainer');
    if (!container) return;
    const el = document.createElement('div');
    el.className = 'toast warning';
    el.innerHTML = '<span>⚠️</span><span>已清除分判</span><button type="button" class="btn-link toast-undo-btn">復原</button>';
    const undoBtn = el.querySelector('.toast-undo-btn');
    undoBtn.onclick = (e) => {
      e.stopPropagation();
      el.remove();
      this.undoLastScClear();
    };
    el.onclick = () => el.remove();
    container.appendChild(el);
    const snap = this._lastScClear;
    setTimeout(() => {
      if (el.parentNode) el.remove();
      if (this._lastScClear === snap) this._lastScClear = null;
    }, 15000);
  },

  async undoLastScClear() {
    const u = this._lastScClear;
    if (!u) {
      toast('沒有可復原的清除操作', 'info');
      return;
    }
    this._lastScClear = null;
    const host = typeof PortfolioFac !== 'undefined' ? PortfolioFac : null;
    try {
      const updated = await api('PUT', `/portfolio/projects/${u.portfolioId}/sc-status`, {
        slots: [{
          slot: u.slot,
          name: u.name || null,
          fac_status: u.fac_status || null,
          subcontractor_id: u.subcontractor_id || null,
        }],
      });
      toast('已復原分判', 'success');
      if (typeof PortfolioProgress !== 'undefined') PortfolioProgress.patchItem(updated);
      if (host) {
        host.patchItem(updated);
        if (host.showMatrix) host.render();
        if (host.drawerId === u.portfolioId) host.renderDrawer(updated);
      }
    } catch (e) {
      toast(e.message || '復原失敗', 'error');
    }
  },

  scNamePicker(portfolioId, slot, sc, projectId) {
    const subs = (typeof PortfolioFac !== 'undefined' && PortfolioFac._projectScCache?.[projectId]) || [];
    const curId = sc?.subcontractor_id;
    const curName = (sc?.name || '').trim();
    const link = sc?.subcontractor_id && projectId
      ? `<button type="button" class="pf-sc-link" title="分判最終結算" onclick="event.stopPropagation();PortfolioCommon.openScFac(${projectId},${sc.subcontractor_id})">🔗</button>`
      : '';
    let matched = false;
    let opts = '';
    if (curName) {
      subs.forEach((s) => {
        const selected = (curId && Number(s.id) === Number(curId))
          || (!curId && this._scNameMatch(s, curName));
        if (selected) matched = true;
      });
      if (!matched) {
        opts += `<option value="__keep__" selected>${escHtml(curName)}</option>`;
      }
    }
    if (!subs.length) {
      if (!curName) {
        opts += '<option value="" selected disabled>— 尚無系統分判 —</option>';
      } else if (!matched) {
        opts += '<option value="" disabled>— 尚無系統分判可選 —</option>';
      }
    } else if (!curName || matched) {
      opts += `<option value=""${!curName ? ' selected' : ''}>— 選分判 —</option>`;
    }
    subs.forEach((s) => {
      const name = this.scCompanyName(s);
      const selected = (curId && Number(s.id) === Number(curId))
        || (!curId && this._scNameMatch(s, curName));
      if (selected) matched = true;
      opts += `<option value="${s.id}"${selected ? ' selected' : ''}>${escHtml(s.sc_no || '—')} · ${escHtml(name || '—')}</option>`;
    });
    if (curName && !matched) {
      opts += '<option value="__clear__">— 清除分判 —</option>';
    }
    const emptyHint = subs.length
      ? ''
      : ' title="此項目尚無系統分判；請至分判付款登記建立，或重新匯入 FA Excel 還原名稱"';
    return `<div class="pf-sc-name-wrap">${link}<select class="form-input pf-sc-name-select" data-id="${portfolioId}" data-slot="${slot}" data-project-id="${projectId || ''}" data-sc-field="name"${emptyHint} onchange="PortfolioCommon.saveScSelect(this)">${opts}</select></div>`;
  },

  async saveScSelect(el) {
    const portfolioId = Number(el.dataset.id);
    const slot = Number(el.dataset.slot);
    const projectId = Number(el.dataset.projectId) || 0;
    const host = typeof PortfolioFac !== 'undefined' ? PortfolioFac : null;
    const item = host?.items?.find((x) => x.id === portfolioId);
    const sc = this.slotAt(item, slot);
    const raw = el.value;
    if (raw === '__keep__') return;
    if (raw === '__clear__') {
      const label = (sc.name || '').trim() || `槽位 ${slot}`;
      if (!window.confirm(`確定清除「${label}」？\n\n清除後可從下拉重新選擇；確認後 15 秒內可按「復原」。`)) {
        this._restoreScSelect(el, sc);
        return;
      }
    }
    const prevSnapshot = (raw === '__clear__' && (sc.name || sc.fac_status || sc.subcontractor_id))
      ? {
        portfolioId,
        slot,
        projectId,
        name: sc.name,
        fac_status: sc.fac_status,
        subcontractor_id: sc.subcontractor_id,
      }
      : null;
    const scId = raw && raw !== '__clear__' ? Number(raw) : null;
    let name = '';
    if (raw === '__clear__') {
      name = '';
    } else if (scId && projectId) {
      const subs = host?._projectScCache?.[projectId] || [];
      const sub = subs.find((s) => Number(s.id) === scId);
      name = this.scCompanyName(sub);
    }
    const body = {
      slots: [{
        slot,
        name: name || null,
        fac_status: sc.fac_status || null,
        subcontractor_id: scId,
      }],
    };
    try {
      const updated = await api('PUT', `/portfolio/projects/${portfolioId}/sc-status`, body);
      el.classList.remove('portfolio-save-err');
      el.classList.add('portfolio-save-ok');
      setTimeout(() => el.classList.remove('portfolio-save-ok'), 800);
      if (typeof PortfolioProgress !== 'undefined') PortfolioProgress.patchItem(updated);
      if (host) {
        host.patchItem(updated);
        if (host.showMatrix) host.render();
        if (host.drawerId === portfolioId) host.renderDrawer(updated);
      }
      if (prevSnapshot) {
        this._lastScClear = prevSnapshot;
        this._showScClearUndoToast();
      }
    } catch (e) {
      el.classList.add('portfolio-save-err');
    }
  },

  scNameInput(portfolioId, slot, sc, projectId) {
    return this.scNamePicker(portfolioId, slot, sc, projectId);
  },

  _scSaveTimer: {},

  saveScField(el) {
    const portfolioId = Number(el.dataset.id);
    const slot = Number(el.dataset.slot);
    const field = el.dataset.scField;
    const key = `${portfolioId}:${slot}:${field}`;
    clearTimeout(this._scSaveTimer[key]);
    const delay = field === 'name' ? 400 : 0;
    this._scSaveTimer[key] = setTimeout(() => this._putSc(portfolioId, slot, field, el.value, el), delay);
  },

  async _putSc(portfolioId, slot, field, value, el) {
    const host = typeof PortfolioFac !== 'undefined' ? PortfolioFac : null;
    const item = host?.items?.find((x) => x.id === portfolioId);
    const sc = this.slotAt(item, slot);
    const name = (field === 'name' ? value : (sc.name || '')).trim();
    const facStatus = (field === 'fac_status' ? value : (sc.fac_status || '')).trim();
    const body = {
      slots: [{
        slot,
        name,
        fac_status: facStatus || null,
        subcontractor_id: field === 'name' ? null : sc.subcontractor_id,
      }],
    };
    try {
      const updated = await api('PUT', `/portfolio/projects/${portfolioId}/sc-status`, body);
      el.classList.remove('portfolio-save-err');
      el.classList.add('portfolio-save-ok');
      setTimeout(() => el.classList.remove('portfolio-save-ok'), 800);
      if (typeof PortfolioProgress !== 'undefined') PortfolioProgress.patchItem(updated);
      if (typeof PortfolioFac !== 'undefined') {
        PortfolioFac.patchItem(updated);
        if (PortfolioFac.showMatrix) PortfolioFac.render();
        if (PortfolioFac.drawerId === portfolioId) PortfolioFac.renderDrawer(updated);
      }
    } catch (e) {
      el.classList.add('portfolio-save-err');
    }
  },

  async openProjectPage(projectId, page) {
    if (!projectId) return;
    await App.selectProject(projectId);
    App.navigate(page || 'dashboard');
  },

  async openScFac(projectId, subcontractorId) {
    if (!projectId) return;
    await App.selectProject(projectId);
    if (typeof ScFac !== 'undefined') ScFac._pendingScId = subcontractorId || null;
    App.navigate('sc-fac');
  },

  scCompanyName(sc) {
    return (sc?.company_name_zh || sc?.company_name_en || sc?.company || '').trim();
  },

  lastImportText(info) {
    if (!info || !info.imported_at) return '尚未匯入 Excel';
    const day = String(info.imported_at).slice(0, 10);
    const n = info.rows_upserted != null ? info.rows_upserted : info.rows_read;
    const name = info.filename ? ` · ${info.filename}` : '';
    return `上次匯入：${day}${name}（${n} 項）`;
  },

  async downloadExport(apiPath, filename) {
    showContentLoading('匯出 Excel…');
    try {
      const r = await fetch(API + apiPath, { credentials: 'include' });
      if (!r.ok) throw new Error('匯出失敗');
      const blob = await r.blob();
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = filename;
      a.click();
      setTimeout(() => URL.revokeObjectURL(a.href), 2000);
      toast('已下載 Excel', 'success');
    } catch (e) {
      toast(e.message || '匯出失敗', 'error');
    } finally {
      hideContentLoading();
    }
  },

  _pendingFile: null,
  _importKind: 'fa',

  pickImport(kind) {
    this._importKind = kind === 'progress' ? 'progress' : 'fa';
    const input = document.getElementById('pfImportFile');
    if (input) {
      input.value = '';
      input.click();
    }
  },

  async onImportFile(ev) {
    const file = ev.target.files && ev.target.files[0];
    ev.target.value = '';
    if (!file) return;
    this._pendingFile = file;
    const isFa = this._importKind === 'fa';
    const path = isFa
      ? '/portfolio/import/fa-list?preview=1'
      : '/portfolio/import/progress-list?preview=1';
    showContentLoading('預覽 Excel…');
    try {
      const fd = new FormData();
      fd.append('file', file);
      const r = await fetch(API + path, { method: 'POST', body: fd, credentials: 'include' });
      const json = await r.json();
      if (!json.success) throw new Error(json.error || '預覽失敗');
      this._showImportPreview(json.data, isFa);
    } catch (e) {
      toast(e.message || '預覽失敗', 'error');
      this._pendingFile = null;
    } finally {
      hideContentLoading();
    }
  },

  _showImportPreview(data, isFa) {
    const modal = document.getElementById('pfImportModal');
    const body = document.getElementById('pfImportPreview');
    const title = document.getElementById('pfImportTitle');
    if (!modal || !body) return;
    if (title) title.textContent = isFa ? '匯入 N 項目結算總表' : '匯入進行中項目';
    const unmatched = data.unmatched_rows || [];
    let extra = '';
    if (unmatched.length) {
      extra = `<p class="form-hint">未配對 ${unmatched.length} 項將建立 placeholder 工程項目：</p>
        <ul class="portfolio-import-unmatched">${unmatched.slice(0, 12).map((r) => (
          `<li><code>${escHtml(r.project_code)}</code> ${escHtml(r.n_code || '')} ${escHtml(r.description || '')}</li>`
        )).join('')}${unmatched.length > 12 ? `<li>…另 ${unmatched.length - 12} 項</li>` : ''}</ul>`;
    }
    body.innerHTML = `
      <p class="form-hint">檔案：${escHtml(data.filename || '')} · sheet ${escHtml(data.sheet || '')}</p>
      <div class="stats-grid" style="grid-template-columns:repeat(3,1fr);margin:12px 0">
        <div class="stat-card"><div class="stat-label">讀取</div><div class="stat-value">${data.rows_read ?? '—'}</div></div>
        <div class="stat-card success"><div class="stat-label">已配對</div><div class="stat-value">${data.matched ?? '—'}</div></div>
        <div class="stat-card warning"><div class="stat-label">未配對</div><div class="stat-value">${data.unmatched ?? '—'}</div></div>
      </div>
      ${extra}
      <p class="form-hint">確認後會 upsert 狀態／N Code／DLP 等欄；Cover 已有的 PM／日期不會覆寫。</p>`;
    modal.classList.add('open');
    if (typeof ModalA11y !== 'undefined') ModalA11y.onOpen(modal);
  },

  closeImportModal() {
    document.getElementById('pfImportModal')?.classList.remove('open');
    this._pendingFile = null;
  },

  async confirmImport() {
    if (!this._pendingFile) {
      toast('請先選擇檔案', 'warning');
      return;
    }
    const isFa = this._importKind === 'fa';
    const path = isFa ? '/portfolio/import/fa-list' : '/portfolio/import/progress-list';
    showContentLoading('寫入資料庫…');
    try {
      const fd = new FormData();
      fd.append('file', this._pendingFile);
      const r = await fetch(API + path, { method: 'POST', body: fd, credentials: 'include' });
      const json = await r.json();
      if (!json.success) throw new Error(json.error || '匯入失敗');
      const d = json.data || {};
      toast(`已匯入 ${d.rows_upserted} 項（新增項目 ${d.created_projects || 0}）`, 'success');
      this.closeImportModal();
      if (typeof PortfolioFac !== 'undefined') PortfolioFac.load();
      if (typeof PortfolioProgress !== 'undefined') PortfolioProgress.load();
    } catch (e) {
      toast(e.message || '匯入失敗', 'error');
    } finally {
      hideContentLoading();
    }
  },

  fillPmSelect(selId, pms, current) {
    const sel = document.getElementById(selId);
    if (!sel) return;
    const keep = current || sel.value || '';
    sel.innerHTML = '<option value="">全部 PM</option>';
    (pms || []).forEach((pm) => {
      sel.innerHTML += `<option value="${escHtml(pm)}">${escHtml(pm)}</option>`;
    });
    if (keep) sel.value = keep;
  },

  queryString(status, pm, q) {
    const params = new URLSearchParams();
    if (status) params.set('status', status);
    if (pm) params.set('pm', pm);
    if (q) params.set('q', q);
    const s = params.toString();
    return s ? `?${s}` : '';
  },
};

const PortfolioProgress = {
  items: [],
  stats: {},
  lastImport: null,
  statusFilter: 'On Progress',
  pmFilter: '',
  q: '',

  async load() {
    const qEl = document.getElementById('ppSearch');
    this.q = (qEl?.value || '').trim();
    this.pmFilter = document.getElementById('ppPmFilter')?.value || '';
    showContentLoading('載入進行中項目…');
    try {
      const data = await api('GET', `/portfolio/progress${PortfolioCommon.queryString(this.statusFilter, this.pmFilter, this.q)}`);
      this.items = data?.items || [];
      this.stats = data?.stats || {};
      this.lastImport = data?.last_import || null;
      PortfolioCommon.fillPmSelect('ppPmFilter', data?.pms, this.pmFilter);
      this._syncTabs();
      this._renderStats();
      this.render();
    } catch (e) {
      const body = document.getElementById('ppTableBody');
      if (body) body.innerHTML = `<tr><td colspan="11"><div class="empty-state" style="padding:40px">載入失敗</div></td></tr>`;
    } finally {
      hideContentLoading();
    }
  },

  setStatus(status) {
    this.statusFilter = status;
    this._syncTabs();
    this.load();
  },

  _syncTabs() {
    document.querySelectorAll('#page-portfolio-progress .portfolio-tab').forEach((btn) => {
      btn.classList.toggle('active', btn.dataset.status === this.statusFilter);
    });
  },

  _renderStats() {
    const s = this.stats;
    const set = (id, v) => {
      const el = document.getElementById(id);
      if (el) el.textContent = v ?? '—';
    };
    set('ppStatOnProgress', s.on_progress ?? '—');
    set('ppStatCompleted', s.completed ?? '—');
    set('ppStatTotal', s.total ?? '—');
    const sub = document.getElementById('ppListCount');
    if (sub) sub.textContent = `顯示 ${this.items.length} 項`;
    const hint = document.getElementById('ppLastImport');
    if (hint) hint.textContent = PortfolioCommon.lastImportText(this.lastImport);
  },

  patchItem(item) {
    if (!item) return;
    const idx = this.items.findIndex((x) => x.id === item.id);
    if (idx >= 0) this.items[idx] = { ...this.items[idx], ...item };
  },

  async syncFromProjects() {
    showContentLoading('從工程項目補列…');
    try {
      const r = await api('POST', '/portfolio/sync-from-projects');
      toast(`已同步：新增 ${r.created} 項，合共 ${r.total} 項`, 'success');
      await this.load();
    } finally {
      hideContentLoading();
    }
  },

  render() {
    const body = document.getElementById('ppTableBody');
    if (!body) return;
    if (!this.items.length) {
      body.innerHTML = `<tr><td colspan="11"><div class="empty-state" style="padding:40px">沒有符合條件的項目</div></td></tr>`;
      return;
    }
    body.innerHTML = this.items.map((it) => `
      <tr>
        <td class="portfolio-sticky pp-sticky-0 td-mono">${PortfolioCommon.projectLink(it)}</td>
        <td class="portfolio-sticky pp-sticky-1">${PortfolioCommon.dash(it.description)}</td>
        <td>${PortfolioCommon.dash(it.client)}</td>
        <td>${PortfolioCommon.dash(it.pm)}</td>
        <td>${PortfolioCommon.dateCell(it.commencement_date)}</td>
        <td>${PortfolioCommon.dateCell(it.contract_completion_date)}</td>
        <td>${PortfolioCommon.dateCell(it.pc_date)}</td>
        <td>${PortfolioCommon.dateInput(it.id, it.expected_completion_date, 'expected_completion_date')}</td>
        <td>${PortfolioCommon.textInput(it.id, it.remark, 'portfolio_remark', '備註')}</td>
        <td class="td-amount">${fmt(it.contract_sum)}</td>
        <td>${PortfolioCommon.statusSelect(it.id, it.project_progress_status, 'project_progress_status')}</td>
      </tr>
    `).join('');
  },
};
