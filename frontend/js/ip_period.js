/* ─── ip_period.js — 地盤糧期狀況編輯 ─────────────────────── */
const IpPeriod = {
  _containerId: null,
  _data: null,
  _editable: false,
  _matrixView: 'by-ip',

  render(containerId, ip, options = {}) {
    this._containerId = containerId;
    this._data = ip;
    this._editable = !!options.editable;
    const el = document.getElementById(containerId);
    if (!el) return;

    const editable = this._editable;
    const toolbar = editable ? `
      <div class="ip-period-toolbar">
        <button type="button" class="btn btn-secondary btn-sm" onclick="IpPeriod.openMetaEdit()">✏️ 編輯匯總</button>
        <button type="button" class="btn btn-primary btn-sm" onclick="IpPeriod.openAdd()">➕ 新增糧期</button>
      </div>` : '';

    if (!ip || !ip.items || !ip.items.length) {
      el.innerHTML = `${toolbar}
        <div class="empty-state" style="padding:24px">
          <div class="empty-icon">🏗️</div>
          <div class="empty-title">尚無糧期資料</div>
          <div class="empty-sub">${editable ? '可手動新增，或從 Excel Summary 工作表匯入' : '請從 Excel Summary 工作表匯入'}</div>
          ${editable ? '<br><button type="button" class="btn btn-primary btn-sm" onclick="IpPeriod.openAdd()">➕ 新增第一期糧款</button>' : ''}
        </div>`;
      this.renderScMatrix('ipPeriodScMatrix', ip?.sc_matrix, { hasMainIp: false });
      return;
    }

    const t = ip.totals || {};
    const period = ip.site_period_text
      ? `<span class="badge badge-muted" style="margin-left:8px">工期 ${ip.site_period_text}</span>` : '';
    const hideTotals = options.hideTotals || false;
    const advClass = parseFloat(t.advance) < 0 ? 'negative' : '';
    const actionTh = editable ? '<th style="width:72px">操作</th>' : '';

    const rows = ip.items.map(r => {
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
          <td class="td-muted">${fmtDate(r.applied_date)}</td>
          <td class="td-amount">${fmt(r.application_amount)}</td>
          <td class="td-muted" style="text-align:right">${fmtPct(r.application_pct)}</td>
          <td class="td-amount positive">${fmt(r.certified_income)}</td>
          <td class="td-muted" style="text-align:right">${fmtPct(r.certified_income_pct)}</td>
          <td class="td-muted">${fmtDate(r.certificate_date)}</td>
          <td class="td-amount">${r.subcon_paid ? fmt(r.subcon_paid) : '—'}</td>
          <td class="td-muted" style="text-align:right">${fmtPct(r.subcon_paid_pct)}</td>
          ${actions}
        </tr>`;
    }).join('');

    const totalsHtml = hideTotals ? '' : `
      <div class="ip-period-totals${editable ? ' ip-period-totals-editable' : ''}">
        <div><span class="label">總收入</span><strong class="positive">${fmtAcct(t.total_income)}</strong></div>
        <div><span class="label">總支出</span><strong class="negative">${fmtIpExpenditure(t.total_expenditure)}</strong></div>
        <div><span class="label">墊支</span><strong class="${advClass}">${fmtAcct(t.advance)}</strong></div>
        ${editable ? '<button type="button" class="btn btn-icon btn-secondary btn-sm ip-totals-edit" title="編輯匯總" onclick="IpPeriod.openMetaEdit()">✏️</button>' : ''}
      </div>`;

    el.innerHTML = `
      ${toolbar}
      <div style="margin-bottom:12px;font-size:12px;color:var(--text-secondary)">
        主合約糧款追蹤（則師批款）${period}
        ${editable ? '<span style="margin-left:8px;color:var(--text-muted)">· 申請% / 批款% 依承建金額自動計算</span>' : ''}
      </div>
      <div class="ip-period-wrap">
        <table class="ip-period-table">
          <thead>
            <tr>
              <th>糧款期數</th>
              <th>申請日期</th>
              <th class="th-num">申請金額</th>
              <th class="th-num">申請%</th>
              <th class="th-num">則師批款</th>
              <th class="th-num">批款%</th>
              <th>批款日期</th>
              <th class="th-num">分包總支出</th>
              <th class="th-num">支出%</th>
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
    const m = matrix || { columns: [], rows: [] };
    if (!m.columns?.length) {
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
    const display = v ? fmt(v) : '—';
    const clickable = v ? ' ip-sc-cell-click' : '';
    const safeIp = (ipNo || '').replace(/'/g, '');
    const safeSc = (scNo || '').replace(/'/g, '');
    const onclick = v
      ? ` onclick="IpPeriod.openScDrilldown('${safeIp}','${safeSc}',${v})"`
      : '';
    return `<td class="td-amount${clickable}"${onclick} title="${v ? '點擊查看付款明細' : ''}">${display}</td>`;
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
      `<td class="td-amount">${colTotals[sc] ? fmt(colTotals[sc]) : '—'}</td>`).join('');
    const footContract = m.columns.map(sc => {
      const v = detailMap[sc]?.contract_amount;
      return `<td class="td-amount td-muted">${v ? fmt(v) : '—'}</td>`;
    }).join('');
    const footPaid = m.columns.map(sc => {
      const d = detailMap[sc] || {};
      const cls = d.matrix_match === false ? 'td-amount warn' : 'td-amount';
      return `<td class="${cls}">${d.total_paid_records ? fmt(d.total_paid_records) : '—'}</td>`;
    }).join('');
    const footRemain = m.columns.map(sc => {
      const v = detailMap[sc]?.remainder;
      if (v == null || v === '') return '<td class="td-amount">—</td>';
      const cls = v < 0 ? 'td-amount negative' : 'td-amount';
      return `<td class="${cls}">${fmt(v)}</td>`;
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
          <td class="td-amount" style="font-weight:600">${r.total ? fmt(r.total) : '—'}</td>
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
              <td class="td-amount" style="font-weight:600">${grandTotal ? fmt(grandTotal) : '—'}</td><td></td></tr>
            <tr class="ip-sc-matrix-foot ip-sc-matrix-meta"><td class="td-muted">判項金額</td>${footContract}
              <td class="td-amount td-muted">${sum.total_contract ? fmt(sum.total_contract) : '—'}</td><td></td></tr>
            <tr class="ip-sc-matrix-foot ip-sc-matrix-meta"><td class="td-muted">付款登記</td>${footPaid}
              <td class="td-amount">${sum.total_paid_records ? fmt(sum.total_paid_records) : '—'}</td><td></td></tr>
            <tr class="ip-sc-matrix-foot ip-sc-matrix-meta"><td class="td-muted">餘額</td>${footRemain}
              <td class="td-amount">${sum.total_contract != null ? fmt((sum.total_contract || 0) - (sum.total_paid_records || 0)) : '—'}</td><td></td></tr>
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
      const remCls = rem < 0 ? 'td-amount negative' : 'td-amount';
      const label = [
        `<div class="td-mono" style="font-weight:600">${escHtml(sc)}</div>`,
        d.trade_label ? `<div class="ip-sc-row-trade">${escHtml(d.trade_label)}</div>` : '',
        `<div class="ip-sc-row-co">${formatCompanyNameHtml(d.company_name_en, d.company_name_zh)}</div>`,
      ].join('');
      return `
        <tr>
          <td class="ip-sc-row-label">${label}</td>
          ${cells}
          <td class="td-amount" style="font-weight:600">${total ? fmt(total) : '—'}</td>
          <td class="td-amount td-muted">${d.contract_amount ? fmt(d.contract_amount) : '—'}</td>
          <td class="${remCls}">${rem != null ? fmt(rem) : '—'}</td>
        </tr>`;
    }).join('');

    const footIpTotals = ipCols.map(ip =>
      `<td class="td-amount">${ipColTotals[ip] ? fmt(ipColTotals[ip]) : '—'}</td>`).join('');
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
              <td class="td-amount" style="font-weight:600">${sum.total_paid_matrix ? fmt(sum.total_paid_matrix) : '—'}</td>
              <td class="td-amount td-muted">${sum.total_contract ? fmt(sum.total_contract) : '—'}</td>
              <td class="td-amount">${sum.total_contract != null ? fmt((sum.total_contract || 0) - (sum.total_paid_records || 0)) : '—'}</td>
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
          <td class="td-amount">${fmt(r.paid_amount)}</td>
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
    document.getElementById('ipPctHint').textContent = '儲存後依承建金額自動計算累計 %';
    document.getElementById('ipModal').classList.add('open');
  },

  async openEdit(id) {
    const row = await api('GET', `/interim-payments/${id}`);
    if (!row) return;
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
    const pctParts = [];
    if (row.application_pct != null) pctParts.push(`申請 ${fmtPct(row.application_pct)}`);
    if (row.certified_income_pct != null) pctParts.push(`批款 ${fmtPct(row.certified_income_pct)}`);
    document.getElementById('ipPctHint').textContent = pctParts.length
      ? `目前累計：${pctParts.join(' · ')}（儲存後重算）` : '';
    document.getElementById('ipModal').classList.add('open');
  },

  closeModal() {
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
    };

    try {
      if (id) {
        await api('PUT', `/interim-payments/${id}`, data);
        toast('糧期已更新', 'success');
      } else {
        await api('POST', '/interim-payments', data);
        toast('糧期已新增', 'success');
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
    const summary = await api('GET', `/reports/summary/${projectId}`);
    if (!summary || !App.currentProject || App.currentProject.id != projectId) return;
    if (switchSeq != null && switchSeq !== App._projectSwitchSeq) return;
    this._data = summary.ip_period || {
      site_period_text: p.site_period_text,
      items: [],
      totals: { total_income: 0, total_expenditure: 0, advance: 0 },
    };
    this.render('ipPeriodMain', this._data, { editable: true });
    this.renderScMatrix('ipPeriodScMatrix', this._data.sc_matrix, { hasMainIp: this._data?.items?.length > 0 });
    await this.loadReconcile(projectId);
  },

  async loadReconcile(projectId) {
    const el = document.getElementById('ipReconcilePanel');
    if (!el) return;
    try {
      const data = await api('GET', `/projects/${projectId}/ip-reconciliation`, null, { silent: true });
      if (!App.currentProject || App.currentProject.id != projectId) return;
      IpReconcile.render(el, data);
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
    this._data = summary.ip_period || {
      site_period_text: p.site_period_text,
      items: [],
      totals: { total_income: 0, total_expenditure: 0, advance: 0 },
    };
    if (this._containerId) {
      this.render(this._containerId, this._data, { editable: this._editable });
    }
    this.renderScMatrix('ipPeriodScMatrix', this._data.sc_matrix, { hasMainIp: this._data?.items?.length > 0 });
    // 同步儀表板唯讀顯示
    if (typeof updateDashIpTotals === 'function') {
      updateDashIpTotals(this._data);
      updateDashProjectHero(summary.project || p, this._data);
    }
    renderSiteIpPeriod(this._data, 'dashSiteIp', { editable: false });
    if (typeof Reports !== 'undefined' && Reports.data) {
      Reports.data.ip_period = this._data;
      renderSiteIpPeriod(this._data, 'rptSiteIp', { editable: false });
    }
    await this.loadReconcile(p.id);
  },
};

function renderSiteIpPeriod(ip, containerId, options = {}) {
  const editable = options.editable === true;
  IpPeriod.render(containerId, ip, { ...options, editable });
}
