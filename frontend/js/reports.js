/* ─── reports.js — 財務報表 ───────────────────────────── */
const Reports = {
  data: null,

  async load() {
    const p = App.currentProject;
    if (!p) {
      document.getElementById('rptTableBody').innerHTML = `<tr><td colspan="8"><div class="empty-state" style="padding:40px">請先選擇項目</div></td></tr>`;
      return;
    }

    this.data = await api('GET', `/reports/summary/${p.id}`);
    if (!this.data) return;

    // 統計卡片
    document.getElementById('rptScCount').textContent = this.data.sc_stats?.length || 0;
    document.getElementById('rptTotalPaid').textContent = fmt(this.data.total_paid);
    document.getElementById('rptRemainder').textContent = fmt(this.data.total_remainder);

    renderContractCalc(this.data.contract_calc, 'rptContractCalc');
    renderSiteIpPeriod(this.data.ip_period, 'rptSiteIp', { editable: false });

    // 表格
    const tbody = document.getElementById('rptTableBody');
    const stats = this.data.sc_stats || [];
    if (stats.length === 0) {
      tbody.innerHTML = `<tr><td colspan="8"><div class="empty-state" style="padding:48px">暫無數據</div></td></tr>`;
      return;
    }

    tbody.innerHTML = stats.map(s => {
      const ca = parseFloat(s.contract_amount) || 0;
      const paid = parseFloat(s.total_paid) || 0;
      const rem = ca - paid;
      const progress = ca > 0 ? Math.min(100, (paid / ca * 100)).toFixed(FMT_DECIMALS) : '0.00';
      const remClass = rem > 0 ? 'negative' : rem < 0 ? '' : '';

      return `
        <tr>
          <td>${fmtRefNo(s.sc_no)}</td>
          <td>
            <div style="font-weight:600">${s.company_name_en || '—'}</div>
            <div style="font-size:11px;color:var(--text-muted)">${s.description || ''}</div>
          </td>
          <td class="td-muted" style="max-width:150px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${s.description || '—'}</td>
          <td class="td-amount">${fmt(s.contract_amount)}</td>
          <td class="td-amount positive">${fmt(s.total_paid)}</td>
          <td class="td-amount ${remClass}">${fmt(rem)}</td>
          <td class="td-muted" style="text-align:center">${s.payment_count || 0}</td>
          <td style="min-width:100px">
            <div style="display:flex;align-items:center;gap:8px">
              <div class="progress-bar-wrap" style="flex:1">
                <div class="progress-bar" style="width:${progress}%;background:${progress >= 100 ? '#10b981' : progress >= 50 ? '#3b82f6' : '#f59e0b'}"></div>
              </div>
              <span style="font-size:11px;color:var(--text-muted);width:30px">${progress}%</span>
            </div>
          </td>
        </tr>
      `;
    }).join('');

    // 匯總行
    tbody.innerHTML += `
      <tr style="background:var(--bg-hover);font-weight:700;border-top:2px solid var(--border)">
        <td colspan="3" style="text-align:right;color:var(--text-secondary);font-size:12px">合計</td>
        <td class="td-amount">
          ${fmt(stats.reduce((s, r) => s + (parseFloat(r.contract_amount) || 0), 0))}
        </td>
        <td class="td-amount positive">
          ${fmt(this.data.total_paid)}
        </td>
        <td class="td-amount negative">
          ${fmt(this.data.total_remainder)}
        </td>
        <td class="td-muted" style="text-align:center">
          ${stats.reduce((s, r) => s + (r.payment_count || 0), 0)}
        </td>
        <td></td>
      </tr>
    `;
  },

  exportCsv() {
    if (!this.data?.sc_stats) { toast('暫無數據', 'warning'); return; }
    const headers = ['判項編號','公司名稱','工程描述','判項金額(J)','累計已付','未付餘額','付款次數','進度%'];
    const rows = this.data.sc_stats.map(s => {
      const ca = parseFloat(s.contract_amount) || 0;
      const paid = parseFloat(s.total_paid) || 0;
      const rem = ca - paid;
      const progress = ca > 0 ? Math.min(100, (paid / ca * 100)).toFixed(FMT_DECIMALS) : '0.00';
      return [s.sc_no, s.company_name_en, s.description,
        fmtNumPlain(ca), fmtNumPlain(paid), fmtNumPlain(rem), s.payment_count, progress];
    });
    // 加合計行
    rows.push(['合計', '', '',
      fmtNumPlain(this.data.sc_stats.reduce((s, r) => s + (parseFloat(r.contract_amount) || 0), 0)),
      fmtNumPlain(this.data.total_paid), fmtNumPlain(this.data.total_remainder),
      this.data.sc_stats.reduce((s, r) => s + (r.payment_count || 0), 0), ''
    ]);
    downloadCsv([headers, ...rows],
      `report_${App.currentProject?.project_code}_${new Date().toISOString().slice(0,10)}.csv`);
  },

  async exportBossPdf() {
    const p = App.currentProject;
    if (!p) { toast('請先選擇項目', 'warning'); return; }
    const btn = document.getElementById('btnBossPdf');
    if (btn) btn.disabled = true;
    showLoading('正在生成 QS 匯報表 PDF…');
    try {
      const r = await fetch(`${API}/reports/boss-pdf/${p.id}`);
      const ct = r.headers.get('Content-Type') || '';
      if (!r.ok) {
        let msg = `生成失敗（HTTP ${r.status}）`;
        if (r.status === 404) {
          msg = 'QS 匯報表功能尚未就緒，請稍後再試或聯絡管理員更新系統';
        } else if (ct.includes('application/json')) {
          try {
            const j = await r.json();
            if (j.error) msg = j.error;
          } catch (e) { /* ignore */ }
        }
        throw new Error(msg);
      }
      if (!ct.includes('application/pdf')) {
        throw new Error('伺服器回應格式錯誤，請重新整理後再試');
      }
      const blob = await r.blob();
      const cd = r.headers.get('Content-Disposition') || '';
      let filename = `QS匯報_${p.project_code}_${new Date().toISOString().slice(0, 10)}.pdf`;
      const m = cd.match(/filename\*?=(?:UTF-8''|")?([^";]+)/i);
      if (m) filename = decodeURIComponent(m[1].replace(/"/g, ''));
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      toast('QS 匯報表 PDF 已下載', 'success');
    } catch (e) {
      toast(e.message || 'PDF 生成失敗', 'error');
    } finally {
      hideLoading();
      if (btn) btn.disabled = false;
    }
  }
};
