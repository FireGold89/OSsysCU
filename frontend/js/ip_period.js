/* ─── ip_period.js — 地盤糧期狀況編輯 ─────────────────────── */
const IpPeriod = {
  _containerId: null,
  _data: null,
  _editable: false,
  _matrixView: 'by-ip',
  _pendingReceiptFile: null,
  _pendingIpCertFile: null,
  _searchQuery: '',
  _reconcileData: null,
  _bankSelectReady: false,

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

  _receiptCellHtml(r) {
    const display = r.receipt_display;
    const attach = r.receipt_attachment;
    const attachName = escHtml(r.receipt_attachment_name || '支票附件');
    const safePath = (attach || '').replace(/'/g, "\\'");
    const clipIcon = attach
      ? `<button type="button" class="ip-receipt-clip" title="已上傳支票附件：${attachName}"
          onclick="event.stopPropagation(); DocViewer.open('${safePath}', '${attachName}')"
          aria-label="預覽支票附件">📎</button>`
      : '';
    const text = display
      ? `<span class="ip-receipt-text" title="${escHtml(this._receiptTooltip(r))}">${escHtml(display)}</span>`
      : (attach ? '' : '<span class="td-muted">—</span>');
    return `<td class="ip-receipt-cell" onclick="event.stopPropagation()">
      <div class="ip-receipt-cell-inner">${text}${clipIcon}</div>
    </td>`;
  },

  _receiptTooltip(row) {
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
      row.receipt_method,
      row.receipt_cheque_no,
      row.receipt_bank,
      row.receipt_note,
      row.receipt_display,
      row.receipt_attachment_name,
      row.ip_cert_attachment_name,
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

  _ipCertCellHtml(r) {
    const attach = r.ip_cert_attachment;
    const attachName = escHtml(r.ip_cert_attachment_name || 'IP Cert.');
    const safePath = (attach || '').replace(/'/g, "\\'");
    if (attach) {
      return `<td class="ip-cert-cell" onclick="event.stopPropagation()">
        <button type="button" class="ip-receipt-clip" title="已上傳 IP Cert.：${attachName}"
          onclick="event.stopPropagation(); DocViewer.open('${safePath}', '${attachName}')"
          aria-label="預覽 IP Cert.">📄</button>
      </td>`;
    }
    return '<td class="ip-cert-cell td-muted" onclick="event.stopPropagation()">—</td>';
  },

  initBankSelect() {
    if (this._bankSelectReady) return;
    this._bankSelectReady = true;
    this.filterBankSelect('');
    if (!this._bankDropdownBound) {
      this._bankDropdownBound = true;
      document.addEventListener('click', (e) => {
        const combo = document.getElementById('ipReceiptBankCombo');
        if (combo && !combo.contains(e.target)) this.closeBankDropdown();
      });
    }
  },

  toggleBankDropdown(event) {
    event?.stopPropagation();
    const panel = document.getElementById('ipReceiptBankDropdown');
    const trigger = document.getElementById('ipReceiptBankTrigger');
    if (!panel) return;
    const open = panel.hidden;
    if (open) {
      this.initBankSelect();
      panel.hidden = false;
      document.getElementById('ipReceiptBankCombo')?.classList.add('is-open');
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
    } else {
      this.closeBankDropdown();
    }
  },

  _positionBankDropdown() {
    const trigger = document.getElementById('ipReceiptBankTrigger');
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
    const trigger = document.getElementById('ipReceiptBankTrigger');
    if (panel) panel.hidden = true;
    this._unbindBankDropdownReposition();
    document.getElementById('ipReceiptBankCombo')?.classList.remove('is-open');
    document.querySelector('#ipModal .modal-body')?.classList.remove('ip-bank-dropdown-open');
    if (trigger) trigger.setAttribute('aria-expanded', 'false');
  },

  selectBank(code) {
    const customEl = document.getElementById('ipReceiptBankCustom');
    if (customEl) customEl.value = '';
    this._setBankSelectValue(code || '');
    this.closeBankDropdown();
    this._updateReceiptPreview();
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

  _applyCustomBankCode(code) {
    const c = this._normalizeBankCode(code);
    const hidden = document.getElementById('ipReceiptBank');
    const labelEl = document.getElementById('ipReceiptBankLabel');
    if (hidden) hidden.value = c;
    if (labelEl) {
      labelEl.textContent = c ? `${c} — 自填銀行代碼` : '— 請選擇銀行 —';
    }
    this._updateBankHint(c);
  },

  onBankCustomInput() {
    const el = document.getElementById('ipReceiptBankCustom');
    if (!el) return;
    const digits = el.value.replace(/\D/g, '').slice(0, 3);
    if (el.value !== digits) el.value = digits;
    if (digits) {
      this._applyCustomBankCode(digits);
    } else if (!this._isMainstreamBankCode(document.getElementById('ipReceiptBank')?.value)) {
      this._setBankSelectValue('');
    }
    this._updateReceiptPreview();
  },

  filterBankSelect(presetQuery) {
    const qEl = document.getElementById('ipReceiptBankSearch');
    const q = (presetQuery != null ? presetQuery : (qEl?.value || '')).trim().toLowerCase();
    const list = document.getElementById('ipReceiptBankList');
    const hidden = document.getElementById('ipReceiptBank');
    if (!list || typeof HK_BANKS_MAINSTREAM === 'undefined') return;
    const current = hidden?.value || '';
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

  _setBankSelectValue(code, opts = {}) {
    const hidden = document.getElementById('ipReceiptBank');
    const labelEl = document.getElementById('ipReceiptBankLabel');
    const customEl = document.getElementById('ipReceiptBankCustom');
    if (!hidden) return;
    if (!code) {
      hidden.value = '';
      if (labelEl) labelEl.textContent = '— 請選擇銀行 —';
      if (!opts.skipHint) this._updateBankHint('');
      return;
    }
    const c = this._normalizeBankCode(code);
    hidden.value = c;
    if (customEl && !opts.keepCustom) customEl.value = '';
    if (labelEl) labelEl.textContent = this._bankLabelForCode(c);
    if (!opts.skipHint) this._updateBankHint(c);
  },

  _updateBankHint(code) {
    const hint = document.getElementById('ipReceiptBankHint');
    if (!hint) return;
    if (!code) {
      hint.textContent = '主流本地銀行，或自填 3 位代碼';
      return;
    }
    const name = typeof hkBankShortName === 'function' ? hkBankShortName(code) : '';
    hint.textContent = name ? `已選：${code} — ${name}` : `已選：${code}`;
  },

  _getSelectedBankCode() {
    const custom = document.getElementById('ipReceiptBankCustom')?.value?.trim();
    if (custom) return this._normalizeBankCode(custom);
    return document.getElementById('ipReceiptBank')?.value?.trim() || '';
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
          ${this._ipCertCellHtml(r)}
          <td class="td-muted ip-col-frozen-hidden">${fmtDate(r.applied_date)}</td>
          <td class="td-amount ip-col-frozen-hidden ${amtClass(r.application_amount)}">${fmt(r.application_amount)}</td>
          <td class="td-muted ip-col-frozen-hidden" style="text-align:right">${fmtPct(r.application_pct)}</td>
          <td class="td-amount ${amtClass(r.certified_income, 'income')}">${fmt(r.certified_income)}</td>
          <td class="td-muted" style="text-align:right">${fmtPct(r.certified_income_pct)}</td>
          <td class="td-muted">${fmtDate(r.certificate_date)}</td>
          ${this._receiptCellHtml(r)}
          <td class="td-amount ip-col-frozen-hidden ${amtClass(r.subcon_paid, 'expense')}">${r.subcon_paid ? fmtExpense(r.subcon_paid) : '—'}</td>
          <td class="td-muted ip-col-frozen-hidden" style="text-align:right">${fmtPct(r.subcon_paid_pct)}</td>
          ${actions}
        </tr>`;
    }).join('')
      : (applySearch
        ? `<tr><td colspan="${editable ? 12 : 11}" class="td-muted" style="padding:24px;text-align:center">無符合「${escHtml(this._searchQuery.trim())}」的糧期</td></tr>`
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
              <th style="width:52px">IP Cert.</th>
              <th class="ip-col-frozen-hidden">申請日期</th>
              <th class="th-num ip-col-frozen-hidden">申請金額</th>
              <th class="th-num ip-col-frozen-hidden">申請%</th>
              <th class="th-num">業主批款</th>
              <th class="th-num">批款%</th>
              <th>批款日期</th>
              <th>收款記錄<br><span class="th-sub">支票／過數</span></th>
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
    this._pendingReceiptFile = null;
    this._pendingIpCertFile = null;
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
    this._renderIpCertAttach({});
    document.getElementById('ipPctHint').textContent = '儲存後依承建金額自動計算批款 %';
    document.getElementById('ipModal').classList.add('open');
  },

  _fillReceiptForm(row) {
    document.getElementById('ipReceiptMethod').value = row.receipt_method || '';
    document.getElementById('ipReceiptChequeNo').value = row.receipt_cheque_no || '';
    const bankSearch = document.getElementById('ipReceiptBankSearch');
    if (bankSearch) bankSearch.value = '';
    const customEl = document.getElementById('ipReceiptBankCustom');
    if (customEl) customEl.value = '';
    this.initBankSelect();
    const bankCode = row.receipt_bank || '';
    if (bankCode && !this._isMainstreamBankCode(bankCode)) {
      this._setBankSelectValue('', { skipHint: true });
      if (customEl) customEl.value = bankCode.replace(/^0+/, '') || bankCode;
      this._applyCustomBankCode(bankCode);
    } else {
      this._setBankSelectValue(bankCode);
    }
    document.getElementById('ipReceiptDate').value = row.receipt_date || '';
    document.getElementById('ipReceiptNote').value = row.receipt_note || '';
    this.onReceiptMethodChange();
    this._renderReceiptAttach(row);
    this._updateReceiptPreview();
  },

  onReceiptMethodChange() {
    const method = document.getElementById('ipReceiptMethod').value;
    document.getElementById('ipReceiptChequeFields').style.display = method === 'cheque' ? '' : 'none';
    document.getElementById('ipReceiptTransferFields').style.display = method === 'transfer' ? '' : 'none';
    this._updateReceiptPreview();
  },

  _updateReceiptPreview() {
    const el = document.getElementById('ipReceiptPreview');
    if (!el) return;
    const preview = this._formatReceiptPreview(
      document.getElementById('ipReceiptMethod').value,
      document.getElementById('ipReceiptChequeNo').value,
      this._getSelectedBankCode(),
      document.getElementById('ipReceiptDate').value,
      document.getElementById('ipReceiptNote').value,
    );
    const bankCode = this._getSelectedBankCode();
    const bankName = bankCode && typeof hkBankShortName === 'function' ? hkBankShortName(bankCode) : '';
    el.textContent = preview
      ? `預覽：${preview}${bankName ? `（${bankName}）` : ''}`
      : '';
    this._updateBankHint(bankCode);
  },

  _renderReceiptAttach(row) {
    const el = document.getElementById('ipReceiptAttachList');
    const hint = document.getElementById('ipReceiptAttachHint');
    if (!el) return;
    const pending = this._pendingReceiptFile;
    if (pending) {
      el.innerHTML = `<div class="ip-receipt-attach-item"><span>待上傳：${escHtml(pending.name)}</span></div>`;
      if (hint) hint.textContent = '儲存後會一併上傳';
      return;
    }
    if (row.receipt_attachment) {
      const name = escHtml(row.receipt_attachment_name || '支票附件');
      const path = (row.receipt_attachment || '').replace(/"/g, '&quot;');
      el.innerHTML = `
        <div class="ip-receipt-attach-item">
          <button type="button" class="btn btn-link btn-sm" onclick="DocViewer.open('${path}', '${name}')">${name}</button>
          <button type="button" class="btn btn-icon btn-danger btn-sm" title="刪除附件" onclick="IpPeriod.deleteReceiptAttachment()">🗑️</button>
        </div>`;
      if (hint) hint.textContent = '已上傳附件';
    } else {
      el.innerHTML = '';
      if (hint) hint.textContent = 'PDF / PNG / JPG · 新增記錄需先儲存再上傳';
    }
  },

  pickReceiptFile() {
    document.getElementById('ipReceiptFileInput')?.click();
  },

  onReceiptFileSelected(event) {
    const file = event.target?.files?.[0];
    if (!file) return;
    const id = document.getElementById('ipModalId').value;
    if (id) {
      this._uploadReceiptFile(id, file);
    } else {
      this._pendingReceiptFile = file;
      this._renderReceiptAttach({});
    }
    if (event.target) event.target.value = '';
  },

  async _uploadReceiptFile(ipId, file) {
    showLoading('上傳附件…');
    try {
      const fd = new FormData();
      fd.append('file', file);
      const res = await fetch(`${API}/interim-payments/${ipId}/receipt-attachment`, { method: 'POST', body: fd });
      const json = await res.json();
      if (!json.success) throw new Error(json.error || '上傳失敗');
      toast('支票附件已上傳', 'success');
      this._pendingReceiptFile = null;
      if (json.data?.summary) {
        this._data = json.data.summary;
        if (this._containerId) this.render(this._containerId, this._data, { editable: this._editable });
      }
      const row = await api('GET', `/interim-payments/${ipId}`);
      if (row) this._renderReceiptAttach(row);
    } catch (e) {
      toast(e.message || '上傳失敗', 'error');
    } finally {
      hideLoading();
    }
  },

  async deleteReceiptAttachment() {
    const id = document.getElementById('ipModalId').value;
    if (!id) return;
    if (!confirm('刪除此支票附件？')) return;
    try {
      await api('DELETE', `/interim-payments/${id}/receipt-attachment`);
      toast('附件已刪除', 'success');
      const row = await api('GET', `/interim-payments/${id}`);
      if (row) this._renderReceiptAttach(row);
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
    const method = document.getElementById('ipReceiptMethod').value || null;
    return {
      receipt_method: method,
      receipt_cheque_no: method === 'cheque'
        ? (document.getElementById('ipReceiptChequeNo').value.trim() || null)
        : null,
      receipt_bank: method === 'cheque'
        ? (this._getSelectedBankCode() || null)
        : null,
      receipt_date: document.getElementById('ipReceiptDate').value || null,
      receipt_note: method === 'transfer'
        ? (document.getElementById('ipReceiptNote').value.trim() || null)
        : null,
    };
  },

  async openEdit(id) {
    const row = await api('GET', `/interim-payments/${id}`);
    if (!row) return;
    this._pendingReceiptFile = null;
    this._pendingIpCertFile = null;
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
    this._renderIpCertAttach(row);
    const pctParts = [];
    if (row.certified_income_pct != null) pctParts.push(`批款 ${fmtPct(row.certified_income_pct)}`);
    document.getElementById('ipPctHint').textContent = pctParts.length
      ? `目前累計：${pctParts.join(' · ')}（儲存後重算）` : '';
    document.getElementById('ipModal').classList.add('open');
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
      application_amount: parseFloat(document.getElementById('ipAppAmt').value) || 0,
      certified_income: parseFloat(document.getElementById('ipCertAmt').value) || 0,
      certificate_date: document.getElementById('ipCertDate').value || null,
      subcon_paid: parseFloat(document.getElementById('ipSubconPaid').value) || 0,
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
      if (this._pendingReceiptFile && newId) {
        await this._uploadReceiptFile(newId, this._pendingReceiptFile);
      }
      if (this._pendingIpCertFile && newId) {
        await this._uploadIpCertFile(newId, this._pendingIpCertFile);
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
      ip_total_income: parseFloat(document.getElementById('ipMetaIncome').value) || 0,
      ip_total_expenditure: parseFloat(document.getElementById('ipMetaExpenditure').value) || 0,
      ip_advance: parseFloat(document.getElementById('ipMetaAdvance').value) || 0,
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
