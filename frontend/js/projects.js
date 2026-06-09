/* ─── projects.js — 項目管理 ──────────────────────────── */
const Projects = {
  render(projects) {
    const container = document.getElementById('projectCards');
    if (!projects || projects.length === 0) {
      container.innerHTML = `
        <div class="empty-state" style="grid-column:1/-1;padding:64px">
          <div class="empty-icon">📁</div>
          <div class="empty-title">暫無項目</div>
          <div class="empty-sub">點擊「新增項目」或從Excel匯入</div>
        </div>`;
      return;
    }

    container.innerHTML = projects.map(p => {
      const statusClass = p.status === 'Active' ? 'success' :
                          p.status === 'Completed' ? 'info' : 'warning';
      const statusLabel = p.status === 'Active' ? '進行中' :
                          p.status === 'Completed' ? '已完成' : '暫停';
      const paid = p.total_paid || 0;
      const contractAmt = p.contract_amount || 0;
      const progress = contractAmt > 0 ? Math.min(100, (paid / contractAmt * 100)).toFixed(0) : 0;

      return `
        <div class="card" style="cursor:pointer" onclick="App.selectProject(${p.id});App.navigate('dashboard')">
          <div class="card-body">
            <div style="display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:12px">
              <div>
                <div style="font-size:12px;color:var(--text-muted);font-family:monospace">${p.project_code}</div>
                <div style="font-size:14px;font-weight:700;margin-top:2px;line-height:1.3">
                  ${p.project_name ? p.project_name.substring(0, 50) + (p.project_name.length > 50 ? '...' : '') : p.project_code}
                </div>
              </div>
              <span class="badge badge-${statusClass}">${statusLabel}</span>
            </div>
            <div style="font-size:12px;color:var(--text-secondary);margin-bottom:12px">
              👤 ${p.client || '—'} &nbsp;|&nbsp; 🏗️ ${p.main_contractor?.substring(0,20) || '—'}
            </div>
            <div style="margin-bottom:8px">
              <div style="display:flex;justify-content:space-between;font-size:11px;color:var(--text-muted);margin-bottom:4px">
                <span>付款進度 ${progress}%</span>
                <span>${fmt(paid)} / ${fmt(contractAmt)}</span>
              </div>
              <div class="progress-bar-wrap">
                <div class="progress-bar" style="width:${progress}%"></div>
              </div>
            </div>
            <div style="display:flex;justify-content:space-between;align-items:center;margin-top:12px">
              <div style="font-size:11px;color:var(--text-muted)">
                📋 ${p.sc_count || 0} 個合同項目
              </div>
              <div style="display:flex;gap:6px" onclick="event.stopPropagation()">
                <button class="btn btn-secondary btn-sm" onclick="Projects.openEdit(${p.id})">✏️ 編輯</button>
                <button class="btn btn-danger btn-sm" onclick="Projects.delete(${p.id}, '${p.project_code}')">刪除</button>
              </div>
            </div>
          </div>
        </div>
      `;
    }).join('');
  },

  openAdd() {
    document.getElementById('projModalTitle').textContent = '新增項目';
    document.getElementById('projModalId').value = '';
    ['pCode','pName','pClient','pMc','pNotes'].forEach(id => document.getElementById(id).value = '');
    document.getElementById('pAmt').value = '';
    document.getElementById('pLabour').value = '';
    document.getElementById('pStartDate').value = '';
    document.getElementById('pStatus').value = 'Active';
    document.getElementById('projectModal').classList.add('open');
  },

  async openEdit(id) {
    const p = await api('GET', `/projects/${id}`);
    if (!p) return;
    document.getElementById('projModalTitle').textContent = '編輯項目';
    document.getElementById('projModalId').value = p.id;
    document.getElementById('pCode').value = p.project_code || '';
    document.getElementById('pName').value = p.project_name || '';
    document.getElementById('pClient').value = p.client || '';
    document.getElementById('pMc').value = p.main_contractor || '';
    document.getElementById('pAmt').value = p.contract_amount || '';
    document.getElementById('pLabour').value = p.labour_allocation || '';
    document.getElementById('pStartDate').value = p.start_date || '';
    document.getElementById('pStatus').value = p.status || 'Active';
    document.getElementById('pNotes').value = p.notes || '';
    document.getElementById('projectModal').classList.add('open');
  },

  closeModal() {
    document.getElementById('projectModal').classList.remove('open');
  },

  async saveModal() {
    const id = document.getElementById('projModalId').value;
    const data = {
      project_code: document.getElementById('pCode').value.trim(),
      project_name: document.getElementById('pName').value.trim(),
      client: document.getElementById('pClient').value.trim(),
      main_contractor: document.getElementById('pMc').value.trim(),
      contract_amount: parseFloat(document.getElementById('pAmt').value) || 0,
      labour_allocation: parseFloat(document.getElementById('pLabour').value) || 0,
      start_date: document.getElementById('pStartDate').value || null,
      status: document.getElementById('pStatus').value,
      notes: document.getElementById('pNotes').value.trim(),
    };

    if (!data.project_code) { toast('請輸入項目代碼', 'warning'); return; }

    try {
      if (id) {
        await api('PUT', `/projects/${id}`, data);
        toast('項目已更新', 'success');
      } else {
        const res = await api('POST', '/projects', data);
        toast('項目已新增', 'success');
      }
      this.closeModal();
      await App.loadProjects();
    } catch (e) {}
  },

  async delete(id, code) {
    if (!confirm(`確認刪除項目「${code}」？\n此操作將同時刪除所有相關合同項目及付款記錄！`)) return;
    await api('DELETE', `/projects/${id}`);
    toast('項目已刪除', 'success');
    if (App.currentProject?.id == id) {
      App.currentProject = null;
      App.scList = [];
    }
    await App.loadProjects();
  }
};

/* ─── sc.js (在同一文件) — 分判商管理 ─────────────────────── */
const SC = {
  data: [],
  filtered: [],

  async load() {
    const p = App.currentProject;
    if (!p) {
      document.getElementById('scTableBody').innerHTML = `<tr><td colspan="8"><div class="empty-state" style="padding:40px">請先選擇項目</div></td></tr>`;
      return;
    }
    this.data = await api('GET', `/projects/${p.id}/subcontractors`) || [];
    this.filtered = [...this.data];
    this.render();
  },

  search(val) {
    const q = val.toLowerCase();
    this.filtered = this.data.filter(s =>
      (s.sc_no || '').toLowerCase().includes(q) ||
      (s.company_name_en || '').toLowerCase().includes(q) ||
      (s.company_name_zh || '').includes(q) ||
      (s.description || '').toLowerCase().includes(q)
    );
    this.render();
  },

  render() {
    const tbody = document.getElementById('scTableBody');
    if (this.filtered.length === 0) {
      tbody.innerHTML = `<tr><td colspan="8"><div class="empty-state" style="padding:48px"><div class="empty-icon">🏢</div><div class="empty-title">暫無合同項目</div></div></td></tr>`;
      return;
    }
    tbody.innerHTML = this.filtered.map(s => {
      const paid = s.total_paid || 0;
      const ca = s.contract_amount || 0;
      const progress = ca > 0 ? Math.min(100, (paid / ca * 100)).toFixed(0) : 0;
      const oaBadge = s.oa_status === 'OK' ? '<span class="badge badge-success">OK</span>' :
                      s.oa_status === '-'  ? '<span class="badge badge-muted">—</span>' :
                      s.oa_status          ? `<span class="badge badge-warning">${s.oa_status}</span>` : '—';
      return `
        <tr>
          <td>${fmtRefNo(s.sc_no)}${s.is_excluded ? ' <span class="badge badge-warning" style="font-size:10px">Excluded (C)</span>' : ''}</td>
          <td>
            <div style="font-weight:600">${s.company_name_en || '—'}</div>
            <div style="font-size:11px;color:var(--text-muted)">${s.company_name_zh || ''}</div>
          </td>
          <td class="td-muted">${s.description || '—'}</td>
          <td class="td-amount">${fmt(s.contract_amount)}</td>
          <td class="td-amount positive">${fmt(s.total_paid)}</td>
          <td>
            <div style="font-size:11px;color:var(--text-secondary);margin-bottom:4px">${s.quotation_no || '—'}</div>
            <div style="font-size:10px;color:var(--text-muted)">${s.quotation_date ? fmtDate(s.quotation_date) : ''}</div>
          </td>
          <td>${oaBadge}</td>
          <td onclick="event.stopPropagation()">
            <div style="display:flex;gap:4px">
              <button class="btn btn-icon btn-secondary btn-sm" onclick="SC.openEdit(${s.id})">✏️</button>
              <button class="btn btn-icon btn-danger btn-sm" onclick="SC.delete(${s.id}, '${s.sc_no}')">🗑️</button>
            </div>
          </td>
        </tr>
      `;
    }).join('');
  },

  openAdd() {
    document.getElementById('scModalTitle').textContent = '新增合同項目';
    document.getElementById('scModalId').value = '';
    ['scNo','scQuotNo','scCompanyEn','scCompanyZh','scDesc','scOaStatus','scOaNo','scPayNote'].forEach(id => document.getElementById(id).value = '');
    document.getElementById('scAmt').value = '';
    document.getElementById('scQuotDate').value = '';
    document.getElementById('scExcluded').checked = false;
    document.getElementById('scPaidAmt').value = '';
    document.getElementById('scRemainAmt').value = '';
    document.getElementById('scModal').classList.add('open');
  },

  async openEdit(id) {
    let s = this.data.find(x => x.id == id) || App.scList.find(x => x.id == id);
    if (!s) {
      try {
        s = await api('GET', `/subcontractors/${id}`);
      } catch (e) {
        return;
      }
    }
    if (!s) return;
    document.getElementById('scModalTitle').textContent = '編輯合同項目';
    document.getElementById('scModalId').value = s.id;
    document.getElementById('scNo').value = s.sc_no || '';
    document.getElementById('scQuotNo').value = s.quotation_no || '';
    document.getElementById('scCompanyEn').value = s.company_name_en || '';
    document.getElementById('scCompanyZh').value = s.company_name_zh || '';
    document.getElementById('scDesc').value = s.description || '';
    document.getElementById('scAmt').value = s.contract_amount || '';
    const paid = parseFloat(s.total_paid) || 0;
    const ca = parseFloat(s.contract_amount) || 0;
    document.getElementById('scPaidAmt').value = fmt(paid);
    document.getElementById('scRemainAmt').value = fmt(ca - paid);
    document.getElementById('scQuotDate').value = s.quotation_date || '';
    document.getElementById('scOaStatus').value = s.oa_status || '';
    document.getElementById('scOaNo').value = s.oa_no || '';
    document.getElementById('scPayNote').value = s.payment_note || '';
    document.getElementById('scExcluded').checked = !!s.is_excluded;
    document.getElementById('scModal').classList.add('open');
  },

  closeModal() {
    document.getElementById('scModal').classList.remove('open');
  },

  async saveModal() {
    const p = App.currentProject;
    if (!p) { toast('請先選擇項目', 'warning'); return; }
    const id = document.getElementById('scModalId').value;
    const scNo = document.getElementById('scNo').value.trim();
    if (!scNo) { toast('請輸入參考編號', 'warning'); return; }

    const data = {
      project_id: p.id,
      sc_no: scNo,
      quotation_no: document.getElementById('scQuotNo').value || null,
      company_name_en: document.getElementById('scCompanyEn').value || null,
      company_name_zh: document.getElementById('scCompanyZh').value || null,
      description: document.getElementById('scDesc').value || null,
      contract_amount: parseFloat(document.getElementById('scAmt').value) || 0,
      quotation_date: document.getElementById('scQuotDate').value || null,
      oa_status: document.getElementById('scOaStatus').value || null,
      oa_ref: null,
      oa_no: document.getElementById('scOaNo').value || null,
      quotation_saved: null,
      payment_note: document.getElementById('scPayNote').value || null,
      is_excluded: document.getElementById('scExcluded').checked ? 1 : 0,
    };

    try {
      await api('POST', '/subcontractors', data);
      toast('合同項目已儲存', 'success');
      this.closeModal();
      // 刷新分判商列表
      App.scList = await api('GET', `/projects/${p.id}/subcontractors`) || [];
      await this.load();
      Payments.populateScFilter();
      OCR.populateScOptions();
    } catch (e) {}
  },

  async delete(id, scNo) {
    if (!confirm(`確認刪除合同項目 ${scNo}？`)) return;
    await api('DELETE', `/subcontractors/${id}`);
    toast('已刪除', 'success');
    const p = App.currentProject;
    if (p) App.scList = await api('GET', `/projects/${p.id}/subcontractors`) || [];
    await this.load();
    Payments.populateScFilter();
  }
};
