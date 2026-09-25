/* ─── ip_period.js — 地盤糧期狀況編輯 ─────────────────────── */
const IpPeriod = {
  _containerId: null,
  _data: null,
  _editable: false,
  _matrixView: 'by-ip',
  _pendingIpCertFile: null,
  _pendingIpAppFile: null,
  _searchQuery: '',
  _reconcileData: null,
  _bankSelectReady: false,
  _receiptRows: [],
  _bankDropdownIdx: null,
  _receiptUploadIdx: null,

  _formatReceiptPreview(method, chequeNo, bank, date, note) {
    const fmtD = (iso) => {
      if (!iso) return '';
      const m = String(iso).match(/^(\d{4})-(\d{2})-(\d{2})/);
      return m ? `${parseInt(m[3], 10)}/${parseInt(m[2], 10)}/${m[1]}` : iso;
    };
    const dateDisp = fmtD(date);
    if (method === 'transfer') {
      const label = (note || '').trim() || '過數';
      return dateDisp ? `${label} · ${dateDisp}` : label;
    }
    if (method === 'cheque' || chequeNo || bank) {
      let no = (chequeNo || '').trim();
      if (no && !no.startsWith('#')) no = `#${no.replace(/^#/, '')}`;
      if (no && bank && dateDisp) return `${no} , ${bank}, ${dateDisp}`;
      if (no && bank) return `${no} , ${bank}`;
      if (no && dateDisp) return `${no}, ${dateDisp}`;
      return no || bank || dateDisp || '';
    }
    return dateDisp || '';
  },

  _legacyReceiptRecord(r) {
    return {
      method: r.receipt_method,
      cheque_no: r.receipt_cheque_no,
      bank: r.receipt_bank,
      date: r.receipt_date,
      note: r.receipt_note,
      attachment: r.receipt_attachment,
      attachment_name: r.receipt_attachment_name,
    };
  },

  _mergeReceiptRecord(rec, legacy, idx) {
    const base = idx === 0 ? (legacy || {}) : {};
    const pick = (primary, ...fallbacks) => {
      for (const val of [primary, ...fallbacks]) {
        const s = val == null ? '' : String(val).trim();
        if (s) return s;
      }
      return '';
    };
    return {
      method: pick(rec?.method, rec?.receipt_method, base.method) || null,
      cheque_no: pick(rec?.cheque_no, rec?.receipt_cheque_no, base.cheque_no) || null,
      bank: pick(rec?.bank, rec?.receipt_bank, base.bank) || null,
      date: pick(rec?.date, rec?.receipt_date, base.date) || null,
      note: pick(rec?.note, rec?.receipt_note, base.note) || null,
      attachment: rec?.attachment || rec?.receipt_attachment || base.attachment || null,
      attachment_name: rec?.attachment_name || rec?.receipt_attachment_name || base.attachment_name || null,
    };
  },

  _receiptRecordHasContent(rec) {
    return !!(rec.method || rec.cheque_no || rec.bank || rec.date || rec.note || rec.attachment);
  },

  _receiptRecordsForCell(r) {
    const legacy = this._legacyReceiptRecord(r);
    let records = (r.receipt_records && r.receipt_records.length)
      ? r.receipt_records.map((rec, idx) => this._mergeReceiptRecord(rec, legacy, idx))
      : [];
    if (!records.length && this._receiptRecordHasContent(legacy)) {
      records = [legacy];
    }
    return records.filter(rec => this._receiptRecordHasContent(rec));
  },

  _receiptLineText(rec, r, idx, total) {
    let display = this._formatReceiptPreview(
      rec.method,
      rec.cheque_no,
      rec.bank,
      rec.date,
      rec.note,
    );
    if (!display && rec.cheque_no) {
      const no = String(rec.cheque_no).trim();
      display = no.startsWith('#') ? no : `#${no.replace(/^#/, '')}`;
    }
    if (!display && r.receipt_display) {
      const parts = String(r.receipt_display).split(/\s*·\s*/);
      if (parts[idx]) display = parts[idx];
      else if (total === 1) display = r.receipt_display;
    }
    if (!display && idx === 0 && r.receipt_cheque_no) {
      const no = String(r.receipt_cheque_no).trim();
      display = no.startsWith('#') ? no : `#${no.replace(/^#/, '')}`;
    }
    return display;
  },

  _receiptCellHtml(r) {
    const records = this._receiptRecordsForCell(r);
    if (!records.length) {
      return `<td class="ip-receipt-cell" onclick="event.stopPropagation()"><span class="td-muted">—</span></td>`;
    }
    const lines = records.map((rec, i) => {
      const display = this._receiptLineText(rec, r, i, records.length);
      const attach = rec.attachment;
      const attachName = escHtml(rec.attachment_name || '支票附件');
      const safePath = (attach || '').replace(/'/g, "\\'");
      const clipIcon = attach
        ? `<button type="button" class="ip-receipt-clip" title="附件：${attachName}"
            onclick="event.stopPropagation(); DocViewer.open('${safePath}', '${attachName}')"
            aria-label="預覽支票附件">📎</button>`
        : '';
      const text = display
        ? `<span class="ip-receipt-text">${escHtml(display)}</span>`
        : (attach ? '' : '<span class="td-muted">—</span>');
      return `<div class="ip-receipt-line">${text}${clipIcon}</div>`;
    }).join('');
    const tooltip = escHtml(this._receiptTooltip(r));
    return `<td class="ip-receipt-cell" onclick="event.stopPropagation()">
      <div class="ip-receipt-cell-inner ip-receipt-cell-lines" title="${tooltip}">${lines}</div>
    </td>`;
  },

  _receiptTooltip(row) {
    const records = row.receipt_records || [];
    if (records.length > 1) {
      return records.map((rec, i) => {
        const d = this._formatReceiptPreview(
          rec.method, rec.cheque_no, rec.bank, rec.date, rec.note,
        );
        const extra = rec.attachment_name ? ` · 附件：${rec.attachment_name}` : '';
        return `${i + 1}. ${d || '—'}${extra}`;
      }).join('\n');
    }
    const parts = [];
    if (row.receipt_display) parts.push(row.receipt_display);
    if (row.receipt_bank && typeof hkBankShortName === 'function') {
      const name = hkBankShortName(row.receipt_bank);
      if (name && !String(row.receipt_display || '').includes(name)) {
        parts.push(`${row.receipt_bank} ${name}`);
      }
    }
    if (row.receipt_attachment_name) parts.push(`附件：${row.receipt_attachment_name}`);
    return parts.join(' · ') || '';
  },

  _normalizeSearch(q) {
    return String(q || '').trim().toLowerCase();
  },

  _itemSearchBlob(row) {
    const parts = [
      row.ip_no,
      row.applied_date,
      row.certificate_date,
      row.receipt_date,
      row.subcon_cert_date,
      row.receipt_display,
      ...(row.receipt_records || []).flatMap(rec => [
        rec.method, rec.cheque_no, rec.bank, rec.note, rec.date,
        rec.attachment_name,
        this._formatReceiptPreview(rec.method, rec.cheque_no, rec.bank, rec.date, rec.note),
      ]),
      row.receipt_method,
      row.receipt_cheque_no,
      row.receipt_bank,
      row.receipt_note,
      row.receipt_attachment_name,
      row.ip_cert_attachment_name,
      row.ip_application_attachment_name,
      row.application_amount,
      row.certified_income,
      row.subcon_paid,
      row.application_pct,
      row.certified_income_pct,
    ];
    if (row.receipt_bank && typeof hkBankShortName === 'function') {
      parts.push(hkBankShortName(row.receipt_bank));
    }
    if (row.applied_date) parts.push(fmtDate(row.applied_date));
    if (row.certificate_date) parts.push(fmtDate(row.certificate_date));
    if (row.receipt_date) parts.push(fmtDate(row.receipt_date));
    return parts.filter(Boolean).join(' ').toLowerCase();
  },

  _itemMatchesSearch(row, q) {
    const needle = this._normalizeSearch(q);
    if (!needle) return true;
    return this._itemSearchBlob(row).includes(needle);
  },

  _filterItems(items) {
    const q = this._searchQuery;
    if (!this._normalizeSearch(q)) return items || [];
    return (items || []).filter(r => this._itemMatchesSearch(r, q));
  },

  _scDetailSearchBlob(d) {
    return [
      d.sc_no, d.trade_label, d.company_name_en, d.company_name_zh, d.description,
    ].filter(Boolean).join(' ').toLowerCase();
  },

  _filteredMatrix(matrix, containerId) {
    const m = matrix || { columns: [], rows: [], columns_detail: [] };
    if (containerId !== 'ipPeriodScMatrix' || !this._normalizeSearch(this._searchQuery)) return m;
    const q = this._normalizeSearch(this._searchQuery);

    const details = m.columns_detail || [];
    const scMatch = new Set(
      details.filter(d => this._scDetailSearchBlob(d).includes(q)).map(d => d.sc_no),
    );

    if (this._matrixView === 'by-sc') {
      const columns = (m.columns || []).filter(sc => {
        if (sc.toLowerCase().includes(q)) return true;
        if (scMatch.has(sc)) return true;
        const d = details.find(x => x.sc_no === sc);
        if (d && this._scDetailSearchBlob(d).includes(q)) return true;
        return (m.rows || []).some(r =>
          (r.ip_no || '').toLowerCase().includes(q) && (parseFloat(r.cells?.[sc]) || 0),
        );
      });
      return { ...m, columns };
    }

    const rows = (m.rows || []).filter(r => {
      if ((r.ip_no || '').toLowerCase().includes(q)) return true;
      for (const sc of m.columns || []) {
        if (scMatch.has(sc) && (parseFloat(r.cells?.[sc]) || 0)) return true;
        if (sc.toLowerCase().includes(q) && (parseFloat(r.cells?.[sc]) || 0)) return true;
      }
      return false;
    });
    return { ...m, rows };
  },

  _updateSearchCount(allCount, filteredCount) {
    const el = document.getElementById('ipPeriodSearchCount');
    if (!el) return;
    const q = this._normalizeSearch(this._searchQuery);
    if (!q) {
      el.style.display = 'none';
      return;
    }
    el.style.display = '';
    el.textContent = `${filteredCount} / ${allCount} 期`;
  },

  search(val) {
    this._searchQuery = val || '';
    if (this._containerId && this._data) {
      this.render(this._containerId, this._data, {
        editable: this._editable,
        project: App.currentProject,
      });
    }
    this.renderScMatrix('ipPeriodScMatrix', this._data?.sc_matrix, {
      hasMainIp: this._data?.items?.length > 0,
    });
    const reconEl = document.getElementById('ipReconcilePanel');
    if (reconEl && this._reconcileData) {
      IpReconcile.render(reconEl, this._reconcileData, { search: this._searchQuery });
    }
  },

  _ipAttachmentCellHtml(r, field, nameField, label) {
    const attach = r[field];
    const attachName = escHtml(r[nameField] || label);
    const safePath = (attach || '').replace(/'/g, "\\'");
    if (attach) {
      return `<td class="ip-cert-cell" onclick="event.stopPropagation()">
        <button type="button" class="ip-receipt-clip" title="已上傳 ${escHtml(label)}：${attachName}"
          onclick="event.stopPropagation(); DocViewer.open('${safePath}', '${attachName}')"
          aria-label="預覽 ${escHtml(label)}">📄</button>
      </td>`;
    }
    return '<td class="ip-cert-cell td-muted" onclick="event.stopPropagation()">—</td>';
  },

  _ipAppCellHtml(r) {
    return this._ipAttachmentCellHtml(
      r, 'ip_application_attachment', 'ip_application_attachment_name', 'IP Application',
    );
  },

  _ipCertCellHtml(r) {
    return this._ipAttachmentCellHtml(r, 'ip_cert_attachment', 'ip_cert_attachment_name', 'IP Cert.');
  },

  initBankSelect() {
    if (this._bankSelectReady) return;
    this._bankSelectReady = true;
    this.filterBankSelect('');
    if (!this._bankDropdownBound) {
      this._bankDropdownBound = true;
      document.addEventListener('click', (e) => {
        const panel = document.getElementById('ipReceiptBankDropdown');
        if (!panel || panel.hidden) return;
        if (panel.contains(e.target)) return;
        if (e.target.closest('.ip-receipt-bank-trigger')) return;
        this.closeBankDropdown();
      });
    }
  },

  toggleBankDropdown(event, idx) {
    event?.stopPropagation();
    const panel = document.getElementById('ipReceiptBankDropdown');
    const trigger = document.querySelector(`.ip-receipt-bank-trigger[data-idx="${idx}"]`);
    if (!panel) return;
    if (!panel.hidden && this._bankDropdownIdx === idx) {
      this.closeBankDropdown();
      return;
    }
    this.syncReceiptRowFromDom(idx);
    this._bankDropdownIdx = idx;
    this.initBankSelect();
    panel.hidden = false;
    document.querySelector(`.ip-receipt-bank-combo[data-idx="${idx}"]`)?.classList.add('is-open');
    document.querySelector('#ipModal .modal-body')?.classList.add('ip-bank-dropdown-open');
    if (trigger) trigger.setAttribute('aria-expanded', 'true');
    this._positionBankDropdown();
    this._bindBankDropdownReposition();
    const search = document.getElementById('ipReceiptBankSearch');
    if (search) {
      search.value = '';
      this.filterBankSelect('');
      setTimeout(() => search.focus(), 0);
    }
  },

  _positionBankDropdown() {
    const idx = this._bankDropdownIdx;
    const trigger = document.querySelector(`.ip-receipt-bank-trigger[data-idx="${idx}"]`);
    const panel = document.getElementById('ipReceiptBankDropdown');
    const list = document.getElementById('ipReceiptBankList');
    if (!trigger || !panel || !list) return;

    const rect = trigger.getBoundingClientRect();
    const gap = 4;
    const pad = 12;
    const searchBlock = 44;
    const maxList = 220;
    const spaceBelow = window.innerHeight - rect.bottom - gap - pad;
    const spaceAbove = rect.top - gap - pad;
    const openUp = spaceBelow < 140 && spaceAbove > spaceBelow;

    panel.style.position = 'fixed';
    panel.style.left = `${Math.max(pad, rect.left)}px`;
    panel.style.width = `${Math.min(rect.width, window.innerWidth - pad * 2)}px`;
    panel.style.zIndex = '300';

    const listH = Math.min(
      maxList,
      Math.max(96, (openUp ? spaceAbove : spaceBelow) - searchBlock - 8),
    );
    list.style.maxHeight = `${listH}px`;

    if (openUp) {
      panel.classList.add('drop-up');
      panel.style.top = 'auto';
      panel.style.bottom = `${window.innerHeight - rect.top + gap}px`;
    } else {
      panel.classList.remove('drop-up');
      panel.style.bottom = 'auto';
      panel.style.top = `${rect.bottom + gap}px`;
    }
  },

  _bindBankDropdownReposition() {
    if (this._bankRepositionHandler) return;
    this._bankRepositionHandler = () => {
      const panel = document.getElementById('ipReceiptBankDropdown');
      if (panel && !panel.hidden) this._positionBankDropdown();
    };
    window.addEventListener('resize', this._bankRepositionHandler);
    const body = document.querySelector('#ipModal .modal-body');
    body?.addEventListener('scroll', this._bankRepositionHandler, { passive: true });
  },

  _unbindBankDropdownReposition() {
    if (!this._bankRepositionHandler) return;
    window.removeEventListener('resize', this._bankRepositionHandler);
    document.querySelector('#ipModal .modal-body')
      ?.removeEventListener('scroll', this._bankRepositionHandler);
    this._bankRepositionHandler = null;
  },

  closeBankDropdown() {
    const panel = document.getElementById('ipReceiptBankDropdown');
    const idx = this._bankDropdownIdx;
    const trigger = idx != null
      ? document.querySelector(`.ip-receipt-bank-trigger[data-idx="${idx}"]`)
      : null;
    if (panel) panel.hidden = true;
    this._unbindBankDropdownReposition();
    document.querySelectorAll('.ip-receipt-bank-combo.is-open').forEach(el => el.classList.remove('is-open'));
    document.querySelector('#ipModal .modal-body')?.classList.remove('ip-bank-dropdown-open');
    if (trigger) trigger.setAttribute('aria-expanded', 'false');
    this._bankDropdownIdx = null;
  },

  selectBank(code) {
    const idx = this._bankDropdownIdx;
    if (idx == null) return;
    const card = document.querySelector(`.ip-receipt-card[data-receipt-idx="${idx}"]`);
    const customEl = card?.querySelector('.ip-receipt-bank-custom');
    if (customEl) customEl.value = '';
    this._setBankSelectValue(idx, code || '');
    this.closeBankDropdown();
    this._updateReceiptPreview(idx);
  },

  _normalizeBankCode(raw) {
    const digits = String(raw || '').replace(/\D/g, '');
    if (!digits) return '';
    return digits.padStart(3, '0').slice(-3);
  },

  _isMainstreamBankCode(code) {
    const c = this._normalizeBankCode(code);
    return !!(c && typeof HK_MAINSTREAM_BY_CODE !== 'undefined' && HK_MAINSTREAM_BY_CODE[c]);
  },

  _applyCustomBankCode(idx, code) {
    const c = this._normalizeBankCode(code);
    const card = document.querySelector(`.ip-receipt-card[data-receipt-idx="${idx}"]`);
    const hidden = card?.querySelector('.ip-receipt-bank-value');
    const labelEl = card?.querySelector('.ip-bank-combo-label');
    if (hidden) hidden.value = c;
    if (this._receiptRows[idx]) this._receiptRows[idx].bank = c;
    if (labelEl) {
      labelEl.textContent = c ? `${c} — 自填銀行代碼` : '— 請選擇銀行 —';
    }
    this._updateBankHint(idx, c);
  },

  onBankCustomInput(idx) {
    const card = document.querySelector(`.ip-receipt-card[data-receipt-idx="${idx}"]`);
    const el = card?.querySelector('.ip-receipt-bank-custom');
    if (!el) return;
    const digits = el.value.replace(/\D/g, '').slice(0, 3);
    if (el.value !== digits) el.value = digits;
    if (digits) {
      this._applyCustomBankCode(idx, digits);
    } else if (!this._isMainstreamBankCode(card?.querySelector('.ip-receipt-bank-value')?.value)) {
      this._setBankSelectValue(idx, '');
    }
    this._updateReceiptPreview(idx);
  },

  filterBankSelect(presetQuery) {
    const qEl = document.getElementById('ipReceiptBankSearch');
    const q = (presetQuery != null ? presetQuery : (qEl?.value || '')).trim().toLowerCase();
    const list = document.getElementById('ipReceiptBankList');
    const idx = this._bankDropdownIdx;
    const card = idx != null ? document.querySelector(`.ip-receipt-card[data-receipt-idx="${idx}"]`) : null;
    const hidden = card?.querySelector('.ip-receipt-bank-value');
    if (!list || typeof HK_BANKS_MAINSTREAM === 'undefined') return;
    const current = hidden?.value || this._receiptRows[idx]?.bank || '';
    const items = [];
    items.push(`<li><button type="button" class="ip-bank-option${!current ? ' active' : ''}" data-code=""
      onclick="IpPeriod.selectBank('')">— 請選擇銀行 —</button></li>`);
    for (const bank of HK_BANKS_MAINSTREAM) {
      if (!hkBankMatchQuery(bank, q)) continue;
      const active = bank.code === current ? ' active' : '';
      items.push(`<li><button type="button" class="ip-bank-option${active}" data-code="${bank.code}"
        onclick="IpPeriod.selectBank('${bank.code}')">${escHtml(hkBankOptionLabel(bank))}</button></li>`);
    }
    if (current && !HK_BANKS_MAINSTREAM.some(b => b.code === current) && (!q || current.includes(q))) {
      items.push(`<li><button type="button" class="ip-bank-option active" data-code="${current}"
        onclick="IpPeriod.selectBank('${current}')">${current} — （已存／未在清單）</button></li>`);
    }
    if (items.length === 1 && q) {
      items.push('<li class="ip-bank-empty">沒有符合的銀行</li>');
    }
    list.innerHTML = items.join('');
  },

  _bankLabelForCode(code) {
    if (!code) return '— 請選擇銀行 —';
    const c = /^\d+$/.test(String(code)) ? String(code).padStart(3, '0') : String(code).trim();
    const mainstream = typeof HK_MAINSTREAM_BY_CODE !== 'undefined' ? HK_MAINSTREAM_BY_CODE[c] : null;
    if (mainstream) return hkBankOptionLabel(mainstream);
    const bank = typeof HK_BANK_BY_CODE !== 'undefined' ? HK_BANK_BY_CODE[c] : null;
    if (bank && bank.zh) return hkBankOptionLabel({ code: c, zh: bank.zh });
    return `${c} — （已存／未在清單）`;
  },

  _setBankSelectValue(idx, code, opts = {}) {
    const card = document.querySelector(`.ip-receipt-card[data-receipt-idx="${idx}"]`);
    const hidden = card?.querySelector('.ip-receipt-bank-value');
    const labelEl = card?.querySelector('.ip-bank-combo-label');
    const customEl = card?.querySelector('.ip-receipt-bank-custom');
    if (!hidden) {
      if (this._receiptRows[idx]) this._receiptRows[idx].bank = code ? this._normalizeBankCode(code) : '';
      return;
    }
    if (!code) {
      hidden.value = '';
      if (this._receiptRows[idx]) this._receiptRows[idx].bank = '';
      if (labelEl) labelEl.textContent = '— 請選擇銀行 —';
      if (!opts.skipHint) this._updateBankHint(idx, '');
      return;
    }
    const c = this._normalizeBankCode(code);
    hidden.value = c;
    if (this._receiptRows[idx]) this._receiptRows[idx].bank = c;
    if (customEl && !opts.keepCustom) customEl.value = '';
    if (labelEl) labelEl.textContent = this._bankLabelForCode(c);
    if (!opts.skipHint) this._updateBankHint(idx, c);
  },

  _updateBankHint(idx, code) {
    const card = document.querySelector(`.ip-receipt-card[data-receipt-idx="${idx}"]`);
    const hint = card?.querySelector('.ip-receipt-bank-hint');
    if (!hint) return;
    if (!code) {
      hint.textContent = '主流本地銀行，或自填 3 位代碼';
      return;
    }
    const name = typeof hkBankShortName === 'function' ? hkBankShortName(code) : '';
    hint.textContent = name ? `已選：${code} — ${name}` : `已選：${code}`;
  },

  _getSelectedBankCode(idx) {
    const card = document.querySelector(`.ip-receipt-card[data-receipt-idx="${idx}"]`);
    const custom = card?.querySelector('.ip-receipt-bank-custom')?.value?.trim();
    if (custom) return this._normalizeBankCode(custom);
    return card?.querySelector('.ip-receipt-bank-value')?.value?.trim()
      || this._receiptRows[idx]?.bank
      || '';
  },

  _mergeIpProject(ip, project) {
    const base = { ...(ip || {}) };
    const p = project || {};
    const pick = (key) => {
      const v = base[key];
      if (v != null && v !== '') return;
      if (p[key] != null && p[key] !== '') base[key] = p[key];
    };
    ['site_period_text', 'project_name_en', 'project_name_zh', 'project_name', 'project_code'].forEach(pick);
    if (base.contract_amount == null || base.contract_amount === '' || parseFloat(base.contract_amount) === 0) {
      const ca = p.contract_amount;
      if (ca != null && ca !== '' && parseFloat(ca) !== 0) base.contract_amount = ca;
    }
    return base;
  },

  _projectHeroHtml(ip) {
    if (!ip) return '';
    const nameHtml = projectNameHtml(ip);
    const amt = ip.contract_amount;
    const amtHtml = amt != null && amt !== '' && parseFloat(amt) !== 0 ? fmt(amt) : '—';
    return `
      <div class="dash-project-hero ip-period-hero">
        <div class="dash-hero-top ip-period-hero-top">
          <div class="dash-hero-title-block">
            <div class="dash-hero-meta-label">主合約名稱</div>
            <h2 class="dash-hero-name">${nameHtml}</h2>
          </div>
          <div class="dash-hero-amount">
            <div class="dash-hero-meta-label">MP承建金額</div>
            <div class="dash-hero-amount-value">${amtHtml}</div>
          </div>
        </div>
      </div>`;
  },

  _ipFallbackData(p) {
    return {
      site_period_text: p.site_period_text,
      project_name_en: p.project_name_en,
      project_name_zh: p.project_name_zh,
      project_name: p.project_name,
      project_code: p.project_code,
      contract_amount: p.contract_amount,
      items: [],
      totals: { total_income: 0, total_expenditure: 0, advance: 0 },
    };
  },

  render(containerId, ip, options = {}) {
    this._containerId = containerId;
    const project = options.project || App.currentProject;
    ip = this._mergeIpProject(ip, project);
    this._data = ip;
    this._editable = !!options.editable;
    const el = document.getElementById(containerId);
    if (!el) return;

    const editable = this._editable;
    const hideProjectMeta = !!options.hideProjectMeta;
    const toolbar = editable ? `
      <div class="ip-period-toolbar">
        <button type="button" class="btn btn-secondary btn-sm" onclick="IpPeriod.openMetaEdit()">✏️ 編輯匯總</button>
        <button type="button" class="btn btn-primary btn-sm" onclick="IpPeriod.openAdd()">➕ 新增糧期</button>
      </div>` : '';

    if (!ip || !ip.items || !ip.items.length) {
      const metaBlock = hideProjectMeta ? '' : this._projectHeroHtml(ip);
      el.innerHTML = `${toolbar}${metaBlock}
        <div class="empty-state" style="padding:24px">
          <div class="empty-icon">🏗️</div>
          <div class="empty-title">尚無糧期資料</div>
          <div class="empty-sub">${editable ? '可手動新增，或從 Excel Summary 工作表匯入' : '請從 Excel Summary 工作表匯入'}</div>
          ${editable ? '<br><button type="button" class="btn btn-primary btn-sm" onclick="IpPeriod.openAdd()">➕ 新增第一期糧款</button>' : ''}
        </div>`;
      this._updateSearchCount(0, 0);
      this.renderScMatrix('ipPeriodScMatrix', ip?.sc_matrix, { hasMainIp: false });
      return;
    }

    const allItems = ip.items;
    const applySearch = containerId === 'ipPeriodMain' && this._normalizeSearch(this._searchQuery);
    const items = applySearch ? this._filterItems(allItems) : allItems;
    if (containerId === 'ipPeriodMain') {
      this._updateSearchCount(allItems.length, items.length);
    }

    const t = ip.totals || {};
    const period = ip.site_period_text
      ? `<span class="badge badge-muted" style="margin-left:8px">工期 ${ip.site_period_text}</span>` : '';
    const hideTotals = options.hideTotals || false;
    const advClass = amtClass(t.advance);
    const actionTh = editable ? '<th style="width:72px">操作</th>' : '';

    const rows = items.length
      ? items.map(r => {
      const actions = editable ? `
        <td onclick="event.stopPropagation()">
          <div style="display:flex;gap:4px">
            <button type="button" class="btn btn-icon btn-secondary btn-sm" title="編輯" onclick="IpPeriod.openEdit(${r.id})">✏️</button>
            <button type="button" class="btn btn-icon btn-danger btn-sm" title="刪除" onclick="IpPeriod.delete(${r.id}, '${(r.ip_no || '').replace(/'/g, "\\'")}')">🗑️</button>
          </div>
        </td>` : '';
      const rowClick = editable ? ` class="row-clickable" onclick="IpPeriod.openEdit(${r.id})" title="點擊編輯"` : '';
      return `
        <tr${rowClick}>
          <td class="td-mono" style="font-weight:600">${r.ip_no}</td>
          ${this._ipAppCellHtml(r)}
          <td class="td-amount ${amtClass(r.application_amount)}">${fmt(r.application_amount)}</td>
          <td class="td-muted">${fmtDate(r.applied_date)}</td>
          ${this._ipCertCellHtml(r)}
          <td class="td-amount ${amtClass(r.certified_income, 'income')}">${fmt(r.certified_income)}</td>
          <td class="td-muted" style="text-align:right">${fmtPct(r.certified_income_pct)}</td>
          <td class="td-muted">${fmtDate(r.certificate_date)}</td>
          ${this._receiptCellHtml(r)}
          <td class="td-muted ip-col-frozen-hidden" style="text-align:right">${fmtPct(r.application_pct)}</td>
          <td class="td-amount ip-col-frozen-hidden ${amtClass(r.subcon_paid, 'expense')}">${r.subcon_paid ? fmtExpense(r.subcon_paid) : '—'}</td>
          <td class="td-muted ip-col-frozen-hidden" style="text-align:right">${fmtPct(r.subcon_paid_pct)}</td>
          ${actions}
        </tr>`;
    }).join('')
      : (applySearch
        ? `<tr><td colspan="${editable ? 13 : 12}" class="td-muted" style="padding:24px;text-align:center">無符合「${escHtml(this._searchQuery.trim())}」的糧期</td></tr>`
        : '');

    const totalsHtml = hideTotals ? '' : `
      <div class="ip-period-totals${editable ? ' ip-period-totals-editable' : ''}">
        <div><span class="label">總收入</span><strong class="${amtClass(t.total_income, 'income')}">${fmtAcct(t.total_income)}</strong></div>
        <div><span class="label">總支出</span><strong class="negative">${fmtIpExpenditure(t.total_expenditure)}</strong></div>
        <div><span class="label">墊支</span><strong class="${advClass}">${fmtAcct(t.advance)}</strong></div>
        ${editable ? '<button type="button" class="btn btn-icon btn-secondary btn-sm ip-totals-edit" title="編輯匯總" onclick="IpPeriod.openMetaEdit()">✏️</button>' : ''}
      </div>`;

    const projectHero = hideProjectMeta ? '' : this._projectHeroHtml(ip);

    el.innerHTML = `
      ${toolbar}
      ${projectHero}
      <div style="margin-bottom:12px;font-size:12px;color:var(--text-secondary)">
        主合約糧款追蹤（業主批款）${period}
        ${editable ? '<span style="margin-left:8px;color:var(--text-muted)">· 批款% 依承建金額自動計算</span>' : ''}
      </div>
      <div class="ip-period-wrap">
        <table class="ip-period-table">
          <thead>
            <tr>
              <th>糧款期數</th>
              <th style="width:52px">IP Application</th>
              <th class="th-num">美博申請付款</th>
              <th>申請日期</th>
              <th style="width:52px">IP Cert.</th>
              <th class="th-num">業主批款</th>
              <th class="th-num">批款%</th>
              <th>批款日期</th>
              <th>收款記錄<br><span class="th-sub">支票／過數</span></th>
              <th class="th-num ip-col-frozen-hidden">申請%</th>
              <th class="th-num ip-col-frozen-hidden">分包總支出</th>
              <th class="th-num ip-col-frozen-hidden">支出%</th>
              ${actionTh}
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>${totalsHtml}`;
    this.renderScMatrix('ipPeriodScMatrix', ip.sc_matrix, { hasMainIp: true });
  },

  renderScMatrix(containerId, matrix, options = {}) {
    const el = document.getElementById(containerId);
    if (!el) return;
    const raw = matrix || { columns: [], rows: [] };
    const m = this._filteredMatrix(raw, containerId);
    if (!raw.columns?.length) {
      const hasMainIp = options.hasMainIp || (this._data?.items?.length > 0);
      const hint = hasMainIp
        ? '主糧期已有資料但分包矩陣為空：請重啟 Flask（載入新版本）後 Ctrl+F5 刷新，並重新匯入 Payment Excel Summary。'
        : '從 Excel Summary 匯入後，會顯示各分判商（SC-004…）每期批款矩陣';
      el.innerHTML = `
        <div class="empty-state" style="padding:24px">
          <div class="empty-icon">📊</div>
          <div class="empty-title">尚無分包糧期明細</div>
          <div class="empty-sub">${escHtml(hint)}</div>
        </div>`;
      return;
    }

    if (containerId === 'ipPeriodScMatrix' && this._normalizeSearch(this._searchQuery) && !(m.rows?.length || m.columns?.length)) {
      el.innerHTML = `
        <div class="empty-state" style="padding:24px">
          <div class="empty-icon">🔍</div>
          <div class="empty-title">無符合搜尋的分包糧期</div>
          <div class="empty-sub">請調整關鍵字，或清除搜尋列</div>
        </div>`;
      return;
    }

    const html = this._matrixView === 'by-sc'
      ? this._renderScMatrixBySc(m)
      : this._renderScMatrixByIp(m);
    el.innerHTML = html;
  },

  setMatrixView(view) {
    this._matrixView = view;
    this.renderScMatrix('ipPeriodScMatrix', this._data?.sc_matrix, {
      hasMainIp: this._data?.items?.length > 0,
    });
  },

  _matrixToolbar(m) {
    const sum = m.summary || {};
    const details = m.columns_detail || [];
    let badges = '';
    if (sum.overpaid_count > 0) {
      badges += `<span class="badge badge-danger" style="margin-left:8px">超付 ${sum.overpaid_count} 個分判</span>`;
    } else if (details.length) {
      badges += '<span class="badge badge-success" style="margin-left:8px">判項餘額正常</span>';
    }
    if (sum.all_matrix_match === false) {
      badges += '<span class="badge badge-warning" style="margin-left:6px">糧期合計 ≠ 付款登記</span>';
    } else if (details.length) {
      badges += '<span class="badge badge-success" style="margin-left:6px">糧期 = 登記</span>';
    }
    const byIpCls = this._matrixView === 'by-ip' ? 'btn-primary' : 'btn-secondary';
    const byScCls = this._matrixView === 'by-sc' ? 'btn-primary' : 'btn-secondary';
    return `
      <div class="ip-sc-matrix-toolbar">
        <div style="font-size:12px;color:var(--text-secondary)">
          美博批款 → 各分判商（Summary Sub-con）${badges}
        </div>
        <div class="ip-sc-view-toggle">
          <button type="button" class="btn btn-sm ${byIpCls}" onclick="IpPeriod.setMatrixView('by-ip')">按期</button>
          <button type="button" class="btn btn-sm ${byScCls}" onclick="IpPeriod.setMatrixView('by-sc')">按分判</button>
        </div>
      </div>`;
  },

  _scCellHtml(ipNo, scNo, amt) {
    const v = parseFloat(amt) || 0;
    const display = v ? fmtExpense(v) : '—';
    const clickable = v ? ' ip-sc-cell-click' : '';
    const safeIp = (ipNo || '').replace(/'/g, '');
    const safeSc = (scNo || '').replace(/'/g, '');
    const onclick = v
      ? ` onclick="IpPeriod.openScDrilldown('${safeIp}','${safeSc}',${v})"`
      : '';
    return `<td class="td-amount ${amtClass(v, 'expense')}${clickable}"${onclick} title="${v ? '點擊查看付款明細' : ''}">${display}</td>`;
  },

  _renderScMatrixByIp(m) {
    const details = m.columns_detail || [];
    const detailMap = Object.fromEntries(details.map(d => [d.sc_no, d]));
    const headScNo = m.columns.map(sc => {
      const d = detailMap[sc] || {};
      const tips = [];
      if (d.trade_label) tips.push(d.trade_label);
      if (d.overpaid) tips.push('超付');
      const tip = tips.length ? ` title="${escHtml(tips.join(' · '))}"` : '';
      return `<th class="th-num ip-sc-col-head"${tip}>${escHtml(sc)}</th>`;
    }).join('');
    const headScTrade = m.columns.map(sc => {
      const lbl = detailMap[sc]?.trade_label;
      return `<th class="th-num ip-sc-col-trade">${lbl ? escHtml(lbl) : '—'}</th>`;
    }).join('');
    const headScCo = m.columns.map(sc => {
      const d = detailMap[sc] || {};
      const nameHtml = formatCompanyNameHtml(d.company_name_en, d.company_name_zh);
      const warn = d.matrix_match === false
        ? '<span class="badge badge-warning" style="margin-top:2px;font-size:9px">差異</span>' : '';
      const over = d.overpaid
        ? '<span class="badge badge-danger" style="margin-top:2px;font-size:9px">超付</span>' : '';
      return `<th class="th-num ip-sc-col-co">${nameHtml}${warn}${over}</th>`;
    }).join('');

    const colTotals = m.column_totals || {};
    const footMatrix = m.columns.map(sc =>
      `<td class="td-amount ${amtClass(colTotals[sc], 'expense')}">${colTotals[sc] ? fmtExpense(colTotals[sc]) : '—'}</td>`).join('');
    const footContract = m.columns.map(sc => {
      const v = detailMap[sc]?.contract_amount;
      return `<td class="td-amount td-muted">${v ? fmt(v) : '—'}</td>`;
    }).join('');
    const footPaid = m.columns.map(sc => {
      const d = detailMap[sc] || {};
      const cls = d.matrix_match === false ? 'td-amount warn' : `td-amount ${amtClass(d.total_paid_records, 'expense')}`;
      return `<td class="${cls}">${d.total_paid_records ? fmtExpense(d.total_paid_records) : '—'}</td>`;
    }).join('');
    const footRemain = m.columns.map(sc => {
      const v = detailMap[sc]?.remainder;
      if (v == null || v === '') return '<td class="td-amount">—</td>';
      const cls = `td-amount ${amtClass(v, 'expense')}`;
      return `<td class="${cls}">${fmtExpense(v)}</td>`;
    }).join('');

    const sum = m.summary || {};
    let grandTotal = 0;
    const body = m.rows.map(r => {
      const cells = m.columns.map(sc =>
        this._scCellHtml(r.ip_no, sc, r.cells?.[sc])).join('');
      grandTotal += parseFloat(r.total) || 0;
      return `
        <tr>
          <td class="td-mono" style="font-weight:600">${escHtml(r.ip_no)}</td>
          ${cells}
          <td class="td-amount ${amtClass(r.total, 'expense')}" style="font-weight:600">${r.total ? fmtExpense(r.total) : '—'}</td>
          <td class="td-muted" style="text-align:right">${fmtPct(r.subcon_paid_pct)}</td>
        </tr>`;
    }).join('');

    return `
      ${this._matrixToolbar(m)}
      <div class="ip-period-wrap">
        <table class="ip-period-table ip-sc-matrix">
          <thead>
            <tr>
              <th rowspan="3">糧款期數</th>
              ${headScNo}
              <th class="th-num" rowspan="3">總支出</th>
              <th class="th-num" rowspan="3">累計%</th>
            </tr>
            <tr>${headScTrade}</tr>
            <tr>${headScCo}</tr>
          </thead>
          <tbody>${body}</tbody>
          <tfoot>
            <tr class="ip-sc-matrix-foot"><td style="font-weight:600">糧期合計</td>${footMatrix}
              <td class="td-amount ${amtClass(grandTotal, 'expense')}" style="font-weight:600">${grandTotal ? fmtExpense(grandTotal) : '—'}</td><td></td></tr>
            <tr class="ip-sc-matrix-foot ip-sc-matrix-meta"><td class="td-muted">判項金額</td>${footContract}
              <td class="td-amount td-muted">${sum.total_contract ? fmt(sum.total_contract) : '—'}</td><td></td></tr>
            <tr class="ip-sc-matrix-foot ip-sc-matrix-meta"><td class="td-muted">付款登記</td>${footPaid}
              <td class="td-amount ${amtClass(sum.total_paid_records, 'expense')}">${sum.total_paid_records ? fmtExpense(sum.total_paid_records) : '—'}</td><td></td></tr>
            <tr class="ip-sc-matrix-foot ip-sc-matrix-meta"><td class="td-muted">餘額</td>${footRemain}
              <td class="td-amount ${amtClass((sum.total_contract || 0) - (sum.total_paid_records || 0), 'expense')}">${sum.total_contract != null ? fmtExpense((sum.total_contract || 0) - (sum.total_paid_records || 0)) : '—'}</td><td></td></tr>
          </tfoot>
        </table>
      </div>
      <div class="form-hint" style="margin-top:8px">點擊有金額的格子可查看付款登記明細與核對</div>`;
  },

  _renderScMatrixBySc(m) {
    const details = m.columns_detail || [];
    const detailMap = Object.fromEntries(details.map(d => [d.sc_no, d]));
    const ipCols = m.rows.map(r => r.ip_no);
    const headIp = ipCols.map(ip =>
      `<th class="th-num">${escHtml(ip)}</th>`).join('');

    const colTotals = m.column_totals || {};
    const ipColTotals = Object.fromEntries(ipCols.map(ip => [ip, 0]));
    const body = m.columns.map(sc => {
      const d = detailMap[sc] || {};
      const cells = m.rows.map(r => {
        const amt = r.cells?.[sc] || 0;
        ipColTotals[r.ip_no] = (ipColTotals[r.ip_no] || 0) + (parseFloat(amt) || 0);
        return this._scCellHtml(r.ip_no, sc, amt);
      }).join('');
      const total = colTotals[sc] || 0;
      const rem = d.remainder;
      const remCls = `td-amount ${amtClass(rem, 'expense')}`;
      const label = [
        `<div class="td-mono" style="font-weight:600">${escHtml(sc)}</div>`,
        d.trade_label ? `<div class="ip-sc-row-trade">${escHtml(d.trade_label)}</div>` : '',
        `<div class="ip-sc-row-co">${formatCompanyNameHtml(d.company_name_en, d.company_name_zh)}</div>`,
      ].join('');
      return `
        <tr>
          <td class="ip-sc-row-label">${label}</td>
          ${cells}
          <td class="td-amount ${amtClass(total, 'expense')}" style="font-weight:600">${total ? fmtExpense(total) : '—'}</td>
          <td class="td-amount td-muted">${d.contract_amount ? fmt(d.contract_amount) : '—'}</td>
          <td class="${remCls}">${rem != null ? fmtExpense(rem) : '—'}</td>
        </tr>`;
    }).join('');

    const footIpTotals = ipCols.map(ip =>
      `<td class="td-amount ${amtClass(ipColTotals[ip], 'expense')}">${ipColTotals[ip] ? fmtExpense(ipColTotals[ip]) : '—'}</td>`).join('');
    const sum = m.summary || {};

    return `
      ${this._matrixToolbar(m)}
      <div class="ip-period-wrap">
        <table class="ip-period-table ip-sc-matrix">
          <thead>
            <tr>
              <th>分判商</th>
              ${headIp}
              <th class="th-num">合計</th>
              <th class="th-num">判項</th>
              <th class="th-num">餘額</th>
            </tr>
          </thead>
          <tbody>${body}</tbody>
          <tfoot>
            <tr class="ip-sc-matrix-foot">
              <td style="font-weight:600">糧期合計</td>
              ${footIpTotals}
              <td class="td-amount ${amtClass(sum.total_paid_matrix, 'expense')}" style="font-weight:600">${sum.total_paid_matrix ? fmtExpense(sum.total_paid_matrix) : '—'}</td>
              <td class="td-amount td-muted">${sum.total_contract ? fmt(sum.total_contract) : '—'}</td>
              <td class="td-amount ${amtClass((sum.total_contract || 0) - (sum.total_paid_records || 0), 'expense')}">${sum.total_contract != null ? fmtExpense((sum.total_contract || 0) - (sum.total_paid_records || 0)) : '—'}</td>
            </tr>
          </tfoot>
        </table>
      </div>
      <div class="form-hint" style="margin-top:8px">點擊有金額的格子可查看付款登記明細與核對</div>`;
  },

  async openScDrilldown(ipNo, scNo, matrixAmt) {
    const p = App.currentProject;
    if (!p) return;
    const modal = document.getElementById('ipScDrillModal');
    const body = document.getElementById('ipScDrillBody');
    const title = document.getElementById('ipScDrillTitle');
    if (!modal || !body) return;
    title.textContent = `${scNo} · ${ipNo}`;
    body.innerHTML = '<div class="empty-state" style="padding:20px">載入中...</div>';
    modal.classList.add('open');
    try {
      const data = await api('GET', `/projects/${p.id}/ip-sc-drilldown?ip_no=${encodeURIComponent(ipNo)}&sc_no=${encodeURIComponent(scNo)}`);
      if (!data) return;
      const matchBadge = data.match
        ? '<span class="badge badge-success">一致</span>'
        : `<span class="badge badge-warning">差異 ${fmt(Math.abs(data.diff))}</span>`;
      const rows = (data.payments || []).map(r => `
        <tr>
          <td class="td-mono">${escHtml(r.seq_no || '')}</td>
          <td class="td-muted">${fmtDate(r.invoice_date)}</td>
          <td class="td-mono">${escHtml(r.invoice_no || '—')}</td>
          <td>${escHtml((r.description || '').substring(0, 48))}</td>
          <td class="td-amount ${amtClass(r.paid_amount, 'expense')}">${fmtExpense(r.paid_amount)}</td>
        </tr>`).join('');
      body.innerHTML = `
        <div class="ip-sc-drill-summary">
          <div><span class="label">糧期矩陣</span><strong>${fmt(data.matrix_amount)}</strong></div>
          <div><span class="label">付款登記合計</span><strong>${fmt(data.records_total)}</strong></div>
          <div>${matchBadge}</div>
        </div>
        ${rows ? `
        <div class="ip-period-wrap" style="margin-top:12px">
          <table class="ip-period-table" style="min-width:520px">
            <thead><tr>
              <th>序號</th><th>發票日期</th><th>發票號</th><th>描述</th><th class="th-num">已付</th>
            </tr></thead>
            <tbody>${rows}</tbody>
          </table>
        </div>` : '<p class="form-hint" style="padding:12px">無符合 Sub-IP No. 的付款登記</p>'}`;
    } catch (e) {
      body.innerHTML = '<p class="form-hint" style="padding:12px">無法載入明細</p>';
    }
  },

  closeScDrillModal() {
    document.getElementById('ipScDrillModal')?.classList.remove('open');
  },

  _suggestIpNo(items) {
    if (!items?.length) return 'IP-01';
    let max = 0;
    for (const it of items) {
      const m = (it.ip_no || '').match(/IP-(\d+)/i);
      if (m) max = Math.max(max, parseInt(m[1], 10));
    }
    return `IP-${String(max + 1).padStart(2, '0')}`;
  },

  openAdd() {
    const p = App.currentProject;
    if (!p) { toast('請先選擇項目', 'warning'); return; }
    this._pendingIpCertFile = null;
    this._pendingIpAppFile = null;
    this._receiptRows = [this._emptyReceiptRow()];
    document.getElementById('ipModalTitle').textContent = '新增糧期';
    document.getElementById('ipModalId').value = '';
    document.getElementById('ipNo').value = this._suggestIpNo(this._data?.items);
    document.getElementById('ipSeqNo').value = '';
    document.getElementById('ipAppliedDate').value = '';
    document.getElementById('ipAppAmt').value = '';
    document.getElementById('ipCertAmt').value = '';
    document.getElementById('ipCertDate').value = '';
    document.getElementById('ipSubconPaid').value = '';
    document.getElementById('ipSubconCertDate').value = '';
    this._fillReceiptForm({});
    this._renderIpAppAttach({});
    this._renderIpCertAttach({});
    document.getElementById('ipPctHint').textContent = '儲存後依承建金額自動計算批款 %';
    document.getElementById('ipModal').classList.add('open');
    AmountInput.init(document.getElementById('ipModal'));
  },

  _emptyReceiptRow() {
    return {
      method: '',
      cheque_no: '',
      bank: '',
      date: '',
      note: '',
      attachment: null,
      attachment_name: null,
      pendingFile: null,
    };
  },

  _normalizeReceiptRow(r) {
    return {
      method: r?.method || r?.receipt_method || '',
      cheque_no: r?.cheque_no || r?.receipt_cheque_no || '',
      bank: r?.bank || r?.receipt_bank || '',
      date: r?.date || r?.receipt_date || '',
      note: r?.note || r?.receipt_note || '',
      attachment: r?.attachment || r?.receipt_attachment || null,
      attachment_name: r?.attachment_name || r?.receipt_attachment_name || null,
      pendingFile: null,
    };
  },

  syncReceiptRowFromDom(idx) {
    const card = document.querySelector(`.ip-receipt-card[data-receipt-idx="${idx}"]`);
    if (!card || !this._receiptRows[idx]) return;
    const row = this._receiptRows[idx];
    row.method = card.querySelector('.ip-receipt-method')?.value || '';
    row.date = card.querySelector('.ip-receipt-date')?.value || '';
    row.cheque_no = card.querySelector('.ip-receipt-cheque-no')?.value?.trim() || '';
    row.note = card.querySelector('.ip-receipt-note')?.value?.trim() || '';
    row.bank = this._getSelectedBankCode(idx);
  },

  syncAllReceiptRowsFromDom() {
    (this._receiptRows || []).forEach((_, idx) => this.syncReceiptRowFromDom(idx));
  },

  addReceiptRow() {
    this.syncAllReceiptRowsFromDom();
    this._receiptRows.push(this._emptyReceiptRow());
    this.renderReceiptRows();
  },

  removeReceiptRow(idx) {
    if (this._receiptRows.length <= 1) return;
    this.syncAllReceiptRowsFromDom();
    this._receiptRows.splice(idx, 1);
    this.renderReceiptRows();
  },

  _receiptAttachHtml(idx, row) {
    if (row.pendingFile) {
      return `<div class="ip-receipt-attach-item"><span>待上傳：${escHtml(row.pendingFile.name)}</span></div>`;
    }
    if (row.attachment) {
      const name = escHtml(row.attachment_name || '支票附件');
      const path = (row.attachment || '').replace(/"/g, '&quot;');
      return `<div class="ip-receipt-attach-item">
        <button type="button" class="btn btn-link btn-sm" onclick="DocViewer.open('${path}', '${name}')">${name}</button>
        <button type="button" class="btn btn-icon btn-danger btn-sm" title="刪除附件"
          onclick="IpPeriod.deleteReceiptAttachment(${idx})">🗑️</button>
      </div>`;
    }
    return '';
  },

  _receiptCardHtml(idx, row) {
    const method = row.method || '';
    const showCheque = method === 'cheque';
    const showTransfer = method === 'transfer';
    const bankCode = row.bank || '';
    const bankLabel = bankCode ? this._bankLabelForCode(bankCode) : '— 請選擇銀行 —';
    const customBank = bankCode && !this._isMainstreamBankCode(bankCode)
      ? (bankCode.replace(/^0+/, '') || bankCode)
      : '';
    const removeBtn = this._receiptRows.length > 1
      ? `<button type="button" class="btn-ip-receipt-remove" onclick="IpPeriod.removeReceiptRow(${idx})" title="移除此筆">×</button>`
      : '';
    return `<div class="ip-receipt-card" data-receipt-idx="${idx}">
      <div class="ip-receipt-card-head">
        <span>第 ${idx + 1} 筆</span>
        ${removeBtn}
      </div>
      <div class="form-row">
        <div class="form-group">
          <label class="form-label">方式</label>
          <select class="form-input ip-receipt-method" onchange="IpPeriod.onReceiptMethodChange(${idx})">
            <option value=""${method === '' ? ' selected' : ''}>— 未填 —</option>
            <option value="cheque"${method === 'cheque' ? ' selected' : ''}>支票</option>
            <option value="transfer"${method === 'transfer' ? ' selected' : ''}>過數</option>
          </select>
        </div>
        <div class="form-group">
          <label class="form-label">收款日期</label>
          <input type="date" class="form-input ip-receipt-date" value="${escHtml(row.date || '')}"
            onchange="IpPeriod._updateReceiptPreview(${idx})">
        </div>
      </div>
      <div class="form-row ip-receipt-cheque-fields" style="display:${showCheque ? '' : 'none'}">
        <div class="form-group">
          <label class="form-label">支票號碼</label>
          <input type="text" class="form-input ip-receipt-cheque-no" placeholder="#828310"
            value="${escHtml(row.cheque_no || '')}" oninput="IpPeriod._updateReceiptPreview(${idx})">
        </div>
        <div class="form-group">
          <label class="form-label">銀行</label>
          <div class="ip-bank-combo ip-receipt-bank-combo" data-idx="${idx}">
            <button type="button" class="form-input ip-bank-combo-trigger ip-receipt-bank-trigger" data-idx="${idx}"
              onclick="IpPeriod.toggleBankDropdown(event, ${idx})" aria-haspopup="listbox" aria-expanded="false">
              <span class="ip-bank-combo-label">${escHtml(bankLabel)}</span>
              <span class="ip-bank-chevron" aria-hidden="true">▾</span>
            </button>
            <input type="hidden" class="ip-receipt-bank-value" value="${escHtml(bankCode)}">
          </div>
          <div class="ip-bank-custom-row">
            <span class="ip-bank-custom-label">或自填</span>
            <input type="text" class="form-input ip-bank-custom ip-receipt-bank-custom" data-idx="${idx}"
              inputmode="numeric" maxlength="3" placeholder="3 位代碼，如 061"
              value="${escHtml(customBank)}" oninput="IpPeriod.onBankCustomInput(${idx})">
          </div>
          <div class="form-hint ip-receipt-bank-hint">主流本地銀行，或自填 3 位代碼</div>
        </div>
      </div>
      <div class="form-group ip-receipt-transfer-fields" style="display:${showTransfer ? '' : 'none'}">
        <label class="form-label">過數備註</label>
        <input type="text" class="form-input ip-receipt-note" placeholder="轉帳參考／備註"
          value="${escHtml(row.note || '')}" oninput="IpPeriod._updateReceiptPreview(${idx})">
      </div>
      <div class="form-hint ip-receipt-preview"></div>
      <div class="ip-receipt-attach-row">
        <button type="button" class="btn btn-secondary btn-sm" onclick="IpPeriod.pickReceiptFile(${idx})">📎 上傳支票附件</button>
        <span class="form-hint ip-receipt-attach-hint">PDF / PNG / JPG · 新增記錄需先儲存再上傳</span>
      </div>
      <div class="ip-receipt-attach-list">${this._receiptAttachHtml(idx, row)}</div>
    </div>`;
  },

  renderReceiptRows() {
    const list = document.getElementById('ipReceiptRowsList');
    if (!list) return;
    if (!this._receiptRows.length) this._receiptRows = [this._emptyReceiptRow()];
    list.innerHTML = `<div class="ip-receipt-rows">${this._receiptRows.map((row, idx) => this._receiptCardHtml(idx, row)).join('')}</div>`;
    this._receiptRows.forEach((_, idx) => this._updateReceiptPreview(idx));
  },

  _fillReceiptForm(row) {
    const bankSearch = document.getElementById('ipReceiptBankSearch');
    if (bankSearch) bankSearch.value = '';
    this.initBankSelect();
    const records = (row.receipt_records && row.receipt_records.length)
      ? row.receipt_records.map(r => this._normalizeReceiptRow(r))
      : [];
    if (!records.length && (row.receipt_method || row.receipt_cheque_no || row.receipt_bank
      || row.receipt_date || row.receipt_note || row.receipt_attachment)) {
      records.push(this._normalizeReceiptRow(row));
    }
    this._receiptRows = records.length ? records : [this._emptyReceiptRow()];
    this.renderReceiptRows();
  },

  onReceiptMethodChange(idx) {
    this.syncReceiptRowFromDom(idx);
    const card = document.querySelector(`.ip-receipt-card[data-receipt-idx="${idx}"]`);
    if (!card) return;
    const method = card.querySelector('.ip-receipt-method')?.value || '';
    this._receiptRows[idx].method = method;
    card.querySelector('.ip-receipt-cheque-fields').style.display = method === 'cheque' ? '' : 'none';
    card.querySelector('.ip-receipt-transfer-fields').style.display = method === 'transfer' ? '' : 'none';
    this._updateReceiptPreview(idx);
  },

  _updateReceiptPreview(idx) {
    this.syncReceiptRowFromDom(idx);
    const card = document.querySelector(`.ip-receipt-card[data-receipt-idx="${idx}"]`);
    const el = card?.querySelector('.ip-receipt-preview');
    if (!el || !this._receiptRows[idx]) return;
    const row = this._receiptRows[idx];
    const preview = this._formatReceiptPreview(
      row.method, row.cheque_no, row.bank, row.date, row.note,
    );
    const bankName = row.bank && typeof hkBankShortName === 'function' ? hkBankShortName(row.bank) : '';
    el.textContent = preview
      ? `預覽：${preview}${bankName ? `（${bankName}）` : ''}`
      : '';
    this._updateBankHint(idx, row.bank);
  },

  pickReceiptFile(idx) {
    this._receiptUploadIdx = idx;
    document.getElementById('ipReceiptFileInput')?.click();
  },

  onReceiptFileSelected(event) {
    const file = event.target?.files?.[0];
    const idx = this._receiptUploadIdx;
    if (!file || idx == null) return;
    const id = document.getElementById('ipModalId').value;
    if (id) {
      this._uploadReceiptFile(id, file, idx);
    } else if (this._receiptRows[idx]) {
      this._receiptRows[idx].pendingFile = file;
      this.renderReceiptRows();
    }
    this._receiptUploadIdx = null;
    if (event.target) event.target.value = '';
  },

  async _uploadReceiptFile(ipId, file, recordIndex = 0) {
    showLoading('上傳附件…');
    try {
      const fd = new FormData();
      fd.append('file', file);
      fd.append('record_index', String(recordIndex));
      const res = await fetch(`${API}/interim-payments/${ipId}/receipt-attachment`, { method: 'POST', body: fd });
      const json = await res.json();
      if (!json.success) throw new Error(json.error || '上傳失敗');
      toast('支票附件已上傳', 'success');
      if (json.data?.summary) {
        this._data = json.data.summary;
        if (this._containerId) this.render(this._containerId, this._data, { editable: this._editable });
      }
      const row = await api('GET', `/interim-payments/${ipId}`);
      if (row) this._fillReceiptForm(row);
    } catch (e) {
      toast(e.message || '上傳失敗', 'error');
    } finally {
      hideLoading();
    }
  },

  async deleteReceiptAttachment(idx) {
    const id = document.getElementById('ipModalId').value;
    if (!id) return;
    if (!confirm('刪除此支票附件？')) return;
    try {
      await api('DELETE', `/interim-payments/${id}/receipt-attachment?record_index=${idx}`);
      toast('附件已刪除', 'success');
      const row = await api('GET', `/interim-payments/${id}`);
      if (row) this._fillReceiptForm(row);
      await this.refresh();
    } catch (e) {}
  },

  _renderIpAppAttach(row) {
    const el = document.getElementById('ipAppAttachList');
    const hint = document.getElementById('ipAppAttachHint');
    if (!el) return;
    const pending = this._pendingIpAppFile;
    if (pending) {
      el.innerHTML = `<div class="ip-receipt-attach-item"><span>待上傳：${escHtml(pending.name)}</span></div>`;
      if (hint) hint.textContent = '儲存後會一併上傳';
      return;
    }
    if (row.ip_application_attachment) {
      const name = escHtml(row.ip_application_attachment_name || 'IP Application');
      const path = (row.ip_application_attachment || '').replace(/"/g, '&quot;');
      el.innerHTML = `
        <div class="ip-receipt-attach-item">
          <button type="button" class="btn btn-link btn-sm" onclick="DocViewer.open('${path}', '${name}')">${name}</button>
          <button type="button" class="btn btn-icon btn-danger btn-sm" title="刪除附件" onclick="IpPeriod.deleteIpAppAttachment()">🗑️</button>
        </div>`;
      if (hint) hint.textContent = '已上傳 IP Application';
    } else {
      el.innerHTML = '';
      if (hint) hint.textContent = 'PDF / PNG / JPG · 新增記錄需先儲存再上傳';
    }
  },

  pickIpAppFile() {
    document.getElementById('ipAppFileInput')?.click();
  },

  onIpAppFileSelected(event) {
    const file = event.target?.files?.[0];
    if (!file) return;
    const id = document.getElementById('ipModalId').value;
    if (id) {
      this._uploadIpAppFile(id, file);
    } else {
      this._pendingIpAppFile = file;
      this._renderIpAppAttach({});
    }
    if (event.target) event.target.value = '';
  },

  async _uploadIpAppFile(ipId, file) {
    showLoading('上傳 IP Application…');
    try {
      const fd = new FormData();
      fd.append('file', file);
      const res = await fetch(`${API}/interim-payments/${ipId}/ip-application-attachment`, { method: 'POST', body: fd });
      const json = await res.json();
      if (!json.success) throw new Error(json.error || '上傳失敗');
      toast('IP Application 已上傳', 'success');
      this._pendingIpAppFile = null;
      if (json.data?.summary) {
        this._data = json.data.summary;
        if (this._containerId) this.render(this._containerId, this._data, { editable: this._editable });
      }
      const row = await api('GET', `/interim-payments/${ipId}`);
      if (row) this._renderIpAppAttach(row);
    } catch (e) {
      toast(e.message || '上傳失敗', 'error');
    } finally {
      hideLoading();
    }
  },

  async deleteIpAppAttachment() {
    const id = document.getElementById('ipModalId').value;
    if (!id) return;
    if (!confirm('刪除此 IP Application 附件？')) return;
    try {
      await api('DELETE', `/interim-payments/${id}/ip-application-attachment`);
      toast('IP Application 已刪除', 'success');
      const row = await api('GET', `/interim-payments/${id}`);
      if (row) this._renderIpAppAttach(row);
      await this.refresh();
    } catch (e) {}
  },

  _renderIpCertAttach(row) {
    const el = document.getElementById('ipCertAttachList');
    const hint = document.getElementById('ipCertAttachHint');
    if (!el) return;
    const pending = this._pendingIpCertFile;
    if (pending) {
      el.innerHTML = `<div class="ip-receipt-attach-item"><span>待上傳：${escHtml(pending.name)}</span></div>`;
      if (hint) hint.textContent = '儲存後會一併上傳';
      return;
    }
    if (row.ip_cert_attachment) {
      const name = escHtml(row.ip_cert_attachment_name || 'IP Cert.');
      const path = (row.ip_cert_attachment || '').replace(/"/g, '&quot;');
      el.innerHTML = `
        <div class="ip-receipt-attach-item">
          <button type="button" class="btn btn-link btn-sm" onclick="DocViewer.open('${path}', '${name}')">${name}</button>
          <button type="button" class="btn btn-icon btn-danger btn-sm" title="刪除附件" onclick="IpPeriod.deleteIpCertAttachment()">🗑️</button>
        </div>`;
      if (hint) hint.textContent = '已上傳 IP Cert.';
    } else {
      el.innerHTML = '';
      if (hint) hint.textContent = 'PDF / PNG / JPG · 新增記錄需先儲存再上傳';
    }
  },

  pickIpCertFile() {
    document.getElementById('ipCertFileInput')?.click();
  },

  onIpCertFileSelected(event) {
    const file = event.target?.files?.[0];
    if (!file) return;
    const id = document.getElementById('ipModalId').value;
    if (id) {
      this._uploadIpCertFile(id, file);
    } else {
      this._pendingIpCertFile = file;
      this._renderIpCertAttach({});
    }
    if (event.target) event.target.value = '';
  },

  async _uploadIpCertFile(ipId, file) {
    showLoading('上傳 IP Cert.…');
    try {
      const fd = new FormData();
      fd.append('file', file);
      const res = await fetch(`${API}/interim-payments/${ipId}/ip-cert-attachment`, { method: 'POST', body: fd });
      const json = await res.json();
      if (!json.success) throw new Error(json.error || '上傳失敗');
      toast('IP Cert. 已上傳', 'success');
      this._pendingIpCertFile = null;
      if (json.data?.summary) {
        this._data = json.data.summary;
        if (this._containerId) this.render(this._containerId, this._data, { editable: this._editable });
      }
      const row = await api('GET', `/interim-payments/${ipId}`);
      if (row) this._renderIpCertAttach(row);
    } catch (e) {
      toast(e.message || '上傳失敗', 'error');
    } finally {
      hideLoading();
    }
  },

  async deleteIpCertAttachment() {
    const id = document.getElementById('ipModalId').value;
    if (!id) return;
    if (!confirm('刪除此 IP Cert. 附件？')) return;
    try {
      await api('DELETE', `/interim-payments/${id}/ip-cert-attachment`);
      toast('IP Cert. 已刪除', 'success');
      const row = await api('GET', `/interim-payments/${id}`);
      if (row) this._renderIpCertAttach(row);
      await this.refresh();
    } catch (e) {}
  },

  _readReceiptFormData() {
    this.syncAllReceiptRowsFromDom();
    const records = this._receiptRows.map((row) => {
      const method = row.method || null;
      return {
        method,
        cheque_no: method === 'cheque' ? (row.cheque_no?.trim() || null) : null,
        bank: method === 'cheque' ? (row.bank?.trim() || null) : null,
        date: row.date || null,
        note: method === 'transfer' ? (row.note?.trim() || null) : null,
        attachment: row.attachment || null,
        attachment_name: row.attachment_name || null,
      };
    }).filter(r => r.method || r.cheque_no || r.bank || r.date || r.note || r.attachment);
    const first = records[0] || {};
    return {
      receipt_records: records,
      receipt_method: first.method || null,
      receipt_cheque_no: first.cheque_no || null,
      receipt_bank: first.bank || null,
      receipt_date: first.date || null,
      receipt_note: first.note || null,
    };
  },

  async openEdit(id) {
    const row = await api('GET', `/interim-payments/${id}`);
    if (!row) return;
    this._pendingIpCertFile = null;
    this._pendingIpAppFile = null;
    document.getElementById('ipModalTitle').textContent = `編輯 ${row.ip_no}`;
    document.getElementById('ipModalId').value = row.id;
    document.getElementById('ipNo').value = row.ip_no || '';
    document.getElementById('ipSeqNo').value = row.seq_no || '';
    document.getElementById('ipAppliedDate').value = row.applied_date || '';
    document.getElementById('ipAppAmt').value = fmtInputNum(row.application_amount);
    document.getElementById('ipCertAmt').value = fmtInputNum(row.certified_income);
    document.getElementById('ipCertDate').value = row.certificate_date || '';
    document.getElementById('ipSubconPaid').value = fmtInputNum(row.subcon_paid);
    document.getElementById('ipSubconCertDate').value = row.subcon_cert_date || '';
    this._fillReceiptForm(row);
    this._renderIpAppAttach(row);
    this._renderIpCertAttach(row);
    const pctParts = [];
    if (row.certified_income_pct != null) pctParts.push(`批款 ${fmtPct(row.certified_income_pct)}`);
    document.getElementById('ipPctHint').textContent = pctParts.length
      ? `目前累計：${pctParts.join(' · ')}（儲存後重算）` : '';
    document.getElementById('ipModal').classList.add('open');
    AmountInput.init(document.getElementById('ipModal'));
  },

  closeModal() {
    this.closeBankDropdown();
    document.getElementById('ipModal').classList.remove('open');
  },

  openMetaEdit() {
    const p = App.currentProject;
    if (!p) { toast('請先選擇項目', 'warning'); return; }
    const ip = this._data || {};
    const t = ip.totals || {};
    document.getElementById('ipMetaPeriod').value = ip.site_period_text || p.site_period_text || '';
    document.getElementById('ipMetaIncome').value = fmtInputNum(t.total_income);
    document.getElementById('ipMetaExpenditure').value = fmtInputNum(Math.abs(parseFloat(t.total_expenditure) || 0));
    document.getElementById('ipMetaAdvance').value = fmtInputNum(t.advance);
    document.getElementById('ipMetaModal').classList.add('open');
    AmountInput.init(document.getElementById('ipMetaModal'));
  },

  closeMetaModal() {
    document.getElementById('ipMetaModal').classList.remove('open');
  },

  async saveModal() {
    const p = App.currentProject;
    if (!p) { toast('請先選擇項目', 'warning'); return; }
    const id = document.getElementById('ipModalId').value;
    const ipNo = document.getElementById('ipNo').value.trim();
    if (!ipNo) { toast('請輸入糧款期數', 'warning'); return; }

    const data = {
      project_id: p.id,
      ip_no: ipNo.toUpperCase(),
      seq_no: parseInt(document.getElementById('ipSeqNo').value, 10) || 0,
      applied_date: document.getElementById('ipAppliedDate').value || null,
      application_amount: parseAmtOrZero(document.getElementById('ipAppAmt').value),
      certified_income: parseAmtOrZero(document.getElementById('ipCertAmt').value),
      certificate_date: document.getElementById('ipCertDate').value || null,
      subcon_paid: parseAmtOrZero(document.getElementById('ipSubconPaid').value),
      subcon_cert_date: document.getElementById('ipSubconCertDate').value || null,
      ...this._readReceiptFormData(),
    };

    try {
      let newId = id;
      if (id) {
        await api('PUT', `/interim-payments/${id}`, data);
        toast('糧期已更新', 'success');
      } else {
        const res = await api('POST', '/interim-payments', data);
        newId = res?.id;
        toast('糧期已新增', 'success');
      }
      if (newId) {
        for (let i = 0; i < this._receiptRows.length; i += 1) {
          const pf = this._receiptRows[i]?.pendingFile;
          if (pf) await this._uploadReceiptFile(newId, pf, i);
        }
      }
      if (this._pendingIpCertFile && newId) {
        await this._uploadIpCertFile(newId, this._pendingIpCertFile);
      }
      if (this._pendingIpAppFile && newId) {
        await this._uploadIpAppFile(newId, this._pendingIpAppFile);
      }
      this.closeModal();
      await this.refresh();
    } catch (e) {}
  },

  async saveMetaModal() {
    const p = App.currentProject;
    if (!p) { toast('請先選擇項目', 'warning'); return; }
    const data = {
      site_period_text: document.getElementById('ipMetaPeriod').value.trim() || null,
      ip_total_income: parseAmtOrZero(document.getElementById('ipMetaIncome').value),
      ip_total_expenditure: parseAmtOrZero(document.getElementById('ipMetaExpenditure').value),
      ip_advance: parseAmtOrZero(document.getElementById('ipMetaAdvance').value),
    };
    try {
      await api('PUT', `/projects/${p.id}/interim-payments/meta`, data);
      toast('匯總已更新', 'success');
      this.closeMetaModal();
      await this.refresh();
    } catch (e) {}
  },

  async delete(id, ipNo) {
    if (!confirm(`確認刪除糧期「${ipNo}」？`)) return;
    try {
      await api('DELETE', `/interim-payments/${id}`);
      toast('已刪除', 'success');
      await this.refresh();
    } catch (e) {}
  },

  async load(switchSeq) {
    const p = App.currentProject;
    const noProj = document.getElementById('ipPeriodNoProject');
    const content = document.getElementById('ipPeriodContent');
    if (!p) {
      if (noProj) noProj.style.display = '';
      if (content) content.style.display = 'none';
      return;
    }
    const projectId = p.id;
    if (noProj) noProj.style.display = 'none';
    if (content) content.style.display = '';

    this._containerId = 'ipPeriodMain';
    this._editable = true;
    this._searchQuery = '';
    this._reconcileData = null;
    const searchEl = document.getElementById('ipPeriodSearch');
    if (searchEl) searchEl.value = '';
    const summary = await api('GET', `/reports/summary/${projectId}`);
    if (!summary || !App.currentProject || App.currentProject.id != projectId) return;
    if (switchSeq != null && switchSeq !== App._projectSwitchSeq) return;
    const proj = summary.project || p;
    this._data = this._mergeIpProject(summary.ip_period || this._ipFallbackData(proj), proj);
    this.render('ipPeriodMain', this._data, { editable: true, project: proj });
    this.renderScMatrix('ipPeriodScMatrix', this._data.sc_matrix, { hasMainIp: this._data?.items?.length > 0 });
    await this.loadReconcile(projectId);
  },

  async loadReconcile(projectId) {
    const el = document.getElementById('ipReconcilePanel');
    if (!el) return;
    try {
      const data = await api('GET', `/projects/${projectId}/ip-reconciliation`, null, { silent: true });
      if (!App.currentProject || App.currentProject.id != projectId) return;
      this._reconcileData = data;
      IpReconcile.render(el, data, { search: this._searchQuery });
    } catch (e) {
      if (!App.currentProject || App.currentProject.id != projectId) return;
      const hint = (e?.message || '').includes('404')
        ? '後端尚未更新糧期核對 API，請重啟 python app.py 後 Ctrl+F5 刷新。'
        : '無法載入糧期核對（請確認 Master List 已配對項目）。';
      el.innerHTML = `<p class="form-hint" style="padding:12px">${escHtml(hint)}</p>`;
    }
  },

  async refresh() {
    const p = App.currentProject;
    if (!p) return;
    const summary = await api('GET', `/reports/summary/${p.id}`);
    if (!summary) return;
    const proj = summary.project || p;
    this._data = this._mergeIpProject(summary.ip_period || this._ipFallbackData(proj), proj);
    if (this._containerId) {
      this.render(this._containerId, this._data, { editable: this._editable, project: proj });
    }
    this.renderScMatrix('ipPeriodScMatrix', this._data.sc_matrix, { hasMainIp: this._data?.items?.length > 0 });
    // 同步項目概覽唯讀顯示
    if (typeof updateDashIpTotals === 'function') {
      updateDashIpTotals(this._data);
      updateDashProjectHero(summary.project || p, this._data);
    }
    renderSiteIpPeriod(this._data, 'dashSiteIp', { editable: false, hideProjectMeta: true, project: summary.project || p });
    if (typeof Reports !== 'undefined' && Reports.data) {
      Reports.data.ip_period = this._data;
      renderSiteIpPeriod(this._data, 'rptSiteIp', { editable: false, hideProjectMeta: true, project: summary.project || p });
    }
    await this.loadReconcile(p.id);
  },
};

function renderSiteIpPeriod(ip, containerId, options = {}) {
  const editable = options.editable === true;
  IpPeriod.render(containerId, ip, { ...options, editable });
}
