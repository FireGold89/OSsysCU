/* ─── payments.js — 付款登記管理 ──────────────────────── */
const Payments = {
  data: [],
  filtered: [],
  sortKey: 'seq_no',
  sortDir: 'asc',

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
    this.filtered = [...this.data];
    this.applySort();
    this.render();
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
      case 'seq_no':
        return parseFloat(row.seq_no) || 0;
      case 'invoice_date':
        return row.invoice_date || '';
      case 'invoice_no':
        return (row.invoice_no || '').toLowerCase();
      case 'sc_no':
        return (row.sc_no || '').toLowerCase();
      case 'company':
        return ((row.company_name_en || row.company_name_zh || '')).toLowerCase();
      case 'description':
        return (row.description || '').toLowerCase();
      case 'contract_amount':
      case 'paid_amount':
      case 'remainder_amount':
        return parseFloat(row[key]) || 0;
      case 'oa_ref':
        return (row.oa_ref || '').toLowerCase();
      default:
        return '';
    }
  },

  _sortIsEmpty(row, key) {
    switch (key) {
      case 'company':
        return !row.company_name_en && !row.company_name_zh;
      case 'contract_amount':
      case 'paid_amount':
      case 'remainder_amount':
        return row[key] == null || row[key] === '';
      default:
        return !this._sortValue(row, key);
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
      const cmp = isNum ? (va - vb) : String(va).localeCompare(String(vb), 'zh-Hant');
      return cmp * dir;
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
    const tbody = document.getElementById('payTableBody');
    const count = document.getElementById('payCount');
    const totalPaidEl = document.getElementById('payTotalPaid');

    count.textContent = `${this.filtered.length} 條`;
    const totalPaid = this.filtered.reduce((s, r) => s + (parseFloat(r.paid_amount) || 0), 0);
    totalPaidEl.textContent = fmt(totalPaid);

    if (this.filtered.length === 0) {
      tbody.innerHTML = `<tr><td colspan="11"><div class="empty-state" style="padding:48px"><div class="empty-icon">💰</div><div class="empty-title">暫無付款登記</div><div class="empty-sub">點擊「新增記錄」或上傳PDF自動識別</div></div></td></tr>`;
      return;
    }

    tbody.innerHTML = this.filtered.map(r => {
      const remClass = parseFloat(r.remainder_amount) > 0 ? 'negative' : '';
      const paidClass = parseFloat(r.paid_amount) > 0 ? 'positive' : '';
      const oaBadge = r.oa_ref === 'OK' ? '<span class="badge badge-success">OK</span>' :
                      r.oa_ref === '-'  ? '<span class="badge badge-muted">—</span>' :
                      r.oa_ref          ? `<span class="badge badge-warning">${r.oa_ref}</span>` : '—';
      return `
        <tr onclick="Payments.openEdit(${r.id})">
          <td class="td-muted" style="font-size:11px">${r.seq_no || '—'}</td>
          <td class="td-muted">${fmtDate(r.invoice_date)}</td>
          <td class="td-mono td-muted" style="font-size:11px">${r.invoice_no || '—'}</td>
          <td>${fmtRefNo(r.sc_no)}</td>
          <td class="td-company-name">${paymentCompanyNameHtml(r)}</td>
          <td class="td-muted" style="max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${r.description || ''}">${r.description || '—'}</td>
          <td class="td-amount">${fmt(r.contract_amount)}</td>
          <td class="td-amount ${paidClass}">${fmt(r.paid_amount)}</td>
          <td class="td-amount ${remClass}">${fmt(r.remainder_amount)}</td>
          <td>${oaBadge}</td>
          <td onclick="event.stopPropagation()">
            <div style="display:flex;gap:4px">
              ${r.pdf_path ? `<button type="button" class="btn btn-icon btn-secondary btn-sm btn-view-pdf" title="查看原PDF" data-pdf-path="${String(r.pdf_path).replace(/"/g, '&quot;')}">📄</button>` : ''}
              <button class="btn btn-icon btn-secondary btn-sm" title="編輯" onclick="Payments.openEdit(${r.id})">✏️</button>
              <button class="btn btn-icon btn-danger btn-sm" title="刪除" onclick="Payments.delete(${r.id})">🗑️</button>
            </div>
          </td>
        </tr>
      `;
    }).join('');
    this.updateSortHeaders();
  },

  renderEmpty() {
    document.getElementById('payTableBody').innerHTML = `
      <tr><td colspan="11"><div class="empty-state" style="padding:48px">
        <div class="empty-icon">📁</div>
        <div class="empty-title">請先選擇項目</div>
      </div></td></tr>`;
    document.getElementById('payCount').textContent = '0 條';
    document.getElementById('payTotalPaid').textContent = 'HK$0';
  },

  search(val) {
    clearTimeout(this._searchTimer);
    this._searchTimer = setTimeout(() => this.load(), 400);
  },

  filterBySc(val) {
    this.load();
  },

  populateScFilter() {
    const sel = document.getElementById('payFilterSc');
    const cur = sel.value;
    sel.innerHTML = '<option value="">全部判項編號</option>';
    (App.scList || []).forEach(sc => {
      const opt = document.createElement('option');
      opt.value = sc.sc_no;
      opt.textContent = `${sc.sc_no} — ${sc.company_name_en || sc.company_name_zh || ''}`.substring(0, 40);
      sel.appendChild(opt);
    });
    const valid = cur && (App.scList || []).some(sc => sc.sc_no === cur);
    sel.value = valid ? cur : '';

    // 同步付款表單的SC選擇
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
      opt.textContent = `${sc.sc_no} — ${sc.company_name_en || sc.company_name_zh || ''}`.substring(0, 45);
      sel.appendChild(opt);
    });
    const valid = cur && (App.scList || []).some(sc => sc.sc_no === cur);
    if (valid) sel.value = cur;
  },

  onScChange(scNo) {
    const sc = App.scList.find(s => s.sc_no === scNo);
    if (sc) {
      document.getElementById('fCompanyEn').value = sc.company_name_en || '';
      document.getElementById('fCompanyZh').value = sc.company_name_zh || '';
      document.getElementById('fDesc').value = sc.description || '';
      document.getElementById('fContractAmt').value = sc.contract_amount || 0;
      this.calcRemainder();
    }
  },

  calcRemainder() {
    const ca = parseFloat(document.getElementById('fContractAmt').value) || 0;
    const pa = parseFloat(document.getElementById('fPaidAmt').value) || 0;
    document.getElementById('fRemAmt').value = fmtInputNum(ca - pa);
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

  openAdd() {
    document.getElementById('payModalTitle').textContent = '新增付款登記';
    document.getElementById('payModalId').value = '';
    this._setPdfUi(null);
    const fields = ['fInvDate','fInvNo','fQuotNo','fCompanyEn','fCompanyZh','fDesc','fOaRef','fOaNo','fMcIpNo','fBcToSub','fSubIpNo','fRemark'];
    fields.forEach(id => { const el = document.getElementById(id); if(el) el.value = ''; });
    const seqEl = document.getElementById('fSeqNo');
    if (seqEl) {
      seqEl.value = '';
      seqEl.placeholder = '自動編號';
      seqEl.readOnly = true;
    }
    ['fContractAmt','fPaidAmt','fRemAmt'].forEach(id => { const el = document.getElementById(id); if(el) el.value = ''; });
    document.getElementById('fScNo').value = '';
    this.populateScSelect();
    document.getElementById('payModal').classList.add('open');
  },

  async openEdit(id) {
    const r = await api('GET', `/payments/${id}`);
    if (!r) return;
    document.getElementById('payModalTitle').textContent = '編輯付款登記';
    document.getElementById('payModalId').value = r.id;
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
    document.getElementById('fMcIpNo').value = r.mc_ip_no || '';
    document.getElementById('fBcToSub').value = r.bc_to_sub || '';
    document.getElementById('fSubIpNo').value = r.sub_ip_no || '';
    document.getElementById('fRemark').value = r.remark || '';
    this._setPdfUi(r.pdf_path || null);
    document.getElementById('payModal').classList.add('open');
  },

  closeModal() {
    document.getElementById('payModal').classList.remove('open');
  },

  async saveModal() {
    const id = document.getElementById('payModalId').value;
    const scNo = document.getElementById('fScNo').value;
    const sc = App.scList.find(s => s.sc_no === scNo);
    const data = {
      project_id: App.currentProject?.id,
      sc_id: sc?.id || null,
      seq_no: document.getElementById('payModalId').value
        ? (document.getElementById('fSeqNo').value || null)
        : null,
      invoice_date: document.getElementById('fInvDate').value || null,
      invoice_no: document.getElementById('fInvNo').value || null,
      quotation_no: document.getElementById('fQuotNo').value || null,
      sc_no: scNo || null,
      company_name_en: document.getElementById('fCompanyEn').value || null,
      company_name_zh: document.getElementById('fCompanyZh').value || null,
      description: document.getElementById('fDesc').value || null,
      contract_amount: parseFloat(document.getElementById('fContractAmt').value) || 0,
      paid_amount: parseFloat(document.getElementById('fPaidAmt').value) || 0,
      remainder_amount: parseFloat(document.getElementById('fRemAmt').value) || 0,
      oa_ref: document.getElementById('fOaRef').value || null,
      oa_no: document.getElementById('fOaNo').value || null,
      mc_ip_no: document.getElementById('fMcIpNo').value || null,
      bc_to_sub: document.getElementById('fBcToSub').value || null,
      sub_ip_no: document.getElementById('fSubIpNo').value || null,
      remark: document.getElementById('fRemark').value || null,
      pdf_path: null,
      ocr_status: null,
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
    if (!confirm('確認刪除此付款登記？')) return;
    await api('DELETE', `/payments/${id}`);
    toast('已刪除', 'success');
    await this.load();
    await Dashboard.load();
  },

  exportCsv() {
    if (!this.filtered.length) { toast('沒有資料可匯出', 'warning'); return; }
    const headers = ['序號','發票日期','發票號碼','判項編號','公司名稱(英)','公司名稱(中)','工程描述','判項金額','已付金額','餘額','OA參考','OA編號','MC IP No.','Sub-IP No.','備注'];
    const rows = this.filtered.map(r => [
      r.seq_no, r.invoice_date, r.invoice_no, r.sc_no, r.company_name_en, r.company_name_zh,
      r.description, fmtNumPlain(r.contract_amount), fmtNumPlain(r.paid_amount), fmtNumPlain(r.remainder_amount),
      r.oa_ref, r.oa_no, r.mc_ip_no, r.sub_ip_no, r.remark
    ]);
    downloadCsv([headers, ...rows], `payments_${App.currentProject?.project_code}_${new Date().toISOString().slice(0,10)}.csv`);
  }
};

function downloadCsv(rows, filename) {
  const content = rows.map(r => r.map(c => `"${(c ?? '').toString().replace(/"/g, '""')}"`).join(',')).join('\n');
  const blob = new Blob(['\uFEFF' + content], { type: 'text/csv;charset=utf-8' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
}
