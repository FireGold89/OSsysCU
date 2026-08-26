/* ─── payments.js — 分判付款登記 ──────────────────────── */
const Payments = {
  data: [],
  filtered: [],
  sortKey: 'seq_no',
  sortDir: 'asc',
  _pendingCert: null,
  _pendingCertModel: null,
  _scVoOptions: [],
  _scVoTemplates: null,
  _standardLineTemplates: null,
  _lineRemarks: { A: { text: '', auto: true }, B: { text: '', auto: true }, C: { text: '', auto: true } },
  _voRemarks: {},
  _prevACum: null,
  _prevACumScNo: null,
  _tab: localStorage.getItem('qs_pay_tab') || 'records',
  _pendingTab: null,
  _pendingOpenPaymentId: null,

  _isRevoked(r) {
    return !!(r && r.revoked_at);
  },

  _isCertRestored(r) {
    return this._isRevoked(r) && r.payment_type === 'interim_cert';
  },

  _remainderDisplay(r) {
    return { amount: r.remainder_amount, html: null, title: '', restored: false };
  },

  _paidDisplay(r) {
    return { html: fmtExpense(r.paid_amount) };
  },

  _renderPayActions(r) {
    const softRevoked = this._isCertRestored(r);
    const isCert = r.payment_type === 'interim_cert';
    const pdfBtn = r.pdf_path
      ? `<button type="button" class="btn btn-icon btn-secondary btn-sm btn-view-pdf" title="查看原PDF" data-pdf-path="${String(r.pdf_path).replace(/"/g, '&quot;')}">📄</button>`
      : '';
    if (softRevoked) {
      if (r.can_revert_to_normal) {
        return `<div class="pay-act-btns">
          <button type="button" class="btn btn-secondary btn-sm" title="恢復原本普通付款列" onclick="Payments.withdrawCertById(${r.id}, event)">還原原本列</button>
        </div>`;
      }
      return `<div class="pay-act-btns">
        <button type="button" class="btn btn-icon btn-secondary btn-sm" title="預覽計算書" onclick="Payments.openInterimCertPdf(${r.id})">📋</button>
        <button type="button" class="btn btn-primary btn-sm" title="恢復為有效糧款並繼續編輯" onclick="Payments.restoreAndEditCert(${r.id})">重新提交</button>
      </div>`;
    }
    if (isCert) {
      return `<div class="pay-act-btns">
        <button type="button" class="btn btn-icon btn-secondary btn-sm" title="預覽計算書" onclick="Payments.openInterimCertPdf(${r.id})">📋</button>
        ${pdfBtn}
        <button type="button" class="btn btn-icon btn-secondary btn-sm" title="編輯" onclick="Payments.openEdit(${r.id})">✏️</button>
        <button type="button" class="btn btn-secondary btn-sm" title="還原至提交前（恢復原本付款列）" onclick="Payments.withdrawCertById(${r.id}, event)">還原</button>
      </div>`;
    }
    return `<div class="pay-act-btns">
      ${pdfBtn}
      <button type="button" class="btn btn-icon btn-secondary btn-sm" title="編輯" onclick="Payments.openEdit(${r.id})">✏️</button>
      <button type="button" class="btn btn-icon btn-danger btn-sm" title="刪除" onclick="Payments.delete(${r.id})">🗑️</button>
    </div>`;
  },

  async _refreshScList() {
    if (!App.currentProject) return;
    App.scList = await api('GET', `/projects/${App.currentProject.id}/subcontractors`) || [];
    if (typeof SC !== 'undefined' && SC.load) SC.load();
    this.populateScSelect?.();
  },

  PAY_COLUMNS: [
    { id: 'seq', label: '#' },
    { id: 'date', label: '發票日期' },
    { id: 'inv', label: '發票號碼' },
    { id: 'sc', label: '判項編號' },
    { id: 'co', label: '公司名稱' },
    { id: 'desc', label: '工程描述' },
    { id: 'contract', label: '判項金額' },
    { id: 'paid', label: '已付金額' },
    { id: 'remainder', label: '餘額' },
    { id: 'oa', label: 'OA狀態' },
    { id: 'act', label: '操作', locked: true },
  ],

  setTab(tab, options = {}) {
    if (!['sc', 'records', 'ocr'].includes(tab)) tab = 'records';
    this._tab = tab;
    try { localStorage.setItem('qs_pay_tab', tab); } catch (e) {}
    const panelSc = document.getElementById('payPanelSc');
    const panelRec = document.getElementById('payPanelRecords');
    const panelOcr = document.getElementById('payPanelOcr');
    document.getElementById('payTabSc')?.classList.toggle('active', tab === 'sc');
    document.getElementById('payTabRecords')?.classList.toggle('active', tab === 'records');
    document.getElementById('payTabOcr')?.classList.toggle('active', tab === 'ocr');
    if (panelSc) panelSc.hidden = tab !== 'sc';
    if (panelRec) panelRec.hidden = tab !== 'records';
    if (panelOcr) panelOcr.hidden = tab !== 'ocr';
    const subs = {
      sc: '分判合約登記表 · 報價單／分判合約 · 先建判項再登付款',
      records: '發票／中期糧款計算書登記',
      ocr: '上傳發票、報價，自動識別並登記付款或判項',
    };
    const subEl = document.getElementById('pageSubtitle');
    if (subEl && App.currentPage === 'payments') {
      subEl.textContent = subs[tab] || subs.records;
    }
    if (tab === 'sc' && App.currentProject) SC.load();
    if (tab === 'ocr') OCR.populateScOptions();
    if (options.focusAdd && tab === 'sc') SC.openAdd();
    if (options.focusAdd && tab === 'records') this.openAdd();
  },

  async load(switchSeq) {
    const p = App.currentProject;
    if (!p) { this.renderEmpty(); return; }
    const projectId = p.id;

    const filters = {
      sc_no: document.getElementById('payFilterSc').value || undefined,
      search: document.getElementById('paySearch').value || undefined,
    };
    const params = new URLSearchParams();
    if (filters.sc_no) params.append('sc_no', filters.sc_no);
    if (filters.search) params.append('search', filters.search);

    this.data = await api('GET', `/projects/${projectId}/payments?${params}`) || [];
    if (!App.currentProject || App.currentProject.id != projectId) return;
    if (switchSeq != null && switchSeq !== App._projectSwitchSeq) return;
    const typeFilter = document.getElementById('payFilterType')?.value || '';
    this.filtered = typeFilter
      ? this.data.filter(r => (r.payment_type || 'normal') === typeFilter)
      : [...this.data];
    this.applySort();
    this.render();
    if (this._pendingOpenPaymentId) {
      const openId = this._pendingOpenPaymentId;
      this._pendingOpenPaymentId = null;
      const row = (this.data || []).find(r => r.id == openId);
      setTimeout(() => {
        if (!row) {
          toast(`找不到套用記錄 #${openId}`, 'warning');
          return;
        }
        if (row.payment_type === 'interim_cert') {
          Payments.openSavedCertPreview(openId);
        } else {
          Payments.openEdit(openId);
        }
      }, 120);
    }
    if (this._pendingTab) {
      const t = this._pendingTab;
      this._pendingTab = null;
      this.setTab(t);
    } else if (App.currentPage === 'payments') {
      this.setTab(this._tab);
    }
  },

  sortBy(key) {
    if (this.sortKey === key) {
      this.sortDir = this.sortDir === 'asc' ? 'desc' : 'asc';
    } else {
      this.sortKey = key;
      this.sortDir = ['invoice_date', 'contract_amount', 'paid_amount', 'remainder_amount'].includes(key)
        ? 'desc' : 'asc';
    }
    this.applySort();
    this.render();
  },

  _sortValue(row, key) {
    switch (key) {
      case 'seq_no': return parseFloat(row.seq_no) || 0;
      case 'invoice_date': return row.invoice_date || '';
      case 'invoice_no': return (row.invoice_no || '').toLowerCase();
      case 'sc_no': return (row.sc_no || '').toLowerCase();
      case 'company': return ((row.company_name_en || row.company_name_zh || '')).toLowerCase();
      case 'description': return (row.description || '').toLowerCase();
      case 'contract_amount':
      case 'paid_amount':
      case 'remainder_amount': return parseFloat(row[key]) || 0;
      case 'oa_ref': return (row.oa_ref || '').toLowerCase();
      default: return '';
    }
  },

  _sortIsEmpty(row, key) {
    switch (key) {
      case 'company': return !row.company_name_en && !row.company_name_zh;
      case 'contract_amount':
      case 'paid_amount':
      case 'remainder_amount': return row[key] == null || row[key] === '';
      default: return !this._sortValue(row, key);
    }
  },

  applySort() {
    if (!this.sortKey || !this.filtered.length) return;
    const key = this.sortKey;
    const dir = this.sortDir === 'asc' ? 1 : -1;
    const isNum = ['seq_no', 'contract_amount', 'paid_amount', 'remainder_amount'].includes(key);
    this.filtered.sort((a, b) => {
      const aEmpty = this._sortIsEmpty(a, key);
      const bEmpty = this._sortIsEmpty(b, key);
      if (aEmpty && bEmpty) return 0;
      if (aEmpty) return 1;
      if (bEmpty) return -1;
      const va = this._sortValue(a, key);
      const vb = this._sortValue(b, key);
      return (isNum ? (va - vb) : String(va).localeCompare(String(vb), 'zh-Hant')) * dir;
    });
  },

  updateSortHeaders() {
    document.querySelectorAll('#payTableHead .th-sortable').forEach(th => {
      th.classList.remove('sort-asc', 'sort-desc');
      const icon = th.querySelector('.sort-icon');
      const key = th.dataset.sort;
      if (key === this.sortKey) {
        th.classList.add(this.sortDir === 'asc' ? 'sort-asc' : 'sort-desc');
        if (icon) icon.textContent = this.sortDir === 'asc' ? '↑' : '↓';
      } else if (icon) {
        icon.textContent = '↕';
      }
    });
  },

  render() {
    if (!this._visibleCols) this._initColPrefs();
    const tbody = document.getElementById('payTableBody');
    const count = document.getElementById('payCount');
    const totalPaidEl = document.getElementById('payTotalPaid');
    const colSpan = this._visibleColCount();
    count.textContent = `${this.filtered.length} 條`;
    const totalPaid = this.filtered.reduce((s, r) => {
      if (this._isRevoked(r)) return s;
      return s + (parseFloat(r.paid_amount) || 0);
    }, 0);
    setAmtEl(totalPaidEl, totalPaid, 'expense');

    if (this.filtered.length === 0) {
      tbody.innerHTML = `<tr><td colspan="${colSpan}"><div class="empty-state" style="padding:48px"><div class="empty-icon">💰</div><div class="empty-title">暫無付款登記</div><div class="empty-sub">點擊「新增記錄」或上傳PDF自動識別</div></div></td></tr>`;
      this.applyColVisibility();
      return;
    }

    tbody.innerHTML = this.filtered.map(r => {
      const remDisp = this._remainderDisplay(r);
      const paidDisp = this._paidDisplay(r);
      const remClass = remDisp.amount == null ? '' : amtClass(remDisp.amount, 'expense');
      const softRevoked = this._isCertRestored(r);
      const typeTag = r.payment_type === 'interim_cert'
        ? ` <span class="badge badge-info" style="font-size:9px">糧款計算書</span>${softRevoked && r.can_revert_to_normal ? ' <span class="badge badge-warning" style="font-size:9px">待還原原本列</span>' : softRevoked ? ' <span class="badge badge-muted" style="font-size:9px">待重新提交</span>' : ''}` : '';
      const oaBadge = r.oa_ref === 'OK' ? '<span class="badge badge-success">OK</span>' :
                      r.oa_ref === '-'  ? '<span class="badge badge-muted">—</span>' :
                      r.oa_ref          ? `<span class="badge badge-warning">${r.oa_ref}</span>` : '—';
      return `
        <tr onclick="Payments.openEdit(${r.id})">
          <td class="td-muted pay-col-seq" data-col="seq" style="font-size:11px">${r.seq_no || '—'}</td>
          <td class="td-muted pay-col-date" data-col="date">${fmtDate(r.invoice_date)}</td>
          <td class="td-mono td-muted pay-col-inv" data-col="inv" style="font-size:11px">${r.invoice_no || '—'}</td>
          <td class="pay-col-sc" data-col="sc">${fmtRefNo(r.sc_no)}${typeTag}</td>
          <td class="td-company-name pay-col-co" data-col="co">${paymentCompanyNameHtml(r)}</td>
          <td class="td-muted pay-col-desc" data-col="desc" title="${escHtml(r.description || '')}">${r.description || '—'}</td>
          <td class="td-amount pay-col-amt" data-col="contract">${fmt(r.contract_amount)}</td>
          <td class="td-amount pay-col-amt" data-col="paid">${paidDisp.html}</td>
          <td class="td-amount pay-col-amt ${remClass}" data-col="remainder">${remDisp.html || fmtExpense(remDisp.amount)}</td>
          <td class="pay-col-oa" data-col="oa">${oaBadge}</td>
          <td class="pay-col-act" data-col="act" onclick="event.stopPropagation()">
            ${this._renderPayActions(r)}
          </td>
        </tr>`;
    }).join('');
    this.updateSortHeaders();
    this.applyColVisibility();
  },

  renderEmpty() {
    if (!this._visibleCols) this._initColPrefs();
    const colSpan = this._visibleColCount();
    document.getElementById('payTableBody').innerHTML = `
      <tr><td colspan="${colSpan}"><div class="empty-state" style="padding:48px">
        <div class="empty-icon">📁</div>
        <div class="empty-title">請先選擇項目</div>
      </div></td></tr>`;
    this.applyColVisibility();
    document.getElementById('payCount').textContent = '0 條';
    document.getElementById('payTotalPaid').textContent = 'HK$0.00';
    document.getElementById('payTotalPaid').classList.remove('negative', 'positive');
    const scBody = document.getElementById('scTableBody');
    if (scBody) {
      scBody.innerHTML = `<tr><td colspan="8"><div class="empty-state" style="padding:40px">請先選擇項目</div></td></tr>`;
    }
    const scCount = document.getElementById('scCount');
    if (scCount) scCount.textContent = '0 項';
  },

  search() {
    clearTimeout(this._searchTimer);
    this._searchTimer = setTimeout(() => this.load(), 400);
  },

  filterBySc() { this.load(); },

  populateScFilter() {
    const sel = document.getElementById('payFilterSc');
    const cur = sel.value;
    sel.innerHTML = '<option value="">全部判項編號</option>';
    (App.scList || []).forEach(sc => {
      const opt = document.createElement('option');
      opt.value = sc.sc_no;
      opt.textContent = `${sc.sc_no} — ${formatCompanyPrimary(sc.company_name_en, sc.company_name_zh)}`.substring(0, 40);
      sel.appendChild(opt);
    });
    sel.value = cur && (App.scList || []).some(sc => sc.sc_no === cur) ? cur : '';
    this.populateScSelect();
  },

  populateScSelect() {
    const sel = document.getElementById('fScNo');
    const cur = sel?.value;
    if (!sel) return;
    sel.innerHTML = '<option value="">— 選擇判項編號 —</option>';
    (App.scList || []).forEach(sc => {
      const opt = document.createElement('option');
      opt.value = sc.sc_no;
      opt.textContent = `${sc.sc_no} — ${formatCompanyPrimary(sc.company_name_en, sc.company_name_zh)}`.substring(0, 45);
      sel.appendChild(opt);
    });
    if (cur && (App.scList || []).some(sc => sc.sc_no === cur)) sel.value = cur;
    this.populateBcSelect();
  },

  populateBcSelect() {
    const sel = document.getElementById('fBcToSub');
    const cur = sel?.value;
    if (!sel) return;
    sel.innerHTML = '<option value="">— 選擇判項編號／公司 —</option>';
    (App.scList || []).forEach(sc => {
      const opt = document.createElement('option');
      let company = formatCompanyPrimary(sc.company_name_en, sc.company_name_zh);
      if (company === '—') company = '';
      opt.value = sc.sc_no;
      opt.textContent = company ? `${sc.sc_no} — ${company}`.substring(0, 50) : sc.sc_no;
      sel.appendChild(opt);
    });
    if (cur) this._ensureBcOption(cur);
    if (cur) sel.value = cur;
  },

  _ensureBcOption(val) {
    const sel = document.getElementById('fBcToSub');
    if (!sel || !val) return;
    if ([...sel.options].some(o => o.value === val)) return;
    const legacy = document.createElement('option');
    legacy.value = val;
    legacy.textContent = val;
    sel.appendChild(legacy);
  },

  _getPayType() {
    return document.querySelector('input[name="payType"]:checked')?.value || 'normal';
  },

  _setPayType(type) {
    const val = type === 'interim_cert' ? 'interim_cert' : 'normal';
    const el = document.querySelector(`input[name="payType"][value="${val}"]`);
    if (el) el.checked = true;
    this.onPayTypeChange();
  },

  _setAmountFieldsReadonly(readonly) {
    ['fContractAmt', 'fPaidAmt'].forEach(id => {
      const el = document.getElementById(id);
      if (!el) return;
      el.readOnly = readonly;
      el.style.opacity = readonly ? '0.85' : '';
    });
  },

  async onPayTypeChange() {
    const isInterim = this._getPayType() === 'interim_cert';
    const extras = document.getElementById('payInterimExtras');
    const saveBtn = document.getElementById('paySaveBtn');
    const nextBtn = document.getElementById('payNextBtn');
    if (extras) extras.style.display = isInterim ? 'block' : 'none';
    if (saveBtn) saveBtn.style.display = isInterim ? 'none' : '';
    if (nextBtn) nextBtn.style.display = isInterim ? '' : 'none';
    this._setAmountFieldsReadonly(isInterim);
    if (isInterim) {
      await this.calcInterimAmounts();
      await this.ensureCertTemplates();
      await this.loadScVoPickList();
    } else {
      this._setAmountFieldsReadonly(false);
    }
  },

  async onScChange(scNo) {
    const sc = App.scList.find(s => s.sc_no === scNo);
    if (!sc) return;
      document.getElementById('fCompanyEn').value = sc.company_name_en || '';
      document.getElementById('fCompanyZh').value = sc.company_name_zh || '';
      document.getElementById('fDesc').value = sc.description || '';
    if (this._getPayType() === 'interim_cert') {
      await this.ensureCertTemplates();
      await this.loadScVoPickList();
      await this.calcInterimAmounts();
    } else {
      document.getElementById('fContractAmt').value = sc.contract_amount || 0;
      this.calcRemainder();
    }
  },

  calcRemainder() {
    const ca = parseFloat(document.getElementById('fContractAmt').value) || 0;
    const pa = parseFloat(document.getElementById('fPaidAmt').value) || 0;
    document.getElementById('fRemAmt').value = fmtInputNum(ca - pa);
  },

  _getSelectedScVoItems() {
    const list = document.getElementById('fScVoPickList');
    if (!list) return [];
    return [...list.querySelectorAll('.sc-vo-cb[data-kind="record"]:checked')]
      .map(cb => this._scVoOptions.find(d => String(d.id) === cb.dataset.id))
      .filter(Boolean);
  },

  _getSelectedStandardCodes() {
    const list = document.getElementById('fScVoPickList');
    if (!list) return [];
    return [...list.querySelectorAll('.sc-vo-cb[data-kind="standard"]:checked')]
      .map(cb => cb.dataset.code)
      .filter(Boolean);
  },

  _readStandardLines() {
    const out = {};
    this._getSelectedStandardCodes().forEach(code => {
      const inp = document.querySelector(`#fScVoPickList .std-amt-input[data-code="${code}"]`);
      const v = inp ? parseFloat(inp.value) : 0;
      out[code] = Number.isNaN(v) ? 0 : v;
    });
    return out;
  },

  _getScDeductionTotalPositive() {
    return this._getSelectedDeductions().reduce((s, d) => s + Math.abs(parseFloat(d.amount) || 0), 0);
  },

  _getStandardAdditionTotal() {
    if (!this._standardLineTemplates) return 0;
    const lines = this._readStandardLines();
    return this._standardLineTemplates
      .filter(t => t.direction === 'add')
      .reduce((s, t) => s + Math.abs(parseFloat(lines[t.code]) || 0), 0);
  },

  _getStandardLinesDeductionPositive() {
    if (!this._standardLineTemplates) return 0;
    const lines = this._readStandardLines();
    return this._standardLineTemplates
      .filter(t => t.direction === 'ded')
      .reduce((s, t) => s + Math.abs(parseFloat(lines[t.code]) || 0), 0);
  },

  _getAdjustmentNet() {
    return this._getStandardAdditionTotal() - this._getStandardLinesDeductionPositive();
  },

  _getDeductionTotalPositive() {
    return this._getScDeductionTotalPositive() + this._getStandardLinesDeductionPositive();
  },

  onPickItemChange() {
    document.querySelectorAll('#fScVoPickList .std-amt-input').forEach(inp => {
      const cb = document.querySelector(`#fScVoPickList .sc-vo-cb[data-code="${inp.dataset.code}"]`);
      const on = cb?.checked;
      inp.disabled = !on;
      if (!on) inp.value = '';
    });
    this.onScVoPickChange();
  },

  _getSelectedDeductions() {
    return this._getSelectedScVoItems().filter(r =>
      r.record_type === 'deduction' || (parseFloat(r.amount) || 0) < 0
    );
  },

  _getSelectedVos() {
    return this._getSelectedScVoItems().filter(r => r.record_type === 'vo');
  },

  _getVoProvisionalTotal() {
    return this._getSelectedVos().reduce((s, d) => s + Math.abs(parseFloat(d.amount) || 0), 0);
  },

  /** 今期原合約完成額（A 行暫批）= 淨額 − VO − 調整項淨額（保固金今期=0 時） */
  _getAProvisionalEstimate() {
    const net = this._getNetCertTotal();
    const vo = this._getVoProvisionalTotal();
    const adj = this._getAdjustmentNet();
    return Math.max(0, Math.round((net - vo - adj) * 100) / 100);
  },

  _getNetCertTotal() {
    const el = document.getElementById('fNetCertTotal');
    if (el && el.value !== '') return parseFloat(el.value) || 0;
    const paid = parseFloat(document.getElementById('fPaidAmt')?.value) || 0;
    return paid;
  },

  async ensureCertTemplates() {
    if (this._scVoTemplates) return;
    const rows = await api('GET', '/sc-vo-templates', null, { silent: true }) || [];
    this._scVoTemplates = rows.filter(t => t.source === 'sc_vo');
    this._standardLineTemplates = rows.filter(t => t.source === 'cert_standard');
  },

  _templateLabelForRecord(r) {
    if (!r.line_code || !this._scVoTemplates) return null;
    const tpl = this._scVoTemplates.find(t => t.code === r.line_code);
    return tpl ? (tpl.cert_label || tpl.description) : null;
  },

  _standardShortLabel(t) {
    return (t.cert_label || t.description || t.code).replace(/^加:\s*|^減:\s*/, '').trim();
  },

  /** 空陣列 [] 在 JS 為 truthy，須用 length 判斷；否則標準項還原失敗 */
  _standardCodesFromCert(cert, stdLines) {
    const std = stdLines || cert?.standard_lines || {};
    const codes = cert?.selected_standard_codes;
    if (Array.isArray(codes) && codes.length) return codes;
    return Object.keys(std);
  },

  _standardCodesFromPickOpts(pickOpts = {}) {
    const std = pickOpts.standardLines || {};
    const codes = pickOpts.standardCodes;
    if (Array.isArray(codes) && codes.length) return codes;
    return Object.keys(std);
  },

  _getAutoRemarkB() {
    return this._getSelectedVos()
      .map(v => {
        const id = String(v.id);
        const entry = this._voRemarks[id];
        if (entry && !entry.auto) return (entry.text || '').trim();
        return this._defaultVoRemark(v);
      })
      .filter(Boolean)
      .join('、')
      .slice(0, 80);
  },

  _defaultVoRemark(v) {
    const desc = (v.description || '').trim();
    if (desc) return desc.length > 80 ? desc.slice(0, 80) : desc;
    return (v.ref_no || '').trim();
  },

  _getAutoRemarkA() {
    const scNo = document.getElementById('fScNo')?.value;
    const sc = App.scList.find(s => s.sc_no === scNo);
    const scContract = parseFloat(sc?.contract_sum || sc?.contract_amount) || 0;
    if (scContract <= 0) return '';
    const aProv = this._getAProvisionalEstimate();
    const aCur = (this._prevACum || 0) + aProv;
    const pct = Math.round(aCur / scContract * 1000) / 10;
    const pctStr = Number.isInteger(pct) ? String(pct) : pct.toFixed(1);
    return `${pctStr}% Work Done`;
  },

  _resetLineRemarks() {
    this._lineRemarks = {
      A: { text: '', auto: true },
      B: { text: '', auto: true },
      C: { text: '', auto: true },
    };
    this._voRemarks = {};
    this._prevACum = null;
    this._prevACumScNo = null;
    ['A', 'C'].forEach(k => {
      const el = document.getElementById(`fLineRemark${k}`);
      const hint = document.getElementById(`fLineRemark${k}Hint`);
      if (el) el.value = '';
      if (hint) hint.textContent = '';
    });
    const bHint = document.getElementById('fLineRemarkBHint');
    if (bHint) bHint.textContent = '';
    this._renderVoRemarkTable();
  },

  _applyVoRemarksToForm(voRemarks) {
    this._voRemarks = {};
    if (voRemarks && typeof voRemarks === 'object') {
      Object.entries(voRemarks).forEach(([id, entry]) => {
        const parsed = typeof entry === 'string' ? { text: entry, auto: false } : entry;
        this._voRemarks[id] = {
          text: parsed?.text || '',
          auto: typeof parsed?.auto === 'boolean' ? parsed.auto : !parsed?.text,
        };
      });
    }
    this._renderVoRemarkTable();
  },

  _readVoRemarks() {
    const out = {};
    this._getSelectedVos().forEach(v => {
      const id = String(v.id);
      const inp = document.querySelector(`#fVoRemarkList .vo-remark-input[data-vo-id="${id}"]`);
      out[id] = {
        text: (inp?.value || this._voRemarks[id]?.text || '').trim(),
        auto: !!this._voRemarks[id]?.auto,
      };
    });
    return out;
  },

  onVoRemarkInput(voId) {
    const id = String(voId);
    const inp = document.querySelector(`#fVoRemarkList .vo-remark-input[data-vo-id="${id}"]`);
    if (!this._voRemarks[id]) this._voRemarks[id] = { text: '', auto: true };
    this._voRemarks[id].auto = false;
    this._voRemarks[id].text = inp?.value || '';
    this._syncVoRemarkRowHint(id);
    this._lineRemarks.B = { text: this._getAutoRemarkB(), auto: this._isVoRemarksAllAuto() };
    this._updateLineRemarkHint('B');
  },

  _isVoRemarksAllAuto() {
    return this._getSelectedVos().every(v => this._voRemarks[String(v.id)]?.auto !== false);
  },

  _syncVoRemarkRowHint(voId) {
    const id = String(voId);
    const row = document.querySelector(`#fVoRemarkList .vo-remark-input[data-vo-id="${id}"]`)
      ?.closest('td');
    const hint = row?.querySelector('.ic-vo-remark-hint');
    if (hint) {
      hint.textContent = this._voRemarks[id]?.auto ? '系統自動' : '已手改';
    }
  },

  _renderVoRemarkTable() {
    const wrap = document.getElementById('fVoRemarkList');
    if (!wrap) return;
    const vos = this._getSelectedVos();
    if (!vos.length) {
      wrap.innerHTML = '<div class="form-hint ic-vo-remark-empty">勾選 VO 後可逐條填寫備註 · 計算書將展開 <strong>B1、B2…</strong> 分行</div>';
      this._updateLineRemarkHint('B');
      return;
    }
    vos.forEach(v => {
      const id = String(v.id);
      if (!this._voRemarks[id]) this._voRemarks[id] = { text: '', auto: true };
      if (this._voRemarks[id].auto) {
        this._voRemarks[id].text = this._defaultVoRemark(v);
      }
    });
    Object.keys(this._voRemarks).forEach(id => {
      if (!vos.some(v => String(v.id) === id)) delete this._voRemarks[id];
    });
    const rows = vos.map(v => {
      const id = String(v.id);
      const entry = this._voRemarks[id];
      const amt = parseFloat(v.amount) || 0;
      const hint = entry.auto ? '系統自動' : '已手改';
      return `<tr>
        <td>${escHtml(v.ref_no || '—')}</td>
        <td class="vo-remark-amt">${fmt(amt)}</td>
        <td>
          <input type="text" class="form-input vo-remark-input" data-vo-id="${escHtml(id)}"
            value="${escHtml(entry.text || '')}" placeholder="例：代支（預填變更內容）"
            oninput="Payments.onVoRemarkInput('${escHtml(id)}')">
          <div class="form-hint ic-line-remark-hint ic-vo-remark-hint">${hint}</div>
        </td>
      </tr>`;
    }).join('');
    wrap.innerHTML = `<table class="vo-remark-table">
      <thead><tr><th>VO 編號</th><th>今期金額</th><th>備註</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
    this._lineRemarks.B = { text: this._getAutoRemarkB(), auto: this._isVoRemarksAllAuto() };
    this._updateLineRemarkHint('B');
  },

  _applyLineRemarksToForm(remarks) {
    if (!remarks) return;
    ['A', 'C'].forEach(k => {
      const entry = remarks[k];
      if (!entry) return;
      const parsed = typeof entry === 'string' ? { text: entry, auto: false } : entry;
      this._lineRemarks[k] = {
        text: parsed.text || '',
        auto: typeof parsed.auto === 'boolean' ? parsed.auto : !parsed.text,
      };
      const el = document.getElementById(`fLineRemark${k}`);
      if (el) el.value = parsed.text || '';
      this._updateLineRemarkHint(k);
    });
    if (remarks.B) {
      const parsed = typeof remarks.B === 'string' ? { text: remarks.B, auto: false } : remarks.B;
      this._lineRemarks.B = {
        text: parsed.text || '',
        auto: typeof parsed.auto === 'boolean' ? parsed.auto : !parsed.text,
      };
    }
  },

  _readLineRemarks() {
    const out = {};
    ['A', 'C'].forEach(k => {
      const el = document.getElementById(`fLineRemark${k}`);
      out[k] = {
        text: (el?.value || '').trim(),
        auto: !!this._lineRemarks[k]?.auto,
      };
    });
    out.B = {
      text: this._getAutoRemarkB(),
      auto: this._isVoRemarksAllAuto(),
    };
    return out;
  },

  onLineRemarkInput(key) {
    if (key === 'B') return;
    const el = document.getElementById(`fLineRemark${key}`);
    if (!this._lineRemarks[key]) this._lineRemarks[key] = { text: '', auto: true };
    this._lineRemarks[key].auto = false;
    this._lineRemarks[key].text = el?.value || '';
    this._updateLineRemarkHint(key);
  },

  _updateLineRemarkHint(key) {
    const hint = document.getElementById(`fLineRemark${key}Hint`);
    if (!hint) return;
    if (key === 'B') {
      const vos = this._getSelectedVos();
      if (!vos.length) {
        hint.textContent = '';
        return;
      }
      const merged = this._getAutoRemarkB();
      hint.textContent = this._isVoRemarksAllAuto()
        ? `合併摘要：${merged || '—'}（計算書按 VO 分行顯示）`
        : `合併摘要：${merged || '—'}（部分備註已手改）`;
      return;
    }
    hint.textContent = this._lineRemarks[key]?.auto
      ? '系統自動（數值／勾選變更時會更新）'
      : '已手動修改（系統不再覆蓋）';
  },

  async _ensurePrevACum() {
    const scNo = document.getElementById('fScNo')?.value;
    if (!scNo || !App.currentProject) {
      this._prevACum = 0;
      this._prevACumScNo = null;
      return;
    }
    if (this._prevACumScNo === scNo && this._prevACum != null) return;
    this._prevACumScNo = scNo;
    this._prevACum = 0;
    try {
      const base = this._readFormBase();
      const cert = {
        ...base,
        project_id: App.currentProject.id,
        payment_type: 'interim_cert',
        vo_ids: [],
        deduction_ids: [],
        standard_lines: {},
        selected_standard_codes: [],
        exclude_payment_id: document.getElementById('payModalId')?.value || null,
        project: { project_code: App.currentProject.project_code },
      };
      const model = await this._fetchCertModel(cert);
      const lineA = (model.lines || []).find(l => (l.label || '').startsWith('A.'));
      this._prevACum = parseFloat(lineA?.cum_previous) || 0;
    } catch {
      this._prevACum = 0;
    }
  },

  _syncLineRemarkDefaults() {
    const autoFns = {
      A: () => this._getAutoRemarkA(),
      C: () => '',
    };
    ['A', 'C'].forEach(k => {
      if (!this._lineRemarks[k]?.auto) return;
      const text = autoFns[k]();
      this._lineRemarks[k].text = text;
      const el = document.getElementById(`fLineRemark${k}`);
      if (el) el.value = text;
      this._updateLineRemarkHint(k);
    });
    this._getSelectedVos().forEach(v => {
      const id = String(v.id);
      if (!this._voRemarks[id]) this._voRemarks[id] = { text: '', auto: true };
      if (this._voRemarks[id].auto) {
        this._voRemarks[id].text = this._defaultVoRemark(v);
      }
    });
    this._renderVoRemarkTable();
  },

  async syncInterimLineRemarks() {
    if (this._getPayType() !== 'interim_cert') return;
    await this._ensurePrevACum();
    this._syncLineRemarkDefaults();
  },

  onScVoPickChange() {
    const voEl = document.getElementById('fVoTotal');
    const addEl = document.getElementById('fAddTotal');
    const dedEl = document.getElementById('fDeductionTotal');
    const addSubEl = document.getElementById('fAddSubtotal');
    const vo = this._getVoProvisionalTotal();
    const stdAdd = this._getStandardAdditionTotal();
    if (voEl) voEl.value = fmtInputNum(vo);
    if (addEl) addEl.value = fmtInputNum(stdAdd);
    if (addSubEl) addSubEl.value = fmtInputNum(vo + stdAdd);
    if (dedEl) dedEl.value = fmtInputNum(this._getDeductionTotalPositive());
    this.calcInterimAmounts();
  },

  async calcInterimAmounts() {
    const scNo = document.getElementById('fScNo').value;
    const sc = App.scList.find(s => s.sc_no === scNo);
    if (!sc) {
      ['fContractAmt', 'fPaidAmt', 'fRemAmt', 'fNetCertTotal'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = '';
      });
      return;
    }
    const contract = parseFloat(sc.contract_sum || sc.contract_amount) || 0;
    const voSum = parseFloat(sc.vo_amount) || 0;
    const totalContract = contract + voSum;
    const prevPaid = parseFloat(sc.total_paid) || 0;
    const scDed = this._getScDeductionTotalPositive();
    const adjNet = this._getAdjustmentNet();
    const voProv = this._getVoProvisionalTotal();
    const balance = Math.max(0, totalContract - prevPaid - scDed);
    // 本次付款 = 合約餘額 + 加項 − 標準扣款 + VO（B 行）；A 行由報告反推
    const thisPay = Math.max(0, balance + adjNet + voProv);
    const netEl = document.getElementById('fNetCertTotal');
    if (netEl) netEl.value = fmtInputNum(thisPay);
    document.getElementById('fContractAmt').value = fmtInputNum(totalContract);
    document.getElementById('fPaidAmt').value = fmtInputNum(thisPay);
    document.getElementById('fRemAmt').value = fmtInputNum(Math.max(0, totalContract - prevPaid - thisPay));
    await this.syncInterimLineRemarks();
  },

  async loadScVoPickList(preselectIds, pickOpts = {}) {
    const p = App.currentProject;
    const scNo = document.getElementById('fScNo')?.value;
    const list = document.getElementById('fScVoPickList');
    const hint = document.getElementById('fScVoHint');
    if (!list || !p) return;
    await this.ensureCertTemplates();
    list.innerHTML = '';
    this._scVoOptions = [];
    const stdVals = pickOpts.standardLines || {};
    const stdChecked = new Set(this._standardCodesFromPickOpts(pickOpts));
    const preIds = new Set((preselectIds || []).map(String));
    const payId = document.getElementById('payModalId')?.value;
    const autoSelectRecords = pickOpts.autoSelectRecords !== false;
    // 新增計算書，或編輯但從未套用 VO／扣款 → 自動勾選所有未套用項目
    const autoCheckAll = autoSelectRecords && (!payId || preIds.size === 0);

    if (!scNo) {
      if (hint) hint.textContent = '請先選擇判項編號';
      return;
    }

    const rows = await api(
      'GET',
      `/projects/${p.id}/sc-vo-records?sc_no=${encodeURIComponent(scNo)}&unapplied=1`,
      null,
      { silent: true },
    ) || [];
    this._scVoOptions = rows.sort((a, b) => {
      const ta = a.record_type === 'vo' ? 0 : 1;
      const tb = b.record_type === 'vo' ? 0 : 1;
      if (ta !== tb) return ta - tb;
      return String(a.ref_no || '').localeCompare(String(b.ref_no || ''), 'zh-Hant');
    });

    let html = '';

    if (this._scVoOptions.length) {
      html += '<div class="sc-vo-pick-group-title">登記項目</div>';
      this._scVoOptions.forEach(d => {
        const isVo = d.record_type === 'vo';
        const tag = isVo ? 'VO' : '扣款';
        const amt = parseFloat(d.amount) || 0;
        const name = this._templateLabelForRecord(d) || d.description || d.ref_no || '—';
        const checked = preIds.has(String(d.id)) || autoCheckAll ? ' checked' : '';
        html += `
          <label class="sc-vo-pick-item">
            <input type="checkbox" class="sc-vo-cb" data-kind="record" data-id="${d.id}"${checked}
              onchange="Payments.onPickItemChange()">
            <span class="sc-vo-pick-tag">${tag}</span>
            <span class="sc-vo-pick-label">${escHtml(name)}</span>
            <span class="sc-vo-pick-amt">${fmt(amt)}</span>
          </label>`;
      });
    }

    if (this._standardLineTemplates?.length) {
      html += '<div class="sc-vo-pick-group-title">標準調整項</div>';
      this._standardLineTemplates.forEach(t => {
        const tag = t.direction === 'add' ? '加' : '減';
        const checked = stdChecked.has(t.code) ? ' checked' : '';
        const val = stdVals[t.code] != null && stdVals[t.code] !== '' ? stdVals[t.code] : '';
        const disabled = checked ? '' : ' disabled';
        html += `
          <label class="sc-vo-pick-item sc-vo-pick-item-std">
            <input type="checkbox" class="sc-vo-cb" data-kind="standard" data-code="${escHtml(t.code)}"${checked}
              onchange="Payments.onPickItemChange()">
            <span class="sc-vo-pick-tag">${tag}</span>
            <span class="sc-vo-pick-label">${escHtml(this._standardShortLabel(t))}</span>
            <input type="number" class="form-input std-amt-input" data-code="${escHtml(t.code)}"
              placeholder="0" step="0.01" value="${val !== '' ? escHtml(String(val)) : ''}"${disabled}
              onclick="event.stopPropagation()" onmousedown="event.stopPropagation()"
              oninput="Payments.onScVoPickChange()">
          </label>`;
      });
    }

    if (!html) {
      list.innerHTML = '<div class="sc-vo-pick-empty">此判項暫無登記項目 · 可勾選下方標準項，或至「分判變更以及扣款登記」新增</div>';
    } else {
      list.innerHTML = html;
    }

    if (hint) {
      hint.textContent = autoCheckAll
        ? '未套用項目已自動勾選 · 不需要的請取消 · [VO]→B 行 · [扣款]→減:列 · 標準項請填今期金額'
        : '勾選項目才會出現在計算書 · [VO]→B 行 · [扣款/減]→減:列 · 標準項請填今期金額';
    }
    this.onScVoPickChange();
  },

  _readFormBase() {
    const scNo = document.getElementById('fScNo').value;
    const sc = App.scList.find(s => s.sc_no === scNo);
    return {
      project_id: App.currentProject?.id,
      sc_id: sc?.id || null,
      sc_no: scNo || null,
      seq_no: document.getElementById('payModalId').value
        ? (document.getElementById('fSeqNo').value || null) : null,
      invoice_date: document.getElementById('fInvDate').value || null,
      invoice_no: document.getElementById('fInvNo').value || null,
      quotation_no: document.getElementById('fQuotNo').value || null,
      company_name_en: document.getElementById('fCompanyEn').value || null,
      company_name_zh: document.getElementById('fCompanyZh').value || null,
      description: document.getElementById('fDesc').value || null,
      contract_amount: parseFloat(document.getElementById('fContractAmt').value) || 0,
      paid_amount: parseFloat(document.getElementById('fPaidAmt').value) || 0,
      remainder_amount: parseFloat(document.getElementById('fRemAmt').value) || 0,
      oa_ref: document.getElementById('fOaRef').value || null,
      oa_no: document.getElementById('fOaNo').value || null,
      mc_ip_no: null,
      bc_to_sub: document.getElementById('fBcToSub').value || null,
      sub_ip_no: null,
      backcharge_amount: parseFloat(document.getElementById('fBackchargeAmt').value) || 0,
      remark: document.getElementById('fRemark').value || null,
      pdf_path: document.getElementById('fPdfPath').value || null,
    };
  },

  async _buildInterimCertPayload() {
    const base = this._readFormBase();
    const p = App.currentProject;
    const sc = App.scList.find(s => s.sc_no === base.sc_no);
    const payId = document.getElementById('payModalId')?.value;
    const existing = payId ? (this.data || []).find(r => r.id == payId) : null;
    const oldCert = existing?.interim_cert && typeof existing.interim_cert === 'object'
      ? existing.interim_cert : {};
    const deductions = this._getSelectedDeductions().map(d => ({
      id: d.id,
      ref_no: d.ref_no,
      description: d.description,
      amount: parseFloat(d.amount) || 0,
    }));
    const voItems = this._getSelectedVos().map(d => ({
      id: d.id,
      ref_no: d.ref_no,
      description: d.description,
      amount: parseFloat(d.amount) || 0,
    }));
    const dedTotal = this._getDeductionTotalPositive();
    let appNo = '第一期';
    if (p && base.sc_no) {
      try {
        const n = await api('GET', `/projects/${p.id}/payments?sc_no=${encodeURIComponent(base.sc_no)}`, null, { silent: true });
        const count = (n || []).filter(r => r.payment_type === 'interim_cert' && !r.revoked_at).length;
        appNo = `第${count + 1}期`;
      } catch (e) {
        appNo = '第一期';
      }
    }
    const prevPaid = oldCert.pre_submit_sc_paid ?? oldCert.previous_paid
      ?? (sc ? (parseFloat(sc.total_paid) || 0) : 0);
    const totalContract = parseFloat(base.contract_amount) || 0;
    const preSubmitRem = oldCert.pre_submit_sc_remainder
      ?? Math.max(0, totalContract - prevPaid);
    const snapKeys = [
      'original_row_snapshot',
      'pre_submit_payment_type', 'pre_submit_row_paid', 'pre_submit_row_remainder', 'pre_submit_row_contract',
      'pre_submit_sc_paid', 'pre_submit_sc_remainder', 'previous_paid',
    ];
    const preserved = {};
    snapKeys.forEach(k => {
      if (oldCert[k] != null) preserved[k] = oldCert[k];
    });
    if (!preserved.original_row_snapshot && existing && existing.payment_type !== 'interim_cert') {
      preserved.pre_submit_payment_type = existing.payment_type || 'normal';
      preserved.pre_submit_row_paid = parseFloat(existing.paid_amount) || 0;
      preserved.pre_submit_row_remainder = parseFloat(existing.remainder_amount) || 0;
      preserved.pre_submit_row_contract = parseFloat(existing.contract_amount) || 0;
      preserved.original_row_snapshot = {
        payment_type: preserved.pre_submit_payment_type,
        paid: preserved.pre_submit_row_paid,
        remainder: preserved.pre_submit_row_remainder,
        contract: preserved.pre_submit_row_contract,
      };
    }
    return {
      ...base,
      ...preserved,
      project_id: p?.id,
      payment_type: 'interim_cert',
      deduction_ids: deductions.map(d => d.id),
      vo_ids: voItems.map(d => d.id),
      deduction_total: dedTotal,
      deductions,
      vo_items: voItems,
      previous_paid: preserved.previous_paid ?? prevPaid,
      pre_submit_sc_paid: preserved.pre_submit_sc_paid ?? prevPaid,
      pre_submit_sc_remainder: preserved.pre_submit_sc_remainder ?? preSubmitRem,
      net_payment: base.paid_amount,
      application_no: appNo,
      vo_amount: parseFloat(sc?.vo_amount) || 0,
      sc_contract_sum: parseFloat(sc?.contract_sum || sc?.contract_amount) || 0,
      trade_label: sc?.trade_label || sc?.description || '',
      mp_contract_sum: parseFloat(p?.contract_amount) || 0,
      work_period: p?.site_period_text || '',
      prepared_by: p?.person_in_charge || '',
      retention_pct: 0.05,
      standard_lines: this._readStandardLines(),
      selected_standard_codes: this._getSelectedStandardCodes(),
      a_current_provisional: this._getAProvisionalEstimate(),
      line_remarks: this._readLineRemarks(),
      vo_remarks: this._readVoRemarks(),
      b_expand_vo: true,
      exclude_payment_id: document.getElementById('payModalId')?.value || null,
      project: {
        project_code: p?.project_code,
        project_name: p?.project_name,
        project_name_en: p?.project_name_en,
        project_name_zh: p?.project_name_zh,
        client: p?.client,
        contract_amount: p?.contract_amount,
        site_period_text: p?.site_period_text,
        person_in_charge: p?.person_in_charge,
      },
      company_en: base.company_name_en,
      company_zh: base.company_name_zh,
    };
  },

  _moneyPlain(n) {
    if (n === null || n === undefined || n === '') return '-';
    const v = parseFloat(n);
    if (Number.isNaN(v)) return '-';
    const abs = Math.abs(v).toLocaleString('en-HK', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    if (v < 0) return `(${abs})`;
    if (v === 0) return '0.00';
    return abs;
  },

  _moneyAmt(n) {
    if (n === null || n === undefined || n === '') return '-';
    const v = parseFloat(n);
    if (Number.isNaN(v) || v === 0) return '-';
    const abs = Math.abs(v).toLocaleString('en-HK', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    return v < 0 ? `(${abs})` : abs;
  },

  _renderCertPreviewHtml(model) {
    if (!model) return '';
    const lineRows = (model.lines || []).map(line => {
      const sum = line.label === '總計' || line.label === 'Sub-total (A+B)';
      const cls = sum ? ' class="ic-sum"' : '';
      return `<tr${cls}>
        <td>${escHtml(line.label)}</td>
        <td class="ic-num">${this._moneyAmt(line.cum_current)}</td>
        <td class="ic-num">${this._moneyAmt(line.cum_previous)}</td>
        <td class="ic-num">${this._moneyAmt(line.current_provisional)}</td>
        <td>${escHtml(line.remark || '')}</td>
      </tr>`;
    }).join('');
    const th = model.table_header || [];
    return `
      <div class="ic-header">
        <img class="ic-logo" src="/assets/mepork_logo.png" alt="Mepork">
        <div class="ic-title">${escHtml(model.title || '承判商工程中期糧款計算書')}</div>
      </div>
      <table class="ic-meta">
        <colgroup><col class="ic-c1"><col class="ic-c2"><col class="ic-c3"><col class="ic-c4"></colgroup>
        <tr><td>承判人/公司名稱(中) :</td><td>${escHtml(model.company_zh || '')}</td><td>發票號碼 :</td><td>${escHtml(model.invoice_no || '')}</td></tr>
        <tr><td>承判人/公司名稱(英) :</td><td>${escHtml(model.company_en || '')}</td><td>申請期數 :</td><td>${escHtml(model.application_no || '')}</td></tr>
        <tr><td>工作期間 :</td><td>${escHtml(model.work_period || '')}</td><td>日期 :</td><td>${escHtml(fmtDate(model.signature_date) || '')}</td></tr>
      </table>
      <table class="ic-meta" style="margin-top:10px">
        <colgroup><col class="ic-c1"><col class="ic-c2"><col class="ic-c3"><col class="ic-c4"></colgroup>
        <tr><td>工程編號:</td><td>${escHtml(model.project_code || '')}</td><td>合約承包價 :</td><td class="ic-num">${this._moneyPlain(model.sc_contract_sum)}</td></tr>
        <tr><td>工程名稱 :</td><td>${escHtml(model.project_name || '')}</td><td>後加/更改承包價 :</td><td class="ic-num">${this._moneyPlain(model.vo_amount)}</td></tr>
        <tr><td>工程性質/工種 :</td><td>${escHtml(model.trade_label || '')}</td><td>合約總承包價 :</td><td class="ic-num">${this._moneyPlain(model.sc_total_sum)}</td></tr>
      </table>
      <table class="ic-amt">
        <colgroup>
          <col class="ic-a1"><col class="ic-a2"><col class="ic-a3"><col class="ic-a4"><col class="ic-a5">
        </colgroup>
        <thead>
          <tr>
            <th class="ic-th-left">${escHtml(th[0] || '累積至申請日期工程完成總額').replace(/\n/g, '<br>')}</th>
            <th class="ic-amt-c">${escHtml(th[1] || '今期累計金額 HK$').replace(/\n/g, '<br>')}</th>
            <th class="ic-amt-c">${escHtml(th[2] || '上期累計金額 HK$').replace(/\n/g, '<br>')}</th>
            <th class="ic-amt-c">${escHtml(th[3] || '今期暫批金額 HK$').replace(/\n/g, '<br>')}</th>
            <th>${escHtml(th[4] || '備註')}</th>
          </tr>
        </thead>
        <tbody>${lineRows}</tbody>
      </table>
      <table class="ic-meta ic-sig ic-amt" style="margin-top:12px">
        <colgroup>
          <col class="ic-a1"><col class="ic-a2"><col class="ic-a3"><col class="ic-a4"><col class="ic-a5">
        </colgroup>
        <tr><td>内部使用</td><td>Prepared by</td><td>QS</td><td>PM</td><td>General Manager</td></tr>
        <tr><td>簽署</td><td>${escHtml(model.prepared_by || '')}</td><td></td><td></td><td></td></tr>
        <tr><td>日期</td><td>${escHtml(fmtDate(model.signature_date) || '')}</td><td></td><td></td><td></td></tr>
      </table>`;
  },

  async _fetchCertModel(cert) {
    return api('POST', '/payments/interim-cert/model', cert, { silent: true });
  },

  /** 由付款記錄 + 已存 interim_cert 合併，確保 vo_ids／扣款等以 DB 最新為準 */
  _certFromPaymentRecord(r) {
    const stored = typeof r.interim_cert === 'object' && r.interim_cert ? { ...r.interim_cert } : {};
    const p = App.currentProject;
    return {
      ...stored,
      project_id: r.project_id || stored.project_id || p?.id,
      sc_no: r.sc_no || stored.sc_no,
      sc_id: stored.sc_id || null,
      invoice_date: r.invoice_date || stored.invoice_date,
      invoice_no: r.invoice_no || stored.invoice_no,
      quotation_no: r.quotation_no || stored.quotation_no,
      company_name_en: r.company_name_en || stored.company_en || stored.company_name_en,
      company_name_zh: r.company_name_zh || stored.company_zh || stored.company_name_zh,
      company_en: r.company_name_en || stored.company_en,
      company_zh: r.company_name_zh || stored.company_zh,
      description: r.description || stored.description,
      paid_amount: r.paid_amount ?? stored.paid_amount,
      contract_amount: r.contract_amount ?? stored.contract_amount,
      remainder_amount: r.remainder_amount ?? stored.remainder_amount,
      vo_ids: r.vo_ids || stored.vo_ids || [],
      deduction_ids: r.deduction_ids || stored.deduction_ids || [],
      deduction_total: r.deduction_total ?? stored.deduction_total ?? 0,
      exclude_payment_id: r.id,
      b_expand_vo: stored.b_expand_vo !== false,
      line_remarks: stored.line_remarks,
      vo_remarks: stored.vo_remarks,
      standard_lines: stored.standard_lines || {},
      selected_standard_codes: stored.selected_standard_codes || [],
      a_current_provisional: stored.a_current_provisional,
      project: stored.project || (p ? {
        project_code: p.project_code,
        project_name: p.project_name,
        project_name_en: p.project_name_en,
        project_name_zh: p.project_name_zh,
        client: p.client,
        contract_amount: p.contract_amount,
        site_period_text: p.site_period_text,
        person_in_charge: p.person_in_charge,
      } : {}),
    };
  },

  /** 編輯表單 → 計算書 payload（優先於已存 json） */
  async _certFromFormOrPayment(r) {
    if (document.getElementById('payModal')?.classList.contains('open')
      && this._getPayType() === 'interim_cert') {
      await this.calcInterimAmounts();
      await this.syncInterimLineRemarks();
      return this._buildInterimCertPayload();
    }
    if (r) return this._certFromPaymentRecord(r);
    return this._buildInterimCertPayload();
  },

  async goInterimPreview() {
    if (!App.currentProject) { toast('請先選擇項目', 'warning'); return; }
    if (!document.getElementById('fScNo').value) { toast('請選擇判項編號', 'warning'); return; }
    await this.calcInterimAmounts();
    await this.syncInterimLineRemarks();
    const cert = await this._buildInterimCertPayload();
    this._pendingCert = cert;
    try {
      this._pendingCertModel = await this._fetchCertModel(cert);
      cert.model = this._pendingCertModel;
      this._pendingCert = cert;
      document.getElementById('payCertPreview').innerHTML = this._renderCertPreviewHtml(this._pendingCertModel);
      this._setCertModalMode('create');
      document.getElementById('payCertModal').classList.add('open');
    } catch (e) {
      toast('無法產生計算書預覽', 'error');
    }
  },

  closeCertModal() {
    document.getElementById('payCertModal').classList.remove('open');
  },

  async submitInterimCert() {
    if (!this._pendingCert) { toast('無計算書資料', 'warning'); return; }
    const id = document.getElementById('payModalId').value;
    const cert = { ...this._pendingCert };
    const preserveKeys = [
      'original_row_snapshot',
      'pre_submit_payment_type', 'pre_submit_row_paid', 'pre_submit_row_remainder', 'pre_submit_row_contract',
      'pre_submit_sc_paid', 'pre_submit_sc_remainder', 'previous_paid',
    ];
    if (id) {
      const existing = (this.data || []).find(r => r.id == id);
      const oldCert = existing?.interim_cert && typeof existing.interim_cert === 'object'
        ? existing.interim_cert : {};
      if (existing && existing.payment_type !== 'interim_cert') {
        cert.pre_submit_payment_type = existing.payment_type || 'normal';
        cert.pre_submit_row_paid = parseFloat(existing.paid_amount) || 0;
        cert.pre_submit_row_remainder = parseFloat(existing.remainder_amount) || 0;
        cert.pre_submit_row_contract = parseFloat(existing.contract_amount) || 0;
        cert.original_row_snapshot = {
          payment_type: cert.pre_submit_payment_type,
          paid: cert.pre_submit_row_paid,
          remainder: cert.pre_submit_row_remainder,
          contract: cert.pre_submit_row_contract,
        };
      } else {
        preserveKeys.forEach(k => {
          if (oldCert[k] != null) cert[k] = oldCert[k];
        });
      }
    }
    const data = {
      ...this._readFormBase(),
      payment_type: 'interim_cert',
      paid_amount: cert.paid_amount,
      remainder_amount: cert.remainder_amount,
      contract_amount: cert.contract_amount,
      deduction_ids: cert.deduction_ids || [],
      vo_ids: cert.vo_ids || [],
      deduction_total: cert.deduction_total || 0,
      interim_cert_json: cert,
      ocr_status: null,
      pdf_path: null,
    };
    try {
      if (id) {
        await api('PUT', `/payments/${id}`, data);
        toast('計算書已更新', 'success');
      } else {
        await api('POST', '/payments', data);
        toast('計算書已提交', 'success');
      }
      this.closeCertModal();
      this.closeModal();
      await this.load();
      await this._refreshScList();
      await Dashboard.load();
    } catch (e) {}
  },

  async printInterimCert() {
    const cert = this._pendingCert || await this._buildInterimCertPayload();
    if (!cert) return;
    try {
      const r = await fetch(API + '/payments/interim-cert/pdf', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(cert),
      });
      if (!r.ok) throw new Error('無法產生打印檔');
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      let iframe = document.getElementById('payCertPrintFrame');
      if (!iframe) {
        iframe = document.createElement('iframe');
        iframe.id = 'payCertPrintFrame';
        iframe.setAttribute('title', '打印計算書');
        iframe.style.cssText = 'position:fixed;right:0;bottom:0;width:0;height:0;border:0;';
        document.body.appendChild(iframe);
      }
      iframe.onload = () => {
        try {
          iframe.contentWindow.focus();
          iframe.contentWindow.print();
        } catch (e) {
          window.open(url, '_blank');
        }
        setTimeout(() => URL.revokeObjectURL(url), 120000);
      };
      iframe.src = url;
    } catch (e) {
      toast(e.message || '打印失敗', 'error');
    }
  },

  async downloadInterimCert() {
    const cert = this._pendingCert || await this._buildInterimCertPayload();
    await this._downloadCertFile('/payments/interim-cert/pdf', cert, 'pdf');
  },

  async downloadInterimCertXlsx() {
    const cert = this._pendingCert || await this._buildInterimCertPayload();
    await this._downloadCertFile('/payments/interim-cert/xlsx', cert, 'xlsx');
  },

  async downloadInterimCertDocx() {
    const cert = this._pendingCert || await this._buildInterimCertPayload();
    await this._downloadCertFile('/payments/interim-cert/docx', cert, 'docx');
  },

  async _downloadCertFile(path, cert, ext) {
    try {
      const r = await fetch(API + path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(cert),
      });
      if (!r.ok) throw new Error('下載失敗');
      const blob = await r.blob();
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = `InterimCert_${cert.project?.project_code || 'cert'}.${ext}`;
      a.click();
    } catch (e) {
      toast(e.message || '下載失敗', 'error');
    }
  },

  _setCertModalMode(mode, revoked) {
    this._certModalMode = mode;
    const saved = mode === 'saved';
    const canManage = saved && !revoked;
    const submitBtn = document.getElementById('payCertSubmitBtn');
    const editBtn = document.getElementById('payCertEditBtn');
    const restoreBtn = document.getElementById('payCertRestoreBtn');
    const withdrawBtn = document.getElementById('payCertWithdrawBtn');
    const backBtn = document.getElementById('payCertBackBtn');
    if (submitBtn) submitBtn.style.display = saved ? 'none' : '';
    if (editBtn) editBtn.style.display = canManage ? '' : 'none';
    if (restoreBtn) restoreBtn.style.display = saved && revoked ? '' : 'none';
    if (withdrawBtn) withdrawBtn.style.display = canManage ? '' : 'none';
    if (backBtn) backBtn.textContent = saved ? '關閉' : '返回';
  },

  async openSavedCertPreview(id) {
    const r = typeof id === 'object' ? id : await api('GET', `/payments/${id}`);
    if (!r) return;
    this._savedPayment = r;
    document.getElementById('payModalId').value = r.id;
    const cert = await this._certFromFormOrPayment(r);
    this._pendingCert = cert;
    try {
      this._pendingCertModel = await this._fetchCertModel(cert);
      cert.model = this._pendingCertModel;
      this._pendingCert = cert;
      document.getElementById('payCertPreview').innerHTML = this._renderCertPreviewHtml(this._pendingCertModel);
    } catch (e) {
      document.getElementById('payCertPreview').innerHTML = '<div class="empty-state">無法載入計算書</div>';
    }
    this._setCertModalMode('saved', this._isRevoked(r));
    document.getElementById('payCertModal').classList.add('open');
  },

  async withdrawCertById(id, ev) {
    if (ev) ev.stopPropagation();
    const row = (this.data || []).find(r => r.id == id);
    if (!row || (this._isRevoked(row) && !row.can_revert_to_normal)) return;
    if (!confirm('還原至提交前？\n將恢復原本付款列（已付／餘額／類型），並解除 VO／扣款套用。')) return;
    try {
      await api('POST', `/payments/${id}/withdraw`);
      toast('已還原至提交前', 'success');
      await this.load();
      await this._refreshScList();
      await Dashboard.load();
    } catch (e) {
      toast(e.message || '撤回失敗', 'error');
    }
  },

  async openInterimCertPdf(id) {
    await this.openSavedCertPreview(id);
  },

  async editSavedCert() {
    const r = this._savedPayment;
    if (!r) return;
    if (this._isRevoked(r)) {
      await this.restoreAndEditCert(r.id);
      return;
    }
    this.closeCertModal();
    let row = r;
    if (this._pendingCert) {
      const stored = typeof r.interim_cert === 'object' ? r.interim_cert : {};
      row = {
        ...r,
        vo_ids: this._pendingCert.vo_ids ?? r.vo_ids,
        deduction_ids: this._pendingCert.deduction_ids ?? r.deduction_ids,
        paid_amount: this._pendingCert.paid_amount ?? r.paid_amount,
        contract_amount: this._pendingCert.contract_amount ?? r.contract_amount,
        remainder_amount: this._pendingCert.remainder_amount ?? r.remainder_amount,
        interim_cert: { ...stored, ...this._pendingCert },
      };
    }
    await this._fillPaymentForm(row);
  },

  async restoreAndEditCert(id) {
    const pid = id || this._savedPayment?.id || document.getElementById('payModalId')?.value;
    if (!pid) return;
    if (!confirm('重新編輯並提交此計算書？\n將恢復為有效糧款並重新套用 VO／扣款。')) return;
    try {
      await api('POST', `/payments/${pid}/restore`);
      toast('已恢復為有效糧款，可繼續編輯', 'success');
      this.closeCertModal();
      const r = await api('GET', `/payments/${pid}`);
      await this.load();
      if (App.currentProject) {
        await this._refreshScList();
      }
      await this._fillPaymentForm(r);
    } catch (e) {
      toast(e.message || '還原失敗', 'error');
    }
  },

  async withdrawCert() {
    const id = this._savedPayment?.id || document.getElementById('payModalId')?.value;
    if (!id) return;
    if (!confirm('還原至提交前？\n將恢復原本付款列（已付／餘額／類型），並解除 VO／扣款套用。')) return;
    try {
      await api('POST', `/payments/${id}/withdraw`);
      toast('已還原至提交前', 'success');
      this.closeCertModal();
      this.closeModal();
      this._savedPayment = null;
      await this.load();
      await this._refreshScList();
      await Dashboard.load();
    } catch (e) {
      toast(e.message || '撤回失敗', 'error');
    }
  },

  viewPdf(pdfPath, title) {
    DocViewer.open(pdfPath, title || '付款單據 PDF');
  },

  viewModalPdf() {
    this.viewPdf(document.getElementById('fPdfPath').value);
  },

  _setPdfUi(pdfPath) {
    const group = document.getElementById('fPdfGroup');
    const pathEl = document.getElementById('fPdfPath');
    if (!group || !pathEl) return;
    pathEl.value = pdfPath || '';
    group.style.display = pdfPath ? 'block' : 'none';
  },

  _resetFormFields() {
    ['fInvDate','fInvNo','fQuotNo','fCompanyEn','fCompanyZh','fDesc','fOaRef','fOaNo','fRemark','fBackchargeAmt'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.value = '';
    });
    document.getElementById('fBcToSub').value = '';
    document.getElementById('fMcIpNo').value = '';
    document.getElementById('fSubIpNo').value = '';
    ['fContractAmt','fPaidAmt','fRemAmt','fDeductionTotal','fVoTotal','fAddTotal','fAddSubtotal','fNetCertTotal'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.value = '';
    });
    const dedSel = document.getElementById('fScVoPickList');
    if (dedSel) dedSel.innerHTML = '';
    this._pendingCert = null;
    this._pendingCertModel = null;
    this._scVoOptions = [];
    this._resetLineRemarks();
  },

  openAdd(type = 'normal') {
    const isCert = type === 'interim_cert';
    document.getElementById('payModalTitle').textContent = isCert
      ? '新增承判商中期糧款計算書'
      : '新增分判付款登記';
    document.getElementById('payModalId').value = '';
    this._resetFormFields();
    this._setPayType(isCert ? 'interim_cert' : 'normal');
    this._setPdfUi(null);
    const seqEl = document.getElementById('fSeqNo');
    if (seqEl) {
      seqEl.value = '';
      seqEl.placeholder = '自動編號';
      seqEl.readOnly = true;
    }
    document.getElementById('fScNo').value = '';
    this.populateScSelect();
    document.getElementById('payModal').classList.add('open');
  },

  async openEdit(id) {
    const r = await api('GET', `/payments/${id}`);
    if (!r) return;
    if (r.payment_type === 'interim_cert' && this._isRevoked(r)) {
      await this.restoreAndEditCert(r.id);
      return;
    }
    await this._fillPaymentForm(r);
  },

  async _fillPaymentForm(r) {
    document.getElementById('payModalTitle').textContent = r.payment_type === 'interim_cert'
      ? '編輯承判商中期糧款計算書'
      : '編輯分判付款登記';
    document.getElementById('payModalId').value = r.id;
    this._setPayType(r.payment_type || 'normal');
    this.populateScSelect();
    const seqEl = document.getElementById('fSeqNo');
    if (seqEl) {
      seqEl.value = r.seq_no || '';
      seqEl.readOnly = false;
      seqEl.placeholder = '自動';
    }
    document.getElementById('fInvDate').value = r.invoice_date || '';
    document.getElementById('fInvNo').value = r.invoice_no || '';
    document.getElementById('fQuotNo').value = r.quotation_no || '';
    document.getElementById('fScNo').value = r.sc_no || '';
    document.getElementById('fCompanyEn').value = r.company_name_en || '';
    document.getElementById('fCompanyZh').value = r.company_name_zh || '';
    document.getElementById('fDesc').value = r.description || '';
    document.getElementById('fContractAmt').value = fmtInputNum(r.contract_amount);
    document.getElementById('fPaidAmt').value = fmtInputNum(r.paid_amount);
    document.getElementById('fRemAmt').value = fmtInputNum(r.remainder_amount);
    document.getElementById('fOaRef').value = r.oa_ref || '';
    document.getElementById('fOaNo').value = r.oa_no || '';
    document.getElementById('fBackchargeAmt').value = fmtInputNum(r.backcharge_amount);
    document.getElementById('fRemark').value = r.remark || '';
    if (r.bc_to_sub) this._ensureBcOption(r.bc_to_sub);
    document.getElementById('fBcToSub').value = r.bc_to_sub || '';
    if (r.payment_type === 'interim_cert') {
      await this.ensureCertTemplates();
      const cert = typeof r.interim_cert === 'object' ? r.interim_cert : null;
      const std = cert?.standard_lines || {};
      const stdCodes = this._standardCodesFromCert(cert, std);
      const preIds = [...(r.vo_ids || []), ...(r.deduction_ids || [])];
      await this.loadScVoPickList(preIds, { standardLines: std, standardCodes: stdCodes });
      const remarks = cert?.line_remarks;
      if (remarks) {
        this._applyLineRemarksToForm(remarks);
      } else {
        this._resetLineRemarks();
      }
      this._applyVoRemarksToForm(cert?.vo_remarks);
      if (!remarks) await this.syncInterimLineRemarks();
      if (cert?.previous_a_cum != null) {
        this._prevACum = parseFloat(cert.previous_a_cum) || 0;
        this._prevACumScNo = r.sc_no || null;
      }
    }
    this._setPdfUi(r.pdf_path || null);
    document.getElementById('payModal').classList.add('open');
  },

  closeModal() {
    document.getElementById('payModal').classList.remove('open');
  },

  async saveModal() {
    if (this._getPayType() === 'interim_cert') {
      this.goInterimPreview();
      return;
    }
    const id = document.getElementById('payModalId').value;
    const data = {
      ...this._readFormBase(),
      payment_type: 'normal',
      ocr_status: null,
      pdf_path: null,
    };
    if (!data.project_id) { toast('請先選擇項目', 'warning'); return; }
    try {
      if (id) {
        await api('PUT', `/payments/${id}`, data);
        toast('記錄已更新', 'success');
      } else {
        await api('POST', '/payments', data);
        toast('記錄已新增', 'success');
      }
      this.closeModal();
      await this.load();
      await Dashboard.load();
    } catch (e) {}
  },

  async delete(id) {
    const row = (this.data || []).find(r => r.id == id);
    if (row?.payment_type === 'interim_cert' && !this._isRevoked(row)) {
      toast('請先按「還原」退回提交前', 'warning');
      return;
    }
    if (!confirm('確認刪除此付款登記？')) return;
    try {
      await api('DELETE', `/payments/${id}`);
      toast('已刪除', 'success');
      await this.load();
      await Dashboard.load();
    } catch (e) {
      toast(e.message || '刪除失敗', 'error');
    }
  },

  exportCsv() {
    if (!this.filtered.length) { toast('沒有資料可匯出', 'warning'); return; }
    const headers = ['序號','類型','發票日期','發票號碼','判項編號','公司名稱(英)','公司名稱(中)','工程描述','判項金額','已付金額','餘額','Backcharge判項','Backcharge金額','扣款合計','OA參考','OA編號','備注'];
    const rows = this.filtered.map(r => [
      r.seq_no,
      r.payment_type === 'interim_cert' ? '中期糧款計算書' : '普通付款',
      r.invoice_date, r.invoice_no, r.sc_no, r.company_name_en, r.company_name_zh,
      r.description, fmtNumPlain(r.contract_amount), fmtNumPlain(r.paid_amount), fmtNumPlain(r.remainder_amount),
      r.bc_to_sub, fmtNumPlain(r.backcharge_amount), fmtNumPlain(r.deduction_total),
      r.oa_ref, r.oa_no, r.remark,
    ]);
    downloadCsv([headers, ...rows], `payments_${App.currentProject?.project_code}_${new Date().toISOString().slice(0,10)}.csv`);
  },
};

ColPicker.attach(Payments, {
  columnsKey: 'PAY_COLUMNS',
  storageKey: 'qs_pay_visible_cols',
  tableSelector: '.pay-records-table',
  wrapId: 'payColPickerWrap',
  panelId: 'payColPickerPanel',
  hostName: 'Payments',
});

function downloadCsv(rows, filename) {
  const content = rows.map(r => r.map(c => `"${(c ?? '').toString().replace(/"/g, '""')}"`).join(',')).join('\n');
  const blob = new Blob(['\uFEFF' + content], { type: 'text/csv;charset=utf-8' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
}
