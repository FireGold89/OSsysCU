/* portfolio_fac.js — N 項目結算總表（P3：分判矩陣 + drawer） */
const PortfolioFac = {
  items: [],
  stats: {},
  lastImport: null,
  statusFilter: 'On Progress',
  quickFilter: '',
  pmFilter: '',
  q: '',
  showMatrix: false,
  drawerId: null,
  _projectScCache: {},
  _matrixSlotNos: [],

  MATRIX_SLOTS: 15,
  MATRIX_STORAGE_KEY: 'qs_pf_show_matrix',

  COLUMNS: [
    { id: 'n_code', label: 'N Code', locked: true },
    { id: 'project_code', label: 'Project Code', locked: true },
    { id: 'description', label: '項目描述', locked: true },
    { id: 'pm', label: 'PM' },
    { id: 'commencement_date', label: '開工' },
    { id: 'contract_completion_date', label: '合約完工' },
    { id: 'pc_date', label: 'PC Date' },
    { id: 'pc_cert_done', label: 'PC Cert' },
    { id: 'dlp_commencement_date', label: 'DLP 開始' },
    { id: 'dlp_days', label: 'DLP (日)' },
    { id: 'dlp_expiry_date', label: 'DLP 到期' },
    { id: 'retention_to_release', label: 'Retention' },
    { id: 'defect_cert_done', label: 'Defect Cert' },
    { id: 'expected_completion_date', label: '預計完工' },
    { id: 'portfolio_remark', label: 'Remark' },
    { id: 'contract_sum', label: 'Contract Sum' },
    { id: 'project_progress_status', label: '項目狀態' },
    { id: 'client', label: 'Client' },
    { id: 'client_fac_status', label: 'Client FA' },
  ],

  COMPACT_COL_IDS: [
    'n_code', 'project_code', 'description', 'pm',
    'pc_date', 'pc_cert_done', 'expected_completion_date',
    'portfolio_remark', 'project_progress_status', 'client', 'client_fac_status',
  ],

  /** 開分判矩陣時：左欄精簡，右側顯示判1–判15 */
  MATRIX_LEFT_COL_IDS: [
    'n_code', 'project_code', 'description', 'client', 'client_fac_status',
  ],

  _colsBeforeMatrix: null,

  _initMatrixPref() {
    this.showMatrix = localStorage.getItem(this.MATRIX_STORAGE_KEY) === '1';
  },

  _saveMatrixPref() {
    try {
      localStorage.setItem(this.MATRIX_STORAGE_KEY, this.showMatrix ? '1' : '0');
    } catch (e) {}
  },

  _colSpan() {
    const matrixCols = this.showMatrix ? this._matrixSlotNos.length * 2 : 0;
    return this.COLUMNS.length + matrixCols;
  },

  _activeMatrixSlots(items) {
    const used = new Set();
    (items || []).forEach((it) => {
      (it.subcontractors || []).forEach((sc) => {
        if (PortfolioCommon.slotHasData(sc)) used.add(Number(sc.slot));
      });
    });
    return [...used].sort((a, b) => a - b);
  },

  _filledSlotsForItem(it) {
    const out = [];
    for (let n = 1; n <= this.MATRIX_SLOTS; n += 1) {
      const sc = PortfolioCommon.slotAt(it, n);
      if (PortfolioCommon.slotHasData(sc)) out.push({ n, sc });
    }
    return out;
  },

  _nextFreeSlot(it) {
    for (let n = 1; n <= this.MATRIX_SLOTS; n += 1) {
      if (!PortfolioCommon.slotHasData(PortfolioCommon.slotAt(it, n))) return n;
    }
    return null;
  },

  async load() {
    this._initMatrixPref();
    const qEl = document.getElementById('pfSearch');
    this.q = (qEl?.value || '').trim();
    this.pmFilter = document.getElementById('pfPmFilter')?.value || '';
    showContentLoading('載入結算總表…');
    try {
      const data = await api('GET', `/portfolio/fac${PortfolioCommon.queryString(this.statusFilter, this.pmFilter, this.q)}`);
      this.items = data?.items || [];
      this.stats = data?.stats || {};
      this.lastImport = data?.last_import || null;
      await this._prefetchScLists(this.items);
      PortfolioCommon.fillPmSelect('pfPmFilter', data?.pms, this.pmFilter);
      if (!this._visibleCols) this._initColPrefs();
      if (this.showMatrix) this._applyMatrixCols();
      this._syncTabs();
      this._syncQuick();
      this._syncMatrixBtn();
      this._renderStats();
      this.render();
      if (this.showMatrix) this._scrollToMatrix();
      if (this.drawerId) {
        const cur = this.items.find((x) => x.id === this.drawerId);
        if (cur) this.renderDrawer(cur);
        else this.closeDrawer();
      }
    } catch (e) {
      const body = document.getElementById('pfTableBody');
      if (body) body.innerHTML = `<tr><td colspan="${this._colSpan()}"><div class="empty-state" style="padding:40px">載入失敗</div></td></tr>`;
    } finally {
      hideContentLoading();
    }
  },

  setStatus(status) {
    this.statusFilter = status;
    this.quickFilter = '';
    this._syncTabs();
    this.load();
  },

  setQuick(key) {
    const next = this.quickFilter === key ? '' : key;
    this.quickFilter = next;
    if (next && this.statusFilter !== 'all') {
      this.statusFilter = 'all';
      this.load();
      return;
    }
    this._syncQuick();
    this._renderStats();
    this.render();
  },

  setDensity(mode) {
    if (!this._visibleCols) this._initColPrefs();
    this._visibleCols = mode === 'full'
      ? this.COLUMNS.map((c) => c.id)
      : [...this.COMPACT_COL_IDS];
    this._saveColPrefs();
    this.applyColVisibility();
    this._renderColPicker();
  },

  toggleMatrix() {
    this.showMatrix = !this.showMatrix;
    this._saveMatrixPref();
    if (this.showMatrix) {
      if (!this._colsBeforeMatrix && this._visibleCols) {
        this._colsBeforeMatrix = [...this._visibleCols];
      }
      this._applyMatrixCols();
      this._syncMatrixBtn();
      this._prefetchScLists(this.items).then(() => {
        this.render();
        this._scrollToMatrix();
      });
      return;
    }
    if (this._colsBeforeMatrix) {
      this._visibleCols = [...this._colsBeforeMatrix];
      this._colsBeforeMatrix = null;
      this._saveColPrefs();
    }
    this._syncMatrixBtn();
    this.render();
    this._updateMatrixHint();
  },

  _applyMatrixCols() {
    if (!this._visibleCols) this._initColPrefs();
    this._visibleCols = [...this.MATRIX_LEFT_COL_IDS];
    this._saveColPrefs();
  },

  _scrollToMatrix() {
    requestAnimationFrame(() => {
      const wrap = document.querySelector('#page-portfolio-fac .portfolio-table-wrap');
      const first = wrap?.querySelector('[data-matrix].pf-sc-col-first');
      if (wrap && first) {
        const stickyW = (wrap.querySelector('.pf-sticky-2')?.offsetLeft || 0)
          + (wrap.querySelector('.pf-sticky-2')?.offsetWidth || 0);
        wrap.scrollLeft = Math.max(0, first.offsetLeft - stickyW - 12);
      }
      this._updateMatrixHint();
    });
  },

  _updateMatrixHint() {
    const el = document.getElementById('pfMatrixHint');
    if (!el) return;
    if (!this.showMatrix) {
      el.hidden = true;
      return;
    }
    el.hidden = false;
    const n = this._matrixSlotNos.length;
    el.textContent = n
      ? `分判矩陣 · 顯示 ${n} 組有資料槽位`
      : '分判矩陣 · 目前篩選結果尚無分判資料（點列於 drawer 新增）';
  },

  _syncMatrixBtn() {
    document.getElementById('pfMatrixToggle')?.classList.toggle('active', this.showMatrix);
  },

  _syncTabs() {
    document.querySelectorAll('#page-portfolio-fac .portfolio-tab[data-status]').forEach((btn) => {
      btn.classList.toggle('active', btn.dataset.status === this.statusFilter);
    });
  },

  _syncQuick() {
    document.querySelectorAll('#page-portfolio-fac [data-quick]').forEach((btn) => {
      btn.classList.toggle('active', btn.dataset.quick === this.quickFilter);
    });
    document.querySelectorAll('#pfStats .stat-card[data-kpi]').forEach((card) => {
      const kpi = card.dataset.kpi;
      const on = (kpi === 'on-progress' && this.statusFilter === 'On Progress' && !this.quickFilter)
        || (kpi === 'completed' && this.statusFilter === 'Completed' && !this.quickFilter)
        || (kpi === this.quickFilter);
      card.classList.toggle('is-selected', on);
    });
  },

  _isCompact() {
    if (!this._visibleCols) return true;
    const vis = [...this._visibleCols].sort().join('|');
    const compact = [...this.COMPACT_COL_IDS].sort().join('|');
    return vis === compact;
  },

  _syncDensity() {
    const compact = this._isCompact();
    const full = this._visibleCols && this._visibleCols.length === this.COLUMNS.length;
    document.getElementById('pfDensityCompact')?.classList.toggle('active', compact);
    document.getElementById('pfDensityFull')?.classList.toggle('active', !!full);
  },

  _filteredItems() {
    const key = this.quickFilter;
    if (!key) return this.items;
    return this.items.filter((it) => {
      if (key === 'fa-pending') return (it.client_fac_status || '') !== 'Completed';
      if (key === 'dlp-soon') {
        const d = PortfolioCommon.daysUntil(it.dlp_expiry_date);
        return d != null && d <= 90;
      }
      if (key === 'sc-pending') return PortfolioCommon.hasScPending(it);
      return true;
    });
  },

  _renderStats() {
    const s = this.stats;
    const set = (id, v) => {
      const el = document.getElementById(id);
      if (el) el.textContent = v ?? '—';
    };
    set('pfStatOnProgress', s.on_progress ?? '—');
    set('pfStatCompleted', s.completed ?? '—');
    set('pfStatFaPending', s.client_fa_pending ?? '—');
    set('pfStatScPending', s.sc_fac_pending ?? '—');
    const shown = this._filteredItems().length;
    const sub = document.getElementById('pfListCount');
    if (sub) {
      sub.textContent = shown === this.items.length
        ? `顯示 ${shown} 項`
        : `顯示 ${shown} / ${this.items.length} 項`;
    }
    const hint = document.getElementById('pfLastImport');
    if (hint) hint.textContent = PortfolioCommon.lastImportText(this.lastImport);
  },

  patchItem(item) {
    if (!item) return;
    const idx = this.items.findIndex((x) => x.id === item.id);
    if (idx >= 0) {
      const prev = this.items[idx];
      this.items[idx] = { ...prev, ...item, subcontractors: item.subcontractors ?? prev.subcontractors };
    }
  },

  async syncFromProjects() {
    showContentLoading('從系統同步…');
    try {
      const r = await api('POST', '/portfolio/sync-from-projects');
      this._projectScCache = {};
      const parts = [
        `新增 ${r.created || 0} 列`,
        `更新 ${r.portfolio_updated || 0} 項`,
      ];
      if (r.sc_slots_filled) parts.push(`填分判槽 ${r.sc_slots_filled}`);
      if (r.sc_slots_linked) parts.push(`連結分判 ${r.sc_slots_linked}`);
      if (r.retention_synced) parts.push(`Retention ${r.retention_synced}`);
      if (r.dlp_filled) parts.push(`DLP ${r.dlp_filled}`);
      let msg = `同步完成：${parts.join(' · ')}（合共 ${r.total} 項）`;
      if (r.projects_no_system_sc) {
        msg += ` · ${r.projects_no_system_sc} 項尚無系統分判，空槽無法自動填`;
      }
      toast(msg, 'success');
      await this.load();
    } finally {
      hideContentLoading();
    }
  },

  _rowClass(it) {
    const d = PortfolioCommon.daysUntil(it.dlp_expiry_date);
    if (d == null) return '';
    if (d < 0) return ' portfolio-row-overdue';
    if (d <= 90) return ' portfolio-row-soon';
    return '';
  },

  _renderMatrixHead() {
    const row = document.getElementById('pfTableHeadRow');
    if (!row) return;
    row.querySelectorAll('[data-matrix]').forEach((el) => el.remove());
    if (!this.showMatrix || !this._matrixSlotNos.length) return;
    this._matrixSlotNos.forEach((n, idx) => {
      const firstCls = idx === 0 ? ' pf-sc-col-first' : '';
      row.insertAdjacentHTML('beforeend', `
        <th class="pf-sc-col${firstCls}" data-matrix="1" data-slot="${n}">判${n}</th>
        <th class="pf-sc-col pf-sc-status-col" data-matrix="1" data-slot="${n}">狀${n}</th>
      `);
    });
  },

  _matrixCells(it) {
    if (!this.showMatrix || !this._matrixSlotNos.length) return '';
    let html = '';
    this._matrixSlotNos.forEach((n, idx) => {
      const sc = PortfolioCommon.slotAt(it, n);
      const firstCls = idx === 0 ? ' pf-sc-col-first' : '';
      if (!PortfolioCommon.slotHasData(sc)) {
        html += `<td class="pf-sc-col pf-sc-empty${firstCls}" data-matrix="1" data-slot="${n}"><span class="td-muted">—</span></td>`;
        html += `<td class="pf-sc-col pf-sc-status-col pf-sc-empty" data-matrix="1" data-slot="${n}"><span class="td-muted">—</span></td>`;
        return;
      }
      html += `<td class="pf-sc-col${firstCls}" data-matrix="1" data-slot="${n}">${PortfolioCommon.scNameInput(it.id, n, sc, it.project_id)}</td>`;
      html += `<td class="pf-sc-col pf-sc-status-col" data-matrix="1" data-slot="${n}">${PortfolioCommon.scFacSelect(it.id, n, sc.fac_status)}</td>`;
    });
    return html;
  },

  onRowClick(ev, portfolioId) {
    if (ev.target.closest('input,select,button,a,label,.pf-sc-link')) return;
    this.openDrawer(portfolioId);
  },

  async openDrawer(portfolioId) {
    const it = this.items.find((x) => x.id === portfolioId);
    if (!it) return;
    this.drawerId = portfolioId;
    document.getElementById('pfDrawerBackdrop')?.removeAttribute('hidden');
    const drawer = document.getElementById('pfDrawer');
    if (drawer) {
      drawer.classList.add('open');
      drawer.setAttribute('aria-hidden', 'false');
    }
    if (it.project_id) await this._loadProjectSc(it.project_id);
    await this.renderDrawer(it);
  },

  closeDrawer() {
    this.drawerId = null;
    document.getElementById('pfDrawerBackdrop')?.setAttribute('hidden', '');
    const drawer = document.getElementById('pfDrawer');
    if (drawer) {
      drawer.classList.remove('open');
      drawer.setAttribute('aria-hidden', 'true');
    }
  },

  async _prefetchScLists(items) {
    const ids = [...new Set((items || []).map((it) => it.project_id).filter(Boolean))];
    await Promise.all(ids.map((id) => this._loadProjectSc(id)));
  },

  async _loadProjectSc(projectId) {
    if (!projectId) return [];
    if (this._projectScCache[projectId]) return this._projectScCache[projectId];
    try {
      const rows = await api('GET', `/projects/${projectId}/subcontractors`) || [];
      this._projectScCache[projectId] = rows;
      return rows;
    } catch (e) {
      return [];
    }
  },

  async renderDrawer(it) {
    const body = document.getElementById('pfDrawerBody');
    const title = document.getElementById('pfDrawerTitle');
    const sub = document.getElementById('pfDrawerSub');
    if (!body || !it) return;
    if (title) title.textContent = it.n_code ? `${it.n_code} · ${it.project_code || '—'}` : (it.project_code || '—');
    if (sub) sub.textContent = it.description || '—';
    const scRows = await this._loadProjectSc(it.project_id);
    const slotRows = this._filledSlotsForItem(it);
    const nextSlot = this._nextFreeSlot(it);
    const sysScHtml = scRows.length
      ? scRows.map((sc) => {
        const name = PortfolioCommon.scCompanyName(sc) || sc.sc_no || '—';
        return `<li><code>${escHtml(sc.sc_no || '')}</code> ${escHtml(name)}
          <button type="button" class="btn-link btn-sm" onclick="PortfolioCommon.openScFac(${it.project_id},${sc.id})">分判 FAC</button></li>`;
      }).join('')
      : '<li class="td-muted">此項目尚無系統分判</li>';
    const slotTableRows = slotRows.map(({ n, sc }) => `<tr>
      <td class="td-muted">${n}</td>
      <td>${PortfolioCommon.scNameInput(it.id, n, sc, it.project_id)}</td>
      <td>${PortfolioCommon.scFacSelect(it.id, n, sc.fac_status)}</td>
      <td>${sc.subcontractor_id ? `<button type="button" class="btn-link btn-sm" onclick="PortfolioCommon.openScFac(${it.project_id},${sc.subcontractor_id})">🔗</button>` : ''}</td>
    </tr>`).join('');
    const addRow = nextSlot
      ? `<tr class="pf-drawer-add-row">
          <td class="td-muted">${nextSlot}</td>
          <td>${PortfolioCommon.scNameInput(it.id, nextSlot, PortfolioCommon.slotAt(it, nextSlot), it.project_id)}</td>
          <td>${PortfolioCommon.scFacSelect(it.id, nextSlot, '')}</td>
          <td></td>
        </tr>`
      : '';
    body.innerHTML = `
      <div class="pf-drawer-actions">
        <button type="button" class="btn btn-secondary btn-sm" onclick="PortfolioCommon.openProjectPage(${it.project_id}, 'dashboard')">項目概覽</button>
        <button type="button" class="btn btn-secondary btn-sm" onclick="PortfolioCommon.openProjectPage(${it.project_id}, 'main-con-fac')">主合約 FAC</button>
        <button type="button" class="btn btn-secondary btn-sm" onclick="PortfolioCommon.openScFac(${it.project_id})">分判 FAC 總表</button>
      </div>
      <div class="pf-drawer-meta">
        <div><span class="pf-drawer-label">PM</span>${PortfolioCommon.dash(it.pm)}</div>
        <div><span class="pf-drawer-label">Client</span>${PortfolioCommon.dash(it.client)}</div>
        <div><span class="pf-drawer-label">開工</span>${PortfolioCommon.dash(it.commencement_date)}</div>
        <div><span class="pf-drawer-label">合約完工</span>${PortfolioCommon.dash(it.contract_completion_date)}</div>
        <div><span class="pf-drawer-label">PC Date</span>${PortfolioCommon.dash(it.pc_date)}</div>
        <div><span class="pf-drawer-label">DLP 到期</span>${PortfolioCommon.dash(it.dlp_expiry_date)}</div>
        <div><span class="pf-drawer-label">Contract Sum</span>${fmt(it.contract_sum)}</div>
        <div><span class="pf-drawer-label">Client FA</span><span class="${PortfolioCommon.statusClass(it.client_fac_status)}">${PortfolioCommon.clientFaLabel(it.client_fac_status)}</span></div>
      </div>
      <h4 class="pf-drawer-section">分判 FAC（${slotRows.length}）</h4>
      <div class="table-wrap pf-drawer-table-wrap">
        <table class="portfolio-table pf-drawer-sc-table">
          <thead><tr><th>#</th><th>分判商</th><th>FAC 狀態</th><th></th></tr></thead>
          <tbody>
            ${slotTableRows || '<tr><td colspan="4" class="td-muted" style="padding:12px">尚無分判槽位</td></tr>'}
            ${addRow}
          </tbody>
        </table>
      </div>
      ${nextSlot ? '<p class="form-hint">最底列為下一空槽，填寫後自動儲存。</p>' : ''}
      <h4 class="pf-drawer-section">系統分判（${scRows.length}）</h4>
      <ul class="pf-drawer-sc-list">${sysScHtml}</ul>
    `;
  },

  render() {
    const body = document.getElementById('pfTableBody');
    const table = document.querySelector('#page-portfolio-fac .portfolio-fac-table');
    if (!body) return;
    const rows = this._filteredItems();
    this._matrixSlotNos = this.showMatrix ? this._activeMatrixSlots(rows) : [];
    const span = this._colSpan();
    this._renderMatrixHead();
    if (table) {
      table.classList.toggle('has-matrix', this.showMatrix && this._matrixSlotNos.length > 0);
    }
    if (!rows.length) {
      body.innerHTML = `<tr><td colspan="${span}"><div class="empty-state" style="padding:40px">沒有符合條件的項目</div></td></tr>`;
      this.applyColVisibility();
      this._applyMatrixVisibility();
      if (this.showMatrix) this._updateMatrixHint();
      return;
    }
    body.innerHTML = rows.map((it) => `
      <tr class="pf-data-row${this._rowClass(it)}" onclick="PortfolioFac.onRowClick(event, ${it.id})">
        <td class="portfolio-sticky pf-sticky-0" data-col="n_code">${PortfolioCommon.textInput(it.id, it.n_code, 'n_code', 'N')}</td>
        <td class="portfolio-sticky pf-sticky-1 td-mono" data-col="project_code">${PortfolioCommon.projectLink(it)}</td>
        <td class="portfolio-sticky pf-sticky-2" data-col="description">${PortfolioCommon.descCell(it.description)}</td>
        <td data-col="pm">${PortfolioCommon.dash(it.pm)}</td>
        <td data-col="commencement_date">${PortfolioCommon.dateCell(it.commencement_date)}</td>
        <td data-col="contract_completion_date">${PortfolioCommon.dateCell(it.contract_completion_date)}</td>
        <td data-col="pc_date">${PortfolioCommon.dateCell(it.pc_date)}</td>
        <td class="td-center" data-col="pc_cert_done">${PortfolioCommon.checkInput(it.id, it.pc_cert_done, 'pc_cert_done')}</td>
        <td data-col="dlp_commencement_date">${PortfolioCommon.dateInput(it.id, it.dlp_commencement_date, 'dlp_commencement_date')}</td>
        <td data-col="dlp_days">${PortfolioCommon.numberInput(it.id, it.dlp_days, 'dlp_days')}</td>
        <td data-col="dlp_expiry_date">${PortfolioCommon.dlpExpiryCell(it.id, it.dlp_expiry_date)}</td>
        <td class="td-amount" data-col="retention_to_release">${it.retention_to_release != null ? fmt(it.retention_to_release) : '<span class="td-muted">—</span>'}</td>
        <td class="td-center" data-col="defect_cert_done">${PortfolioCommon.checkInput(it.id, it.defect_cert_done, 'defect_cert_done')}</td>
        <td data-col="expected_completion_date">${PortfolioCommon.dateInput(it.id, it.expected_completion_date, 'expected_completion_date')}</td>
        <td data-col="portfolio_remark">${PortfolioCommon.textInput(it.id, it.remark, 'portfolio_remark', '備註')}</td>
        <td class="td-amount" data-col="contract_sum">${fmt(it.contract_sum)}</td>
        <td data-col="project_progress_status">${PortfolioCommon.statusSelect(it.id, it.project_progress_status, 'project_progress_status')}</td>
        <td data-col="client">${PortfolioCommon.clientCell(it.client)}</td>
        <td data-col="client_fac_status">${PortfolioCommon.clientFaSelect(it.id, it.client_fac_status)}</td>
        ${this._matrixCells(it)}
      </tr>
    `).join('');
    this.applyColVisibility();
    this._applyMatrixVisibility();
    if (this.showMatrix) this._updateMatrixHint();
  },

  _applyMatrixVisibility() {
    const show = this.showMatrix;
    document.querySelectorAll('#page-portfolio-fac [data-matrix]').forEach((el) => {
      el.classList.toggle('col-hidden', !show);
    });
  },
};

ColPicker.attach(PortfolioFac, {
  columnsKey: 'COLUMNS',
  storageKey: 'qs_pf_visible_cols',
  tableSelector: '#page-portfolio-fac .portfolio-fac-table',
  wrapId: 'pfColPickerWrap',
  panelId: 'pfColPickerPanel',
  hostName: 'PortfolioFac',
  defaultVisible: PortfolioFac.COMPACT_COL_IDS,
});

(function wrapPfColApply() {
  const orig = PortfolioFac.applyColVisibility;
  PortfolioFac.applyColVisibility = function applyColVisibilityWrapped() {
    orig.call(this);
    const table = document.querySelector('#page-portfolio-fac .portfolio-fac-table');
    if (table) table.classList.toggle('is-compact', this._isCompact());
    this._syncDensity();
    this._applyMatrixVisibility();
  };
}());

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && PortfolioFac.drawerId) PortfolioFac.closeDrawer();
});
