/* eng_intake.js — 項目登記 · 會簽出表（NN1 → Master → Word/PDF） */
const EngIntake = {
  items: [],
  stats: {},
  sourceFile: '',
  selectedIdx: 0,
  _editorSnapshot: null,
  _dirty: false,
  _STORAGE_KEY: 'qs_eng_intake_drafts',

  _EDIT_FIELDS: [
    'quotation_raw', 'quotation_no', 'project_name', 'client_name', 'amount',
    'contract_start_date', 'contract_end_date', 'expected_period', 'subcon_name', 'subcon_quotation',
    'start_date', 'completion_date',
    'person_in_charge', 'approval_category', 'approval_other',
    'submit_date', 'tender_date', 'bid_deadline', 'bid_deadline_ampm', 'bid_deadline_meridiem',
    'attachments', 'remark',
  ],

  async load() {
    this._bindOnce();
    if (!this.items.length) {
      this.renderEmpty();
    } else {
      this.render();
    }
  },

  _bindOnce() {
    if (this._bound) return;
    this._bound = true;
    document.getElementById('eiFileInput')?.addEventListener('change', (e) => this.onFile(e));
    const root = document.getElementById('eiEditor');
    if (root) {
      root.addEventListener('input', (e) => {
        if (e.target.id === 'eiQuotationNo') {
          const tender = document.getElementById('eiTenderNo');
          if (tender) tender.value = e.target.value;
        }
        this._markDirty();
      });
      root.addEventListener('change', (e) => {
        if (e.target.name === 'eiApprovalCat') {
          this.onApprovalChange();
        }
        if (['eiSubmitDate', 'eiBidDeadline', 'eiTenderDate'].includes(e.target.id)) {
          this._updateDateHints();
        }
        this._markDirty();
      });
    }
  },

  _itemKey(it) {
    return (it?.quotation_raw || it?.quotation_no || '').trim();
  },

  _snapshotItem(it) {
    if (!it) return null;
    const snap = {};
    for (const k of this._EDIT_FIELDS) snap[k] = it[k] ?? null;
    return snap;
  },

  _applySnapshot(it, snap) {
    if (!it || !snap) return;
    for (const k of this._EDIT_FIELDS) it[k] = snap[k] ?? null;
  },

  _persistDrafts() {
    if (!this.sourceFile || !this.items.length) return;
    const drafts = {};
    for (const it of this.items) {
      const id = this._itemKey(it);
      if (id) drafts[id] = this._snapshotItem(it);
    }
    try {
      localStorage.setItem(this._STORAGE_KEY, JSON.stringify({
        source: this.sourceFile,
        saved_at: new Date().toISOString(),
        drafts,
      }));
    } catch (_) { /* quota / private mode */ }
  },

  _sanitizeContractDates(it) {
    if (!it) return;
    const cs = it.contract_start_date;
    const ce = it.contract_end_date;
    if (!cs && !ce) return;
    if (cs === it.start_date && (!ce || ce === it.completion_date)) {
      it.contract_start_date = null;
      it.contract_end_date = null;
    }
  },

  _sanitizeAllItems() {
    for (const it of this.items) this._sanitizeContractDates(it);
  },

  _applyDrafts() {
    if (!this.sourceFile || !this.items.length) return;
    try {
      const raw = localStorage.getItem(this._STORAGE_KEY);
      if (!raw) return;
      const data = JSON.parse(raw);
      if (data.source !== this.sourceFile || !data.drafts) return;
      for (const it of this.items) {
        const id = this._itemKey(it);
        if (id && data.drafts[id]) {
          this._applySnapshot(it, data.drafts[id]);
          this._sanitizeContractDates(it);
        }
      }
    } catch (_) { /* ignore corrupt storage */ }
  },

  _markDirty() {
    this._dirty = true;
    this._updateEditorStatus();
  },

  _updateEditorStatus() {
    const el = document.getElementById('eiEditorStatus');
    if (!el) return;
    const cancelBtn = document.getElementById('eiCancelBtn');
    if (this._dirty) {
      el.textContent = '● 有未儲存變更';
      el.className = 'ei-editor-status ei-editor-status-dirty';
      if (cancelBtn) cancelBtn.disabled = false;
    } else {
      el.textContent = '已儲存';
      el.className = 'ei-editor-status';
      if (cancelBtn) cancelBtn.disabled = true;
    }
  },

  _normalizeNn1Quotation(raw) {
    const s = String(raw || '').trim().replace(/\s+/g, '');
    if (!s) return null;
    const t = s.replace(/^([QTC])\./i, '$1');
    const m = t.match(/^([QTC])(\d+)\/(\d{2,4})$/i);
    if (!m) return null;
    const letter = m[1].toUpperCase();
    const num = parseInt(m[2], 10);
    let year = m[3];
    if (year.length === 4) year = year.slice(-2);
    const numStr = num < 1000 ? String(num).padStart(3, '0') : String(num);
    return `${letter}${numStr}/${year}`;
  },

  _parseIsoDateLocal(s) {
    if (!s) return null;
    const d = new Date(`${s}T12:00:00`);
    return Number.isNaN(d.getTime()) ? null : d;
  },

  _businessDaysBetween(earlier, later) {
    if (!earlier || !later || earlier >= later) return 0;
    let n = 0;
    const d = new Date(earlier);
    d.setDate(d.getDate() + 1);
    while (d <= later) {
      const dow = d.getDay();
      if (dow !== 0 && dow !== 6) n += 1;
      d.setDate(d.getDate() + 1);
    }
    return n;
  },

  _subtractBusinessDays(date, n) {
    const d = new Date(date);
    let left = n;
    while (left > 0) {
      d.setDate(d.getDate() - 1);
      if (d.getDay() !== 0 && d.getDay() !== 6) left -= 1;
    }
    return d;
  },

  _fmtIsoDate(d) {
    if (!d) return '';
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${day}`;
  },

  _validateEngDates() {
    const submit = this._parseIsoDateLocal(this._val('eiSubmitDate'));
    const bid = this._parseIsoDateLocal(this._val('eiBidDeadline'));
    const tender = this._parseIsoDateLocal(this._val('eiTenderDate'));
    const errors = [];
    const warnings = [];
    const TENDER_BIZ_DAYS = 10;
    const TENDER_TOLERANCE = 2;

    if (submit && bid && submit > bid) {
      errors.push('遞交日期不可晚於截標日期');
    }
    if (tender && submit && tender >= submit) {
      errors.push('招標日期須早於遞交日期');
    }
    if (tender && bid && tender >= bid) {
      errors.push('招標日期須早於截標日期');
    }
    const ref = submit || bid;
    if (tender && ref) {
      const biz = this._businessDaysBetween(tender, ref);
      if (biz < TENDER_BIZ_DAYS - TENDER_TOLERANCE || biz > TENDER_BIZ_DAYS + TENDER_TOLERANCE) {
        const expect = this._fmtIsoDate(this._subtractBusinessDays(ref, TENDER_BIZ_DAYS));
        warnings.push(
          `招標日期距${submit ? '遞交' : '截標'}日期約 ${biz} 個工作天（一般約 ${TENDER_BIZ_DAYS} 天，參考：${expect}）`,
        );
      }
    }
    return { errors, warnings, submit, bid, tender };
  },

  _renderDateHints(check) {
    const el = document.getElementById('eiDateHints');
    if (!el) return;
    const c = check || this._validateEngDates();
    if (!c.errors.length && !c.warnings.length) {
      el.innerHTML = '';
      el.className = 'ei-span-2 ei-date-hints';
      return;
    }
    const lines = [
      ...c.errors.map((t) => `<div class="ei-date-hint ei-date-hint-error">${escHtml(t)}</div>`),
      ...c.warnings.map((t) => `<div class="ei-date-hint ei-date-hint-warn">${escHtml(t)}</div>`),
    ];
    el.innerHTML = lines.join('');
    el.className = 'ei-span-2 ei-date-hints ei-date-hints-active';
  },

  _updateDateHints() {
    this._renderDateHints(this._validateEngDates());
  },

  _applyLocalNn1Rematch(it) {
    const core = this._normalizeNn1Quotation(it.quotation_raw);
    if (!core) return;
    it.core_no = core;
    const pc = document.getElementById('eiPersonCode')?.value || it.person_code || 'dc';
    it.quotation_no = `MS/${core}/${pc}`;
  },

  async saveEdits() {
    const check = this._validateEngDates();
    this._renderDateHints(check);
    if (check.errors.length) {
      toast(check.errors[0], 'error');
      return;
    }
    if (check.warnings.length) {
      const ok = window.confirm(`${check.warnings.join('\n')}\n\n仍要儲存？`);
      if (!ok) return;
    }
    const it = this.items[this.selectedIdx];
    if (!it) return;
    const rawChanged = (this._editorSnapshot?.quotation_raw ?? '') !== this._val('eiQuotationRaw');
    this.saveEditorToItem();
    if (rawChanged) {
      await this._rematchCurrentItem();
    }
    this._editorSnapshot = this._snapshotItem(it);
    this._dirty = false;
    this._persistDrafts();
    this._updateEditorStatus();
    this.renderTable();
    toast('已儲存此項目編輯', 'success');
  },

  async _rematchCurrentItem() {
    const it = this.items[this.selectedIdx];
    if (!it?.quotation_raw) return;
    const pc = document.getElementById('eiPersonCode')?.value || it.person_code || 'dc';
    try {
      const r = await api('POST', '/eng/intake/rematch', { item: it, person_code: pc }, { silent: true });
      if (r?.item) {
        Object.assign(it, r.item);
        this.renderEditor();
        return;
      }
    } catch (_) { /* fallback below */ }
    this._applyLocalNn1Rematch(it);
    this.renderEditor();
  },

  cancelEdits() {
    const it = this.items[this.selectedIdx];
    if (!it || !this._editorSnapshot) return;
    this._applySnapshot(it, this._editorSnapshot);
    this._dirty = false;
    this.renderEditor();
    toast('已還原未儲存變更', 'info');
  },

  _confirmLeaveRow() {
    if (!this._dirty) return true;
    return window.confirm('有未儲存的變更。離開此項將捨棄，確定繼續？');
  },

  async onFile(ev) {
    const file = ev.target.files?.[0];
    if (!file) return;
    const pc = document.getElementById('eiPersonCode')?.value || '';
    const fd = new FormData();
    fd.append('file', file);
    if (pc) fd.append('person_code', pc);
    try {
      const r = await fetch(`${API}/eng/intake/preview`, { method: 'POST', body: fd });
      const j = await r.json();
      if (!j.success) throw new Error(j.error || '預覽失敗');
      this.items = j.data.items || [];
      this.stats = j.data.stats || {};
      this.sourceFile = j.data.source_file || file.name;
      this.selectedIdx = 0;
      this._applyDrafts();
      this._sanitizeAllItems();
      this.render();
      toast(`已解析 ${this.items.length} 個項目`, 'success');
    } catch (e) {
      toast(e.message || '匯入失敗', 'error');
    } finally {
      ev.target.value = '';
    }
  },

  pickFile() {
    document.getElementById('eiFileInput')?.click();
  },

  selectRow(idx) {
    if (idx === this.selectedIdx) return;
    if (!this._confirmLeaveRow()) return;
    if (this._dirty && this._editorSnapshot) {
      this._applySnapshot(this.items[this.selectedIdx], this._editorSnapshot);
    } else {
      this.saveEditorToItem();
    }
    this.selectedIdx = idx;
    this.renderTable();
    this.renderEditor();
  },

  _statusBadge(st) {
    const map = {
      ok: ['Master 齊', 'badge-success'],
      partial: ['Master 缺欄', 'badge-warning'],
      missing: ['未有 Master', 'badge-danger'],
    };
    const [label, cls] = map[st] || ['—', ''];
    return `<span class="badge ${cls}">${label}</span>`;
  },

  _money(v) {
    if (v == null || v === '') return '—';
    return `HK$${Number(v).toLocaleString('en-HK', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
  },

  _periodMonthsDisplay(val) {
    if (val == null || val === '') return '';
    if (typeof val === 'number' && !Number.isNaN(val)) return String(val);
    const s = String(val).trim();
    const m = s.match(/^([\d.]+)/);
    if (m) return m[1];
    const m2 = s.match(/([\d.]+)\s*months?/i);
    return m2 ? m2[1] : '';
  },

  _parsePeriodMonths(raw) {
    const s = String(raw ?? '').trim();
    if (!s) return null;
    const n = Number(s);
    return Number.isFinite(n) && n > 0 ? n : null;
  },

  _parseBidTimeState(ampmRaw, meridiemRaw) {
    let meridiem = meridiemRaw === 'am' || meridiemRaw === 'pm' ? meridiemRaw : null;
    let hour = '';
    let minute = '';
    const s = String(ampmRaw || '').trim();
    if (/上午/.test(s)) meridiem = meridiem || 'am';
    if (/下午/.test(s)) meridiem = meridiem || 'pm';
    const tm = s.match(/(\d{1,2})\s*:\s*(\d{2})/);
    if (tm) {
      let h = parseInt(tm[1], 10);
      const m = parseInt(tm[2], 10);
      if (h >= 13) h -= 12;
      if (h === 0) h = 12;
      hour = h;
      minute = m;
    }
    return { meridiem, hour, minute };
  },

  _readBidTimeFromDom() {
    const checked = document.querySelector('input[name="eiBidMeridiem"]:checked');
    const meridiem = checked?.value === 'am' ? 'am' : checked?.value === 'pm' ? 'pm' : null;
    const hourRaw = this._val('eiBidHour');
    const minRaw = this._val('eiBidMinute');
    let hour = hourRaw === '' ? null : parseInt(hourRaw, 10);
    let minute = minRaw === '' ? null : parseInt(minRaw, 10);
    if (hour != null && (!Number.isFinite(hour) || hour < 1 || hour > 12)) hour = null;
    if (minute != null && (!Number.isFinite(minute) || minute < 0 || minute > 59)) minute = null;
    return { meridiem, hour, minute };
  },

  _formatBidAmpm(hour, minute) {
    if (hour == null && minute == null) return '';
    const h = hour != null ? hour : 12;
    const m = minute != null ? minute : 0;
    return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
  },

  _val(id) {
    if (id === 'eiApprovalCat') {
      return document.querySelector('input[name="eiApprovalCat"]:checked')?.value ?? '';
    }
    return document.getElementById(id)?.value ?? '';
  },

  onApprovalChange() {
    const wrap = document.getElementById('eiApprovalOtherWrap');
    const input = document.getElementById('eiApprovalOther');
    const cat = document.querySelector('input[name="eiApprovalCat"]:checked')?.value || '合約';
    const show = cat === '其他';
    if (wrap) wrap.style.display = show ? '' : 'none';
    if (show && input) {
      input.focus();
    }
    this._markDirty();
  },

  saveEditorToItem() {
    const it = this.items[this.selectedIdx];
    if (!it) return;
    const amt = this._val('eiAmount');
    const periodRaw = this._val('eiExpectedPeriod');
    const bidT = this._readBidTimeFromDom();
    Object.assign(it, {
      quotation_raw: this._val('eiQuotationRaw') || null,
      quotation_no: this._val('eiQuotationNo'),
      project_name: this._val('eiProjectName'),
      client_name: this._val('eiClientName'),
      amount: parseAmtOrNull(amt),
      contract_start_date: this._val('eiContractStartDate') || null,
      contract_end_date: this._val('eiContractEndDate') || null,
      expected_period: this._parsePeriodMonths(periodRaw),
      start_date: this._val('eiStartDate') || null,
      completion_date: this._val('eiCompletionDate') || null,
      subcon_name: this._val('eiSubconName') || null,
      subcon_quotation: this._val('eiSubcon') || null,
      person_in_charge: this._val('eiPersonInCharge') || null,
      approval_category: this._val('eiApprovalCat') || '合約',
      approval_other: this._val('eiApprovalOther') || '',
      submit_date: this._val('eiSubmitDate') || null,
      tender_date: this._val('eiTenderDate') || null,
      bid_deadline: this._val('eiBidDeadline') || null,
      bid_deadline_ampm: bidT.meridiem ? this._formatBidAmpm(bidT.hour, bidT.minute) : '',
      bid_deadline_meridiem: bidT.meridiem || null,
      attachments: this._val('eiAttachments') || '',
      remark: this._val('eiRemark') || '',
    });
  },

  _collectPayload() {
    if (this._dirty) {
      toast('請先按「儲存」再出表', 'warning');
      return null;
    }
    const check = this._validateEngDates();
    if (check.errors.length) {
      toast(check.errors[0], 'error');
      this._renderDateHints(check);
      return null;
    }
    if (check.warnings.length) {
      toast(check.warnings[0], 'warning');
    }
    this.saveEditorToItem();
    const it = this.items[this.selectedIdx];
    if (!it) return null;
    const approvalCat = this._val('eiApprovalCat') || it.approval_category || '合約';
    it.approval_category = approvalCat;
    const contractStart = this._val('eiContractStartDate') || null;
    const contractEnd = this._val('eiContractEndDate') || null;
    return {
      item: it,
      content: {
        quotation_no: it.quotation_no,
        project_name: it.project_name,
        client_name: it.client_name,
        amount: it.amount,
        contract_start_date: contractStart,
        contract_end_date: contractEnd,
        expected_period: it.expected_period,
        subcon_name: it.subcon_name,
        subcon_quotation: it.subcon_quotation,
        person_in_charge: it.person_in_charge,
        person_code: it.person_code,
        remark: it.remark,
        approval_category: approvalCat,
        approval_other: it.approval_other || '',
      },
      pm: {
        submit_date: it.submit_date || '',
        tender_date: it.tender_date || '',
        bid_deadline: it.bid_deadline || '',
        bid_deadline_ampm: it.bid_deadline_ampm || '',
        bid_deadline_meridiem: it.bid_deadline_meridiem || '',
        approval_category: approvalCat,
        approval_other: it.approval_other || '',
        attachments: it.attachments || '',
        remark: it.remark || '',
      },
    };
  },

  renderEmpty() {
    const el = document.getElementById('eiTableBody');
    if (el) el.innerHTML = '<tr><td colspan="8" class="text-muted" style="padding:24px">請上傳 NN1 Excel 開始</td></tr>';
    document.getElementById('eiStats').innerHTML = '';
    document.getElementById('eiEditor').innerHTML = '<p class="text-muted">選擇左側項目以編輯內容並出表</p>';
  },

  render() {
    this.renderStats();
    this.renderTable();
    this.renderEditor();
    const src = document.getElementById('eiSourceFile');
    if (src) src.textContent = this.sourceFile ? `來源：${this.sourceFile}` : '';
  },

  renderStats() {
    const el = document.getElementById('eiStats');
    if (!el) return;
    const s = this.stats;
    el.innerHTML = `
      <div class="stat-card"><div class="stat-label">項目</div><div class="stat-value">${s.total ?? this.items.length}</div></div>
      <div class="stat-card success"><div class="stat-label">Master 齊</div><div class="stat-value">${s.master_ok ?? 0}</div></div>
      <div class="stat-card warning"><div class="stat-label">缺欄</div><div class="stat-value">${s.master_partial ?? 0}</div></div>
      <div class="stat-card"><div class="stat-label">未有 Master</div><div class="stat-value">${s.master_missing ?? 0}</div></div>`;
  },

  renderTable() {
    const tbody = document.getElementById('eiTableBody');
    if (!tbody) return;
    if (!this.items.length) {
      this.renderEmpty();
      return;
    }
    tbody.innerHTML = this.items.map((it, idx) => {
      const sel = idx === this.selectedIdx ? ' ei-row-selected' : '';
      const gaps = (it.master_gaps || []).slice(0, 2).join('、');
      return `<tr class="ei-row${sel}" onclick="EngIntake.selectRow(${idx})">
        <td>${escHtml(it.quotation_raw || '—')}</td>
        <td><code>${escHtml(it.quotation_no || '—')}</code></td>
        <td>${escHtml(it.project_name || '—')}</td>
        <td class="text-right">${this._money(it.amount)}</td>
        <td>${escHtml(it.start_date || '—')}</td>
        <td>${escHtml(it.completion_date || '—')}</td>
        <td>${this._statusBadge(it.master_status)}</td>
        <td class="text-muted" style="font-size:12px">${escHtml(gaps || '—')}</td>
      </tr>`;
    }).join('');
  },

  renderEditor() {
    const el = document.getElementById('eiEditor');
    const it = this.items[this.selectedIdx];
    if (!el || !it) return;
    this._sanitizeContractDates(it);
    const gaps = (it.master_gaps || []).join('、') || '無';
    const amt = it.amount != null && it.amount !== '' ? it.amount : '';
    const period = this._periodMonthsDisplay(it.expected_period);
    const bidT = this._parseBidTimeState(it.bid_deadline_ampm, it.bid_deadline_meridiem);
    const bidHourVal = bidT.hour === '' || bidT.hour == null ? '' : bidT.hour;
    const bidMinVal = bidT.minute === '' || bidT.minute == null ? '' : String(bidT.minute).padStart(2, '0');
    const cat = it.approval_category || '合約';
    const showOther = cat === '其他';
    el.innerHTML = `
      <div class="ei-editor-head">
        <div class="form-hint">Master 配對：${escHtml(it.master_matched_no || '—')} · 缺：${escHtml(gaps)}</div>
        <div id="eiEditorStatus" class="ei-editor-status">已儲存</div>
      </div>
      <div class="ei-section-title">會簽表內容（可編輯 · 次序同 Template）</div>
      <div class="form-grid ei-form-grid">
        <div class="ei-span-2 ei-approval-block">
          <div class="form-label" style="margin-bottom:6px">審批類別（三選一）</div>
          <div class="ei-approval-radios">
            <label class="ei-approval-opt"><input type="radio" name="eiApprovalCat" value="合約" ${cat === '合約' ? 'checked' : ''}> 合約</label>
            <label class="ei-approval-opt"><input type="radio" name="eiApprovalCat" value="投標意向書" ${cat === '投標意向書' ? 'checked' : ''}> 投標意向書</label>
            <label class="ei-approval-opt"><input type="radio" name="eiApprovalCat" value="其他" ${cat === '其他' ? 'checked' : ''}> 其他</label>
          </div>
          <div id="eiApprovalOtherWrap" class="ei-approval-other-wrap" style="${showOther ? '' : 'display:none'}">
            <label for="eiApprovalOther">其他說明 <span class="form-hint">（會印入會簽表「其他」底線欄）</span></label>
            <input type="text" class="form-input" id="eiApprovalOther" placeholder="例：補充協議、變更令等" value="${escHtml(it.approval_other || '')}">
          </div>
        </div>
        <label>NN1 編號
          <input type="text" class="form-input" id="eiQuotationRaw" placeholder="例：Q.0080/25" value="${escHtml(it.quotation_raw || '')}">
          ${it.core_no ? `<span class="form-hint">Master 比對鍵：${escHtml(it.core_no)}</span>` : '<span class="form-hint">儲存後依此編號重新比對 Master</span>'}
        </label>
        <label>項目編號
          <input type="text" class="form-input" id="eiQuotationNo" value="${escHtml(it.quotation_no || '')}">
        </label>
        <label>遞交日期
          <input type="date" class="form-input" id="eiSubmitDate" value="${escHtml(it.submit_date || '')}">
        </label>
        <label class="ei-span-2">項目名稱
          <input type="text" class="form-input" id="eiProjectName" value="${escHtml(it.project_name || '')}">
        </label>
        <label>截標日期
          <input type="date" class="form-input" id="eiBidDeadline" value="${escHtml(it.bid_deadline || '')}">
        </label>
        <label>招標日期
          <input type="date" class="form-input" id="eiTenderDate" value="${escHtml(it.tender_date || '')}">
          <span class="form-hint">一般較遞交／截標早約 10 個工作天（不含週六日）</span>
        </label>
        <div class="ei-span-2 ei-date-hints" id="eiDateHints"></div>
        <div class="ei-span-2 ei-field-block">
          <div class="form-label">截標時間</div>
          <div class="ei-bid-time">
            <div class="ei-bid-meridiem">
              <div class="form-hint" style="margin-bottom:4px">上／下午（三選一）</div>
              <div class="ei-approval-radios ei-bid-meridiem-radios">
                <label class="ei-approval-opt"><input type="radio" name="eiBidMeridiem" value="am" ${bidT.meridiem === 'am' ? 'checked' : ''}> 上午</label>
                <label class="ei-approval-opt"><input type="radio" name="eiBidMeridiem" value="pm" ${bidT.meridiem === 'pm' ? 'checked' : ''}> 下午</label>
                <label class="ei-approval-opt"><input type="radio" name="eiBidMeridiem" value="" ${!bidT.meridiem ? 'checked' : ''}> 不填</label>
              </div>
            </div>
            <div class="ei-bid-clock">
              <input type="number" class="form-input ei-bid-hm" id="eiBidHour" min="1" max="12" step="1" placeholder="時" value="${bidHourVal}" aria-label="小時（12小時制）">
              <span class="ei-bid-colon">:</span>
              <input type="number" class="form-input ei-bid-hm" id="eiBidMinute" min="0" max="59" step="1" placeholder="分" value="${bidMinVal}" aria-label="分鐘">
            </div>
          </div>
        </div>
        <label>供方名稱
          <input type="text" class="form-input" id="eiClientName" value="${escHtml(it.client_name || '')}">
        </label>
        <label>標書編號
          <input type="text" class="form-input" id="eiTenderNo" readonly tabindex="-1" value="${escHtml(it.quotation_no || '')}" title="同項目編號，出表自動帶入">
        </label>
        <label class="ei-span-2">合約總價 (HKD)
          <input type="number" class="form-input" id="eiAmount" step="0.01" value="${escHtml(amt !== '' && amt != null ? fmtInputNum(amt) : '')}">
        </label>
        <label>合約年期（起）
          <input type="date" class="form-input" id="eiContractStartDate" value="${escHtml(it.contract_start_date || '')}">
        </label>
        <label>合約年期（迄）
          <input type="date" class="form-input" id="eiContractEndDate" value="${escHtml(it.contract_end_date || '')}">
        </label>
        <label>合約期（月）
          <input type="number" class="form-input" id="eiExpectedPeriod" step="0.1" min="0" placeholder="例：1 或 0.5" value="${escHtml(period)}">
          <span class="form-hint">會簽表「合約年期」欄；非 Master 開工／完工日期</span>
        </label>
        <label class="ei-span-2">附件及其他事項
          <textarea class="form-input" id="eiAttachments" rows="2">${escHtml(it.attachments || '')}</textarea>
        </label>
        <label>分判商名稱
          <input type="text" class="form-input" id="eiSubconName" placeholder="分判商公司名稱" value="${escHtml(it.subcon_name || '')}">
        </label>
        <label>分判報價
          <input type="text" class="form-input" id="eiSubcon" value="${escHtml(it.subcon_quotation || '')}">
        </label>
        <label>備註
          <input type="text" class="form-input" id="eiRemark" value="${escHtml(it.remark || '')}">
        </label>
        <label class="ei-span-2">項目負責人 <span class="form-hint">（Master 用，非會簽表欄）</span>
          <input type="text" class="form-input" id="eiPersonInCharge" value="${escHtml(it.person_in_charge || '')}">
        </label>
        <label>開工日期 <span class="form-hint">（Master 備用）</span>
          <input type="date" class="form-input" id="eiStartDate" value="${escHtml(it.start_date || '')}">
        </label>
        <label>完工日期 <span class="form-hint">（Master 備用）</span>
          <input type="date" class="form-input" id="eiCompletionDate" value="${escHtml(it.completion_date || '')}">
        </label>
      </div>
      <div class="ei-edit-actions">
        <button type="button" class="btn btn-primary btn-sm" onclick="EngIntake.saveEdits()">💾 儲存</button>
        <button type="button" class="btn btn-secondary btn-sm" onclick="EngIntake.cancelEdits()" disabled id="eiCancelBtn">↩ 取消</button>
      </div>
      <div class="ei-actions" style="margin-top:12px;display:flex;gap:8px;flex-wrap:wrap">
        <button type="button" class="btn btn-primary btn-sm" onclick="EngIntake.preview()">👁 預覽 PDF</button>
        <button type="button" class="btn btn-secondary btn-sm" onclick="EngIntake.download('docx')">📄 下載 Word</button>
        <button type="button" class="btn btn-secondary btn-sm" onclick="EngIntake.download('pdf')">📑 下載 PDF</button>
      </div>
      <p class="form-hint" style="margin-top:10px">編輯後請先「儲存」，再預覽或下載；換項目前未儲存會提示。Template：<code>投標合約會簽表Template.docx</code></p>`;
    this._editorSnapshot = this._snapshotItem(it);
    this._dirty = false;
    this._updateEditorStatus();
    this._updateDateHints();
    AmountInput.init(el);
  },

  async preview() {
    const payload = this._collectPayload();
    if (!payload) {
      toast('請先選擇項目', 'warning');
      return;
    }
    try {
      toast('正在產生預覽…', 'info');
      const r = await fetch(`${API}/eng/signoff/preview`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!r.ok) {
        const j = await r.json().catch(() => ({}));
        throw new Error(j.error || `預覽失敗 (${r.status})`);
      }
      const blob = await r.blob();
      this._lastPreviewBlob = blob;
      const q = payload.item?.quotation_no || '會簽表';
      await DocViewer.openBlob(blob, `會簽表預覽 — ${q}`, {
        kind: 'pdf',
        downloadName: `會簽表_${q.replace(/\//g, '_')}.pdf`,
      });
      toast('預覽已開啟，可於視窗內下載', 'success');
    } catch (e) {
      toast(e.message || '預覽失敗', 'error');
    }
  },

  async download(fmt) {
    const payload = this._collectPayload();
    if (!payload) {
      toast('請先選擇項目', 'warning');
      return;
    }
    try {
      const r = await fetch(`${API}/eng/signoff/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...payload, format: fmt }),
      });
      if (!r.ok) {
        const j = await r.json().catch(() => ({}));
        throw new Error(j.error || `出表失敗 (${r.status})`);
      }
      const blob = await r.blob();
      const disp = r.headers.get('Content-Disposition') || '';
      const m = disp.match(/filename=\"?([^\";]+)/);
      const fname = m ? m[1] : `會簽表.${fmt === 'pdf' ? 'pdf' : 'docx'}`;
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = fname;
      a.click();
      URL.revokeObjectURL(url);
      this.renderTable();
      toast(fmt === 'pdf' ? 'PDF 已下載' : 'Word 已下載', 'success');
    } catch (e) {
      toast(e.message || '出表失敗', 'error');
    }
  },
};
