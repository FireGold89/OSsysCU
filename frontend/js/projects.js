/* ─── projects.js — 工程項目 ──────────────────────────── */
const Projects = {
  _editOriginalCode: '',
  _settleProjectId: null,
  _settleCover: null,
  _activeTab: 'basic',
  _rows: [],
  _viewMode: localStorage.getItem('qs_project_view') || 'list',
  _sortKey: localStorage.getItem('qs_summary_sort_key') || 'account_code',
  _sortDir: localStorage.getItem('qs_summary_sort_dir') || 'asc',
  _mpExpandedGroups: null,

  PROJ_COLUMNS: [
    { id: 'mp_code', label: 'MP合約編號' },
    { id: 'account_code', label: '會計編號' },
    { id: 'title', label: '主合約名稱' },
    { id: 'parties', label: '客方／承判' },
    { id: 'person', label: '負責人' },
    { id: 'contract_amount', label: 'MP承建' },
    { id: 'profit_pct', label: '利潤率' },
    { id: 'status', label: '狀態' },
    { id: 'act', label: '操作', locked: true },
  ],

  _mpCodesFromRow(r) {
    return (r.mp_contract_codes || []).map(c => (
      typeof c === 'object' ? c.mp_contract_code : c
    )).filter(Boolean);
  },

  _ensureMpCollapseState() {
    if (this._mpExpandedGroups instanceof Set) return;
    try {
      const raw = localStorage.getItem('qs_summary_mp_expanded');
      this._mpExpandedGroups = raw ? new Set(JSON.parse(raw)) : new Set();
    } catch (e) {
      this._mpExpandedGroups = new Set();
    }
  },

  _saveMpCollapseState() {
    this._ensureMpCollapseState();
    localStorage.setItem('qs_summary_mp_expanded', JSON.stringify([...this._mpExpandedGroups]));
  },

  isMpGroupExpanded(projectId) {
    this._ensureMpCollapseState();
    return this._mpExpandedGroups.has(String(projectId));
  },

  toggleMpGroup(projectId, event) {
    if (event) event.stopPropagation();
    this._ensureMpCollapseState();
    const key = String(projectId);
    if (this._mpExpandedGroups.has(key)) this._mpExpandedGroups.delete(key);
    else this._mpExpandedGroups.add(key);
    this._saveMpCollapseState();
    this.renderView();
  },

  _mpCodes: [],
  _projDocCategory: null,
  _projDocs: [],
  _categoryTree: null,

  async ensureCategoryTree() {
    if (this._categoryTree) return this._categoryTree;
    try {
      const data = await api('GET', '/engineering-categories');
      this._categoryTree = data?.tree || [];
    } catch (e) {
      this._categoryTree = [];
    }
    this._renderCategoryL1Options();
    return this._categoryTree;
  },

  _renderCategoryL1Options() {
    const sel = document.getElementById('pCatL1');
    if (!sel) return;
    const cur = sel.value;
    sel.innerHTML = '<option value="">— 一級大類 —</option>';
    (this._categoryTree || []).forEach(n => {
      const opt = document.createElement('option');
      opt.value = n.l1_code;
      opt.textContent = n.l1_label || `${n.l1_code} ${n.l1_name_zh || n.l1_name_en || ''}`.trim();
      sel.appendChild(opt);
    });
    if (cur) sel.value = cur;
  },

  _renderCategoryL2Options(l1Code, selectedL2) {
    const sel = document.getElementById('pCatL2');
    if (!sel) return;
    sel.innerHTML = '<option value="">— 二級分類 —</option>';
    const node = (this._categoryTree || []).find(n => n.l1_code === l1Code);
    (node?.children || []).forEach(c => {
      const opt = document.createElement('option');
      opt.value = c.l2_code;
      opt.textContent = c.l2_label || c.l2_code;
      opt.dataset.scope = c.scope || '';
      sel.appendChild(opt);
    });
    if (selectedL2) sel.value = selectedL2;
    this.onCategoryL2Change();
  },

  onCategoryL1Change() {
    const l1 = this._val('pCatL1');
    this._renderCategoryL2Options(l1, '');
    const hint = document.getElementById('pCatScopeHint');
    if (hint) hint.textContent = '';
  },

  onCategoryL2Change() {
    const sel = document.getElementById('pCatL2');
    const hint = document.getElementById('pCatScopeHint');
    if (!sel || !hint) return;
    const opt = sel.selectedOptions[0];
    const scope = opt?.dataset?.scope || '';
    hint.textContent = scope ? scope.slice(0, 120) + (scope.length > 120 ? '…' : '') : '';
  },

  _setCategoryFields(p) {
    const l1 = p?.category_l1_code || '';
    const l2 = p?.category_l2_code || '';
    this._set('pCatL1', l1);
    this._renderCategoryL2Options(l1, l2);
  },

  _readCategoryFields() {
    const l2 = this._val('pCatL2') || null;
    const l1 = this._val('pCatL1') || (l2 ? l2.split('.')[0] : null);
    return { category_l1_code: l1, category_l2_code: l2 };
  },

  async _maybeSuggestCategory(projectId) {
    if (this._val('pCatL2')) return;
    try {
      const s = await api('GET', `/projects/${projectId}/category-suggest`);
      if (s?.l2_code) {
        this._setCategoryFields({ category_l1_code: s.l1_code, category_l2_code: s.l2_code });
        toast(`已建議工程分類：${s.l2_code} ${s.l2_name_zh || s.l2_name_en || ''}`.trim(), 'info');
      }
    } catch (e) {}
  },

  _normalizeMpCode(raw) {
    return String(raw || '').trim().toUpperCase();
  },

  _setMpCodes(codes) {
    const seen = new Set();
    this._mpCodes = [];
    (codes || []).forEach(c => {
      const code = this._normalizeMpCode(typeof c === 'object' ? c.mp_contract_code : c);
      if (code && !seen.has(code)) {
        seen.add(code);
        this._mpCodes.push(code);
      }
    });
    this._renderMpCodes();
  },

  _readMpCodes() {
    return [...this._mpCodes];
  },

  _renderMpCodes() {
    const list = document.getElementById('pMpCodesList');
    if (!list) return;
    if (!this._mpCodes.length) {
      list.innerHTML = '<span class="mp-codes-empty">尚未加入 MP 編號</span>';
    } else {
      list.innerHTML = this._mpCodes.map((code, i) => {
        const primary = i === 0
          ? '<span class="mp-code-badge">主</span>'
          : `<button type="button" class="mp-code-promote" title="設為主編號" onclick="Projects.promoteMpCode(${i})">↑</button>`;
        return `<span class="mp-code-chip${i === 0 ? ' is-primary' : ''}">
          ${primary}
          <span class="mp-code-text">${escHtml(code)}</span>
          <button type="button" class="mp-code-remove" title="移除" onclick="Projects.removeMpCode(${i})">×</button>
        </span>`;
      }).join('');
    }
    const input = document.getElementById('pMpCodeInput');
    if (input) input.value = '';
    this._syncMpCodeHint();
  },

  _syncMpCodeHint() {
    const hint = document.getElementById('pMpCodesHint');
    if (!hint) return;
    const n = this._mpCodes.length;
    hint.textContent = n > 1
      ? `共 ${n} 個 MP · 主編號「${this._mpCodes[0]}」`
      : '可加入多個 MP 編號 · 首個為主編號 · 留空則由項目代碼推導';
  },

  addMpCode() {
    const input = document.getElementById('pMpCodeInput');
    const raw = this._normalizeMpCode(input?.value);
    if (!raw) return;
    if (this._mpCodes.includes(raw)) {
      toast('此 MP 編號已存在', 'warning');
      return;
    }
    this._mpCodes.push(raw);
    this._renderMpCodes();
  },

  promoteMpCode(idx) {
    if (idx <= 0 || idx >= this._mpCodes.length) return;
    const code = this._mpCodes.splice(idx, 1)[0];
    this._mpCodes.unshift(code);
    this._renderMpCodes();
  },

  removeMpCode(idx) {
    if (idx < 0 || idx >= this._mpCodes.length) return;
    this._mpCodes.splice(idx, 1);
    this._renderMpCodes();
  },

  pickProjDoc(category) {
    const id = document.getElementById('projModalId')?.value;
    if (!id) {
      toast('請先儲存項目，再上傳附件', 'warning');
      return;
    }
    this._projDocCategory = category;
    document.getElementById('projDocFileInput')?.click();
  },

  async onProjDocFile(input) {
    const file = input?.files?.[0];
    if (!file) return;
    const pid = document.getElementById('projModalId')?.value;
    const cat = this._projDocCategory;
    if (!pid || !cat) {
      if (input) input.value = '';
      return;
    }
    showLoading('上傳附件…');
    try {
      const fd = new FormData();
      fd.append('file', file);
      const up = await fetch(`${API}/files/upload`, { method: 'POST', body: fd });
      const upJson = await up.json();
      if (!upJson.success) throw new Error(upJson.error || '上傳失敗');
      await api('POST', `/projects/${pid}/documents`, {
        doc_category: cat,
        file_path: upJson.data.pdf_path,
        original_filename: upJson.data.filename || file.name,
      });
      toast('附件已上傳', 'success');
      await this._loadProjDocuments(pid);
    } catch (e) {
      toast(e.message || '上傳失敗', 'error');
    } finally {
      hideLoading();
      if (input) input.value = '';
      this._projDocCategory = null;
    }
  },

  async deleteProjDoc(docId, event) {
    if (event) event.stopPropagation();
    if (!confirm('刪除此附件？')) return;
    await api('DELETE', `/project-documents/${docId}`);
    const pid = document.getElementById('projModalId')?.value;
    if (pid) await this._loadProjDocuments(pid);
    toast('已刪除附件', 'success');
  },

  async _loadProjDocuments(projectId) {
    this._projDocs = projectId
      ? (await api('GET', `/projects/${projectId}/documents`) || [])
      : [];
    this._renderProjDocLists();
  },

  viewProjDoc(filePath, title) {
    DocViewer.open(filePath, title || '項目附件');
  },

  _renderProjDocLists() {
    const render = (elId, cats) => {
      const el = document.getElementById(elId);
      if (!el) return;
      const docs = (this._projDocs || []).filter(d => cats.includes(d.doc_category));
      if (!docs.length) {
        el.innerHTML = '';
        return;
      }
      el.innerHTML = docs.map(d => {
        const rawName = d.original_filename || d.file_path || '附件';
        const name = escHtml(rawName);
        const path = (d.file_path || '').replace(/"/g, '&quot;');
        const viewBtn = path
          ? `<button type="button" class="btn btn-icon btn-secondary btn-sm btn-view-pdf proj-doc-view"
              title="預覽" data-pdf-path="${path}" data-doc-title="${name}">👁</button>`
          : '';
        const nameBtn = path
          ? `<button type="button" class="proj-doc-file-name btn-view-pdf" data-pdf-path="${path}"
              data-doc-title="${name}" title="點擊預覽">📄 ${name}</button>`
          : `<span class="proj-doc-file-name">📄 ${name}</span>`;
        return `<div class="proj-doc-file">
          ${nameBtn}
          ${viewBtn}
          <button type="button" class="proj-doc-del" title="刪除" onclick="Projects.deleteProjDoc(${d.id}, event)">×</button>
        </div>`;
      }).join('');
    };
    render('projDocList_main_loa', ['attachment1_main_contract', 'attachment1_loa']);
    render('projDocList_signoff', ['attachment1_signoff']);
    render('projDocList_email', ['attachment1_email']);
    render('projDocList_related', ['attachment1_related']);
    render('projDoc_sot_sor', ['attachment3_sot_sor']);
  },

  initView() {
    this.setView(this._viewMode, { persist: false });
  },

  setView(mode, opts = {}) {
    const { persist = true } = opts;
    this._viewMode = mode === 'card' ? 'card' : 'list';
    if (persist) localStorage.setItem('qs_project_view', this._viewMode);
    document.getElementById('projViewList')?.classList.toggle('active', this._viewMode === 'list');
    document.getElementById('projViewCard')?.classList.toggle('active', this._viewMode === 'card');
    document.getElementById('projListView').style.display = this._viewMode === 'list' ? '' : 'none';
    document.getElementById('projCardView').style.display = this._viewMode === 'card' ? '' : 'none';
  },

  _statusBadge(status) {
    const cls = status === 'Active' ? 'success' : status === 'Completed' ? 'info' : 'warning';
    const label = status === 'Active' ? '進行中' : status === 'Completed' ? '已完成' : '暫停';
    return `<span class="badge badge-${cls}">${label}</span>`;
  },

  _actionButtons(pid, code, compact) {
    const delArg = JSON.stringify(code || '');
    if (compact) {
      return `<div class="proj-row-actions" onclick="event.stopPropagation()">
        <button type="button" class="btn btn-primary btn-sm btn-icon" title="註冊及更新" onclick="Projects.openSettlement(${pid})">📋</button>
        <button type="button" class="btn btn-secondary btn-sm btn-icon" title="編輯" onclick="Projects.openEdit(${pid})">✏️</button>
        <button type="button" class="btn btn-danger btn-sm btn-icon" title="刪除" onclick="Projects.delete(${pid}, ${delArg})">🗑️</button>
      </div>`;
    }
    return `<div style="display:flex;gap:6px;flex-wrap:wrap" onclick="event.stopPropagation()">
      <button type="button" class="btn btn-primary btn-sm" onclick="Projects.openSettlement(${pid})">📋 註冊及更新</button>
      <button type="button" class="btn btn-secondary btn-sm" onclick="Projects.openEdit(${pid})">✏️</button>
      <button type="button" class="btn btn-danger btn-sm" onclick="Projects.delete(${pid}, ${delArg})">🗑️</button>
    </div>`;
  },

  _summaryCodeCell(r, opts = {}) {
    const codes = this._mpCodesFromRow(r);
    const mp = escHtml(r.mp_contract_label || r.mp_contract_code || codes[0] || '—');
    if (opts.groupHeader && codes.length > 1) {
      const expanded = this.isMpGroupExpanded(r.project_id);
      return `<td class="td-mono col-code" data-col="mp_code">
        <span class="sc-group-toggle" aria-hidden="true">${expanded ? '▼' : '▶'}</span>
        ${escHtml(codes[0])} 等${codes.length}個
        <span class="badge badge-muted" style="font-size:9px;margin-left:4px">×${codes.length}</span>
        ${!expanded ? '<span class="badge badge-info" style="margin-left:4px;font-size:9px">已收合</span>' : ''}
      </td>`;
    }
    const tip = codes.length > 1 ? ` title="${escHtml(codes.join(' · '))}"` : '';
    return `<td class="td-mono col-code" data-col="mp_code"${tip}><div>${mp}</div></td>`;
  },

  _summaryAccountCell(r) {
    const acc = r.account_code || '';
    return `<td class="td-mono col-account" data-col="account_code">${acc ? escHtml(acc) : '<span class="td-muted">—</span>'}</td>`;
  },

  sortBy(key) {
    if (this._sortKey === key) {
      this._sortDir = this._sortDir === 'asc' ? 'desc' : 'asc';
    } else {
      this._sortKey = key;
      this._sortDir = ['contract_amount', 'current_profit_pct'].includes(key) ? 'desc' : 'asc';
    }
    localStorage.setItem('qs_summary_sort_key', this._sortKey);
    localStorage.setItem('qs_summary_sort_dir', this._sortDir);
    this.renderView();
  },

  _summarySortValue(row, key) {
    switch (key) {
      case 'mp_code': {
        const codes = this._mpCodesFromRow(row);
        return (codes[0] || row.mp_contract_code || '').toLowerCase();
      }
      case 'account_code':
        return (row.account_code || '').toLowerCase();
      case 'title':
        return (row.main_contract_title || row.main_contract_title_en || '').toLowerCase();
      case 'parties': {
        const parts = [row.client, row.client_secondary, row.main_contractor].filter(Boolean);
        return parts.join(' ').toLowerCase();
      }
      case 'person':
        return (row.person_in_charge || '').toLowerCase();
      case 'contract_amount':
        return parseFloat(row.contract_amount) || 0;
      case 'current_profit_pct':
        return row.current_profit_pct != null ? parseFloat(row.current_profit_pct) : -Infinity;
      case 'status':
        return row.status || '';
      default:
        return '';
    }
  },

  _summarySortEmpty(row, key) {
    switch (key) {
      case 'contract_amount':
        return !row.contract_amount;
      case 'current_profit_pct':
        return row.current_profit_pct == null;
      case 'parties':
        return !row.client && !row.client_secondary && !row.main_contractor;
      default:
        return !this._summarySortValue(row, key);
    }
  },

  _sortedRows() {
    const rows = [...(this._rows || [])];
    if (!this._sortKey || !rows.length) return rows;
    const key = this._sortKey;
    const dir = this._sortDir === 'asc' ? 1 : -1;
    const isNum = key === 'contract_amount' || key === 'current_profit_pct';
    rows.sort((a, b) => {
      const aEmpty = this._summarySortEmpty(a, key);
      const bEmpty = this._summarySortEmpty(b, key);
      if (aEmpty && bEmpty) return 0;
      if (aEmpty) return 1;
      if (bEmpty) return -1;
      const va = this._summarySortValue(a, key);
      const vb = this._summarySortValue(b, key);
      if (isNum) return (va - vb) * dir;
      return String(va).localeCompare(String(vb), 'zh-Hant', { numeric: true, sensitivity: 'base' }) * dir;
    });
    return rows;
  },

  _updateSummarySortHeaders() {
    document.querySelectorAll('#projSummaryHead .th-sortable').forEach(th => {
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

  _summaryTitleCell(r) {
    const title = r.main_contract_title || r.main_contract_title_en || '—';
    const cat = r.category_l2_label || r.category_l2_code || '';
    const full = cat ? `${title} · ${cat}` : title;
    return `<td class="col-title" data-col="title">
      <div class="cell-ellipsis" title="${escHtml(full)}">${escHtml(title)}</div>
      ${cat ? `<div class="cell-sub">${escHtml(cat)}</div>` : ''}
    </td>`;
  },

  _summaryPartiesCell(r) {
    const client = r.client || '';
    const c2 = r.client_secondary || '';
    const mc = r.main_contractor || '';
    let html = '';
    if (client && c2) {
      html = `<div class="cell-ellipsis" title="${escHtml(client + ' · ' + c2)}">${escHtml(client)}</div>
        <div class="cell-sub cell-ellipsis" title="${escHtml(c2)}">${escHtml(c2)}</div>`;
    } else if (client) {
      html = `<div class="cell-ellipsis" title="${escHtml(client)}">${escHtml(client)}</div>`;
    } else {
      html = '<span class="td-muted">—</span>';
    }
    if (mc) {
      html += `<div class="cell-party-mc cell-ellipsis" title="${escHtml(mc)}">主承判 ${escHtml(mc)}</div>`;
    }
    return `<td class="col-parties" data-col="parties">${html}</td>`;
  },

  _summaryPersonCell(r) {
    const name = (r.person_in_charge || '').trim();
    return `<td class="col-person" data-col="person"><div class="cell-ellipsis" title="${escHtml(name)}">${escHtml(name || '—')}</div></td>`;
  },

  async load() {
    this.initView();
    const tbody = document.getElementById('projSummaryBody');
    const cards = document.getElementById('projCardView');
    if (tbody) {
      tbody.innerHTML = '<tr><td colspan="8"><div class="empty-state" style="padding:24px">載入中...</div></td></tr>';
    }
    if (cards) {
      cards.innerHTML = '<div class="empty-state" style="grid-column:1/-1;padding:40px">載入中...</div>';
    }
    this._rows = await api('GET', '/company-summary') || [];
    this.renderView();
  },

  render(projects) {
    /* App.loadProjects 仍會呼叫；工程項目頁以 Summary 為準 */
    this.load();
  },

  renderView() {
    if (!this._visibleCols) this._initColPrefs();
    const rows = this._sortedRows();
    const colSpan = this._visibleColCount();
    const countEl = document.getElementById('projSummaryCount');
    if (countEl) countEl.textContent = `${(this._rows || []).length} 個項目`;

    if (!rows.length) {
      const empty = '<div class="empty-state" style="padding:48px"><div class="empty-icon">📁</div><div class="empty-title">暫無項目</div><div class="empty-sub">按「同步 Ref/Summary.xlsx」或「匯入 Summary」</div></div>';
      const tbody = document.getElementById('projSummaryBody');
      if (tbody) tbody.innerHTML = `<tr><td colspan="${colSpan}">${empty}</td></tr>`;
      const cards = document.getElementById('projCardView');
      if (cards) cards.innerHTML = empty;
      this._updateSummarySortHeaders();
      this.applyColVisibility();
      return;
    }

    const tbody = document.getElementById('projSummaryBody');
    if (tbody) {
      tbody.innerHTML = rows.map(r => this._renderListRows(r)).join('');
    }
    const cards = document.getElementById('projCardView');
    if (cards) {
      cards.innerHTML = rows.map(r => this._renderCard(r)).join('');
    }
    this._updateSummarySortHeaders();
    this.applyColVisibility();
  },

  _renderListRows(r) {
    const codes = this._mpCodesFromRow(r);
    if (codes.length <= 1) return this._renderListRow(r);
    return this._renderMpGroupRows(r, codes);
  },

  _renderMpGroupRows(r, codes) {
    const pid = r.project_id;
    const expanded = this.isMpGroupExpanded(pid);
    const rate = r.current_profit_pct != null ? `${Number(r.current_profit_pct).toFixed(2)}%` : '—';
    const html = [`<tr class="proj-mp-group-header" onclick="Projects.toggleMpGroup(${pid}, event)" title="點擊收合/展開 MP 編號">
      ${this._summaryCodeCell(r, { groupHeader: true })}
      ${this._summaryAccountCell(r)}
      ${this._summaryTitleCell(r)}
      ${this._summaryPartiesCell(r)}
      ${this._summaryPersonCell(r)}
      <td class="td-amount col-amt" data-col="contract_amount">${fmt(r.contract_amount)}</td>
      <td class="td-amount col-rate" data-col="profit_pct">${rate}</td>
      <td class="col-status" data-col="status">${this._statusBadge(r.status)}</td>
      <td class="col-actions" data-col="act">${this._actionButtons(pid, r.project_code || r.mp_contract_code, true)}</td>
    </tr>`];
    if (expanded) {
      codes.forEach((code, i) => {
        const primary = i === 0
          ? ' <span class="mp-code-badge" style="font-size:9px;padding:1px 4px;vertical-align:middle">主</span>'
          : '';
        html.push(`<tr class="row-clickable proj-mp-group-child" onclick="Projects.openSettlement(${pid})" title="點擊進入註冊及更新">
          <td class="td-mono col-code" data-col="mp_code">${escHtml(code)}${primary}</td>
          <td class="td-mono col-account td-muted" data-col="account_code">—</td>
          <td class="col-title td-muted" data-col="title" style="font-size:11px">MP 合約編號 ${i + 1}/${codes.length}</td>
          <td class="col-parties" data-col="parties"></td>
          <td class="col-person" data-col="person"></td>
          <td class="col-amt" data-col="contract_amount"></td>
          <td class="col-rate" data-col="profit_pct"></td>
          <td class="col-status" data-col="status"></td>
          <td class="col-actions" data-col="act"></td>
        </tr>`);
      });
    }
    return html.join('');
  },

  _renderListRow(r) {
    const pid = r.project_id;
    const rate = r.current_profit_pct != null ? `${Number(r.current_profit_pct).toFixed(2)}%` : '—';
    return `<tr class="row-clickable" onclick="Projects.openSettlement(${pid})" title="點擊進入註冊及更新">
      ${this._summaryCodeCell(r)}
      ${this._summaryAccountCell(r)}
      ${this._summaryTitleCell(r)}
      ${this._summaryPartiesCell(r)}
      ${this._summaryPersonCell(r)}
      <td class="td-amount col-amt" data-col="contract_amount">${fmt(r.contract_amount)}</td>
      <td class="td-amount col-rate" data-col="profit_pct">${rate}</td>
      <td class="col-status" data-col="status">${this._statusBadge(r.status)}</td>
      <td class="col-actions" data-col="act">${this._actionButtons(pid, r.project_code || r.mp_contract_code, true)}</td>
    </tr>`;
  },

  _renderCard(r) {
    const pid = r.project_id;
    const title = escHtml(r.main_contract_title || r.main_contract_title_en || '—');
    const paid = r.total_paid || 0;
    const contractAmt = r.contract_amount || 0;
    const pctRaw = contractAmt > 0 ? (paid / contractAmt * 100) : 0;
    const progress = pctRaw.toFixed(FMT_DECIMALS);
    const barWidth = Math.min(100, Math.max(0, pctRaw));
    const rate = r.current_profit_pct != null ? `${Number(r.current_profit_pct).toFixed(2)}%` : '—';
    const codes = this._mpCodesFromRow(r);
    let mpHead;
    if (codes.length > 1) {
      const expanded = this.isMpGroupExpanded(pid);
      mpHead = `<div class="proj-mp-card-head" onclick="Projects.toggleMpGroup(${pid}, event)" title="點擊收合/展開 MP 編號">
          <span class="sc-group-toggle">${expanded ? '▼' : '▶'}</span>
          <span style="font-family:monospace">${escHtml(codes[0])} 等${codes.length}個</span>
          <span class="badge badge-muted" style="font-size:10px;margin-left:4px">×${codes.length}</span>
          · ${escHtml(r.account_code || '—')}
        </div>
        ${expanded ? `<div class="proj-mp-card-children">${codes.map((c, i) =>
          `<div class="proj-mp-card-child">${escHtml(c)}${i === 0 ? ' <span class="mp-code-badge" style="font-size:9px;padding:1px 4px">主</span>' : ''}</div>`
        ).join('')}</div>` : ''}`;
    } else {
      const mpLabel = escHtml(r.mp_contract_label || r.mp_contract_code || '—');
      mpHead = `<div style="font-size:11px;color:var(--text-muted);font-family:monospace">
                ${mpLabel} · ${escHtml(r.account_code || '—')}
              </div>`;
    }
    return `
      <div class="card proj-summary-card">
        <div class="card-body">
          <div style="display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:10px">
            <div style="min-width:0">
              ${mpHead}
              <div style="font-weight:600;font-size:14px;margin-top:4px;line-height:1.35">${title}</div>
            </div>
            ${this._statusBadge(r.status)}
          </div>
          <div style="font-size:12px;color:var(--text-secondary);margin-bottom:4px">👤 客方：${escHtml(r.client || '—')}</div>
          ${r.client_secondary ? `<div style="font-size:12px;color:var(--text-secondary);margin-bottom:4px">👤 第二客方：${escHtml(r.client_secondary)}</div>` : ''}
          <div style="font-size:12px;color:var(--text-secondary);margin-bottom:4px">🏗️ 主承判：${escHtml(r.main_contractor || '—')}</div>
          <div style="font-size:12px;color:var(--text-secondary);margin-bottom:10px">👔 負責人：${escHtml(r.person_in_charge || '—')}</div>
          <div style="display:flex;justify-content:space-between;font-size:12px;margin-bottom:8px">
            <span>MP承建 <strong>${fmt(contractAmt)}</strong></span>
            <span>利潤率 <strong>${rate}</strong></span>
          </div>
          <div style="margin-bottom:10px">
            <div style="display:flex;justify-content:space-between;font-size:11px;color:var(--text-muted);margin-bottom:4px">
              <span>付款 ${progress}%</span>
              <span>${fmt(paid)}</span>
            </div>
            <div class="progress-bar-wrap"><div class="progress-bar" style="width:${barWidth}%"></div></div>
          </div>
          <div style="display:flex;justify-content:space-between;align-items:center;margin-top:10px">
            <span style="font-size:11px;color:var(--text-muted)">📋 ${r.sc_count || 0} 判項</span>
            ${this._actionButtons(pid, r.project_code || r.mp_contract_code)}
          </div>
        </div>
      </div>`;
  },

  importSummary() {
    document.getElementById('projSummaryFile')?.click();
  },

  async onSummaryFile(input) {
    const file = input?.files?.[0];
    if (!file) return;
    showLoading('匯入 Summary…');
    try {
      const fd = new FormData();
      fd.append('file', file);
      const r = await fetch(`${API}/import/summary`, { method: 'POST', body: fd });
      const json = await r.json();
      if (!json.success) throw new Error(json.error || '匯入失敗');
      toast(`Summary 匯入完成：新增 ${json.data.created} · 更新 ${json.data.updated}`, 'success');
      await App.loadProjects();
      await Projects.load();
      await this.load();
    } catch (e) {
      toast(e.message || '匯入失敗', 'error');
    } finally {
      hideLoading();
      if (input) input.value = '';
    }
  },

  async syncSummaryRef() {
    showLoading('同步 Ref/Summary.xlsx…');
    try {
      const json = await api('POST', '/import/summary/sync');
      if (!json) return;
      toast(`同步完成：新增 ${json.created} · 更新 ${json.updated} · 共 ${json.rows_parsed} 項`, 'success');
      await App.loadProjects();
      await Projects.load();
      await this.load();
    } catch (e) {
      toast(e.message || '同步失敗', 'error');
    } finally {
      hideLoading();
    }
  },

  switchTab(tab) {
    this._activeTab = tab || 'basic';
    if (tab === 'cover') {
      document.getElementById('projSectionRetention')
        ?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  },

  _val(id) {
    return document.getElementById(id)?.value?.trim() ?? '';
  },

  _num(id) {
    const v = document.getElementById(id)?.value;
    if (v === '' || v == null) return null;
    const n = parseFloat(v);
    return Number.isNaN(n) ? null : n;
  },

  _constructionPeriodDisplay(p) {
    const proj = p || {};
    if (proj.site_period_text) return proj.site_period_text;
    if (proj.construction_period_days != null && proj.construction_period_days !== '') {
      return String(proj.construction_period_days);
    }
    return '';
  },

  _parseConstructionPeriod(raw) {
    const s = String(raw || '').trim();
    if (!s) return { site_period_text: null, construction_period_days: null };
    if (/^\d+$/.test(s)) {
      const n = parseInt(s, 10);
      return { site_period_text: `${n}天`, construction_period_days: n };
    }
    const m = s.match(/(\d+)\s*天/);
    const days = m ? parseInt(m[1], 10) : null;
    return { site_period_text: s, construction_period_days: days };
  },

  _set(id, val) {
    const el = document.getElementById(id);
    if (!el) return;
    el.value = val == null || val === '' ? '' : val;
  },

  _retentionDateOneOff: 'pRetentionDateOneOff',
  _retentionDateFirst: 'pRetentionDateFirstHalf',
  _retentionDateSecond: 'pRetentionDateSecondHalf',
  _retentionNaOn: 'pRetentionNaOn',
  _retentionOneOffOn: 'pRetentionOneOffOn',
  _retentionFirstOn: 'pRetentionFirstHalfOn',
  _retentionSecondOn: 'pRetentionSecondHalfOn',

  _deriveRetentionMode(na, oneOff, firstOn, secondOn) {
    if (na) return 'na';
    if (!oneOff && !firstOn && !secondOn) return 'na';
    if (oneOff && !firstOn && !secondOn) return 'one_off';
    if (!oneOff && firstOn && !secondOn) return 'first_half';
    if (!oneOff && !firstOn && secondOn) return 'second_half';
    if (!oneOff && firstOn && secondOn) return 'two_half';
    return 'multi';
  },

  _setRetentionFields(p) {
    const proj = p || {};
    const mode = (proj.retention_release_mode || 'na').toLowerCase();
    let dOne = proj.retention_release_date || null;
    let dFirst = proj.retention_release_date_first || null;
    let dSecond = proj.retention_release_date_second || null;
    if (!dFirst && mode === 'first_half') dFirst = proj.retention_release_date;
    if (!dSecond && mode === 'second_half') dSecond = proj.retention_release_date;

    let oneOff = !!dOne;
    let firstOn = !!dFirst;
    let secondOn = !!dSecond;
    if (!oneOff && !firstOn && !secondOn) {
      if (mode === 'one_off') oneOff = true;
      else if (mode === 'first_half') firstOn = true;
      else if (mode === 'second_half') secondOn = true;
      else if (mode === 'two_half') {
        firstOn = true;
        secondOn = true;
      }
    }
    const naOn = !oneOff && !firstOn && !secondOn;

    const naEl = document.getElementById(this._retentionNaOn);
    const oneEl = document.getElementById(this._retentionOneOffOn);
    const firstEl = document.getElementById(this._retentionFirstOn);
    const secondEl = document.getElementById(this._retentionSecondOn);
    if (naEl) naEl.checked = naOn;
    if (oneEl) oneEl.checked = oneOff && !naOn;
    if (firstEl) firstEl.checked = firstOn && !naOn;
    if (secondEl) secondEl.checked = secondOn && !naOn;

    this._set(this._retentionDateOneOff, dOne || '');
    this._set(this._retentionDateFirst, dFirst || '');
    this._set(this._retentionDateSecond, dSecond || '');
    this.onRetentionModeChange();
  },

  onRetentionModeChange() {
    const naEl = document.getElementById(this._retentionNaOn);
    const oneEl = document.getElementById(this._retentionOneOffOn);
    const firstEl = document.getElementById(this._retentionFirstOn);
    const secondEl = document.getElementById(this._retentionSecondOn);
    let na = naEl?.checked;
    let oneOff = oneEl?.checked;
    let first = firstEl?.checked;
    let second = secondEl?.checked;

    if (na) {
      if (oneEl) oneEl.checked = false;
      if (firstEl) firstEl.checked = false;
      if (secondEl) secondEl.checked = false;
      oneOff = false;
      first = false;
      second = false;
      this._set(this._retentionDateOneOff, '');
      this._set(this._retentionDateFirst, '');
      this._set(this._retentionDateSecond, '');
    } else if (oneOff || first || second) {
      if (naEl) naEl.checked = false;
      na = false;
    }

    const oneDate = document.getElementById(this._retentionDateOneOff);
    const firstDate = document.getElementById(this._retentionDateFirst);
    const secondDate = document.getElementById(this._retentionDateSecond);
    if (oneDate) oneDate.disabled = !oneOff;
    if (firstDate) firstDate.disabled = !first;
    if (secondDate) secondDate.disabled = !second;
  },

  enableRetentionOption(which) {
    const map = {
      one_off: this._retentionOneOffOn,
      first: this._retentionFirstOn,
      second: this._retentionSecondOn,
    };
    const el = document.getElementById(map[which]);
    if (el) el.checked = true;
    this.onRetentionModeChange();
  },

  _readRetentionFields() {
    const naOn = document.getElementById(this._retentionNaOn)?.checked;
    const oneOff = document.getElementById(this._retentionOneOffOn)?.checked;
    const firstOn = document.getElementById(this._retentionFirstOn)?.checked;
    const secondOn = document.getElementById(this._retentionSecondOn)?.checked;

    if (naOn || (!oneOff && !firstOn && !secondOn)) {
      return {
        retention_release_mode: 'na',
        retention_release_date: null,
        retention_release_date_first: null,
        retention_release_date_second: null,
      };
    }

    const dOne = oneOff ? (this._val(this._retentionDateOneOff) || null) : null;
    const dFirst = firstOn ? (this._val(this._retentionDateFirst) || null) : null;
    const dSecond = secondOn ? (this._val(this._retentionDateSecond) || null) : null;

    return {
      retention_release_mode: this._deriveRetentionMode(false, oneOff, firstOn, secondOn),
      retention_release_date: dOne,
      retention_release_date_first: dFirst,
      retention_release_date_second: dSecond,
    };
  },

  async _loadQsField(selectedName) {
    await StaffRoster.loadQsStaff();
    StaffRoster.fillQsSelect(document.getElementById('pQsSelect'), { selectedName });
  },

  async _fillCoverFields(p) {
    const codes = p.mp_contract_codes || [];
    if (codes.length) {
      this._setMpCodes(codes);
    } else if (p.mp_contract_code) {
      this._setMpCodes([p.mp_contract_code]);
    } else {
      this._setMpCodes([]);
    }
    this._set('pAccountCode', p.account_code);
    this._set('pJobNo', p.job_no);
    this._set('pTenderSum', p.tender_sum || '');
    this._set('pAnticipatedProfitPct', p.anticipated_profit_pct ?? '');
    this._set('pMcCommence', p.main_contract_commencement_date);
    this._set('pMpCommence', p.mp_commencement_date || p.start_date);
    this._set('pCompletionDate', p.project_completion_date);
    this._set('pPcCertDate', p.pc_cert_date);
    this._set('pExtendedCompletion', p.extended_completion_date);
    this._set('pConstructionDays', this._constructionPeriodDisplay(p));
    this._set('pDlpMonths', p.dlp_period_months ?? '');
    await this._loadQsField(p.qs_in_charge || p.person_in_charge || '');
    this._setRetentionFields(p);
    this._set('pRetentionPct', p.retention_pct ?? '');
    this._set('pRetentionMaxPct', p.retention_max_pct ?? '');
    this._set('pRetentionMaxAmt', p.retention_max_amount ?? '');
    this._set('pDlpCertDate', p.dlp_cert_date);
    this._set('pMpFacDate', p.mp_fac_signed_date);
  },

  _readCoverFields() {
    const mpCodes = this._readMpCodes();
    return {
      mp_contract_code: mpCodes[0] || null,
      mp_contract_codes: mpCodes,
      account_code: this._val('pAccountCode') || null,
      job_no: this._val('pJobNo') || null,
      ...this._readCategoryFields(),
      tender_sum: this._num('pTenderSum') || 0,
      anticipated_profit_pct: this._num('pAnticipatedProfitPct'),
      main_contract_commencement_date: this._val('pMcCommence') || null,
      mp_commencement_date: this._val('pMpCommence') || null,
      project_completion_date: this._val('pCompletionDate') || null,
      pc_cert_date: this._val('pPcCertDate') || null,
      extended_completion_date: this._val('pExtendedCompletion') || null,
      ...this._parseConstructionPeriod(this._val('pConstructionDays')),
      dlp_period_months: this._num('pDlpMonths'),
      qs_in_charge: this._val('pQsSelect') || null,
      retention_pct: this._num('pRetentionPct'),
      retention_max_pct: this._num('pRetentionMaxPct'),
      retention_max_amount: this._num('pRetentionMaxAmt'),
      ...this._readRetentionFields(),
      dlp_cert_date: this._val('pDlpCertDate') || null,
      mp_fac_signed_date: this._val('pMpFacDate') || null,
    };
  },

  _readFormData() {
    const staff = StaffRoster.staffFromSelect(document.getElementById('pPersonSelect'));
    const personName = staff ? StaffRoster.displayName(staff) : null;
    const qsName = this._val('pQsSelect') || personName;
    return {
      project_code: this._val('pCode'),
      quotation_no: this._val('pQuotationNo') || null,
      person_code: null,
      person_in_charge: personName,
      project_name_en: this._val('pNameEn'),
      project_name_zh: this._val('pNameZh'),
      client: this._val('pClient'),
      client_secondary: this._val('pClient2') || null,
      main_contractor: this._val('pMc'),
      contract_amount: this._num('pAmt') || 0,
      labour_allocation: this._num('pLabour') || 0,
      start_date: this._val('pMpCommence') || null,
      status: document.getElementById('pStatus').value,
      notes: this._val('pNotes'),
      qs_in_charge: qsName,
      ...this._readCoverFields(),
      project_manager: personName,
    };
  },

  async openAdd() {
    await this.ensureCategoryTree();
    this._editOriginalCode = '';
    this.switchTab('basic');
    document.getElementById('projModalTitle').textContent = '新增項目';
    document.getElementById('projModalId').value = '';
    ['pCode','pNameEn','pNameZh','pClient','pClient2','pMc','pNotes','pQuotationNo',
      'pAccountCode','pJobNo','pTenderSum','pAnticipatedProfitPct',
      'pMcCommence','pMpCommence','pCompletionDate','pPcCertDate','pExtendedCompletion',
      'pConstructionDays','pDlpMonths',
      'pRetentionPct','pRetentionMaxPct','pRetentionMaxAmt',
      'pRetentionDateOneOff','pRetentionDateFirstHalf','pRetentionDateSecondHalf',
      'pDlpCertDate','pMpFacDate'].forEach(id => this._set(id, ''));
    this._loadPersonFields(null, '');
    await this._loadQsField('');
    this._set('pAmt', '');
    this._set('pLabour', '');
    document.getElementById('pStatus').value = 'Active';
    this._setRetentionFields(null);
    this._setMpCodes([]);
    this._setCategoryFields(null);
    this._projDocs = [];
    this._renderProjDocLists();
    document.getElementById('projectModal').classList.add('open');
  },

  async openEdit(id, tab) {
    await this.ensureCategoryTree();
    const p = await api('GET', `/projects/${id}`);
    if (!p) return;
    document.getElementById('projModalTitle').textContent = '編輯項目';
    document.getElementById('projModalId').value = p.id;
    const code = p.project_code || '';
    this._editOriginalCode = code;
    this._set('pCode', code);
    this._set('pQuotationNo', p.quotation_no || '');
    await this._loadPersonFields(null, p.person_in_charge || p.project_manager || '');
    this._set('pNameEn', p.project_name_en || '');
    this._set('pNameZh', p.project_name_zh || '');
    if (!p.project_name_en && !p.project_name_zh && p.project_name) {
      const parts = projectNameParts(p);
      this._set('pNameEn', parts.en);
      this._set('pNameZh', parts.zh);
    }
    this._set('pClient', p.client || '');
    this._set('pClient2', p.client_secondary || '');
    this._set('pMc', p.main_contractor || '');
    this._set('pAmt', p.contract_amount || '');
    this._set('pLabour', p.labour_allocation || '');
    document.getElementById('pStatus').value = p.status || 'Active';
    this._set('pNotes', p.notes || '');
    await this._fillCoverFields(p);
    this._setCategoryFields(p);
    if (!p.category_l2_code) await this._maybeSuggestCategory(id);
    await this._loadProjDocuments(p.id);
    document.getElementById('projectModal').classList.add('open');
    if (tab === 'cover') this.switchTab('cover');
  },

  closeModal() {
    document.getElementById('projectModal').classList.remove('open');
  },

  async saveModal() {
    const id = document.getElementById('projModalId').value;
    const data = this._readFormData();
    const code = data.project_code;
    if (!code) { toast('請輸入項目代碼', 'warning'); return; }
    if (id && this._editOriginalCode && code !== this._editOriginalCode) {
      const ok = confirm(
        `項目代碼將由「${this._editOriginalCode}」改為「${code}」\n` +
        '這會同時更新 Master List 配對。確定？'
      );
      if (!ok) return;
    }

    try {
      if (id) {
        await api('PUT', `/projects/${id}`, data);
        toast('項目已更新', 'success');
      } else {
        await api('POST', '/projects', data);
        toast('項目已新增', 'success');
      }
      this.closeModal();
      await App.loadProjects();
      if (id && App.currentProject?.id == id) await App.selectProject(id);
      await Projects.load();
      if (this._settleProjectId && String(this._settleProjectId) === String(id)) {
        await this.loadSettlement();
      }
    } catch (e) {}
  },

  async delete(id, code) {
    if (!confirm(`確認刪除項目「${code}」？\n此操作將同時刪除所有相關判項及付款登記！`)) return;
    await api('DELETE', `/projects/${id}`);
    toast('項目已刪除', 'success');
    if (App.currentProject?.id == id) {
      App.currentProject = null;
      App.scList = [];
    }
    await App.loadProjects();
  },

  pickFromMaster() {
    document.getElementById('projMasterSearch').value = '';
    document.getElementById('projMasterPickBody').innerHTML =
      '<tr><td colspan="5" class="td-muted" style="padding:24px;text-align:center">輸入關鍵字搜尋</td></tr>';
    document.getElementById('projMasterPickModal').classList.add('open');
  },

  closeMasterPick() {
    document.getElementById('projMasterPickModal').classList.remove('open');
  },

  async searchMasterPick() {
    const q = document.getElementById('projMasterSearch')?.value.trim() || '';
    const params = new URLSearchParams({ limit: 30, offset: 0 });
    if (q) params.set('q', q);
    const data = await api('GET', `/master/quotations?${params}`);
    const tbody = document.getElementById('projMasterPickBody');
    if (!data?.items?.length) {
      tbody.innerHTML = '<tr><td colspan="5" class="td-muted" style="padding:24px;text-align:center">沒有結果</td></tr>';
      return;
    }
    tbody.innerHTML = data.items.map(r => {
      const desc = escHtml((r.description || '').slice(0, 40));
      return `<tr>
        <td class="td-mono">${escHtml(r.quotation_no)}</td>
        <td>${fmtMasterPerson(r)}</td>
        <td>${escHtml(r.site_name || '—')}</td>
        <td class="td-muted">${desc}</td>
        <td><button type="button" class="btn btn-primary btn-sm" onclick="Projects.applyMasterPick(${r.id})">選擇</button></td>
      </tr>`;
    }).join('');
  },

  async applyMasterPick(rowId) {
    const row = await api('GET', `/master/item?id=${rowId}`);
    if (!row) return;
    const cur = document.getElementById('pCode').value.trim();
    if (cur && cur !== row.quotation_no) {
      const ok = confirm(
        `目前項目代碼：${cur}\n` +
        `將改為 Master List：${row.quotation_no}\n` +
        `（${row.site_name || row.description || ''}）\n\n確定帶入？`
      );
      if (!ok) return;
    }
    document.getElementById('pCode').value = row.quotation_no;
    document.getElementById('pQuotationNo').value = row.quotation_no;
    await this._loadPersonFields(null, row.person_in_charge || '');
    if (row.site_name && !document.getElementById('pNameZh').value) {
      document.getElementById('pNameZh').value = row.site_name;
    }
    if (row.client_name && !document.getElementById('pClient').value) {
      document.getElementById('pClient').value = row.client_name;
    }
    if (row.awarded_amount && !document.getElementById('pAmt').value) {
      document.getElementById('pAmt').value = row.awarded_amount;
    }
    this.closeMasterPick();
    toast('已帶入報價資料', 'success');
  },

  async _loadPersonFields(selectedStaffId, selectedName) {
    await StaffRoster.load(true);
    const sel = document.getElementById('pPersonSelect');
    const staffId = selectedStaffId
      || (StaffRoster.findByName(selectedName)?.id ?? null);
    StaffRoster.fillPersonSelect(sel, { selectedStaffId: staffId, selectedName });
  },

  async openSettlement(projectId) {
    this._settleProjectId = projectId;
    await App.selectProject(projectId);
    App.navigate('project-settlement');
    await this.loadSettlement();
  },

  backToList() {
    App.navigate('projects');
  },

  async goToMainConFac() {
    const pid = this._settleProjectId || App.currentProject?.id;
    if (pid) await App.selectProject(pid);
    App.navigate('main-con-fac');
  },

  async goToScFac() {
    const pid = this._settleProjectId || App.currentProject?.id;
    if (pid) await App.selectProject(pid);
    App.navigate('sc-fac');
  },

  async loadSettlement() {
    const pid = this._settleProjectId;
    const body = document.getElementById('settleBody');
    if (!pid || !body) return;
    body.innerHTML = '<div class="empty-state" style="padding:40px">載入中...</div>';

    const [cover, scList, summary, project] = await Promise.all([
      api('GET', `/projects/${pid}/cover-page`),
      api('GET', `/projects/${pid}/subcontractors`),
      api('GET', `/reports/summary/${pid}`),
      api('GET', `/projects/${pid}`),
    ]);
    if (!cover) {
      body.innerHTML = '<div class="empty-state" style="padding:40px">項目不存在</div>';
      return;
    }
    this._settleCover = cover;
    const s = cover.settlement || {};
    const calc = summary?.contract_calc || {};
    const id = cover.summary || {};
    const titleEl = document.getElementById('settlePageTitle');
    const subEl = document.getElementById('settlePageSub');
    if (titleEl) titleEl.textContent = id.main_contract_title || cover.identity?.main_contract_title_zh || '項目金額結算';
    if (subEl) {
      subEl.textContent = [
        id.mp_contract_code || cover.identity?.mp_contract_code,
        id.account_code || cover.identity?.account_code,
        id.client || cover.identity?.client,
      ].filter(Boolean).join(' · ') || '—';
    }

    const bItems = (scList || []).filter(x => !x.is_excluded);
    const excludedItems = (scList || []).filter(x => x.is_excluded);
    const labour = calc.labour_allocation ?? project?.labour_allocation ?? s.labour_allocation ?? 0;

    const bRows = bItems.map((x, i) => `
      <tr><td class="td-muted">(${i + 1})</td><td>${fmtRefNo(x.sc_no)}</td>
      <td>${escHtml(formatCompanyPrimary(x.company_name_en, x.company_name_zh))}</td>
      <td class="td-amount ${amtClass(x.contract_amount, 'expense')}">${fmtExpense(x.contract_amount)}</td></tr>`).join('');

    const storedManualC = project?.material_other_expenses;

    body.innerHTML = `
      <div class="settle-grid">
        <div>
          <div class="section-title" style="margin-bottom:10px">合約金額結算</div>
          ${contractCalcTableHtml(calc)}
        </div>
        <div class="settle-side">
          <div class="form-group">
            <label class="form-label">覆寫 C — 物料及其他支出 (HK$)</label>
            <input type="number" class="form-input" id="settleMaterialC" placeholder="留空則自動計算" step="0.01"
              value="${storedManualC != null && storedManualC !== '' ? storedManualC : ''}">
            <div class="form-hint">Cover Page 結算用；含 M/O 判項、除外 (C) 扣減（不含上表人工分攤）</div>
          </div>
          <div class="form-group">
            <label class="form-label">財務會作調撥（人工分攤）(HK$)</label>
            <input type="number" class="form-input" id="settleLabour" placeholder="0" step="0.01"
              value="${project?.labour_allocation ?? labour ?? ''}">
            <div class="form-hint">與項目編輯表單「待辦」欄位同步</div>
          </div>
          <div class="form-group">
            <label class="form-label">結算工程總額 (HK$)</label>
            <input type="number" class="form-input" id="settleFinalSub" step="0.01"
              value="${project?.final_subcontract_sum ?? s.final_subcontract_sum ?? s.subcontract_sum_b ?? ''}">
          </div>
          <div class="form-group">
            <label class="form-label">分判商工程帳目總結算日</label>
            <input type="date" class="form-input" id="settleScFacDate" value="${project?.sc_fac_signed_date || ''}">
          </div>
        </div>
      </div>
      ${bItems.length ? `
      <div class="section-title" style="margin-top:20px">(B) 分判及代支小計明細</div>
      <div class="table-wrap" style="border:none;border-radius:0">
        <table><thead><tr><th></th><th>判項</th><th>公司</th><th class="td-amount">金額</th></tr></thead>
        <tbody>${bRows}</tbody></table>
      </div>` : ''}
      ${excludedItems.length ? `
      <div class="section-title" style="margin-top:16px">(C) 除外合約收費項目</div>
      <div class="table-wrap" style="border:none;border-radius:0">
        <table><thead><tr><th>判項</th><th>公司</th><th class="td-amount">金額</th></tr></thead>
        <tbody>${excludedItems.map(x => `
          <tr><td>${fmtRefNo(x.sc_no)}</td><td>${escHtml(formatCompanyPrimary(x.company_name_en, x.company_name_zh))}</td>
          <td class="td-amount ${amtClass(-Math.abs(x.contract_amount || 0), 'expense')}">${fmtExpense(-Math.abs(x.contract_amount || 0))}</td></tr>`).join('')}
        </tbody></table>
      </div>` : ''}
      <div class="section-title" style="margin-top:16px">財務會作調撥（人工分攤）</div>
      <div class="table-wrap" style="border:none;border-radius:0">
        <table><tbody>
          <tr><td class="td-muted">財務會作調撥（人工分攤）</td>
          <td class="td-amount ${amtClass(labour, 'expense')}">${fmtExpense(labour)}</td></tr>
        </tbody></table>
      </div>
      <div class="card settle-fac-hub" style="margin-top:20px">
        <div class="card-header">
          <div class="card-title">Final Account · 最終結算</div>
          <div class="card-sub">本頁 = PPT 第5頁項目金額結算（進行中監控）；對外結算書請用下方專頁</div>
        </div>
        <div class="card-body settle-fac-hub-body">
          <p class="settle-fac-hub-desc">主合約工程帳目總結算 (A–K)、分判每判項 PDF（3 頁含簽名欄）已獨立於左欄「最終結算」模組。</p>
          <div class="settle-fac-hub-actions">
            <button type="button" class="btn btn-secondary btn-sm" onclick="Projects.goToMainConFac()">📑 主合約最終結算</button>
            <button type="button" class="btn btn-secondary btn-sm" onclick="Projects.goToScFac()">📋 分判最終結算</button>
          </div>
        </div>
      </div>
    `;
  },

  async saveSettlement() {
    const pid = this._settleProjectId;
    if (!pid) return;
    const project = await api('GET', `/projects/${pid}`);
    if (!project) return;

    const matRaw = document.getElementById('settleMaterialC')?.value;
    const labourRaw = document.getElementById('settleLabour')?.value;
    const data = {
      ...project,
      material_other_expenses: matRaw === '' || matRaw == null ? null : parseFloat(matRaw),
      labour_allocation: labourRaw === '' || labourRaw == null ? 0 : parseFloat(labourRaw),
      final_subcontract_sum: parseFloat(document.getElementById('settleFinalSub')?.value) || 0,
      sc_fac_signed_date: document.getElementById('settleScFacDate')?.value || null,
    };

    try {
      await api('PUT', `/projects/${pid}`, data);
      toast('結算資料已儲存', 'success');
      await App.selectProject(pid);
      await this.loadSettlement();
      await App.loadProjects();
      await Projects.load();
    } catch (e) {}
  },
};

/* ─── sc.js (在同一文件) — 分判及支出管理 ─────────────────────── */
const SC = {
  _descItems: [],
  _editSc: null,
  _quotationPdfRemoved: false,
  _pendingQuotationPdf: null,
  _pendingQuotationFilename: null,
  _pendingOcrId: null,
  _msCHintTimer: null,
  _scNoManual: false,
  _msCRows: [],
  _msCApplied: null,

  _esc(s) {
    return String(s ?? '')
      .replace(/&/g, '&amp;')
      .replace(/"/g, '&quot;')
      .replace(/</g, '&lt;');
  },

  _isContractType() {
    return document.getElementById('scEntryType')?.value === 'contract';
  },

  onEntryTypeChange() {
    const isContract = this._isContractType();
    const quotLabel = document.getElementById('scQuotNoLabel');
    const quotDateWrap = document.getElementById('scQuotDateWrap');
    const retentionWrap = document.getElementById('scRetentionWrap');
    const paidRow = document.getElementById('scPaidRow');
    const oaStatusRow = document.getElementById('scOaStatusRow');
    const quotNo = document.getElementById('scQuotNo');
    if (quotLabel) quotLabel.textContent = isContract ? '合約編號' : '報價單號';
    if (quotNo) quotNo.placeholder = isContract ? '合約編號' : 'Q-001';
    if (quotDateWrap) quotDateWrap.hidden = isContract;
    if (retentionWrap) retentionWrap.hidden = !isContract;
    if (paidRow) paidRow.hidden = isContract;
    if (oaStatusRow) oaStatusRow.hidden = isContract;
    if (isContract) {
      document.getElementById('scQuotDate').value = '';
    } else {
      document.getElementById('scRetentionSum').value = '';
    }
  },

  _entryTypeLabel(type) {
    return type === 'contract' ? '分判合約' : '報價單';
  },

  _parseScPrefix(scNo) {
    const m = /^(SC|M|O)-/i.exec((scNo || '').trim());
    return m ? m[1].toUpperCase() : null;
  },

  _nextScNoForPrefix(prefix) {
    prefix = (prefix || 'SC').toUpperCase();
    if (!['SC', 'M', 'O'].includes(prefix)) prefix = 'SC';
    let maxMain = 0;
    let count = 0;
    (App.scList || []).forEach(s => {
      const m = /^(SC|M|O)-(\d+)/i.exec((s.sc_no || '').trim());
      if (!m || m[1].toUpperCase() !== prefix) return;
      count += 1;
      maxMain = Math.max(maxMain, parseInt(m[2], 10) || 0);
    });
    return {
      prefix,
      last: maxMain ? `${prefix}-${String(maxMain).padStart(3, '0')}` : null,
      next: `${prefix}-${String(maxMain + 1).padStart(3, '0')}`,
      count,
    };
  },

  _setScNoHint(info) {
    const hint = document.getElementById('scNoHint');
    if (!hint || !info) return;
    if (info.last) {
      hint.textContent = `本項目 ${info.prefix} 已用至 ${info.last}（${info.count} 項），下一號 ${info.next}`;
    } else {
      hint.textContent = `本項目尚無 ${info.prefix} 編號，建議由 ${info.next} 開始`;
    }
  },

  suggestNextScNo(force = false) {
    const prefixEl = document.getElementById('scNoPrefix');
    const input = document.getElementById('scNo');
    if (!prefixEl || !input) return;
    const info = this._nextScNoForPrefix(prefixEl.value);
    this._setScNoHint(info);
    if (this._editSc && !force) return;
    if (this._scNoManual && !force) return;
    input.value = info.next;
    this._scNoManual = false;
  },

  onScPrefixChange() {
    this._scNoManual = false;
    this.suggestNextScNo(true);
    this.scheduleMsCHint();
  },

  onScNoInput() {
    this._scNoManual = true;
    const parsed = this._parseScPrefix(document.getElementById('scNo')?.value);
    const prefixEl = document.getElementById('scNoPrefix');
    if (parsed && prefixEl && prefixEl.value !== parsed) {
      prefixEl.value = parsed;
      this._setScNoHint(this._nextScNoForPrefix(parsed));
    }
    this.scheduleMsCHint();
  },

  _projectCoreFromCurrent() {
    const p = App.currentProject || {};
    const raws = [p.quotation_no, p.project_code, p.mp_contract_code, p.job_no];
    for (const raw of raws) {
      if (!raw) continue;
      let t = String(raw).trim().toUpperCase().replace(/[/-]/g, '_').replace(/_+/g, '_');
      let m = t.match(/^(MS_Q\d+_\d+)/);
      if (m) return m[1];
      m = t.match(/^Q(\d+_\d+)/);
      if (m) return `MS_Q${m[1]}`;
    }
    return '';
  },

  async loadMsCOptions() {
    const list = document.getElementById('scMsContractList');
    if (!list) return;
    const core = this._projectCoreFromCurrent();
    let rows = [];
    try {
      if (core) {
        const data = await api('GET', `/sc-contract-registry?project_core=${encodeURIComponent(core)}`, null, { silent: true });
        rows = data?.rows || [];
      }
      if (rows.length < 8) {
        const extra = await api('GET', '/sc-contract-registry', null, { silent: true });
        const seen = new Set(rows.map(r => r.sub_contract_no));
        (extra?.rows || []).forEach(r => {
          if (r.sub_contract_no && !seen.has(r.sub_contract_no)) {
            seen.add(r.sub_contract_no);
            rows.push(r);
          }
        });
      }
    } catch (e) {
      rows = [];
    }
    this._msCRows = rows;
    list.innerHTML = rows.slice(0, 400).map(r => {
      const no = this._esc(r.sub_contract_no || '');
      const extra = [r.company, r.works].filter(Boolean).join(' · ');
      const label = extra ? `${no} — ${this._esc(extra)}` : no;
      return `<option value="${no}" label="${label}">`;
    }).join('');
  },

  _looksChinese(s) {
    return /[\u4e00-\u9fff]/.test(s || '');
  },

  _applyMsCRow(row) {
    const zhEl = document.getElementById('scCompanyZh');
    const enEl = document.getElementById('scCompanyEn');
    const titleEl = document.getElementById('scDescTitle');
    if (!row) return;
    const prev = this._msCApplied || {};
    const company = (row.company || '').trim();
    const works = (row.works || '').trim();
    const nextZh = this._looksChinese(company) ? company : '';
    const nextEn = nextZh ? '' : company;

    const fillIfAuto = (el, nextVal, prevVal) => {
      if (!el) return;
      const cur = (el.value || '').trim();
      if (!nextVal && !prevVal) return;
      if (!cur || cur === prevVal) el.value = nextVal || '';
    };
    fillIfAuto(zhEl, nextZh, prev.companyZh);
    fillIfAuto(enEl, nextEn, prev.companyEn);
    fillIfAuto(titleEl, works, prev.descTitle);

    this._msCApplied = {
      sub_contract_no: row.sub_contract_no,
      companyZh: (zhEl?.value || '').trim(),
      companyEn: (enEl?.value || '').trim(),
      descTitle: (titleEl?.value || '').trim(),
    };
  },

  onMsCInput() {
    const val = document.getElementById('scMsContractNo')?.value?.trim() || '';
    const row = (this._msCRows || []).find(r => (r.sub_contract_no || '') === val);
    if (row) this._applyMsCRow(row);
    this.scheduleMsCHint();
  },

  scheduleMsCHint() {
    clearTimeout(this._msCHintTimer);
    this._msCHintTimer = setTimeout(() => this.updateMsCHint(), 350);
  },

  async updateMsCHint() {
    const hint = document.getElementById('scMsContractHint');
    if (!hint) return;
    const p = App.currentProject;
    const manual = document.getElementById('scMsContractNo')?.value?.trim() || '';
    if (!p) {
      hint.textContent = '請先選擇項目';
      hint.className = 'form-hint';
      return;
    }
    if (manual) {
      hint.textContent = '已手動指定 MS/C（優先於 MS/C 自動配對）';
      hint.className = 'form-hint sc-ms-c-hint-manual';
      return;
    }
    hint.textContent = '配對中…';
    hint.className = 'form-hint';
    try {
      const payload = {
        sc_no: document.getElementById('scNo')?.value?.trim() || null,
        company_name_en: document.getElementById('scCompanyEn')?.value?.trim() || null,
        company_name_zh: document.getElementById('scCompanyZh')?.value?.trim() || null,
        description: this.buildDescText(),
        contract_amount: parseFloat(document.getElementById('scAmt')?.value) || 0,
        contract_sum: parseFloat(document.getElementById('scContractSum')?.value) || 0,
        quotation_no: document.getElementById('scQuotNo')?.value?.trim() || null,
        sub_contract_no: null,
      };
      const r = await api('POST', `/projects/${p.id}/subcontractors/ms-c-resolve`, payload);
      const resolved = r?.resolved || '—';
      if (resolved !== '—') {
        hint.textContent = `MS/C 自動配對：${resolved}（儲存後用於 P1 PDF）`;
        hint.className = 'form-hint sc-ms-c-hint-ok';
      } else {
        hint.textContent = 'MS/C 尚未配對；可手動填寫或至「分判合約編號表」維護';
        hint.className = 'form-hint sc-ms-c-hint-warn';
      }
    } catch (e) {
      hint.textContent = 'P1 PDF「Sub-Contracts No.」專用；留空則從分判合約編號表自動配對';
      hint.className = 'form-hint';
    }
  },

  _loadDescFromText(text) {
    const parsed = parseDescriptionItems(text);
    if (parsed.items.length) {
      this._descItems = parsed.items.map((it, i) => ({
        no: it.no || String(i + 1),
        description: it.description || '',
        qty: it.qty != null ? String(it.qty) : '',
        unit: it.unit || '',
        unit_price: it.unit_price != null ? String(it.unit_price) : '',
        amount: it.amount != null ? String(it.amount) : '',
      }));
      document.getElementById('scDescTitle').value = parsed.title || '';
    } else {
      this._descItems = [];
      document.getElementById('scDescTitle').value = parsed.plain || parsed.title || '';
    }
    this.renderDescItems();
  },

  renderDescItems() {
    const tbody = document.getElementById('scItemsBody');
    if (!tbody) return;

    if (!this._descItems.length) {
      tbody.innerHTML = '<tr><td colspan="7" class="ocr-items-empty">尚無明細，可新增項目或於摘要填寫簡述</td></tr>';
      this._updateDescItemsTotal();
      return;
    }

    tbody.innerHTML = this._descItems.map((it, idx) => `
      <tr data-idx="${idx}">
        <td><input type="text" value="${this._esc(it.no)}" data-field="no" oninput="SC.onDescItemChange()"></td>
        <td><input type="text" value="${this._esc(it.description)}" data-field="description" oninput="SC.onDescItemChange()"></td>
        <td><input type="text" value="${this._esc(it.qty)}" data-field="qty" oninput="SC.onDescItemChange()"></td>
        <td><input type="text" value="${this._esc(it.unit)}" data-field="unit" oninput="SC.onDescItemChange()"></td>
        <td><input type="number" value="${it.unit_price}" data-field="unit_price" step="0.01" oninput="SC.onDescItemChange()"></td>
        <td><input type="number" value="${it.amount}" data-field="amount" step="0.01" oninput="SC.onDescItemChange()"></td>
        <td><button type="button" class="btn-del" onclick="SC.removeDescItem(${idx})" title="刪除">×</button></td>
      </tr>
    `).join('');

    this._updateDescItemsTotal();
  },

  _updateDescItemsTotal() {
    const totalEl = document.getElementById('scItemsTotal');
    if (!totalEl) return;
    let sum = 0;
    this._descItems.forEach(it => {
      const a = parseFloat(it.amount);
      if (!isNaN(a)) sum += a;
    });
    totalEl.innerHTML = this._descItems.length
      ? `明細合計: <strong>${fmt(sum)}</strong> (${this._descItems.length} 項)`
      : '';
  },

  readDescItemsFromDom(keepEmpty = false) {
    const rows = document.querySelectorAll('#scItemsBody tr[data-idx]');
    const items = [];
    rows.forEach((row, i) => {
      const get = (field) => row.querySelector(`[data-field="${field}"]`)?.value?.trim() ?? '';
      const desc = get('description');
      if (!keepEmpty && !desc && !get('amount') && !get('qty') && !get('unit') && !get('unit_price')) return;
      items.push({
        no: get('no') || String(i + 1), description: desc,
        qty: get('qty'), unit: get('unit'),
        unit_price: get('unit_price'), amount: get('amount'),
      });
    });
    this._descItems = items;
    return items;
  },

  onDescItemChange() {
    this.readDescItemsFromDom(true);
    this._updateDescItemsTotal();
  },

  addDescItem() {
    const tbody = document.getElementById('scItemsBody');
    if (tbody?.querySelector('.ocr-items-empty')) tbody.innerHTML = '';
    const n = this._descItems.length + 1;
    this._descItems.push({ no: String(n), description: '', qty: '', unit: '', unit_price: '', amount: '' });
    this.renderDescItems();
  },

  removeDescItem(idx) {
    this._descItems.splice(idx, 1);
    this.renderDescItems();
  },

  buildDescText() {
    this.readDescItemsFromDom();
    const title = document.getElementById('scDescTitle')?.value?.trim() || '';
    if (!this._descItems.length) return title || null;
    return buildDescriptionText(this._descItems, title);
  },

  _renderDocToolbar(s) {
    const bar = document.getElementById('scDocToolbar');
    if (!bar) return;
    if (!s && !this._pendingQuotationPdf && !this._quotationPdfRemoved) {
      bar.innerHTML = '<span class="sc-doc-none">尚無 PDF 存證</span>';
      return;
    }
    const docs = s?.documents || [];
    const items = [];
    const seen = new Set();
    const push = (file_path, label, when, removable = false) => {
      if (!file_path || seen.has(file_path)) return;
      seen.add(file_path);
      items.push({ file_path, label, when, removable });
    };
    const activePdf = this._pendingQuotationPdf
      || (s?.quotation_saved && !this._quotationPdfRemoved ? s.quotation_saved : null);
    if (activePdf) {
      const when = this._pendingQuotationPdf
        ? (document.getElementById('scQuotDate')?.value || s?.quotation_date)
        : s?.quotation_date;
      push(activePdf, '報價 PDF', when, true);
    }
    docs.forEach(d => {
      const kind = { quotation: '報價', invoice: '發票', scan: '掃描' }[d.doc_type] || '存證';
      push(d.file_path, `${kind} PDF`, d.created_at, false);
    });
    if (!items.length) {
      const hint = this._quotationPdfRemoved
        ? '報價 PDF 已移除（可按「上傳 PDF」或儲存後再處理）'
        : '尚無 PDF 存證';
      bar.innerHTML = `<span class="sc-doc-none">${hint}</span>`;
      return;
    }
    bar.innerHTML = items.map(d => {
      const when = d.when ? fmtDate(d.when) : '';
      const title = `${d.label}${when ? ` · ${when}` : ''}`;
      const removeBtn = d.removable
        ? `<button type="button" class="sc-pdf-remove" title="移除報價 PDF">×</button>`
        : '';
      return `<span class="sc-pdf-chip-wrap"><button type="button" class="sc-pdf-chip"
        data-path="${this._esc(d.file_path)}"
        data-title="${this._esc(title)}"
        title="預覽 ${this._esc(d.label)}">
        <span class="sc-pdf-icon">📄</span>
        <span class="sc-pdf-label">${this._esc(d.label)}${when ? ` · ${when}` : ''}</span>
      </button>${removeBtn}</span>`;
    }).join('');

    if (!bar.dataset.docBound) {
      bar.dataset.docBound = '1';
      bar.addEventListener('click', (e) => {
        if (e.target.closest('.sc-pdf-remove')) {
          e.preventDefault();
          e.stopPropagation();
          this.removeQuotationPdf();
          return;
        }
        const btn = e.target.closest('.sc-pdf-chip');
        if (!btn) return;
        e.preventDefault();
        e.stopPropagation();
        const path = btn.getAttribute('data-path');
        const title = btn.getAttribute('data-title') || '文件預覽';
        if (path) DocViewer.open(path, title);
      });
    }
  },

  removeQuotationPdf() {
    const hasPdf = this._pendingQuotationPdf
      || (this._editSc?.quotation_saved && !this._quotationPdfRemoved);
    if (!hasPdf) return;
    if (!confirm('移除報價 PDF 連結？\n\n已上傳的編輯中檔案會取消；已儲存檔案須按「儲存」才會正式移除。\n\n確定移除？')) return;
    this._quotationPdfRemoved = true;
    this._pendingQuotationPdf = null;
    this._pendingQuotationFilename = null;
    this._pendingOcrId = null;
    if (this._editSc) this._editSc.quotation_saved = null;
    this._renderDocToolbar(this._editSc);
    toast('報價 PDF 已標記移除，請按儲存', 'info');
  },

  _resolveOcrLineItems(ex, rawText) {
    if (!ex) return [];
    const items = ex.line_items || [];
    if (items.length) return items;
    if (ex.description && ex.description.includes('\t')) {
      const parsed = OCR.parseDescriptionTable(ex.description);
      if (parsed.length) return parsed;
    }
    return OCR.parseRawLineItems(rawText || '');
  },

  applyOcrExtracted(ex, rawText) {
    if (!ex) return 0;
    const quotNo = (ex.quotation_no || '').trim();
    if (quotNo) document.getElementById('scQuotNo').value = quotNo;
    const quotDate = ex.quotation_date || ex.invoice_date || '';
    if (quotDate) document.getElementById('scQuotDate').value = quotDate;

    const companyEn = (ex.company_name_en || '').trim();
    const companyZh = (ex.company_name_zh || '').trim();
    const fallback = companyEn || companyZh;
    if (companyEn) {
      document.getElementById('scCompanyEn').value = companyEn;
    } else if (fallback && !/[\u4e00-\u9fff]/.test(fallback)) {
      document.getElementById('scCompanyEn').value = fallback;
    }
    if (companyZh) {
      document.getElementById('scCompanyZh').value = companyZh;
    } else if (fallback && /[\u4e00-\u9fff]/.test(fallback)) {
      document.getElementById('scCompanyZh').value = fallback;
    }

    const items = this._resolveOcrLineItems(ex, rawText);
    if (items.length) {
      this._descItems = items.map((it, i) => ({
        no: it.no || String(i + 1),
        description: it.description || '',
        qty: it.qty != null ? String(it.qty) : '',
        unit: it.unit || '',
        unit_price: it.unit_price != null ? String(it.unit_price) : '',
        amount: it.amount != null ? String(it.amount) : '',
      }));
      const titleEl = document.getElementById('scDescTitle');
      if (titleEl) {
        titleEl.value = items.length === 1
          ? (items[0].description || '')
          : ((ex.description || '').split('\n')[0] || '').trim();
      }
      this.renderDescItems();
    } else if (ex.description) {
      this._loadDescFromText(ex.description);
    }

    let amount = parseFloat(ex.total_amount || ex.amount) || 0;
    if (!amount && items.length) {
      amount = items.reduce((s, it) => s + (parseFloat(it.amount) || 0), 0);
    }
    if (amount) {
      const vo = parseFloat(document.getElementById('scVoAmt').value) || 0;
      document.getElementById('scContractSum').value = fmtInputNum(amount);
      document.getElementById('scAmt').value = fmtInputNum(amount + vo);
      const paidStr = document.getElementById('scPaidAmt').value;
      if (paidStr) {
        const paid = parseFloat(paidStr.replace(/[^0-9.-]/g, '')) || 0;
        document.getElementById('scRemainAmt').value = fmt(amount + vo - paid);
      }
    }
    return items.length;
  },

  pickQuotationPdf() {
    const input = document.getElementById('scPdfInput');
    if (!input) return;
    input.value = '';
    input.click();
  },

  async onQuotationPdfSelected(input) {
    const file = input?.files?.[0];
    if (!file) return;
    const ext = file.name.split('.').pop().toLowerCase();
    if (!['pdf', 'png', 'jpg', 'jpeg'].includes(ext)) {
      toast('請上傳 PDF、PNG 或 JPG', 'warning');
      return;
    }

    const p = App.currentProject;
    if (!p) { toast('請先選擇項目', 'warning'); return; }
    showLoading('OCR 識別中...');
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('project_id', p.id);
      const r = await fetch(`${API}/ocr/upload`, { method: 'POST', body: formData });
      const text = await r.text();
      let json;
      try {
        json = JSON.parse(text);
      } catch (e) {
        throw new Error(
          r.ok
            ? '伺服器回應格式錯誤'
            : `OCR 失敗 (${r.status})，請稍後再試`
        );
      }
      if (!json.success) throw new Error(json.error || 'OCR 失敗');
      const data = json.data;
      const pdfPath = data.pdf_path;
      const itemCount = this.applyOcrExtracted(data.extracted, data.raw_text);
      this._pendingQuotationPdf = pdfPath;
      this._pendingQuotationFilename = file.name;
      this._pendingOcrId = data.ocr_id || null;
      this._quotationPdfRemoved = false;
      if (this._editSc) this._editSc.quotation_saved = pdfPath;
      this._renderDocToolbar(this._editSc);
      const methodLabels = {
        gemini: 'Gemini',
        quark_handwritten: '夸克手寫',
        quark_general: '夸克通用',
        quark_invoice: '夸克發票',
        rapidocr: 'RapidOCR',
        pymupdf: 'PDF 文字',
        pdfplumber: 'PDF 文字',
      };
      const method = methodLabels[data.method] || data.method || 'OCR';
      if (itemCount) {
        toast(`${method} 完成，已識別 ${itemCount} 項明細，請確認後儲存`, 'success');
      } else if (data.extracted?.total_amount || data.extracted?.amount) {
        toast(`${method} 完成，已填入金額，請確認後儲存`, 'success');
      } else if (data.extracted) {
        toast(`${method} 完成，部分欄位已填入，請確認後儲存`, 'info');
      } else {
        toast('PDF 已上傳，未能識別內容，請手動填寫', 'warning');
      }
      if (data.error) toast(data.error, 'warning');
    } catch (e) {
      toast(e.message || '上傳失敗', 'error');
    } finally {
      hideLoading();
      if (input) input.value = '';
    }
  },

  data: [],
  filtered: [],
  _payModalSc: null,
  _collapsedGroups: null,

  _groupKey(s) {
    return s.parent_sc_no || deriveParentScNo(s.sc_no) || s.sc_no;
  },

  _collapseKey(parent) {
    return `${App.currentProject?.id || 0}:${parent}`;
  },

  _ensureCollapseState() {
    if (this._collapsedGroups instanceof Set) return;
    try {
      const raw = localStorage.getItem('qs_sc_collapsed');
      this._collapsedGroups = raw ? new Set(JSON.parse(raw)) : new Set();
    } catch (e) {
      this._collapsedGroups = new Set();
    }
  },

  _saveCollapseState() {
    this._ensureCollapseState();
    localStorage.setItem('qs_sc_collapsed', JSON.stringify([...this._collapsedGroups]));
  },

  isGroupCollapsed(parent) {
    this._ensureCollapseState();
    return this._collapsedGroups.has(this._collapseKey(parent));
  },

  _listGroups(items) {
    return this._groupItems(items).filter(g => g.isGroup);
  },

  toggleGroup(parent, event) {
    if (event) event.stopPropagation();
    this._ensureCollapseState();
    const key = this._collapseKey(parent);
    if (this._collapsedGroups.has(key)) this._collapsedGroups.delete(key);
    else this._collapsedGroups.add(key);
    this._saveCollapseState();
    this.render();
  },

  expandAllGroups() {
    this._ensureCollapseState();
    const prefix = `${App.currentProject?.id || 0}:`;
    let n = 0;
    for (const key of [...this._collapsedGroups]) {
      if (key.startsWith(prefix)) {
        this._collapsedGroups.delete(key);
        n++;
      }
    }
    this._saveCollapseState();
    this.render();
    toast(n > 0 ? `已展開 ${n} 個分組` : '所有分組已展開', 'info');
  },

  collapseAllGroups() {
    const source = this.data.length ? this.data : this.filtered;
    const groups = this._listGroups(source);
    if (!groups.length) {
      toast('沒有可收合的分組', 'warning');
      return;
    }
    this._ensureCollapseState();
    for (const g of groups) {
      this._collapsedGroups.add(this._collapseKey(g.parent));
    }
    this._saveCollapseState();
    this.render();
    toast(`已收合 ${groups.length} 個分組`, 'info');
  },

  async load(switchSeq) {
    const p = App.currentProject;
    if (!p) {
      document.getElementById('scTableBody').innerHTML = `<tr><td colspan="8"><div class="empty-state" style="padding:40px">請先選擇項目</div></td></tr>`;
      return;
    }
    const projectId = p.id;
    this.data = await api('GET', `/projects/${projectId}/subcontractors`) || [];
    if (!App.currentProject || App.currentProject.id != projectId) return;
    if (switchSeq != null && switchSeq !== App._projectSwitchSeq) return;
    this.filtered = [...this.data];
    this.render();
  },

  search(val) {
    const q = val.toLowerCase();
    this.filtered = this.data.filter(s =>
      (s.sc_no || '').toLowerCase().includes(q) ||
      (s.company_name_en || '').toLowerCase().includes(q) ||
      (s.company_name_zh || '').includes(q) ||
      (s.description || '').toLowerCase().includes(q)
    );
    this.render();
  },

  _groupItems(items) {
    if (!items.length) return [];
    const sorted = [...items].sort((a, b) => {
      const ga = this._groupKey(a);
      const gb = this._groupKey(b);
      if (ga !== gb) return ga.localeCompare(gb, 'zh-Hant', { numeric: true });
      return (a.sc_no || '').localeCompare(b.sc_no || '', 'zh-Hant', { numeric: true });
    });
    const result = [];
    let i = 0;
    while (i < sorted.length) {
      const parent = this._groupKey(sorted[i]);
      const groupItems = [];
      while (i < sorted.length && this._groupKey(sorted[i]) === parent) {
        groupItems.push(sorted[i++]);
      }
      const isGroup = groupItems.length > 1;
      result.push({ parent, items: groupItems, isGroup });
    }
    return result;
  },

  _renderGroupHeader(g) {
    const totalRev = g.items.reduce((s, x) => s + (parseFloat(x.contract_amount) || 0), 0);
    const totalPaid = g.items.reduce((s, x) => s + (parseFloat(x.total_paid) || 0), 0);
    const company = formatCompanyPrimary(g.items[0].company_name_en, g.items[0].company_name_zh);
    const collapsed = this.isGroupCollapsed(g.parent);
    const parentAttr = (g.parent || '').replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    return `
      <tr class="sc-group-header" data-group-parent="${parentAttr}" onclick="SC.toggleGroup(this.getAttribute('data-group-parent'), event)" title="點擊收合/展開">
        <td colspan="2">
          <span class="sc-group-toggle" aria-hidden="true">${collapsed ? '▶' : '▼'}</span>
          ${fmtRefNo(g.parent)}
          <span class="badge badge-muted" style="margin-left:6px">${g.items.length} 項</span>
          ${collapsed ? '<span class="badge badge-info" style="margin-left:4px;font-size:10px">已收合</span>' : ''}
          <div style="font-size:11px;color:var(--text-muted);font-weight:400;margin-top:2px">${company}</div>
        </td>
        <td class="td-muted" style="font-size:11px">小計</td>
        <td class="td-amount">${fmt(totalRev)}</td>
        <td class="td-amount ${amtClass(totalPaid, 'expense')}">${fmtExpense(totalPaid)}</td>
        <td colspan="3"></td>
      </tr>`;
  },

  _renderRow(s, isChild) {
    const isContract = s.sc_entry_type === 'contract';
    const oaBadge = !isContract && (s.oa_status === 'OK' ? '<span class="badge badge-success">OK</span>' :
                    s.oa_status === '-'  ? '<span class="badge badge-muted">—</span>' :
                    s.oa_status          ? `<span class="badge badge-warning">${s.oa_status}</span>` : '—');
    const quotDateStr = !isContract && s.quotation_date ? fmtDate(s.quotation_date) : '';
    const oaDateStr = s.oa_date ? fmtDate(s.oa_date) : '';
    const voHint = (parseFloat(s.vo_amount) || 0) !== 0
      ? `<div style="font-size:10px;color:var(--text-muted)">H ${fmt(s.contract_sum)} + VO ${fmt(s.vo_amount)}</div>` : '';
    const scNoEsc = (s.sc_no || '').replace(/'/g, "\\'");
    const excludedCls = s.is_excluded ? ' sc-row-excluded' : '';
    const typeBadge = `<span class="badge badge-muted" style="font-size:9px;margin-left:4px">${this._entryTypeLabel(s.sc_entry_type)}</span>`;
    const refLine = isContract
      ? `<div>${s.quotation_no || '—'}</div>`
      : `<div>${s.quotation_no || '—'}</div>${quotDateStr ? `<div style="font-size:10px;color:var(--text-muted);margin-top:4px">報價 ${quotDateStr}</div>` : ''}`;
    const oaCol = isContract
      ? `${oaDateStr ? `<div style="font-size:11px">OA ${oaDateStr}</div>` : ''}${s.retention_sum != null && s.retention_sum !== '' ? `<div style="font-size:10px;color:var(--text-muted);margin-top:4px">Retention ${fmt(s.retention_sum)}</div>` : ''}`
      : `<div>${oaBadge}</div>${oaDateStr ? `<div style="font-size:10px;color:var(--text-muted);margin-top:4px">OA ${oaDateStr}</div>` : ''}`;
    return `
      <tr class="row-clickable${isChild ? ' sc-group-child' : ''}${excludedCls}" onclick="SC.showPayments(${s.id})" title="點擊查看付款登記">
        <td>${fmtRefNo(s.sc_no)}${typeBadge}${s.is_excluded ? ' <span class="badge badge-warning" style="font-size:10px">除外 (C)</span>' : ''}</td>
        <td class="td-company-name">${formatCompanyNameHtml(s.company_name_en, s.company_name_zh)}</td>
        <td class="td-muted">${s.description || '—'}</td>
        <td class="td-amount">${fmt(s.contract_amount)}${voHint}</td>
        <td class="td-amount ${amtClass(s.total_paid, 'expense')}">${fmtExpense(s.total_paid)}</td>
        <td style="font-size:11px;color:var(--text-secondary)">${refLine}</td>
        <td style="font-size:11px">${oaCol || '—'}</td>
        <td onclick="event.stopPropagation()">
          <div style="display:flex;gap:4px">
            <button class="btn btn-icon btn-secondary btn-sm" onclick="SC.openEdit(${s.id})">✏️</button>
            <button class="btn btn-icon btn-danger btn-sm" onclick="SC.delete(${s.id}, '${scNoEsc}')">🗑️</button>
          </div>
        </td>
      </tr>`;
  },

  render() {
    const tbody = document.getElementById('scTableBody');
    if (this.filtered.length === 0) {
      tbody.innerHTML = `<tr><td colspan="8"><div class="empty-state" style="padding:48px"><div class="empty-icon">📋</div><div class="empty-title">暫無合約／判項</div><div class="empty-sub">按「新增合約／判項」開始登記</div></div></td></tr>`;
      return;
    }
    const html = [];
    for (const g of this._groupItems(this.filtered)) {
      if (g.isGroup) html.push(this._renderGroupHeader(g));
      if (!g.isGroup || !this.isGroupCollapsed(g.parent)) {
        g.items.forEach(s => html.push(this._renderRow(s, g.isGroup)));
      }
    }
    tbody.innerHTML = html.join('');
    const countEl = document.getElementById('scCount');
    if (countEl) countEl.textContent = `${this.filtered.length} 項`;
  },

  calcRevised() {
    const h = parseFloat(document.getElementById('scContractSum').value) || 0;
    const v = parseFloat(document.getElementById('scVoAmt').value) || 0;
    document.getElementById('scAmt').value = fmtInputNum(h + v);
    const paidStr = document.getElementById('scPaidAmt').value;
    if (paidStr) {
      const paid = parseFloat(paidStr.replace(/[^0-9.-]/g, '')) || 0;
      document.getElementById('scRemainAmt').value = fmt(h + v - paid);
    }
  },

  openAdd() {
    this._editSc = null;
    this._quotationPdfRemoved = false;
    this._pendingQuotationPdf = null;
    this._pendingQuotationFilename = null;
    this._pendingOcrId = null;
    document.getElementById('scModalTitle').textContent = '新增合約／判項';
    document.getElementById('scModalId').value = '';
    document.getElementById('scEntryType').value = 'quotation';
    ['scNo','scQuotNo','scQuotDate','scMsContractNo','scCompanyEn','scCompanyZh','scDescTitle','scOaStatus','scOaNo','scPayNote','scRetentionSum'].forEach(id => document.getElementById(id).value = '');
    this._descItems = [];
    this.renderDescItems();
    this._renderDocToolbar(null);
    document.getElementById('scContractSum').value = '';
    document.getElementById('scVoAmt').value = '';
    document.getElementById('scAmt').value = '';
    document.getElementById('scOaDate').value = '';
    document.getElementById('scExcluded').checked = false;
    document.getElementById('scPaidAmt').value = '';
    document.getElementById('scRemainAmt').value = '';
    this._msCApplied = null;
    this._scNoManual = false;
    document.getElementById('scNoPrefix').value = 'SC';
    this.suggestNextScNo(true);
    this.loadMsCOptions();
    this.onEntryTypeChange();
    this.updateMsCHint();
    document.getElementById('scModal').classList.add('open');
  },

  async openEdit(id) {
    let s = this.data.find(x => x.id == id) || App.scList.find(x => x.id == id);
    if (!s) {
      try {
        s = await api('GET', `/subcontractors/${id}`);
      } catch (e) {
        return;
      }
    }
    if (!s) return;
    this._editSc = s;
    this._quotationPdfRemoved = false;
    this._pendingQuotationPdf = null;
    this._pendingQuotationFilename = null;
    this._pendingOcrId = null;
    document.getElementById('scModalTitle').textContent = `編輯 ${s.sc_no}`;
    document.getElementById('scModalId').value = s.id;
    document.getElementById('scEntryType').value = s.sc_entry_type || 'quotation';
    document.getElementById('scNo').value = s.sc_no || '';
    this._scNoManual = true;
    document.getElementById('scNoPrefix').value = this._parseScPrefix(s.sc_no) || 'SC';
    this._setScNoHint(this._nextScNoForPrefix(document.getElementById('scNoPrefix').value));
    this.loadMsCOptions();
    document.getElementById('scQuotNo').value = s.quotation_no || '';
    document.getElementById('scMsContractNo').value = s.sub_contract_no || '';
    document.getElementById('scCompanyEn').value = s.company_name_en || '';
    document.getElementById('scCompanyZh').value = s.company_name_zh || '';
    this._loadDescFromText(s.description || '');
    this._msCApplied = {
      sub_contract_no: s.sub_contract_no || '',
      companyZh: (s.company_name_zh || '').trim(),
      companyEn: (s.company_name_en || '').trim(),
      descTitle: document.getElementById('scDescTitle')?.value?.trim() || '',
    };
    this._renderDocToolbar(s);
    document.getElementById('scContractSum').value = fmtInputNum(s.contract_sum ?? s.contract_amount);
    document.getElementById('scVoAmt').value = fmtInputNum(s.vo_amount);
    document.getElementById('scAmt').value = fmtInputNum(s.contract_amount);
    const paid = parseFloat(s.total_paid) || 0;
    const ca = parseFloat(s.contract_amount) || 0;
    document.getElementById('scPaidAmt').value = fmt(paid);
    document.getElementById('scRemainAmt').value = fmt(ca - paid);
    document.getElementById('scQuotDate').value = s.quotation_date || '';
    document.getElementById('scOaDate').value = s.oa_date || '';
    document.getElementById('scOaStatus').value = s.oa_status || '';
    document.getElementById('scOaNo').value = s.oa_no || '';
    document.getElementById('scPayNote').value = s.payment_note || '';
    document.getElementById('scRetentionSum').value = fmtInputNum(s.retention_sum);
    document.getElementById('scExcluded').checked = !!s.is_excluded;
    this.onEntryTypeChange();
    this.updateMsCHint();
    document.getElementById('scModal').classList.add('open');
  },

  closeModal() {
    document.getElementById('scModal').classList.remove('open');
    this._editSc = null;
    this._quotationPdfRemoved = false;
    this._pendingQuotationPdf = null;
    this._pendingQuotationFilename = null;
    this._pendingOcrId = null;
  },

  async showPayments(id) {
    const p = App.currentProject;
    if (!p) { toast('請先選擇項目', 'warning'); return; }

    let s = this.data.find(x => x.id == id) || App.scList.find(x => x.id == id);
    if (!s) {
      try { s = await api('GET', `/subcontractors/${id}`); } catch (e) { return; }
    }
    if (!s) return;

    this._payModalSc = s;
    const paid = parseFloat(s.total_paid) || 0;
    const ca = parseFloat(s.contract_amount) || 0;
    const pending = ca - paid;
    const h = parseFloat(s.contract_sum) || 0;
    const vo = parseFloat(s.vo_amount) || 0;
    const hvoLine = (h || vo)
      ? `<div style="font-size:11px;color:var(--text-muted);margin-top:8px">Contract Sum ${fmt(h)} + VO ${fmt(vo)} = 修訂 ${fmt(ca)}</div>` : '';

    document.getElementById('scPayModalTitle').textContent = `${s.sc_no} — 付款登記`;
    const subParts = [s.company_name_en, s.company_name_zh].filter(Boolean);
    document.getElementById('scPayModalSub').textContent =
      subParts.join(' / ') || s.description || '';
    document.getElementById('scPaySummary').innerHTML = `
      <div style="display:flex;flex-wrap:wrap;gap:20px;font-size:12px">
        <div><span style="color:var(--text-muted)">修訂判項金額 (J)</span><br><strong>${fmt(ca)}</strong></div>
        <div><span style="color:var(--text-muted)">累計已付</span><br><strong class="${amtClass(paid, 'expense')}">${fmtExpense(paid)}</strong></div>
        <div><span style="color:var(--text-muted)">待付金額</span><br><strong style="color:${pending > 0 ? 'var(--warning)' : 'var(--text-primary)'}">${fmt(pending)}</strong></div>
        <div><span style="color:var(--text-muted)">付款登記</span><br><strong id="scPayCount">載入中...</strong></div>
      </div>${hvoLine}`;

    document.getElementById('scPayTableBody').innerHTML =
      `<tr><td colspan="9"><div class="empty-state" style="padding:32px">載入中...</div></td></tr>`;
    document.getElementById('scPayModal').classList.add('open');

    const payments = await api('GET',
      `/projects/${p.id}/payments?sc_no=${encodeURIComponent(s.sc_no)}`) || [];
    this._renderPayModal(payments, ca, paid, pending);
  },

  _renderPayModal(payments, ca, paid, pending) {
    const countEl = document.getElementById('scPayCount');
    if (countEl) countEl.textContent = `${payments.length} 條`;

    const tbody = document.getElementById('scPayTableBody');
    if (!payments.length) {
      const pendingFmt = fmt(Math.max(0, pending != null ? pending : ca - paid));
      tbody.innerHTML = `<tr><td colspan="9"><div class="empty-state" style="padding:40px">
        <div class="empty-icon">💰</div>
        <div class="empty-title">尚無付款登記</div>
        <div class="empty-sub" style="margin-top:8px">待付金額：<strong style="color:var(--warning)">${pendingFmt}</strong></div>
        <div class="empty-sub" style="margin-top:4px">此判項已建立，尚未錄入付款</div>
      </div></td></tr>`;
      return;
    }

    const sorted = [...payments].sort((a, b) => {
      const sa = parseFloat(a.seq_no) || a.id;
      const sb = parseFloat(b.seq_no) || b.id;
      return sa - sb;
    });

    tbody.innerHTML = sorted.map(r => {
      const remClass = amtClass(r.remainder_amount, 'expense');
      const paidClass = amtClass(r.paid_amount, 'expense');
      const oaBadge = r.oa_ref === 'OK' ? '<span class="badge badge-success">OK</span>' :
                      r.oa_ref === '-'  ? '<span class="badge badge-muted">—</span>' :
                      r.oa_ref          ? `<span class="badge badge-warning">${r.oa_ref}</span>` : '—';
      const pdfBtn = r.pdf_path
        ? `<button type="button" class="btn btn-icon btn-secondary btn-sm btn-view-pdf" title="查看原PDF" data-pdf-path="${String(r.pdf_path).replace(/"/g, '&quot;')}">📄</button>`
        : '';
      return `
        <tr class="row-clickable" onclick="SC.openPayEdit(${r.id})" title="點擊編輯">
          <td class="td-muted" style="font-size:11px">${r.seq_no || '—'}</td>
          <td class="td-muted">${fmtDate(r.invoice_date)}</td>
          <td class="td-mono td-muted" style="font-size:11px">${r.invoice_no || '—'}</td>
          <td class="td-muted" style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${r.description || ''}">${r.description || '—'}</td>
          <td class="td-amount">${fmt(r.contract_amount)}</td>
          <td class="td-amount ${paidClass}">${fmtExpense(r.paid_amount)}</td>
          <td class="td-amount ${remClass}">${fmtExpense(r.remainder_amount)}</td>
          <td>${oaBadge}</td>
          <td onclick="event.stopPropagation()">
            <div style="display:flex;gap:4px">
              ${pdfBtn}
              <button class="btn btn-icon btn-secondary btn-sm" title="編輯" onclick="SC.openPayEdit(${r.id})">✏️</button>
            </div>
          </td>
        </tr>`;
    }).join('');
  },

  closePayModal() {
    document.getElementById('scPayModal').classList.remove('open');
    this._payModalSc = null;
  },

  goToPayments() {
    const sc = this._payModalSc;
    if (!sc) return;
    const scNo = sc.sc_no;
    this.closePayModal();
    const sel = document.getElementById('payFilterSc');
    if (sel) sel.value = scNo;
    App.navigate('payments', { tab: 'records' });
  },

  openPayEdit(paymentId) {
    this.closePayModal();
    App.navigate('payments', { tab: 'records' });
    setTimeout(() => Payments.openEdit(paymentId), 150);
  },

  async saveModal() {
    const p = App.currentProject;
    if (!p) { toast('請先選擇項目', 'warning'); return; }
    const id = document.getElementById('scModalId').value;
    const scNo = document.getElementById('scNo').value.trim();
    if (!scNo) { toast('請輸入判項編號', 'warning'); return; }

    const entryType = document.getElementById('scEntryType').value || 'quotation';
    const isContract = entryType === 'contract';
    const data = {
      project_id: p.id,
      sc_no: scNo,
      sc_entry_type: entryType,
      quotation_no: document.getElementById('scQuotNo').value.trim() || null,
      sub_contract_no: document.getElementById('scMsContractNo').value.trim() || null,
      company_name_en: document.getElementById('scCompanyEn').value || null,
      company_name_zh: document.getElementById('scCompanyZh').value || null,
      description: this.buildDescText(),
      contract_sum: parseFloat(document.getElementById('scContractSum').value) || 0,
      vo_amount: parseFloat(document.getElementById('scVoAmt').value) || 0,
      contract_amount: parseFloat(document.getElementById('scAmt').value) || 0,
      quotation_date: isContract ? null : (document.getElementById('scQuotDate').value || null),
      oa_date: document.getElementById('scOaDate').value || null,
      retention_sum: isContract
        ? (parseFloat(document.getElementById('scRetentionSum').value) || null)
        : null,
      oa_status: isContract ? null : (document.getElementById('scOaStatus').value || null),
      oa_ref: null,
      oa_no: isContract ? null : (document.getElementById('scOaNo').value || null),
      quotation_saved: this._quotationPdfRemoved
        ? null
        : (this._pendingQuotationPdf || this._editSc?.quotation_saved || null),
      clear_quotation_pdf: this._quotationPdfRemoved || undefined,
      original_filename: this._pendingQuotationFilename || undefined,
      ocr_id: this._pendingOcrId || undefined,
      payment_note: document.getElementById('scPayNote').value || null,
      is_excluded: document.getElementById('scExcluded').checked ? 1 : 0,
    };

    try {
      await api('POST', '/subcontractors', data);
      toast('合約／判項已儲存', 'success');
      this.closeModal();
      // 刷新判項清單
      App.scList = await api('GET', `/projects/${p.id}/subcontractors`) || [];
      await this.load();
      Payments.populateScFilter();
      OCR.populateScOptions();
      if (App.currentPage === 'payments') Payments.setTab('sc');
    } catch (e) {}
  },

  async delete(id, scNo) {
    if (!confirm(`確認刪除判項 ${scNo}？`)) return;
    await api('DELETE', `/subcontractors/${id}`);
    toast('已刪除', 'success');
    const p = App.currentProject;
    if (p) App.scList = await api('GET', `/projects/${p.id}/subcontractors`) || [];
    await this.load();
    Payments.populateScFilter();
  }
};

ColPicker.attach(Projects, {
  columnsKey: 'PROJ_COLUMNS',
  storageKey: 'qs_proj_visible_cols',
  tableSelector: '.proj-summary-table',
  wrapId: 'projColPickerWrap',
  panelId: 'projColPickerPanel',
  hostName: 'Projects',
});
