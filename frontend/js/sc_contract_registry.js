/* sc_contract_registry.js — 分判工程合約編號（MS/C）· 對照 Excel 2026 */
const ScContractRegistry = {
  rows: [],
  status: null,
  filters: null,
  _editNo: null,
  COLS: 10,
  _sortKey: localStorage.getItem('qs_scr_sort_key') || 'sub_contract_no',
  _sortDir: localStorage.getItem('qs_scr_sort_dir') || 'asc',
  _defaultYear: '2026',

  SCR_COLUMNS: [
    { id: 'ms', label: '合約編號' },
    { id: 'co', label: '外判公司' },
    { id: 'works', label: '工程項目' },
    { id: 'proj', label: '項目編號' },
    { id: 'person', label: '負責同事' },
    { id: 'amt', label: '分判合約合額' },
    { id: 'countersign', label: '會簽' },
    { id: 'partner', label: '伙伴' },
    { id: 'tender', label: '定標' },
    { id: 'act', label: '操作', locked: true },
  ],

  _esc(s) {
    return escHtml(String(s ?? ''));
  },

  _flagCell(v) {
    const s = (v || '').trim();
    if (!s) return '<span class="text-muted">—</span>';
    if (s === '✔' || s === '✓') return '<span class="scr-flag-yes">✔</span>';
    return this._esc(s);
  },

  _shortText(v, max = 48) {
    const s = (v || '').trim();
    if (!s) return '<span class="text-muted">—</span>';
    const esc = this._esc(s);
    if (s.length <= max) return esc;
    return `<span title="${esc}">${this._esc(s.slice(0, max))}…</span>`;
  },

  _formIds() {
    return [
      'scrMsNo', 'scrCompany', 'scrWorks', 'scrProjectCode',
      'scrPerson', 'scrAmount', 'scrSheet', 'scrCountersign', 'scrPartner',
      'scrTenderMinutes', 'scrFinalAccount', 'scrFinalAccountStatement', 'scrIso', 'scrRemark',
    ];
  },

  _clearForm() {
    this._formIds().forEach(id => {
      const el = document.getElementById(id);
      if (el) el.value = '';
    });
  },

  async _loadPersonSelect(selectedName) {
    await StaffRoster.load(true);
    const sel = document.getElementById('scrPerson');
    StaffRoster.fillPersonSelect(sel, { selectedName });
    const want = (selectedName || '').trim();
    if (want && sel && sel.value !== want) {
      const norm = (s) => (s || '').trim().toLowerCase();
      const has = [...sel.options].some(o => norm(o.value) === norm(want));
      if (!has) {
        sel.innerHTML += `<option value="${escHtml(want)}" selected>${escHtml(want)}（舊資料）</option>`;
      }
    }
  },

  _fillForm(r) {
    document.getElementById('scrMsNo').value = r.sub_contract_no || '';
    document.getElementById('scrCompany').value = r.company || '';
    document.getElementById('scrWorks').value = r.works || '';
    document.getElementById('scrProjectCode').value = r.project_code || '';
    document.getElementById('scrAmount').value = r.amount != null ? String(r.amount) : '';
    document.getElementById('scrSheet').value = r.sheet || '';
    document.getElementById('scrCountersign').value = r.countersign || '';
    document.getElementById('scrPartner').value = r.partner || '';
    document.getElementById('scrTenderMinutes').value = r.tender_minutes || '';
    document.getElementById('scrFinalAccount').value = r.final_account || '';
    document.getElementById('scrFinalAccountStatement').value = r.final_account_statement || '';
    document.getElementById('scrIso').value = r.iso_flag || '';
    document.getElementById('scrRemark').value = r.remark || '';
  },

  _readPayload() {
    return {
      sub_contract_no: document.getElementById('scrMsNo').value.trim(),
      company: document.getElementById('scrCompany').value.trim() || null,
      works: document.getElementById('scrWorks').value.trim() || null,
      project_code: document.getElementById('scrProjectCode').value.trim() || null,
      person_in_charge: document.getElementById('scrPerson').value.trim() || null,
      amount: parseFloat(document.getElementById('scrAmount').value) || 0,
      sheet: document.getElementById('scrSheet').value.trim() || null,
      countersign: document.getElementById('scrCountersign').value.trim() || null,
      partner: document.getElementById('scrPartner').value.trim() || null,
      tender_minutes: document.getElementById('scrTenderMinutes').value.trim() || null,
      final_account: document.getElementById('scrFinalAccount').value.trim() || null,
      final_account_statement: document.getElementById('scrFinalAccountStatement').value.trim() || null,
      iso_flag: document.getElementById('scrIso').value.trim() || null,
      remark: document.getElementById('scrRemark').value.trim() || null,
      source_file: 'UI',
    };
  },

  _fillSelect(id, values, labelAll) {
    const el = document.getElementById(id);
    if (!el) return;
    const cur = el.value;
    el.innerHTML = `<option value="">${labelAll}</option>` +
      (values || []).map(v => `<option value="${this._esc(v)}">${this._esc(v)}</option>`).join('');
    if (cur && (values || []).includes(cur)) el.value = cur;
  },

  _applyFilters(f) {
    this.filters = f || this.filters;
    if (!this.filters) return;
    this._fillSelect('scrYearFilter', this.filters.years, '全部年份');
    this._fillSelect('scrPersonFilter', this.filters.persons, '全部負責同事');
    this._fillSelect('scrCompanyFilter', this.filters.companies, '全部外判公司');
    this._syncYearSelect();
  },

  _readYearFilter() {
    const saved = localStorage.getItem('qs_scr_year_filter');
    if (saved !== null) return saved;
    return this._defaultYear;
  },

  _syncYearSelect() {
    const el = document.getElementById('scrYearFilter');
    if (!el) return;
    const target = this._readYearFilter();
    if (target && [...el.options].some(o => o.value === target)) {
      el.value = target;
    } else if (localStorage.getItem('qs_scr_year_filter') === '') {
      el.value = '';
    }
  },

  _saveYearFilter() {
    const el = document.getElementById('scrYearFilter');
    if (el) localStorage.setItem('qs_scr_year_filter', el.value || '');
  },

  async load() {
    const root = document.getElementById('scrContent');
    if (!root) return;
    root.innerHTML = `<tr><td colspan="${this.COLS}"><div class="empty-state" style="padding:40px"><div class="spinner"></div></div></td></tr>`;
    try {
      const qs = new URLSearchParams();
      const q = document.getElementById('scrSearch')?.value?.trim();
      const year = this._readYearFilter();
      const person = document.getElementById('scrPersonFilter')?.value;
      const company = document.getElementById('scrCompanyFilter')?.value;
      if (q) qs.set('q', q);
      if (year) qs.set('year', year);
      if (person) qs.set('person', person);
      if (company) qs.set('company', company);
      const suffix = qs.toString() ? `?${qs}` : '';
      const data = await api('GET', `/sc-contract-registry${suffix}`);
      this.rows = data?.rows || [];
      this.status = data?.status || null;
      this._applyFilters(data?.filters);
      this.render();
    } catch (e) {
      root.innerHTML = `<tr><td colspan="${this.COLS}"><div class="empty-state" style="padding:40px"><div class="empty-title">載入失敗</div></div></td></tr>`;
    }
  },

  sortBy(key) {
    if (this._sortKey === key) {
      this._sortDir = this._sortDir === 'asc' ? 'desc' : 'asc';
    } else {
      this._sortKey = key;
      this._sortDir = 'asc';
    }
    localStorage.setItem('qs_scr_sort_key', this._sortKey);
    localStorage.setItem('qs_scr_sort_dir', this._sortDir);
    this.render();
  },

  _sortValue(row, key) {
    switch (key) {
      case 'sub_contract_no':
        return (row.sub_contract_no || '').toLowerCase();
      case 'company':
        return (row.company || '').toLowerCase();
      case 'project_code':
        return (row.project_code || '').toLowerCase();
      case 'person': {
        const p = row.person_in_charge || row.person_code || '';
        return String(p).toLowerCase();
      }
      default:
        return '';
    }
  },

  _sortIsEmpty(row, key) {
    return !this._sortValue(row, key);
  },

  _sortedRows() {
    const rows = [...(this.rows || [])];
    if (!this._sortKey || !rows.length) return rows;
    const key = this._sortKey;
    const dir = this._sortDir === 'asc' ? 1 : -1;
    rows.sort((a, b) => {
      const aEmpty = this._sortIsEmpty(a, key);
      const bEmpty = this._sortIsEmpty(b, key);
      if (aEmpty && bEmpty) return 0;
      if (aEmpty) return 1;
      if (bEmpty) return -1;
      const va = this._sortValue(a, key);
      const vb = this._sortValue(b, key);
      return String(va).localeCompare(String(vb), 'zh-Hant') * dir;
    });
    return rows;
  },

  _updateSortHeaders() {
    document.querySelectorAll('#scrTableHead .th-sortable').forEach(th => {
      th.classList.remove('sort-asc', 'sort-desc');
      const icon = th.querySelector('.sort-icon');
      const key = th.dataset.sort;
      if (key === this._sortKey) {
        th.classList.add(this._sortDir === 'asc' ? 'sort-asc' : 'sort-desc');
        if (icon) icon.textContent = this._sortDir === 'asc' ? '↑' : '↓';
      } else if (icon) {
        icon.textContent = '↕';
      }
    });
  },

  render() {
    if (!this._visibleCols) this._initColPrefs();
    const root = document.getElementById('scrContent');
    if (!root) return;
    const colSpan = this._visibleColCount();
    const st = this.status || {};
    const last = st.last_import;
    const imported = last?.imported_at
      ? `上次同步 ${String(last.imported_at).slice(0, 16)}`
      : '尚未同步';
    const statEl = document.getElementById('scrStatMeta');
    if (statEl) {
      statEl.textContent = `資料庫 ${st.row_count ?? '—'} 筆 · ${imported}`;
    }
    const countEl = document.getElementById('scrListCount');
    if (countEl) countEl.textContent = `顯示 ${this.rows.length} 筆`;

    if (!this.rows.length) {
      root.innerHTML = `<tr><td colspan="${colSpan}"><div class="empty-state" style="padding:48px"><div class="empty-icon">📋</div><div class="empty-title">尚無記錄</div><div class="empty-sub">可新增或從 Ref Excel 同步</div></div></td></tr>`;
      this._updateSortHeaders();
      this.applyColVisibility();
      return;
    }

    const rows = this._sortedRows();
    root.innerHTML = rows.map(r => {
      const noArg = this._esc(r.sub_contract_no).replace(/'/g, "\\'");
      const person = r.person_in_charge || '';
      const pc = (r.person_code || '').trim();
      const pcValid = pc && /^[a-z]{2,4}$/i.test(pc);
      const personHint = pcValid && person && !person.toLowerCase().includes(pc.toLowerCase())
        ? ` (${pc})` : (pcValid && !person ? pc : '');
      return `<tr>
        <td class="td-mono scr-col-ms" data-col="ms"><code>${this._esc(r.sub_contract_no)}</code></td>
        <td class="scr-col-co" data-col="co"><div class="cell-clip" title="${this._esc(r.company || '')}">${this._esc(r.company || '—')}</div></td>
        <td class="td-muted scr-col-works" data-col="works"><div class="cell-ellipsis" title="${this._esc(r.works || '')}">${this._esc(r.works || '—')}</div></td>
        <td class="td-mono scr-col-proj" data-col="proj"><div class="cell-clip" title="${this._esc(r.project_code || '')}">${this._esc(r.project_code || '—')}</div></td>
        <td class="scr-col-person" data-col="person"><div class="cell-clip" title="${this._esc(person + personHint)}">${this._esc(person || personHint || '—')}${person && personHint ? `<span class="td-muted">${this._esc(personHint)}</span>` : ''}</div></td>
        <td class="td-amount scr-col-amt" data-col="amt">${fmt(r.amount)}</td>
        <td class="scr-col-flag" data-col="countersign">${this._flagCell(r.countersign)}</td>
        <td class="scr-col-flag" data-col="partner">${this._flagCell(r.partner)}</td>
        <td class="scr-col-flag" data-col="tender">${this._flagCell(r.tender_minutes)}</td>
        <td class="scr-col-actions" data-col="act">
          <div class="scr-row-actions" onclick="event.stopPropagation()">
            <button type="button" class="btn btn-secondary btn-sm btn-icon" title="編輯" onclick="ScContractRegistry.openEdit('${noArg}')">✏️</button>
            <button type="button" class="btn btn-danger btn-sm btn-icon" title="刪除" onclick="ScContractRegistry.remove('${noArg}')">🗑️</button>
          </div>
        </td>
      </tr>`;
    }).join('');
    this._updateSortHeaders();
    this.applyColVisibility();
  },

  search() {
    this._saveYearFilter();
    this.load();
  },

  async syncFromRef() {
    showLoading('正在同步 Ref Excel…');
    try {
      const r = await api('POST', '/sc-contract-registry/sync');
      toast(`已同步 ${r.rows_read || 0} 筆（新增 ${r.rows_new || 0} · 更新 ${r.rows_updated || 0}）`, 'success');
      await this.load();
    } catch (e) {
      toast(e.message || '同步失敗', 'error');
    } finally {
      hideLoading();
    }
  },

  async openAdd() {
    this._editNo = null;
    document.getElementById('scrModalTitle').textContent = '新增分判合約編號';
    this._clearForm();
    await this._loadPersonSelect('');
    document.getElementById('scrMsNo').readOnly = false;
    document.getElementById('scrModal').classList.add('open');
  },

  async openEdit(subContractNo) {
    const r = this.rows.find(x => x.sub_contract_no === subContractNo);
    if (!r) return;
    this._editNo = subContractNo;
    document.getElementById('scrModalTitle').textContent = `編輯 ${subContractNo}`;
    this._fillForm(r);
    await this._loadPersonSelect(r.person_in_charge || '');
    document.getElementById('scrMsNo').readOnly = true;
    document.getElementById('scrModal').classList.add('open');
  },

  closeModal() {
    document.getElementById('scrModal')?.classList.remove('open');
    this._editNo = null;
  },

  async saveModal() {
    const payload = this._readPayload();
    if (!payload.sub_contract_no) {
      toast('請填寫合約編號', 'warning');
      return;
    }
    try {
      if (this._editNo) {
        await api('PUT', `/sc-contract-registry/${encodeURIComponent(this._editNo)}`, payload);
        toast('已更新', 'success');
      } else {
        await api('POST', '/sc-contract-registry', payload);
        toast('已新增', 'success');
      }
      this.closeModal();
      await this.load();
    } catch (e) {}
  },

  async remove(subContractNo) {
    if (!confirm(`確認刪除 ${subContractNo}？`)) return;
    try {
      await api('DELETE', `/sc-contract-registry/${encodeURIComponent(subContractNo)}`);
      toast('已刪除', 'success');
      await this.load();
    } catch (e) {}
  },

  fillProjectFromCurrent() {
    const p = App.currentProject;
    if (!p) {
      toast('請先在左上角選擇項目', 'warning');
      return;
    }
    document.getElementById('scrProjectCode').value = p.project_code || p.mp_contract_code || '';
  },
};

ColPicker.attach(ScContractRegistry, {
  columnsKey: 'SCR_COLUMNS',
  storageKey: 'qs_scr_visible_cols',
  tableSelector: '.scr-registry-table',
  wrapId: 'scrColPickerWrap',
  panelId: 'scrColPickerPanel',
  hostName: 'ScContractRegistry',
});
