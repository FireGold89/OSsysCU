/* ip_reconcile.js — 地盤糧期 ↔ 行政業主糧期 對照（共用渲染） */
const IpReconcile = {
  _statusBadge(status) {
    const map = {
      matched: ['success', '✓'],
      matched_open: ['info', '✓ 待收票'],
      amount_diff: ['danger', '金額差'],
      admin_only: ['warning', '僅行政'],
      site_only: ['warning', '僅地盤'],
    };
    const [cls, label] = map[status] || ['muted', '—'];
    return `<span class="badge badge-${cls}">${label}</span>`;
  },

  _fmtDate(iso, fallback) {
    if (fallback && /\d{1,2}\/\d{1,2}\/\d{2,4}/.test(String(fallback))) {
      const m = String(fallback).match(/(\d{1,2}\/\d{1,2}\/\d{2,4})/);
      if (m) return m[1];
    }
    return fmtDate(iso);
  },

  summaryText(st) {
    if (!st || !st.site_count && !st.admin_count) return '';
    const parts = [];
    if (st.matched) parts.push(`${st.matched} 期一致`);
    if (st.amount_diff) parts.push(`${st.amount_diff} 期金額差`);
    if (st.admin_only) parts.push(`${st.admin_only} 期僅行政`);
    if (st.site_only) parts.push(`${st.site_only} 期僅地盤`);
    return parts.join(' · ') || '—';
  },

  render(el, data) {
    const target = typeof el === 'string' ? document.getElementById(el) : el;
    if (!target) return;

    if (!data || !data.linked) {
      target.innerHTML = `<p class="form-hint" style="padding:12px">${
        escHtml(data?.message || '請先將 Master List 與工程項目配對，方可對照糧期。')
      }</p>`;
      return;
    }

    const rows = data.rows || [];
    if (!rows.length) {
      target.innerHTML = '<p class="form-hint" style="padding:12px">兩邊均無糧期資料。地盤請 sync Payment Status；行政請 sync Master List。</p>';
      return;
    }

    const st = data.stats || {};
    const head = `
      <p class="form-hint ip-reconcile-hint">
        地盤 ${st.site_count || 0} 期 · 行政 ${st.admin_count || 0} 期 · ${this.summaryText(st)}
        <span class="ip-reconcile-note">（各自更新，只對照不覆寫）</span>
      </p>`;

    const body = rows.map(r => {
      const site = r.site || {};
      const admin = r.admin || {};
      return `<tr>
        <td class="td-mono">${r.ip_label || '—'}</td>
        <td>${this._statusBadge(r.status)}<div class="ip-reconcile-status-sub">${escHtml(r.status_label || '')}</div></td>
        <td class="td-muted">${site.ip_no || '—'}</td>
        <td class="td-muted">${fmtDate(site.applied_date)}</td>
        <td class="td-muted">${fmtDate(site.certificate_date)}</td>
        <td class="td-amount">${site.amount_display || (site.certified_income != null ? fmt(site.certified_income) : '—')}</td>
        <td class="td-muted">${admin.ip_no || '—'}</td>
        <td class="td-muted">${this._fmtDate(admin.invoice_date, admin.invoice_date_display)}</td>
        <td class="td-muted">${this._fmtDate(admin.receipt_date, admin.receipt_date_display)}</td>
        <td class="td-amount">${admin.amount_display || (admin.invoice_amount != null ? fmt(admin.invoice_amount) : '—')}</td>
      </tr>`;
    }).join('');

    target.innerHTML = `${head}
      <div class="table-wrap ip-reconcile-wrap">
        <table class="master-preview-table ip-reconcile-table">
          <thead>
            <tr>
              <th rowspan="2">期數</th>
              <th rowspan="2">狀態</th>
              <th colspan="4" class="ip-reconcile-th-site">地盤 QS（申請／批款）</th>
              <th colspan="4" class="ip-reconcile-th-admin">行政 Admin（開票／收票）</th>
            </tr>
            <tr>
              <th>糧期</th><th>申請日</th><th>批款日</th><th>則師批款</th>
              <th>糧期</th><th>出發票</th><th>收票</th><th>發票金額</th>
            </tr>
          </thead>
          <tbody>${body}</tbody>
        </table>
      </div>`;
  },
};
