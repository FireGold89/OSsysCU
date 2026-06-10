/* ─── ip_period.js — 地盤糧期狀況編輯 ─────────────────────── */
const IpPeriod = {
  _containerId: null,
  _data: null,
  _editable: false,

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
          <td class="td-muted">${fmtDate(r.subcon_cert_date)}</td>
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
              <th class="th-num">分包支出</th>
              <th>分包批款日</th>
              ${actionTh}
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>${totalsHtml}`;
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

  async load() {
    const p = App.currentProject;
    const noProj = document.getElementById('ipPeriodNoProject');
    const content = document.getElementById('ipPeriodContent');
    if (!p) {
      if (noProj) noProj.style.display = '';
      if (content) content.style.display = 'none';
      return;
    }
    if (noProj) noProj.style.display = 'none';
    if (content) content.style.display = '';

    this._containerId = 'ipPeriodMain';
    this._editable = true;
    const summary = await api('GET', `/reports/summary/${p.id}`);
    if (!summary) return;
    this._data = summary.ip_period || {
      site_period_text: p.site_period_text,
      items: [],
      totals: { total_income: 0, total_expenditure: 0, advance: 0 },
    };
    this.render('ipPeriodMain', this._data, { editable: true });
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
  },
};

function renderSiteIpPeriod(ip, containerId, options = {}) {
  const editable = options.editable === true;
  IpPeriod.render(containerId, ip, { ...options, editable });
}
