/* ─── projects.js — 項目管理 ──────────────────────────── */
const Projects = {
  render(projects) {
    const container = document.getElementById('projectCards');
    if (!projects || projects.length === 0) {
      container.innerHTML = `
        <div class="empty-state" style="grid-column:1/-1;padding:64px">
          <div class="empty-icon">📁</div>
          <div class="empty-title">暫無項目</div>
          <div class="empty-sub">點擊「新增項目」或從Excel匯入</div>
        </div>`;
      return;
    }

    container.innerHTML = projects.map(p => {
      const statusClass = p.status === 'Active' ? 'success' :
                          p.status === 'Completed' ? 'info' : 'warning';
      const statusLabel = p.status === 'Active' ? '進行中' :
                          p.status === 'Completed' ? '已完成' : '暫停';
      const paid = p.total_paid || 0;
      const contractAmt = p.contract_amount || 0;
      const progress = contractAmt > 0 ? Math.min(100, (paid / contractAmt * 100)).toFixed(FMT_DECIMALS) : '0.00';

      return `
        <div class="card" style="cursor:pointer" onclick="App.selectProject(${p.id});App.navigate('dashboard')">
          <div class="card-body">
            <div style="display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:12px">
              <div>
                <div style="font-size:12px;color:var(--text-muted);font-family:monospace">${p.project_code}</div>
                <div style="font-size:14px;font-weight:700;margin-top:2px;line-height:1.3">
                  ${p.project_name ? p.project_name.substring(0, 50) + (p.project_name.length > 50 ? '...' : '') : p.project_code}
                </div>
              </div>
              <span class="badge badge-${statusClass}">${statusLabel}</span>
            </div>
            <div style="font-size:12px;color:var(--text-secondary);margin-bottom:12px">
              👤 ${p.client || '—'} &nbsp;|&nbsp; 🏗️ ${p.main_contractor?.substring(0,20) || '—'}
            </div>
            <div style="margin-bottom:8px">
              <div style="display:flex;justify-content:space-between;font-size:11px;color:var(--text-muted);margin-bottom:4px">
                <span>付款進度 ${progress}%</span>
                <span>${fmt(paid)} / ${fmt(contractAmt)}</span>
              </div>
              <div class="progress-bar-wrap">
                <div class="progress-bar" style="width:${progress}%"></div>
              </div>
            </div>
            <div style="display:flex;justify-content:space-between;align-items:center;margin-top:12px">
              <div style="font-size:11px;color:var(--text-muted)">
                📋 ${p.sc_count || 0} 個合同項目
              </div>
              <div style="display:flex;gap:6px" onclick="event.stopPropagation()">
                <button class="btn btn-secondary btn-sm" onclick="Projects.openEdit(${p.id})">✏️ 編輯</button>
                <button class="btn btn-danger btn-sm" onclick="Projects.delete(${p.id}, '${p.project_code}')">刪除</button>
              </div>
            </div>
          </div>
        </div>
      `;
    }).join('');
  },

  openAdd() {
    document.getElementById('projModalTitle').textContent = '新增項目';
    document.getElementById('projModalId').value = '';
    ['pCode','pName','pClient','pMc','pNotes'].forEach(id => document.getElementById(id).value = '');
    document.getElementById('pAmt').value = '';
    document.getElementById('pLabour').value = '';
    document.getElementById('pStartDate').value = '';
    document.getElementById('pStatus').value = 'Active';
    document.getElementById('projectModal').classList.add('open');
  },

  async openEdit(id) {
    const p = await api('GET', `/projects/${id}`);
    if (!p) return;
    document.getElementById('projModalTitle').textContent = '編輯項目';
    document.getElementById('projModalId').value = p.id;
    document.getElementById('pCode').value = p.project_code || '';
    document.getElementById('pName').value = p.project_name || '';
    document.getElementById('pClient').value = p.client || '';
    document.getElementById('pMc').value = p.main_contractor || '';
    document.getElementById('pAmt').value = p.contract_amount || '';
    document.getElementById('pLabour').value = p.labour_allocation || '';
    document.getElementById('pStartDate').value = p.start_date || '';
    document.getElementById('pStatus').value = p.status || 'Active';
    document.getElementById('pNotes').value = p.notes || '';
    document.getElementById('projectModal').classList.add('open');
  },

  closeModal() {
    document.getElementById('projectModal').classList.remove('open');
  },

  async saveModal() {
    const id = document.getElementById('projModalId').value;
    const data = {
      project_code: document.getElementById('pCode').value.trim(),
      project_name: document.getElementById('pName').value.trim(),
      client: document.getElementById('pClient').value.trim(),
      main_contractor: document.getElementById('pMc').value.trim(),
      contract_amount: parseFloat(document.getElementById('pAmt').value) || 0,
      labour_allocation: parseFloat(document.getElementById('pLabour').value) || 0,
      start_date: document.getElementById('pStartDate').value || null,
      status: document.getElementById('pStatus').value,
      notes: document.getElementById('pNotes').value.trim(),
    };

    if (!data.project_code) { toast('請輸入項目代碼', 'warning'); return; }

    try {
      if (id) {
        await api('PUT', `/projects/${id}`, data);
        toast('項目已更新', 'success');
      } else {
        const res = await api('POST', '/projects', data);
        toast('項目已新增', 'success');
      }
      this.closeModal();
      await App.loadProjects();
    } catch (e) {}
  },

  async delete(id, code) {
    if (!confirm(`確認刪除項目「${code}」？\n此操作將同時刪除所有相關合同項目及付款記錄！`)) return;
    await api('DELETE', `/projects/${id}`);
    toast('項目已刪除', 'success');
    if (App.currentProject?.id == id) {
      App.currentProject = null;
      App.scList = [];
    }
    await App.loadProjects();
  }
};

/* ─── sc.js (在同一文件) — 分判商管理 ─────────────────────── */
const SC = {
  _descItems: [],
  _editSc: null,

  _esc(s) {
    return String(s ?? '')
      .replace(/&/g, '&amp;')
      .replace(/"/g, '&quot;')
      .replace(/</g, '&lt;');
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
    const totalEl = document.getElementById('scItemsTotal');
    if (!tbody) return;

    if (!this._descItems.length) {
      tbody.innerHTML = '<tr><td colspan="7" class="ocr-items-empty">尚無明細，可新增項目或於摘要填寫簡述</td></tr>';
      if (totalEl) totalEl.innerHTML = '';
      return;
    }

    tbody.innerHTML = this._descItems.map((it, idx) => `
      <tr data-idx="${idx}">
        <td><input type="text" value="${this._esc(it.no)}" data-field="no" oninput="SC.onDescItemChange(${idx})"></td>
        <td><input type="text" value="${this._esc(it.description)}" data-field="description" oninput="SC.onDescItemChange(${idx})"></td>
        <td><input type="text" value="${this._esc(it.qty)}" data-field="qty" oninput="SC.onDescItemChange(${idx})"></td>
        <td><input type="text" value="${this._esc(it.unit)}" data-field="unit" oninput="SC.onDescItemChange(${idx})"></td>
        <td><input type="number" value="${it.unit_price}" data-field="unit_price" step="0.01" oninput="SC.onDescItemChange(${idx})"></td>
        <td><input type="number" value="${it.amount}" data-field="amount" step="0.01" oninput="SC.onDescItemChange(${idx})"></td>
        <td><button type="button" class="btn-del" onclick="SC.removeDescItem(${idx})" title="刪除">×</button></td>
      </tr>
    `).join('');

    let sum = 0;
    this._descItems.forEach(it => {
      const a = parseFloat(it.amount);
      if (!isNaN(a)) sum += a;
    });
    if (totalEl) {
      totalEl.innerHTML = `明細合計: <strong>${fmt(sum)}</strong> (${this._descItems.length} 項)`;
    }
  },

  readDescItemsFromDom() {
    const rows = document.querySelectorAll('#scItemsBody tr[data-idx]');
    const items = [];
    rows.forEach((row, i) => {
      const get = (field) => row.querySelector(`[data-field="${field}"]`)?.value?.trim() ?? '';
      const desc = get('description');
      if (!desc && !get('amount')) return;
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
    this.readDescItemsFromDom();
    this.renderDescItems();
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
    if (!s) {
      bar.innerHTML = '';
      return;
    }
    const docs = s.documents || [];
    const items = [];
    const seen = new Set();
    const push = (file_path, label, when) => {
      if (!file_path || seen.has(file_path)) return;
      seen.add(file_path);
      items.push({ file_path, label, when });
    };
    if (s.quotation_saved) {
      push(s.quotation_saved, '報價 PDF', s.quotation_date);
    }
    docs.forEach(d => {
      const kind = { quotation: '報價', invoice: '發票', scan: '掃描' }[d.doc_type] || '存證';
      push(d.file_path, `${kind} PDF`, d.created_at);
    });
    if (!items.length) {
      bar.innerHTML = '<span class="sc-doc-none">尚無 PDF 存證</span>';
      return;
    }
    bar.innerHTML = items.map(d => {
      const when = d.when ? fmtDate(d.when) : '';
      const title = `${d.label}${when ? ` · ${when}` : ''}`;
      return `<button type="button" class="sc-pdf-chip"
        data-path="${this._esc(d.file_path)}"
        data-title="${this._esc(title)}"
        title="預覽 ${this._esc(d.label)}">
        <span class="sc-pdf-icon">📄</span>
        <span class="sc-pdf-label">${this._esc(d.label)}${when ? ` · ${when}` : ''}</span>
      </button>`;
    }).join('');

    if (!bar.dataset.docBound) {
      bar.dataset.docBound = '1';
      bar.addEventListener('click', (e) => {
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

  async load() {
    const p = App.currentProject;
    if (!p) {
      document.getElementById('scTableBody').innerHTML = `<tr><td colspan="8"><div class="empty-state" style="padding:40px">請先選擇項目</div></td></tr>`;
      return;
    }
    this.data = await api('GET', `/projects/${p.id}/subcontractors`) || [];
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
    const company = g.items[0].company_name_en || g.items[0].company_name_zh || '';
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
        <td class="td-amount positive">${fmt(totalPaid)}</td>
        <td colspan="3"></td>
      </tr>`;
  },

  _renderRow(s, isChild) {
    const oaBadge = s.oa_status === 'OK' ? '<span class="badge badge-success">OK</span>' :
                    s.oa_status === '-'  ? '<span class="badge badge-muted">—</span>' :
                    s.oa_status          ? `<span class="badge badge-warning">${s.oa_status}</span>` : '—';
    const quotDateStr = s.quotation_date ? fmtDate(s.quotation_date) : '';
    const oaDateStr = s.oa_date ? fmtDate(s.oa_date) : '';
    const voHint = (parseFloat(s.vo_amount) || 0) !== 0
      ? `<div style="font-size:10px;color:var(--text-muted)">H ${fmt(s.contract_sum)} + VO ${fmt(s.vo_amount)}</div>` : '';
    const scNoEsc = (s.sc_no || '').replace(/'/g, "\\'");
    const excludedCls = s.is_excluded ? ' sc-row-excluded' : '';
    return `
      <tr class="row-clickable${isChild ? ' sc-group-child' : ''}${excludedCls}" onclick="SC.showPayments(${s.id})" title="點擊查看付款記錄">
        <td>${fmtRefNo(s.sc_no)}${s.is_excluded ? ' <span class="badge badge-warning" style="font-size:10px">除外 (C)</span>' : ''}</td>
        <td>
          <div style="font-weight:600">${s.company_name_en || '—'}</div>
          <div style="font-size:11px;color:var(--text-muted)">${s.company_name_zh || ''}</div>
        </td>
        <td class="td-muted">${s.description || '—'}</td>
        <td class="td-amount">${fmt(s.contract_amount)}${voHint}</td>
        <td class="td-amount positive">${fmt(s.total_paid)}</td>
        <td style="font-size:11px;color:var(--text-secondary)">
          <div>${s.quotation_no || '—'}</div>
          ${quotDateStr ? `<div style="font-size:10px;color:var(--text-muted);margin-top:4px">報價 ${quotDateStr}</div>` : ''}
        </td>
        <td>
          <div>${oaBadge}</div>
          ${oaDateStr ? `<div style="font-size:10px;color:var(--text-muted);margin-top:4px">OA ${oaDateStr}</div>` : ''}
        </td>
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
      tbody.innerHTML = `<tr><td colspan="8"><div class="empty-state" style="padding:48px"><div class="empty-icon">🏢</div><div class="empty-title">暫無合同項目</div></div></td></tr>`;
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
    document.getElementById('scModalTitle').textContent = '新增合同項目';
    document.getElementById('scModalId').value = '';
    ['scNo','scQuotNo','scQuotDate','scCompanyEn','scCompanyZh','scDescTitle','scOaStatus','scOaNo','scPayNote'].forEach(id => document.getElementById(id).value = '');
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
    document.getElementById('scModalTitle').textContent = '編輯合同項目';
    document.getElementById('scModalId').value = s.id;
    document.getElementById('scNo').value = s.sc_no || '';
    document.getElementById('scQuotNo').value = s.quotation_no || '';
    document.getElementById('scCompanyEn').value = s.company_name_en || '';
    document.getElementById('scCompanyZh').value = s.company_name_zh || '';
    this._loadDescFromText(s.description || '');
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
    document.getElementById('scExcluded').checked = !!s.is_excluded;
    document.getElementById('scModal').classList.add('open');
  },

  closeModal() {
    document.getElementById('scModal').classList.remove('open');
    this._editSc = null;
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

    document.getElementById('scPayModalTitle').textContent = `${s.sc_no} — 付款記錄`;
    const subParts = [s.company_name_en, s.company_name_zh].filter(Boolean);
    document.getElementById('scPayModalSub').textContent =
      subParts.join(' / ') || s.description || '';
    document.getElementById('scPaySummary').innerHTML = `
      <div style="display:flex;flex-wrap:wrap;gap:20px;font-size:12px">
        <div><span style="color:var(--text-muted)">修訂合約金額 (J)</span><br><strong>${fmt(ca)}</strong></div>
        <div><span style="color:var(--text-muted)">累計已付</span><br><strong style="color:var(--success)">${fmt(paid)}</strong></div>
        <div><span style="color:var(--text-muted)">待付金額</span><br><strong style="color:${pending > 0 ? 'var(--warning)' : 'var(--text-primary)'}">${fmt(pending)}</strong></div>
        <div><span style="color:var(--text-muted)">付款記錄</span><br><strong id="scPayCount">載入中...</strong></div>
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
        <div class="empty-title">尚無付款記錄</div>
        <div class="empty-sub" style="margin-top:8px">待付金額：<strong style="color:var(--warning)">${pendingFmt}</strong></div>
        <div class="empty-sub" style="margin-top:4px">此項目已在合同清單立約，尚未錄入付款</div>
      </div></td></tr>`;
      return;
    }

    const sorted = [...payments].sort((a, b) => {
      const sa = parseFloat(a.seq_no) || a.id;
      const sb = parseFloat(b.seq_no) || b.id;
      return sa - sb;
    });

    tbody.innerHTML = sorted.map(r => {
      const remClass = parseFloat(r.remainder_amount) > 0 ? 'negative' : '';
      const paidClass = parseFloat(r.paid_amount) > 0 ? 'positive' : '';
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
          <td class="td-amount ${paidClass}">${fmt(r.paid_amount)}</td>
          <td class="td-amount ${remClass}">${fmt(r.remainder_amount)}</td>
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
    App.navigate('payments');
  },

  openPayEdit(paymentId) {
    this.closePayModal();
    App.navigate('payments');
    setTimeout(() => Payments.openEdit(paymentId), 150);
  },

  async saveModal() {
    const p = App.currentProject;
    if (!p) { toast('請先選擇項目', 'warning'); return; }
    const id = document.getElementById('scModalId').value;
    const scNo = document.getElementById('scNo').value.trim();
    if (!scNo) { toast('請輸入參考編號', 'warning'); return; }

    const data = {
      project_id: p.id,
      sc_no: scNo,
      quotation_no: document.getElementById('scQuotNo').value || null,
      company_name_en: document.getElementById('scCompanyEn').value || null,
      company_name_zh: document.getElementById('scCompanyZh').value || null,
      description: this.buildDescText(),
      contract_sum: parseFloat(document.getElementById('scContractSum').value) || 0,
      vo_amount: parseFloat(document.getElementById('scVoAmt').value) || 0,
      contract_amount: parseFloat(document.getElementById('scAmt').value) || 0,
      quotation_date: document.getElementById('scQuotDate').value || null,
      oa_date: document.getElementById('scOaDate').value || null,
      oa_status: document.getElementById('scOaStatus').value || null,
      oa_ref: null,
      oa_no: document.getElementById('scOaNo').value || null,
      quotation_saved: this._editSc?.quotation_saved || null,
      payment_note: document.getElementById('scPayNote').value || null,
      is_excluded: document.getElementById('scExcluded').checked ? 1 : 0,
    };

    try {
      await api('POST', '/subcontractors', data);
      toast('合同項目已儲存', 'success');
      this.closeModal();
      // 刷新分判商列表
      App.scList = await api('GET', `/projects/${p.id}/subcontractors`) || [];
      await this.load();
      Payments.populateScFilter();
      OCR.populateScOptions();
    } catch (e) {}
  },

  async delete(id, scNo) {
    if (!confirm(`確認刪除合同項目 ${scNo}？`)) return;
    await api('DELETE', `/subcontractors/${id}`);
    toast('已刪除', 'success');
    const p = App.currentProject;
    if (p) App.scList = await api('GET', `/projects/${p.id}/subcontractors`) || [];
    await this.load();
    Payments.populateScFilter();
  }
};
