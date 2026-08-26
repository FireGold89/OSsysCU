/* master_trade.js — Master List 工作範疇 + 工程類別分類 */
const MasterTradeCats = {
  EXTRA_GROUP: '資料補充',
  scopeOptions: [],
  overrideOptions: [],
  scopeGroups: [],
  scopeByName: {},
  scopeSet: new Set(),
  overrideSet: new Set(),
  _loaded: false,
  _manageTab: 'scope',
  _overrideExpanded: false,

  _inferDefaultOverride() {
    const group = document.getElementById('masterEditTradeScopeGroup')?.value.trim() || '';
    if (group && group !== '未分類' && this.overrideSet.has(group)) return group;
    const scope = document.getElementById('masterEditTradeScope')?.value.trim() || '';
    const row = scope ? this.scopeByName[scope] : null;
    const g = (row?.group_name || '').trim();
    if (g && g !== '未分類' && this.overrideSet.has(g)) return g;
    return '';
  },

  _overrideDiffersFromDefault() {
    const override = document.getElementById('masterEditTradeOverride')?.value.trim() || '';
    const def = this._inferDefaultOverride();
    return override !== def;
  },

  refreshOverrideUi() {
    const collapsed = document.getElementById('masterEditEngCatCollapsed');
    const expanded = document.getElementById('masterEditEngCatExpanded');
    const summary = document.getElementById('masterEditEngCatSummary');
    if (!collapsed || !expanded || !summary) return;

    const def = this._inferDefaultOverride();
    const override = document.getElementById('masterEditTradeOverride')?.value.trim() || '';
    const showExpanded = this._overrideExpanded || this._overrideDiffersFromDefault();

    if (showExpanded) {
      collapsed.hidden = true;
      expanded.hidden = false;
      if (!override && def) {
        const sel = document.getElementById('masterEditTradeOverride');
        if (sel) sel.value = def;
      }
    } else {
      collapsed.hidden = false;
      expanded.hidden = true;
      const sel = document.getElementById('masterEditTradeOverride');
      if (sel && def) sel.value = def;
      if (def) {
        summary.innerHTML = `同大類別：<strong>${escHtml(def)}</strong>`;
      } else {
        summary.textContent = '同大類別：請先選大類別或細項';
      }
    }
  },

  expandOverride() {
    this._overrideExpanded = true;
    this.refreshOverrideUi();
    document.getElementById('masterEditTradeOverride')?.focus();
  },

  collapseOverride() {
    this._overrideExpanded = false;
    const def = this._inferDefaultOverride();
    const sel = document.getElementById('masterEditTradeOverride');
    if (sel) sel.value = def;
    this.refreshOverrideUi();
  },

  onOverrideChange() {
    if (!this._overrideDiffersFromDefault()) {
      this._overrideExpanded = false;
    }
    this.refreshOverrideUi();
  },

  async ensureLoaded(force = false) {
    if (this._loaded && !force) return;
    const data = await api('GET', '/master/trade-categories');
    this.scopeOptions = data?.scope_options || [];
    this.overrideOptions = data?.override_options || [];
    this.scopeGroups = data?.scope_groups || [];
    this.scopeByName = {};
    this.scopeOptions.forEach(r => {
      this.scopeByName[(r.name_zh || '').trim()] = r;
    });
    this.scopeSet = new Set(Object.keys(this.scopeByName));
    this.overrideSet = new Set(this.overrideOptions.map(r => (r.name_zh || '').trim()).filter(Boolean));
    this._loaded = true;
    this._renderScopeGroupSelect();
    this._renderScopeDatalist();
    this._renderOverrideSelect();
    this.refreshOverrideUi();
  },

  _scopedOptions(groupFilter) {
    const g = (groupFilter ?? document.getElementById('masterEditTradeScopeGroup')?.value ?? '').trim();
    if (!g) return this.scopeOptions;
    return this.scopeOptions.filter(r => ((r.group_name || '').trim() || '未分類') === g);
  },

  _renderScopeGroupSelect(selected) {
    const sel = document.getElementById('masterEditTradeScopeGroup');
    if (!sel) return;
    const want = (selected ?? sel.value ?? '').trim();
    let html = '<option value="">— 全部大類別 —</option>';
    (this.scopeGroups || []).forEach(g => {
      const name = (g.group_name || '').trim();
      if (!name) return;
      const n = (g.children || []).length;
      html += `<option value="${escHtml(name)}"${want === name ? ' selected' : ''}>${escHtml(name)}（${n} 項）</option>`;
    });
    sel.innerHTML = html;
  },

  _renderScopeDatalist(groupFilter) {
    const dl = document.getElementById('masterTradeScopeList');
    if (!dl) return;
    const group = (groupFilter ?? document.getElementById('masterEditTradeScopeGroup')?.value ?? '').trim();
    const items = this._scopedOptions(groupFilter);
    dl.innerHTML = items.map(r => {
      const val = escHtml(r.name_zh);
      // 已選大類別時只顯示細項名稱；未篩選時才用 label 標示所屬大類
      if (group) return `<option value="${val}"></option>`;
      const hint = (r.group_name || '').trim();
      return hint ? `<option value="${val}">${escHtml(hint)}</option>` : `<option value="${val}"></option>`;
    }).join('');
  },

  onScopeGroupChange() {
    this._renderScopeDatalist();
    const scopeEl = document.getElementById('masterEditTradeScope');
    const group = document.getElementById('masterEditTradeScopeGroup')?.value.trim();
    if (scopeEl?.value) {
      const row = this.scopeByName[scopeEl.value.trim()];
      const g = (row?.group_name || '').trim() || '未分類';
      if (group && g !== group) scopeEl.value = '';
    }
    this._syncOverrideFromGroup(group);
    this.refreshOverrideUi();
  },

  /** 大類別 = 工程類別分類；選定時跟著更新（「全部」與「未分類」除外） */
  _syncOverrideFromGroup(group) {
    const overrideEl = document.getElementById('masterEditTradeOverride');
    if (!overrideEl) return;
    const g = (group || '').trim();
    if (!g) return; // 全部大類別 — 不動工程類別
    if (g === '未分類') {
      overrideEl.value = '';
      return;
    }
    if (this.overrideSet.has(g)) {
      overrideEl.value = g;
    }
  },

  _overrideSourceLabel(r) {
    if ((r?.group_name || '') === this.EXTRA_GROUP) return '資料補充';
    return '分類清單';
  },

  _overrideL1Label(r) {
    const g = (r?.group_name || '').trim();
    if (!g || g === this.EXTRA_GROUP) return '—';
    return g;
  },

  onScopeInput() {
    const scope = document.getElementById('masterEditTradeScope')?.value.trim();
    if (!scope) return;
    const row = this.scopeByName[scope];
    if (!row) return;
    const g = (row.group_name || '').trim() || '未分類';
    const groupSel = document.getElementById('masterEditTradeScopeGroup');
    if (groupSel && groupSel.value !== g) {
      this._renderScopeGroupSelect(g);
      this._renderScopeDatalist(g);
    }
    this._syncOverrideFromGroup(g);
    this.refreshOverrideUi();
  },

  _renderOverrideSelect(selected) {
    const sel = document.getElementById('masterEditTradeOverride');
    if (!sel) return;
    const want = (selected ?? sel.value ?? '').trim();
    let html = '<option value="">— 請選擇 —</option>';
    this.overrideOptions.forEach(r => {
      const name = (r.name_zh || '').trim();
      if (!name) return;
      html += `<option value="${escHtml(name)}"${want === name ? ' selected' : ''}>${escHtml(name)}</option>`;
    });
    sel.innerHTML = html;
    if (want && !this.overrideSet.has(want)) {
      sel.innerHTML += `<option value="${escHtml(want)}" selected>${escHtml(want)}</option>`;
    }
    this.refreshOverrideUi();
  },

  _fillEditGroupOptions(selected) {
    const sel = document.getElementById('masterTradeEditGroup');
    if (!sel) return;
    const want = (selected || '').trim();
    let html = '<option value="">未分類</option>';
    this.overrideOptions.forEach(r => {
      const name = (r.name_zh || '').trim();
      if (!name) return;
      html += `<option value="${escHtml(name)}"${want === name ? ' selected' : ''}>${escHtml(name)}</option>`;
    });
    sel.innerHTML = html;
  },

  readTradeFields() {
    const scope = document.getElementById('masterEditTradeScope')?.value.trim() || '';
    const override = document.getElementById('masterEditTradeOverride')?.value.trim() || '';
    return {
      trade_scope: scope || null,
      trade_override: override || null,
      trade_category: override || scope || null,
    };
  },

  async setTradeFieldsFromRow(row) {
    await this.ensureLoaded();
    const scopeEl = document.getElementById('masterEditTradeScope');
    const overrideEl = document.getElementById('masterEditTradeOverride');
    if (!scopeEl || !overrideEl) return;

    let scope = (row?.trade_scope || '').trim();
    let override = (row?.trade_override || '').trim();
    const effective = (row?.trade_category || '').trim();

    if (!scope && !override && effective) {
      if (this.overrideSet.has(effective)) override = effective;
      else scope = effective;
    }

    scopeEl.value = scope;
    const scopeRow = this.scopeByName[scope];
    const group = (scopeRow?.group_name || '').trim() || (override && this.overrideSet.has(override) ? override : '');
    this._renderScopeGroupSelect(group);
    this._renderScopeDatalist(group);
    this._renderOverrideSelect(override);
    this._overrideExpanded = false;
    if (override) {
      const def = this._inferDefaultOverride();
      if (override !== def) this._overrideExpanded = true;
    }
    this.refreshOverrideUi();
  },

  clearTradeFields() {
    this._overrideExpanded = false;
    document.getElementById('masterEditTradeScope').value = '';
    this._renderScopeGroupSelect('');
    this._renderScopeDatalist('');
    this._renderOverrideSelect('');
    this.refreshOverrideUi();
  },

  async openManage(tab = 'scope') {
    this._manageTab = tab;
    await this.ensureLoaded(true);
    document.getElementById('masterTradeModal')?.classList.add('open');
    this._switchManageTab(tab);
    const st = await api('GET', '/master/trade-categories/status', null, { silent: true });
    const el = document.getElementById('masterTradeRefHint');
    if (el) {
      const ng = (this.scopeGroups || []).length;
      el.textContent = st?.ref_file
        ? `I 欄 ${this.scopeOptions.length} 細項 · 工程類別 ${this.overrideOptions.length} 項（分類清單 ${st.fenlei_count || '—'} + 資料補充）`
        : `I 欄 ${this.scopeOptions.length} 細項 · 工程類別 ${this.overrideOptions.length} 項`;
    }
  },

  closeManage() {
    document.getElementById('masterTradeModal')?.classList.remove('open');
  },

  _switchManageTab(tab) {
    this._manageTab = tab;
    document.querySelectorAll('.master-trade-tab').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.tab === tab);
    });
    document.getElementById('masterTradePanelScope').style.display = tab === 'scope' ? '' : 'none';
    document.getElementById('masterTradePanelOverride').style.display = tab === 'override' ? '' : 'none';
    document.getElementById('masterTradeAddFieldType').value = tab;
    this.renderManageTable();
  },

  renderManageTable() {
    const tbody = document.getElementById(
      this._manageTab === 'scope' ? 'masterTradeScopeBody' : 'masterTradeOverrideBody'
    );
    if (!tbody) return;
    const rows = (this._manageTab === 'scope' ? this.scopeOptions : this.overrideOptions).slice();
    const cols = this._manageTab === 'scope' ? 5 : 6;
    if (!rows.length) {
      tbody.innerHTML = `<tr><td colspan="${cols}"><div class="empty-state" style="padding:24px">尚無選項 — 請按「從 Excel 同步」</div></td></tr>`;
      return;
    }
    if (this._manageTab === 'scope') {
      tbody.innerHTML = rows.map(r => `
        <tr>
          <td>${escHtml(r.name_zh)}</td>
          <td class="td-muted">${escHtml(r.group_name || '未分類')}</td>
          <td class="td-muted">${r.use_count ?? '—'}</td>
          <td>${r.sort_order ?? '—'}</td>
          <td>
            <div class="table-row-actions">
              <button type="button" class="btn btn-icon btn-secondary btn-sm" title="編輯" onclick="MasterTradeCats.openEdit(${r.id})">✏️</button>
              <button type="button" class="btn btn-icon btn-danger btn-sm" title="停用" onclick="MasterTradeCats.deactivate(${r.id})">🚫</button>
            </div>
          </td>
        </tr>`).join('');
    } else {
      tbody.innerHTML = rows.map(r => `
        <tr>
          <td>${escHtml(r.name_zh)}</td>
          <td class="td-muted">${escHtml(this._overrideL1Label(r))}</td>
          <td>${escHtml(this._overrideSourceLabel(r))}</td>
          <td class="td-muted">${r.use_count ?? '—'}</td>
          <td>${r.sort_order ?? '—'}</td>
          <td>
            <div class="table-row-actions">
              <button type="button" class="btn btn-icon btn-secondary btn-sm" title="編輯" onclick="MasterTradeCats.openEdit(${r.id})">✏️</button>
              <button type="button" class="btn btn-icon btn-danger btn-sm" title="停用" onclick="MasterTradeCats.deactivate(${r.id})">🚫</button>
            </div>
          </td>
        </tr>`).join('');
    }
  },

  async addCategory() {
    const field_type = document.getElementById('masterTradeAddFieldType')?.value || this._manageTab;
    const name_zh = document.getElementById('masterTradeAddName')?.value.trim();
    if (!name_zh) {
      toast('請填寫名稱', 'warning');
      return;
    }
    const body = { field_type, name_zh };
    if (field_type === 'override') {
      body.group_name = this.EXTRA_GROUP;
    }
    await api('POST', '/master/trade-categories', body);
    toast('已新增', 'success');
    document.getElementById('masterTradeAddName').value = '';
    await this.ensureLoaded(true);
    this.renderManageTable();
    this._renderScopeGroupSelect();
    this._renderScopeDatalist();
    this._renderOverrideSelect(document.getElementById('masterEditTradeOverride')?.value);
  },

  openEdit(id) {
    const row = [...this.scopeOptions, ...this.overrideOptions].find(r => r.id === id);
    if (!row) return;
    document.getElementById('masterTradeEditId').value = id;
    document.getElementById('masterTradeEditFieldType').value = row.field_type || 'scope';
    document.getElementById('masterTradeEditName').value = row.name_zh || '';
    document.getElementById('masterTradeEditSort').value = row.sort_order ?? '';
    const groupRow = document.getElementById('masterTradeEditGroupRow');
    if (groupRow) groupRow.style.display = row.field_type === 'scope' ? '' : 'none';
    this._fillEditGroupOptions(row.group_name || '');
    document.getElementById('masterTradeEditModal')?.classList.add('open');
  },

  closeEdit() {
    document.getElementById('masterTradeEditModal')?.classList.remove('open');
  },

  async saveEdit() {
    const id = document.getElementById('masterTradeEditId')?.value;
    if (!id) return;
    const field_type = document.getElementById('masterTradeEditFieldType')?.value;
    const sortRaw = document.getElementById('masterTradeEditSort')?.value;
    const body = {
      field_type,
      name_zh: document.getElementById('masterTradeEditName')?.value.trim(),
      sort_order: sortRaw === '' ? 0 : parseInt(sortRaw, 10),
    };
    if (field_type === 'scope') {
      body.group_name = document.getElementById('masterTradeEditGroup')?.value.trim() || null;
    }
    await api('PUT', `/master/trade-categories/${id}`, body);
    toast('已更新', 'success');
    this.closeEdit();
    await this.ensureLoaded(true);
    this.renderManageTable();
    this._renderScopeGroupSelect(document.getElementById('masterEditTradeScopeGroup')?.value);
    this._renderScopeDatalist();
    this._renderOverrideSelect(document.getElementById('masterEditTradeOverride')?.value);
  },

  async deactivate(id) {
    if (!confirm('確定停用此選項？')) return;
    await api('DELETE', `/master/trade-categories/${id}`);
    toast('已停用', 'success');
    await this.ensureLoaded(true);
    this.renderManageTable();
    this._renderScopeGroupSelect();
    this._renderScopeDatalist();
    this._renderOverrideSelect(document.getElementById('masterEditTradeOverride')?.value);
  },

  async syncFromRef() {
    const r = await api('POST', '/master/trade-categories/sync');
    toast(
      `已同步：I 欄 ${r.scope_count || 0} 細項 · 工程類別 ${r.override_count || 0} 項（清單 ${r.catalog_count || 0} + 補充 ${r.extra_count || 0}）`,
      'success',
    );
    await this.ensureLoaded(true);
    this.renderManageTable();
    this._renderScopeGroupSelect();
    this._renderScopeDatalist();
    this._renderOverrideSelect(document.getElementById('masterEditTradeOverride')?.value);
  },
};
