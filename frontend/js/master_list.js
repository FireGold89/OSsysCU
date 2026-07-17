/* master_list.js — Master List 主檔同步與查詢 */
const MasterList = {
  offset: 0,
  limit: 50,
  sortBy: 'quote_date',
  sortDir: 'desc',
  pendingFile: null,
  syncMode: 'preview',
  _rowMap: {},

  SORT_COLUMNS: [
    { key: 'quotation_no', label: '報價編號' },
    { key: 'quote_date', label: '日期' },
    { key: 'person_in_charge', label: '項目負責人' },
    { key: 'doc_type', label: '類型' },
    { key: 'awarded', label: '中標' },
    { key: 'site_name', label: '屋苑/地點' },
    { key: 'description', label: '內容' },
    { key: 'awarded_amount', label: '中標金額', align: 'right' },
    { key: 'project_code', label: '配對項目' },
  ],

  _itemPath(rowId, suffix = '') {
    return `/master/item${suffix}?id=${rowId}`;
  },

  _rowFromCache(rowId) {
    return this._rowMap[String(rowId)] || null;
  },

  async _fetchRow(rowId) {
    const cached = this._rowFromCache(rowId);
    if (cached) return cached;
    return api('GET', this._itemPath(rowId));
  },

  async load() {
    this._initDefaultYear();
    await Promise.all([this.loadStats(), this.loadTable()]);
  },

  _initDefaultYear() {
    const sel = document.getElementById('masterYearFilter');
    if (!sel || sel.dataset.userPicked === '1') return;
    const saved = localStorage.getItem('qs_master_year');
    if (saved !== null && saved !== '') {
      sel.dataset.pendingYear = saved;
    } else if (saved === null) {
      sel.dataset.pendingYear = String(new Date().getFullYear());
    }
  },

  _getEffectiveYear() {
    const sel = document.getElementById('masterYearFilter');
    if (!sel) return '';
    if (sel.value) return sel.value;
    return sel.dataset.pendingYear || '';
  },

  onYearFilterChange() {
    const sel = document.getElementById('masterYearFilter');
    if (sel) {
      sel.dataset.userPicked = '1';
      delete sel.dataset.pendingYear;
      if (sel.value) localStorage.setItem('qs_master_year', sel.value);
      else localStorage.setItem('qs_master_year', '');
    }
    this.resetAndLoad();
  },

  DOC_TYPE_OPTIONS: ['報價', '標書'],

  _filterParams(includePagination = false) {
    const q = document.getElementById('masterSearch')?.value.trim() || '';
    const year = this._getEffectiveYear();
    const person = document.getElementById('masterPersonFilter')?.value || '';
    const docType = document.getElementById('masterTypeFilter')?.value || '';
    const awarded = document.getElementById('masterAwardedOnly')?.checked ? '1' : '';
    const unlinked = document.getElementById('masterUnlinkedOnly')?.checked ? '1' : '';
    const params = new URLSearchParams();
    if (q) params.set('q', q);
    if (year) params.set('year', year);
    if (person) params.set('person', person);
    if (docType) params.set('doc_type', docType);
    if (awarded) params.set('awarded', awarded);
    if (unlinked) params.set('unlinked', unlinked);
    if (includePagination) {
      params.set('limit', this.limit);
      params.set('offset', this.offset);
      if (this.sortBy) {
        params.set('sort', this.sortBy);
        params.set('dir', this.sortDir || 'desc');
      }
    }
    return params;
  },

  renderTableHead() {
    const tr = document.querySelector('#masterTableHead tr');
    if (!tr) return;
    const cols = this.SORT_COLUMNS.map(col => {
      const active = this.sortBy === col.key;
      const icon = active ? (this.sortDir === 'asc' ? '▲' : '▼') : '⇅';
      const align = col.align === 'right' ? ' style="text-align:right"' : '';
      return `<th class="th-sortable${active ? ' th-sort-active' : ''}"${align} onclick="MasterList.setSort('${col.key}')">${col.label}<span class="th-sort-icon">${icon}</span></th>`;
    }).join('');
    tr.innerHTML = `${cols}<th></th>`;
  },

  setSort(col) {
    if (this.sortBy === col) {
      this.sortDir = this.sortDir === 'asc' ? 'desc' : 'asc';
    } else {
      this.sortBy = col;
      this.sortDir = (col === 'quote_date' || col === 'awarded_amount') ? 'desc' : 'asc';
    }
    this.offset = 0;
    this.loadTable();
  },

  _filterScopeLabel() {
    const parts = [];
    const year = this._getEffectiveYear();
    const person = document.getElementById('masterPersonFilter')?.value;
    const docType = document.getElementById('masterTypeFilter')?.value;
    const q = document.getElementById('masterSearch')?.value.trim();
    if (year) parts.push(`${year} 年`);
    if (docType) parts.push(docType);
    if (person) parts.push(person);
    if (q) parts.push(`搜尋「${q}」`);
    if (document.getElementById('masterAwardedOnly')?.checked) parts.push('只顯示中標');
    if (document.getElementById('masterUnlinkedOnly')?.checked) parts.push('未配對項目');
    return parts.length ? parts.join(' · ') : '';
  },

  async loadStats() {
    const stats = await api('GET', `/master/stats?${this._filterParams()}`);
    if (!stats) return;
    document.getElementById('masterStatTotal').textContent = stats.total ?? '0';
    document.getElementById('masterStatAwarded').textContent = stats.awarded_count ?? '0';
    document.getElementById('masterStatUnlinked').textContent = stats.unlinked_count ?? '0';
    const last = stats.last_import;
    document.getElementById('masterStatLastImport').textContent = last
      ? `${last.source_file || '—'} (${fmtDateTime(last.imported_at)})`
      : '尚未匯入';

    const scopeEl = document.getElementById('masterStatScope');
    const scopeText = this._filterScopeLabel();
    if (scopeEl) {
      const textEl = scopeEl.querySelector('.master-scope-text');
      if (textEl) textEl.textContent = scopeText ? `統計範圍：${scopeText}` : '';
      scopeEl.hidden = !scopeText;
    }

    const sel = document.getElementById('masterYearFilter');
    const cur = sel.value || this._getEffectiveYear();
    const years = (stats.by_year || []).map(y => y.source_year);
    sel.innerHTML = '<option value="">全部年份</option>' +
      (stats.by_year || []).map(y =>
        `<option value="${y.source_year}">${y.source_year} · ${y.cnt}</option>`
      ).join('');
    if (cur && years.some(y => String(y) === String(cur))) {
      sel.value = String(cur);
    } else if (sel.dataset.pendingYear && years.some(y => String(y) === String(sel.dataset.pendingYear))) {
      sel.value = String(sel.dataset.pendingYear);
    } else if (years.length && sel.dataset.userPicked !== '1' && !sel.value) {
      sel.value = String(years[0]);
    }
    if (sel.value && sel.dataset.userPicked !== '1') {
      localStorage.setItem('qs_master_year', sel.value);
    }
    delete sel.dataset.pendingYear;

    const psel = document.getElementById('masterPersonFilter');
    if (psel) {
      const pcur = psel.value;
      const persons = stats.by_person || [];
      psel.innerHTML = '<option value="">全部項目負責人</option>' +
        persons.map(p => {
          const label = (p.person_name || '').trim();
          const val = label.replace(/"/g, '&quot;');
          return `<option value="${val}">${label} · ${p.cnt}</option>`;
        }).join('');
      if (pcur && persons.some(p => (p.person_name || '').trim() === pcur)) psel.value = pcur;
    }

    const tsel = document.getElementById('masterTypeFilter');
    if (tsel) {
      const tcur = tsel.value;
      const typeMap = {};
      (stats.by_doc_type || []).forEach(t => { typeMap[t.doc_type] = t.cnt; });
      tsel.innerHTML = '<option value="">全部類型</option>' +
        this.DOC_TYPE_OPTIONS.map(dt => {
          const cnt = typeMap[dt];
          const suffix = cnt != null ? ` · ${cnt}` : '';
          return `<option value="${dt}">${dt}${suffix}</option>`;
        }).join('');
      if (tcur && this.DOC_TYPE_OPTIONS.includes(tcur)) tsel.value = tcur;
    }
  },

  search() {
    this.offset = 0;
    this.load();
  },

  /** 篩選條件變更時回到第一頁 */
  resetAndLoad() {
    this.offset = 0;
    this.load();
  },

  async loadTable() {
    this.renderTableHead();
    const data = await api('GET', `/master/quotations?${this._filterParams(true)}`);
    if (!data) return;

    this._rowMap = {};
    (data.items || []).forEach(r => { this._rowMap[String(r.id)] = r; });

    // 篩選後總筆數變少時，避免停在超出範圍的頁碼（例：9 / 8）
    if (data.total > 0 && !data.items.length && this.offset > 0) {
      this.offset = 0;
      return this.loadTable();
    }
    const maxOffset = Math.max(0, Math.ceil(data.total / this.limit) - 1) * this.limit;
    if (this.offset > maxOffset) {
      this.offset = maxOffset;
      return this.loadTable();
    }

    const tbody = document.getElementById('masterTableBody');
    document.getElementById('masterListCount').textContent =
      `共 ${data.total} 筆（顯示 ${data.items.length} 筆）`;

    if (!data.items.length) {
      const emptyMsg = data.total > 0
        ? '此頁沒有資料'
        : '尚無主檔資料，請上傳 Master List Excel';
      tbody.innerHTML = `<tr><td colspan="11"><div class="empty-state" style="padding:40px">${emptyMsg}</div></td></tr>`;
      this.renderPagination(data.total);
      return;
    }

    tbody.innerHTML = data.items.map(r => {
      const awardedBadge = r.awarded === '中'
        ? '<span class="badge badge-success">中</span>'
        : '<span class="badge badge-muted">—</span>';
      const linked = r.project_code
        ? `<span class="sc-no-chip">${r.project_code}</span>`
        : '<span class="badge badge-warning">未配對</span>';
      const desc = (r.description || '—').replace(/</g, '&lt;');
      const shortDesc = desc.length > 48 ? desc.slice(0, 48) + '…' : desc;
      const personCell = fmtMasterPerson(r);
      return `<tr>
        <td class="td-mono">${r.quotation_no}</td>
        <td class="td-muted">${fmtDate(r.quote_date)}</td>
        <td>${personCell}</td>
        <td>${r.doc_type || '—'}</td>
        <td>${awardedBadge}</td>
        <td>${r.site_name || '—'}</td>
        <td class="td-muted" title="${desc}">${shortDesc}</td>
        <td class="td-amount">${r.awarded_amount ? fmt(r.awarded_amount) : '—'}</td>
        <td>${linked}</td>
        <td>
          <button class="btn btn-secondary btn-sm" onclick="MasterList.openEdit(${r.id})">編輯</button>
          <button class="btn btn-secondary btn-sm" onclick="MasterList.openLink(${r.id})">配對</button>
          ${r.project_id ? `<button class="btn btn-secondary btn-sm" onclick="MasterList.unlink(${r.id})">解除</button>` : ''}
        </td>
      </tr>`;
    }).join('');
    this.renderPagination(data.total);
  },

  renderPagination(total) {
    const el = document.getElementById('masterPagination');
    if (!el) return;
    const pages = Math.ceil(total / this.limit) || 1;
    const page = Math.floor(this.offset / this.limit) + 1;
    if (pages <= 1) {
      el.innerHTML = '';
      return;
    }
    el.innerHTML = `
      <button class="btn btn-secondary btn-sm" ${page <= 1 ? 'disabled' : ''} onclick="MasterList.prevPage()">上一頁</button>
      <span class="master-page-info">${page} / ${pages}</span>
      <button class="btn btn-secondary btn-sm" ${page >= pages ? 'disabled' : ''} onclick="MasterList.nextPage()">下一頁</button>`;
  },

  prevPage() {
    this.offset = Math.max(0, this.offset - this.limit);
    this.loadTable();
  },

  nextPage() {
    this.offset += this.limit;
    this.loadTable();
  },

  openPreview() {
    this.syncMode = 'preview';
    this.pendingFile = null;
    document.getElementById('masterSyncModalTitle').textContent = 'Master List 預覽';
    document.getElementById('masterPreviewResult').style.display = 'none';
    document.getElementById('masterPreviewResult').innerHTML = '';
    document.getElementById('masterSyncFooter').style.display = 'none';
    document.getElementById('masterConfirmSyncBtn').style.display = '';
    document.getElementById('masterSyncModal').classList.add('open');
  },

  openSync() {
    this.syncMode = 'sync';
    this.openPreview();
    document.getElementById('masterSyncModalTitle').textContent = 'Master List 同步';
  },

  closeSyncModal() {
    document.getElementById('masterSyncModal').classList.remove('open');
    document.getElementById('masterFileInput').value = '';
    this.pendingFile = null;
  },

  async onFileSelected(event) {
    const file = event.target.files[0];
    if (!file) return;
    this.pendingFile = file;
    const status = document.getElementById('masterSyncStatus');
    const result = document.getElementById('masterPreviewResult');
    const footer = document.getElementById('masterSyncFooter');
    status.style.display = '';
    result.style.display = 'none';
    footer.style.display = 'none';

    const formData = new FormData();
    formData.append('file', file);
    const endpoint = this.syncMode === 'sync' ? '/master/sync' : '/master/preview';

    try {
      const r = await fetch(`${API}${endpoint}`, { method: 'POST', body: formData });
      const json = await r.json();
      if (!json.success) throw new Error(json.error || '處理失敗');
      const d = json.data;
      if (this.syncMode === 'sync') {
        toast(`同步完成：新增 ${d.new}、更新 ${d.updated}、不變 ${d.unchanged}`, 'success');
        this.closeSyncModal();
        await this.load();
        return;
      }
      result.innerHTML = this.renderPreview(d);
      result.style.display = '';
      footer.style.display = '';
    } catch (e) {
      toast(e.message, 'error');
    } finally {
      status.style.display = 'none';
      event.target.value = '';
    }
  },

  renderPreview(d) {
    const errs = (d.parse_errors || []).slice(0, 5).map(e => `<li>${e}</li>`).join('');
    const newRows = (d.new_sample || []).slice(0, 8).map(r =>
      `<tr><td class="td-mono">${r.quotation_no}</td><td>${r.site_name || '—'}</td><td>${r.awarded === '中' ? '中' : '—'}</td></tr>`
    ).join('');
    const updRows = (d.updated_sample || []).slice(0, 8).map(r =>
      `<tr><td class="td-mono">${r.quotation_no}</td><td>${r.changes?.length || 0} 欄變更</td><td>${r.site_name || '—'}</td></tr>`
    ).join('');
    return `
      <div class="master-preview-summary">
        <span class="badge badge-info">讀取 ${d.rows_read} 行</span>
        <span class="badge badge-success">新增 ${d.new_count}</span>
        <span class="badge badge-warning">更新 ${d.updated_count}</span>
        <span class="badge badge-muted">不變 ${d.unchanged_count}</span>
      </div>
      ${errs ? `<div class="form-hint" style="margin-top:8px;color:var(--warning)"><ul>${errs}</ul></div>` : ''}
      ${newRows ? `<div class="section-title" style="margin-top:12px">新增範例</div>
        <table class="master-preview-table"><thead><tr><th>報價編號</th><th>屋苑</th><th>中標</th></tr></thead><tbody>${newRows}</tbody></table>` : ''}
      ${updRows ? `<div class="section-title" style="margin-top:12px">更新範例</div>
        <table class="master-preview-table"><thead><tr><th>報價編號</th><th>變更</th><th>屋苑</th></tr></thead><tbody>${updRows}</tbody></table>` : ''}`;
  },

  async confirmSync() {
    if (!this.pendingFile) {
      toast('請先選擇檔案並預覽', 'warning');
      return;
    }
    this.syncMode = 'sync';
    const input = document.getElementById('masterFileInput');
    const dt = new DataTransfer();
    dt.items.add(this.pendingFile);
    input.files = dt.files;
    await this.onFileSelected({ target: input });
  },

  async openLink(rowId) {
    const row = await this._fetchRow(rowId);
    if (!row) return;
    document.getElementById('masterLinkRowId').value = rowId;
    document.getElementById('masterLinkQuotationNo').value = row.quotation_no;
    document.getElementById('masterLinkQuotationDisplay').value = row.quotation_no;
    const sel = document.getElementById('masterLinkProjectSelect');
    sel.innerHTML = '<option value="">— 選擇項目 —</option>';
    (App.projects || []).forEach(p => {
      const opt = document.createElement('option');
      opt.value = p.id;
      opt.textContent = `${p.project_code} — ${projectNameOneLine(p, 36)}`;
      sel.appendChild(opt);
    });
    document.getElementById('masterLinkModal').classList.add('open');
  },

  closeLinkModal() {
    document.getElementById('masterLinkModal').classList.remove('open');
  },

  async saveLink() {
    const rowId = document.getElementById('masterLinkRowId').value;
    const projectId = document.getElementById('masterLinkProjectSelect').value;
    if (!projectId) {
      toast('請選擇工程項目', 'warning');
      return;
    }
    await api('POST', this._itemPath(rowId, '/link'), {
      project_id: Number(projectId),
    });
    toast('已配對項目（已同步報價編號與負責人）', 'success');
    this.closeLinkModal();
    await this.load();
    if (typeof App !== 'undefined' && App.loadProjects) await App.loadProjects();
  },

  async unlink(rowId) {
    const row = await this._fetchRow(rowId);
    if (!row) return;
    if (!confirm(`解除 ${row.quotation_no} 的項目配對？`)) return;
    await api('POST', this._itemPath(rowId, '/unlink'), {});
    toast('已解除配對', 'success');
    await this.load();
  },

  async openEdit(rowId) {
    const row = await this._fetchRow(rowId);
    if (!row) return;
    const qno = row.quotation_no;
    await StaffRoster.load(true);
    const dl = document.getElementById('masterPersonSuggestions');
    if (dl) {
      dl.innerHTML = StaffRoster.list
        .filter(s => s.is_active)
        .map(s => {
          const name = s.name_en || s.name_zh;
          return name ? `<option value="${name.replace(/"/g, '&quot;')}">` : '';
        })
        .join('');
    }
    document.getElementById('masterEditPersonName').value = row.person_in_charge || '';
    document.getElementById('masterEditRowId').value = rowId;
    document.getElementById('masterEditQuotationNo').value = qno;
    document.getElementById('masterEditQuotDisplay').value = qno;
    document.getElementById('masterEditDate').value = row.quote_date || '';
    document.getElementById('masterEditDocType').value = row.doc_type || '報價';
    document.getElementById('masterEditAwarded').value = row.awarded || '';
    document.getElementById('masterEditSite').value = row.site_name || '';
    document.getElementById('masterEditTrade').value = row.trade_category || '';
    document.getElementById('masterEditClient').value = row.client_name || '';
    document.getElementById('masterEditDesc').value = row.description || '';
    document.getElementById('masterEditQuoted').value = row.quoted_amount ?? '';
    document.getElementById('masterEditAwardedAmt').value = row.awarded_amount ?? '';
    document.getElementById('masterEditMargin').value = row.margin_pct ?? '';
    document.getElementById('masterEditSubconType').value = row.subcon_type || '';
    document.getElementById('masterEditSubconCo').value = row.subcon_company || '';
    document.getElementById('masterEditSubconCo').readOnly = false;
    document.getElementById('masterEditSubconAmt').value = row.subcon_amount ?? '';
    document.getElementById('masterEditSubconAmt').readOnly = false;
    document.getElementById('masterEditContractDays').value = row.contract_days ?? '';
    document.getElementById('masterEditStartDate').value = row.start_date || '';
    document.getElementById('masterEditCompletionDate').value = row.completion_date || '';
    const cl = this._parseChecklist(row.checklist_json);
    document.getElementById('masterEditBidSignoff').checked = this._isChecklistDone(cl.bid_signoff);
    document.getElementById('masterEditPartnerForm').checked = this._isChecklistDone(cl.partner_form);
    document.getElementById('masterEditContractSignoff').checked = this._isChecklistDone(cl.contract_signoff);
    this._bindChecklistVisibility();
    const hint = document.getElementById('masterEditSubconHint');
    if (hint) hint.style.display = 'none';
    await this.loadFinancePanel(rowId);
    this.recalcProfit();
    document.getElementById('masterEditModal').classList.add('open');
  },

  _parseChecklist(raw) {
    if (!raw) return {};
    if (typeof raw === 'object') return raw;
    try { return JSON.parse(raw) || {}; } catch { return {}; }
  },

  _isChecklistDone(val) {
    if (!val) return false;
    const s = String(val).trim();
    return s === '已填妥' || s === '✓' || s.toLowerCase() === 'y' || s === '1';
  },

  onEditDocTypeChange() {
    this._bindChecklistVisibility();
  },

  _bindChecklistVisibility() {
    const docType = document.getElementById('masterEditDocType')?.value;
    const row = document.getElementById('masterEditBidSignoffRow');
    if (row) row.style.display = docType === '標書' ? '' : 'none';
  },

  _buildChecklistPayload() {
    const cl = {};
    const mark = (key, id) => {
      const el = document.getElementById(id);
      if (el?.checked) cl[key] = '已填妥';
    };
    if (document.getElementById('masterEditDocType')?.value === '標書') {
      mark('bid_signoff', 'masterEditBidSignoff');
    }
    mark('partner_form', 'masterEditPartnerForm');
    mark('contract_signoff', 'masterEditContractSignoff');
    return Object.keys(cl).length ? cl : null;
  },

  /** 依 Master List 公式自動計算利潤$ / 利潤% */
  recalcProfit() {
    const profitEl = document.getElementById('masterEditProfitAmt');
    const pctEl = document.getElementById('masterEditProfitPct');
    if (!profitEl || !pctEl) return;

    const num = (id) => {
      const v = document.getElementById(id)?.value;
      if (v === '' || v == null) return null;
      const n = parseFloat(v);
      return Number.isFinite(n) ? n : null;
    };

    const awarded = num('masterEditAwardedAmt');
    const quoted = num('masterEditQuoted');
    const subcon = num('masterEditSubconAmt');

    if (awarded == null || subcon == null) {
      profitEl.value = '';
      pctEl.value = '';
      return;
    }

    const profit = Math.round((awarded - subcon) * 100) / 100;
    profitEl.value = profit;
    if (quoted != null && quoted !== 0) {
      pctEl.value = Math.round((profit / quoted) * 10000) / 100;
    } else {
      pctEl.value = '';
    }
  },

  async loadFinancePanel(rowId) {
    const panel = document.getElementById('masterFinancePanel');
    panel.style.display = 'none';
    let fin;
    try {
      fin = await api('GET', this._itemPath(rowId, '/finance'), null, { silent: true });
    } catch {
      return;
    }
    if (!fin || (!fin.stats?.ip_count && !fin.stats?.qs_subcon_count && !fin.stats?.subcon_payment_count && !fin.stats?.cheque_count && !fin.summary)) {
      panel.style.display = '';
      document.getElementById('masterFinanceSummary').textContent =
        '尚無財務明細。請在 Master List 重新「同步」對應年份 Excel（含 Admin 糧期／分判／支票欄）。';
      ['masterFinanceTabIp', 'masterFinanceTabRecon', 'masterFinanceTabQs', 'masterFinanceTabSub', 'masterFinanceTabChq'].forEach(id => {
        document.getElementById(id).innerHTML =
          '<p class="form-hint" style="padding:12px">尚無明細 — 請重新同步 Master List</p>';
      });
      this.switchFinanceTab('ip');
      return;
    }
    panel.style.display = '';
    const st = fin.stats || {};
    const companies = (st.subcon_companies || []).join('、') || '—';
    const qsPart = st.qs_subcon_count
      ? `${st.qs_subcon_count} 家主分判 QS（合計 ${fmt(st.qs_subcon_total || 0)}）· `
      : '';
    document.getElementById('masterFinanceSummary').textContent =
      `${st.ip_count || 0} 期糧 · ${qsPart}${st.subcon_payment_count || 0} 筆分判付款 · ${st.subcon_company_count || 0} 個分判商（${companies}）· ${st.cheque_count || 0} 筆支票`;
    this._renderFinanceTable('masterFinanceTabIp', [
      ['#', '糧期', '出發票日期', '發票編號', '發票/糧期金額', '收票日期'],
      ...(fin.client_invoices || []).map(r => [
        r.line_seq,
        r.ip_no || '—',
        this._finDate(r.invoice_date, r.invoice_date_display),
        r.invoice_no || '—',
        r.amount_display || (r.invoice_amount != null ? fmt(r.invoice_amount) : '—'),
        this._finDate(r.receipt_date, r.receipt_date_display),
      ]),
    ]);
    this._renderFinanceTable('masterFinanceTabQs', [
      ['#', '主要分判商', '分判金額'],
      ...(fin.qs_subcon_lines || []).map(r => [
        r.line_seq,
        r.subcon_company || '—',
        r.amount_display || (r.subcon_amount != null ? fmt(r.subcon_amount) : '—'),
      ]),
    ]);
    this._renderFinanceTable('masterFinanceTabSub', [
      ['#', '分判商', '分判金額', '上憑單日期', '主分判'],
      ...(fin.subcon_payments || []).map(r => [
        r.line_seq,
        r.subcon_company || '—',
        r.amount_display || (r.subcon_amount != null ? fmt(r.subcon_amount) : '—'),
        this._finDate(r.voucher_date, r.voucher_display),
        r.is_main_subcon ? '✓' : '—',
      ]),
    ]);
    this._renderFinanceTable('masterFinanceTabChq', [
      ['#', '支票號碼', '銀行', '日期'],
      ...(fin.cheques || []).map(r => [
        r.line_seq,
        r.cheque_no || '—',
        r.bank || '—',
        this._finDate(r.cheque_date, r.cheque_date_display),
      ]),
    ]);
    this.switchFinanceTab('ip');
    this._applyQsSubconToForm(fin);
    await this.loadIpReconcile(rowId);
  },

  async loadIpReconcile(rowId) {
    const el = document.getElementById('masterFinanceTabRecon');
    if (!el) return;
    try {
      const data = await api('GET', this._itemPath(rowId, '/ip-reconcile'), null, { silent: true });
      IpReconcile.render(el, data);
    } catch (e) {
      const hint = (e?.message || '').includes('404')
        ? '後端尚未更新糧期核對 API，請重啟 python app.py 後 Ctrl+F5 刷新。'
        : '無法載入糧期核對（請確認 Master List 已配對項目）。';
      el.innerHTML = `<p class="form-hint" style="padding:12px">${escHtml(hint)}</p>`;
    }
  },

  _applyQsSubconToForm(fin) {
    const qs = fin?.qs_subcon_lines || [];
    const coEl = document.getElementById('masterEditSubconCo');
    const amtEl = document.getElementById('masterEditSubconAmt');
    const hint = document.getElementById('masterEditSubconHint');
    if (!coEl || !amtEl || !qs.length) return;
    coEl.readOnly = true;
    amtEl.readOnly = true;
    coEl.value = qs.map(r => r.subcon_company).filter(Boolean).join('\n');
    const total = fin.stats?.qs_subcon_total;
    amtEl.value = total != null ? total : (qs[0].subcon_amount ?? '');
    if (hint) hint.style.display = qs.length > 1 ? '' : 'none';
    this.recalcProfit();
  },

  _renderFinanceTable(elId, rows) {
    const el = document.getElementById(elId);
    if (!rows.length || rows.length === 1) {
      el.innerHTML = '<p class="form-hint" style="padding:12px">尚無明細（請重新同步 Master List）</p>';
      return;
    }
    const [head, ...body] = rows;
    el.innerHTML = `<div class="table-wrap" style="max-height:220px;overflow:auto"><table class="master-preview-table"><thead><tr>${
      head.map(h => `<th>${h}</th>`).join('')
    }</tr></thead><tbody>${body.map(r => `<tr>${r.map(c => `<td>${c}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
  },

  switchFinanceTab(tab) {
    document.querySelectorAll('.master-fin-tab').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.tab === tab);
    });
    document.getElementById('masterFinanceTabIp').style.display = tab === 'ip' ? '' : 'none';
    document.getElementById('masterFinanceTabRecon').style.display = tab === 'recon' ? '' : 'none';
    document.getElementById('masterFinanceTabQs').style.display = tab === 'qs' ? '' : 'none';
    document.getElementById('masterFinanceTabSub').style.display = tab === 'sub' ? '' : 'none';
    document.getElementById('masterFinanceTabChq').style.display = tab === 'chq' ? '' : 'none';
    if (tab === 'recon') {
      const rowId = document.getElementById('masterEditRowId')?.value;
      const el = document.getElementById('masterFinanceTabRecon');
      if (rowId && el && !el.querySelector('.ip-reconcile-table')) {
        this.loadIpReconcile(rowId);
      }
    }
  },

  /** 財務日期：優先 Excel 格式 dd/m/yyyy，否則 ISO */
  _finDate(iso, fallback) {
    if (fallback && /\d{1,2}\/\d{1,2}\/\d{2,4}/.test(String(fallback))) {
      const m = String(fallback).match(/(\d{1,2}\/\d{1,2}\/\d{2,4})\s*$/);
      if (m) return m[1];
    }
    return fmtDate(iso);
  },

  closeEditModal() {
    document.getElementById('masterEditModal').classList.remove('open');
  },

  async saveEdit() {
    const rowId = document.getElementById('masterEditRowId').value;
    const num = (id) => {
      const v = document.getElementById(id).value;
      return v === '' ? null : parseFloat(v);
    };
    const intOrNull = (id) => {
      const v = document.getElementById(id).value;
      if (v === '') return null;
      const n = parseInt(v, 10);
      return Number.isFinite(n) ? n : null;
    };
    const body = {
      quote_date: document.getElementById('masterEditDate').value || null,
      doc_type: document.getElementById('masterEditDocType').value,
      awarded: document.getElementById('masterEditAwarded').value || null,
      person_in_charge: document.getElementById('masterEditPersonName').value.trim() || null,
      site_name: document.getElementById('masterEditSite').value.trim() || null,
      trade_category: document.getElementById('masterEditTrade').value.trim() || null,
      client_name: document.getElementById('masterEditClient').value.trim() || null,
      description: document.getElementById('masterEditDesc').value.trim() || null,
      quoted_amount: num('masterEditQuoted'),
      awarded_amount: num('masterEditAwardedAmt'),
      margin_pct: num('masterEditMargin'),
      contract_days: intOrNull('masterEditContractDays'),
      start_date: document.getElementById('masterEditStartDate').value || null,
      completion_date: document.getElementById('masterEditCompletionDate').value || null,
      checklist_json: this._buildChecklistPayload(),
      subcon_type: document.getElementById('masterEditSubconType').value.trim() || null,
      subcon_company: document.getElementById('masterEditSubconCo').value.trim() || null,
      subcon_amount: num('masterEditSubconAmt'),
      profit_amount: num('masterEditProfitAmt'),
      profit_pct: num('masterEditProfitPct'),
    };
    await api('PUT', this._itemPath(rowId), body);
    toast('Master List 已更新', 'success');
    this.closeEditModal();
    await this.load();
  },
};

function fmtDateTime(s) {
  if (!s) return '—';
  return s.replace('T', ' ').slice(0, 16);
}

/** 項目負責人（Master List 全名） */
function fmtMasterPerson(r) {
  const name = (r.person_in_charge || '').trim();
  return name || '—';
}
