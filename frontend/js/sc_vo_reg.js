/* ─── sc_vo_reg.js — 分判變更以及扣款登記（矩陣 + 模板快速新增） ── */
const ScVoReg = {
  data: [],
  filtered: [],
  templates: [],
  _refManual: false,

  async ensureTemplates() {
    if (this.templates.length) return;
    this.templates = await api('GET', '/sc-vo-templates', null, { silent: true }) || [];
  },

  _tpl(code) {
    return this.templates.find(t => t.code === code);
  },

  /** 範本 ref_no（VO、CC 等）僅為前綴佔位，需 API 自動編號 */
  _isPlaceholderRef(ref, recordType) {
    if (!ref || !String(ref).trim()) return true;
    const s = String(ref).trim().toUpperCase();
    const prefix = recordType === 'vo' ? 'VO' : 'CC';
    if (new RegExp(`^${prefix}-\\d+$`, 'i').test(s)) return false;
    const placeholders = new Set(['VO', 'CC', 'MAT', 'PN', 'BC', 'ADV']);
    return placeholders.has(s) || s === prefix;
  },

  async load() {
    const p = App.currentProject;
    if (!p) { this.renderEmpty(); return; }
    await this.ensureTemplates();
    this.renderQuickAdd();
    const scNo = document.getElementById('svrFilterSc')?.value || '';
    let rows = await api('GET', `/projects/${p.id}/sc-vo-records${scNo ? `?sc_no=${encodeURIComponent(scNo)}` : ''}`) || [];
    this.data = rows;
    this.applyFilters();
  },

  renderQuickAdd() {
    const box = document.getElementById('svrQuickAdd');
    if (!box) return;
    const items = this.templates.filter(t => t.source === 'sc_vo');
    if (!items.length) {
      box.innerHTML = '';
      box.style.display = 'none';
      return;
    }
    box.style.display = 'flex';
    box.innerHTML = items.map(t => {
      const tag = t.record_type === 'vo' ? 'VO' : '扣款';
      const label = (t.cert_label || t.description || t.code).replace(/^減: |^加: /, '');
      return `<button type="button" class="btn btn-secondary btn-sm" onclick="ScVoReg.quickAdd('${t.code}')">+ [${tag}] ${escHtml(label)}</button>`;
    }).join('');
  },

  populateTemplateSelect() {
    const sel = document.getElementById('svrTemplate');
    if (!sel) return;
    const cur = sel.value;
    sel.innerHTML = '<option value="">— 自訂 —</option>';
    this.templates.filter(t => t.source === 'sc_vo').forEach(t => {
      const opt = document.createElement('option');
      opt.value = t.code;
      const tag = t.record_type === 'vo' ? 'VO' : '扣款';
      opt.textContent = `[${tag}] ${t.cert_label || t.description || t.code}`;
      sel.appendChild(opt);
    });
    if (cur) sel.value = cur;
  },

  _applyTemplate(code) {
    const lineEl = document.getElementById('svrLineCode');
    if (lineEl) lineEl.value = code || '';
    const tpl = code ? this._tpl(code) : null;
    if (!tpl) return;
    const t = tpl.record_type === 'deduction' ? 'deduction' : 'vo';
    const radio = document.querySelector(`input[name="svrRegType"][value="${t}"]`);
    if (radio) radio.checked = true;
    const tplRef = tpl.ref_no || '';
    if (this._isPlaceholderRef(tplRef, t)) {
      document.getElementById('svrRefNo').value = '';
      this._refManual = false;
    } else {
      document.getElementById('svrRefNo').value = tplRef;
      this._refManual = !!tplRef;
    }
    const desc = (tpl.cert_label || tpl.description || '').replace(/^減: |^加: /, '');
    document.getElementById('svrContent').value = desc;
    this.onTypeChange();
    if (!this._refManual) this.suggestRefNo();
  },

  onTemplatePick() {
    this._refManual = false;
    this._applyTemplate(document.getElementById('svrTemplate')?.value || '');
  },

  quickAdd(code) {
    this.openAdd();
    const sel = document.getElementById('svrTemplate');
    if (sel) sel.value = code;
    this._applyTemplate(code);
  },

  _scCompany(scNo) {
    const sc = (App.scList || []).find(s => s.sc_no === scNo);
    if (!sc) return '—';
    return sc.company_name_zh || sc.company_name_en || '—';
  },

  _appliedPaymentLabel(ap) {
    if (!ap) return '';
    if (ap.display_label) return ap.display_label;
    const id = ap.id || '';
    return id ? `付款 #${id}` : '已套用';
  },

  _appliedCell(r) {
    if (!r.applied_payment_id) {
      return '<span class="badge badge-info">未套用</span>';
    }
    const ap = r.applied_payment || { id: r.applied_payment_id };
    const label = escHtml(this._appliedPaymentLabel(ap));
    const tip = escHtml(`點擊查看：${this._appliedPaymentLabel(ap)}`);
    return `<button type="button" class="svr-applied-link" title="${tip}" onclick="ScVoReg.openAppliedPayment(${r.applied_payment_id}, event)">${label}</button>`;
  },

  openAppliedPayment(paymentId, ev) {
    if (ev) ev.stopPropagation();
    if (!paymentId) return;
    App.navigate('payments', { openPaymentId: paymentId });
  },

  _searchHaystack(r) {
    return [
      r.sc_no, r.ref_no, r.description, r.service_description,
      r.company_name_en, r.company_name_zh, r.invoice_no, r.quotation_no,
      r.seq_no, r.main_contract_vo_no, r.oa_ref, r.oa_no, r.remark,
      this._scCompany(r.sc_no),
    ].filter(Boolean).join(' ').toLowerCase();
  },

  applyFilters() {
    const q = (document.getElementById('svrSearch')?.value || '').trim().toLowerCase();
    const type = document.getElementById('svrFilterType')?.value || '';
    this.filtered = this.data.filter(r => {
      if (type && r.record_type !== type) return false;
      if (!q) return true;
      return this._searchHaystack(r).includes(q);
    });
    this.render();
  },

  search() { this.applyFilters(); },
  filterByType() { this.applyFilters(); },
  filterBySc() { this.load(); },

  _pdfCell(r) {
    if (r.record_type !== 'vo') return '—';
    const path = r.approval_attachment;
    if (!path) return '—';
    const name = escHtml(r.approval_attachment_name || '審批表');
    return `<a href="${uploadUrl(path)}" target="_blank" rel="noopener" class="svr-pdf-link">📄 ${name}</a>`;
  },

  renderEmpty() {
    const tbody = document.getElementById('svrTableBody');
    if (!tbody) return;
    tbody.innerHTML = `<tr><td colspan="11"><div class="empty-state" style="padding:48px"><div class="empty-icon">📁</div><div class="empty-title">請先選擇項目</div></div></td></tr>`;
    const count = document.getElementById('svrCount');
    if (count) count.textContent = '0 條';
  },

  render() {
    const tbody = document.getElementById('svrTableBody');
    const countEl = document.getElementById('svrCount');
    if (!tbody) return;

    const groups = {};
    this.filtered.forEach(r => {
      if (!groups[r.sc_no]) groups[r.sc_no] = [];
      groups[r.sc_no].push(r);
    });
    const scNos = Object.keys(groups).sort((a, b) => a.localeCompare(b, undefined, { numeric: true }));

    const total = this.filtered.length;
    const all = this.data.length;
    if (countEl) {
      countEl.textContent = total === all ? `${total} 條` : `${total} / ${all} 條`;
    }

    if (!scNos.length) {
      const msg = all
        ? '無符合搜尋／篩選的記錄'
        : '暫無變更工程 / 扣款記錄';
      const sub = all ? '請調整搜尋或篩選條件' : '用上方模板快速新增，或按「新增變更登記」';
      tbody.innerHTML = `<tr><td colspan="11"><div class="empty-state" style="padding:40px"><div class="empty-icon">📝</div><div class="empty-title">${msg}</div><div class="empty-sub">${sub}</div></div></td></tr>`;
      return;
    }

    let html = '';
    for (const scNo of scNos) {
      const rows = groups[scNo];
      const company = escHtml(this._scCompany(scNo));
      rows.forEach((r, idx) => {
        const isVo = r.record_type === 'vo';
        const amt = parseFloat(r.amount) || 0;
        const voRef = isVo ? escHtml(r.ref_no || '—') : '';
        const voDesc = isVo ? escHtml(r.description || '—') : '';
        const voAmt = isVo ? fmt(amt) : '';
        const dedRef = !isVo ? escHtml(r.ref_no || '—') : '';
        const dedDesc = !isVo ? escHtml(r.description || '—') : '';
        const dedAmt = !isVo ? fmtExpense(amt) : '';
        const locked = r.applied_payment_id ? 'disabled title="已套用於糧款"' : '';
        const applied = this._appliedCell(r);

        html += '<tr>';
        if (idx === 0) {
          html += `<td rowspan="${rows.length}" class="svr-sc-cell td-mono">${fmtRefNo(scNo)}</td>`;
          html += `<td rowspan="${rows.length}" class="svr-company-cell">${company}</td>`;
        }
        html += `<td class="td-mono svr-vo-col">${voRef || '—'}</td>`;
        html += `<td class="svr-vo-col svr-desc-cell" title="${voDesc}">${voDesc || '—'}</td>`;
        html += `<td class="td-amount svr-vo-col">${voAmt || '—'}</td>`;
        html += `<td class="svr-vo-col svr-pdf-col">${this._pdfCell(r)}</td>`;
        html += `<td class="td-mono svr-ded-col">${dedRef || '—'}</td>`;
        html += `<td class="svr-ded-col svr-desc-cell" title="${dedDesc}">${dedDesc || '—'}</td>`;
        html += `<td class="td-amount svr-ded-col ${!isVo && amt < 0 ? 'negative' : ''}">${dedAmt || '—'}</td>`;
        html += `<td class="svr-applied-col">${applied}</td>`;
        html += `<td><div style="display:flex;gap:4px">
          <button class="btn btn-icon btn-secondary btn-sm" title="編輯" onclick="ScVoReg.openEdit(${r.id})">✏️</button>
          <button class="btn btn-icon btn-danger btn-sm" title="刪除" ${locked} onclick="ScVoReg.delete(${r.id})">🗑️</button>
        </div></td>`;
        html += '</tr>';
      });
    }
    tbody.innerHTML = html;
  },

  populateScFilter() {
    const sel = document.getElementById('svrFilterSc');
    const modalSel = document.getElementById('svrScNo');
    const cur = sel?.value;
    [sel, modalSel].forEach(s => {
      if (!s) return;
      const keep = s.value;
      s.innerHTML = '<option value="">— 全部判項 —</option>';
      (App.scList || []).forEach(sc => {
        const opt = document.createElement('option');
        opt.value = sc.sc_no;
        opt.textContent = `${sc.sc_no} — ${formatCompanyPrimary(sc.company_name_en, sc.company_name_zh).substring(0, 35)}`;
        s.appendChild(opt);
      });
      if (keep && (App.scList || []).some(sc => sc.sc_no === keep)) s.value = keep;
    });
    if (cur && sel) sel.value = cur;
  },

  _regType() {
    const el = document.querySelector('input[name="svrRegType"]:checked');
    return el ? el.value : 'vo';
  },

  onTypeChange() {
    const isVo = this._regType() === 'vo';
    const amtLabel = document.getElementById('svrAmtLabel');
    const contentLabel = document.getElementById('svrContentLabel');
    const refLabel = document.getElementById('svrRefLabel');
    const refInput = document.getElementById('svrRefNo');
    const contentInput = document.getElementById('svrContent');
    const quotGroup = document.getElementById('svrQuotGroup');
    const authSection = document.getElementById('svrAuthSection');
    const dedHint = document.getElementById('svrDedAmtHint');

    if (amtLabel) {
      amtLabel.innerHTML = isVo
        ? '變更金額 (HK$) <span class="required">*</span>'
        : '扣款金額 (HK$) <span class="required">*</span>';
    }
    if (contentLabel) contentLabel.textContent = isVo ? '變更內容' : '扣款內容';
    if (refLabel) refLabel.textContent = isVo ? '變更工程編號' : '扣款編號';
    if (refInput) refInput.placeholder = isVo ? 'VO-001' : 'CC-001';
    if (contentInput) contentInput.placeholder = isVo ? '變更描述' : '扣款原因';
    if (quotGroup) quotGroup.style.display = isVo ? '' : 'none';
    if (authSection) authSection.style.display = isVo ? '' : 'none';
    if (dedHint) dedHint.style.display = isVo ? 'none' : '';
    this.suggestRefNo();
  },

  onRefInput() {
    this._refManual = true;
  },

  async suggestRefNo() {
    if (document.getElementById('svrModalId')?.value || this._refManual) return;
    const p = App.currentProject;
    const scNo = document.getElementById('svrScNo')?.value;
    if (!p || !scNo) return;
    const t = this._regType();
    try {
      const r = await api(
        'GET',
        `/projects/${p.id}/sc-vo-records/next-ref?sc_no=${encodeURIComponent(scNo)}&record_type=${t}`,
        null,
        { silent: true },
      );
      if (r?.ref_no) document.getElementById('svrRefNo').value = r.ref_no;
    } catch (e) {}
  },

  onScChange(scNo) {
    const sc = (App.scList || []).find(s => s.sc_no === scNo);
    if (!sc) return;
    document.getElementById('svrCompanyEn').value = sc.company_name_en || '';
    document.getElementById('svrCompanyZh').value = sc.company_name_zh || '';
    document.getElementById('svrServiceDesc').value = sc.description || '';
    this.suggestRefNo();
  },

  _resetFormFields() {
    const fields = [
      'svrInvDate', 'svrInvNo', 'svrQuotNo', 'svrCompanyEn', 'svrCompanyZh',
      'svrServiceDesc', 'svrAmount', 'svrContent', 'svrRefNo',
      'svrOaRef', 'svrOaNo', 'svrMainContractVoNo', 'svrRemark',
    ];
    fields.forEach(id => {
      const el = document.getElementById(id);
      if (el) el.value = '';
    });
    const approval = document.getElementById('svrApprovalFile');
    const quotation = document.getElementById('svrQuotationFile');
    if (approval) approval.value = '';
    if (quotation) quotation.value = '';
    const lineEl = document.getElementById('svrLineCode');
    if (lineEl) lineEl.value = '';
    const tplSel = document.getElementById('svrTemplate');
    if (tplSel) tplSel.value = '';
    this._setAttachmentUi('approval', null, null);
    this._setAttachmentUi('quotation', null, null);
  },

  _setAttachmentUi(type, path, name) {
    const box = document.getElementById(type === 'approval' ? 'svrApprovalExisting' : 'svrQuotationExisting');
    if (!box) return;
    if (path) {
      box.style.display = '';
      box.innerHTML = `已上傳：<a href="${uploadUrl(path)}" target="_blank" rel="noopener">${escHtml(name || '檔案')}</a>`;
    } else {
      box.style.display = 'none';
      box.innerHTML = '';
    }
  },

  _readForm() {
    const scNo = document.getElementById('svrScNo').value;
    const sc = (App.scList || []).find(s => s.sc_no === scNo);
    const t = this._regType();
    const amount = parseFloat(document.getElementById('svrAmount').value) || 0;
    return {
      sc_no: scNo,
      sc_id: sc?.id || null,
      record_type: t,
      seq_no: document.getElementById('svrModalId').value
        ? (document.getElementById('svrSeqNo').value || null) : null,
      invoice_date: document.getElementById('svrInvDate').value || null,
      invoice_no: document.getElementById('svrInvNo').value || null,
      quotation_no: t === 'vo' ? (document.getElementById('svrQuotNo').value || null) : null,
      company_name_en: document.getElementById('svrCompanyEn').value || null,
      company_name_zh: document.getElementById('svrCompanyZh').value || null,
      service_description: document.getElementById('svrServiceDesc').value || null,
      amount,
      description: document.getElementById('svrContent').value || null,
      ref_no: document.getElementById('svrRefNo').value || null,
      oa_ref: t === 'vo' ? (document.getElementById('svrOaRef').value || null) : null,
      oa_no: t === 'vo' ? (document.getElementById('svrOaNo').value || null) : null,
      main_contract_vo_no: t === 'vo' ? (document.getElementById('svrMainContractVoNo').value || null) : null,
      remark: document.getElementById('svrRemark').value || null,
      line_code: document.getElementById('svrLineCode')?.value || null,
    };
  },

  _fillForm(r) {
    document.getElementById('svrSeqNo').value = r.seq_no || '';
    document.getElementById('svrInvDate').value = r.invoice_date || '';
    document.getElementById('svrInvNo').value = r.invoice_no || '';
    document.getElementById('svrQuotNo').value = r.quotation_no || '';
    document.getElementById('svrScNo').value = r.sc_no || '';
    document.getElementById('svrCompanyEn').value = r.company_name_en || '';
    document.getElementById('svrCompanyZh').value = r.company_name_zh || '';
    document.getElementById('svrServiceDesc').value = r.service_description || '';
    document.getElementById('svrAmount').value = fmtInputNum(Math.abs(parseFloat(r.amount) || 0));
    document.getElementById('svrContent').value = r.description || '';
    document.getElementById('svrRefNo').value = r.ref_no || '';
    document.getElementById('svrOaRef').value = r.oa_ref || '';
    document.getElementById('svrOaNo').value = r.oa_no || '';
    document.getElementById('svrMainContractVoNo').value = r.main_contract_vo_no || '';
    document.getElementById('svrRemark').value = r.remark || '';
    const lineEl = document.getElementById('svrLineCode');
    if (lineEl) lineEl.value = r.line_code || '';
    const tplSel = document.getElementById('svrTemplate');
    if (tplSel) tplSel.value = r.line_code || '';
    this._setAttachmentUi('approval', r.approval_attachment, r.approval_attachment_name);
    this._setAttachmentUi('quotation', r.quotation_attachment, r.quotation_attachment_name);
  },

  async _uploadPendingFiles(recordId) {
    const approval = document.getElementById('svrApprovalFile')?.files?.[0];
    const quotation = document.getElementById('svrQuotationFile')?.files?.[0];
    for (const [type, file] of [['approval', approval], ['quotation', quotation]]) {
      if (!file) continue;
      const fd = new FormData();
      fd.append('file', file);
      fd.append('type', type);
      const res = await fetch(`${API}/sc-vo-records/${recordId}/upload`, { method: 'POST', body: fd });
      const json = await res.json();
      if (!res.ok) throw new Error(json.error || '上傳失敗');
    }
  },

  async openAdd() {
    await this.ensureTemplates();
    document.getElementById('svrModalTitle').textContent = '新增變更登記';
    document.getElementById('svrModalId').value = '';
    this._refManual = false;
    this._resetFormFields();
    this.populateScFilter();
    this.populateTemplateSelect();
    const seqEl = document.getElementById('svrSeqNo');
    if (seqEl) {
      seqEl.value = '';
      seqEl.placeholder = '儲存時自動分配';
      seqEl.readOnly = true;
    }
    document.getElementById('svrScNo').value = document.getElementById('svrFilterSc')?.value || '';
    const voRadio = document.querySelector('input[name="svrRegType"][value="vo"]');
    if (voRadio) voRadio.checked = true;
    if (document.getElementById('svrScNo').value) this.onScChange(document.getElementById('svrScNo').value);
    document.getElementById('svrModal').classList.add('open');
    this.onTypeChange();
  },

  async openEdit(id) {
    await this.ensureTemplates();
    const r = await api('GET', `/sc-vo-records/${id}`);
    if (!r) return;
    const t = r.record_type === 'deduction' ? 'deduction' : 'vo';
    this._refManual = !this._isPlaceholderRef(r.ref_no, t);
    document.getElementById('svrModalTitle').textContent = '編輯變更登記';
    document.getElementById('svrModalId').value = r.id;
    this.populateScFilter();
    this.populateTemplateSelect();
    const radio = document.querySelector(`input[name="svrRegType"][value="${t}"]`);
    if (radio) radio.checked = true;
    const seqEl = document.getElementById('svrSeqNo');
    if (seqEl) {
      seqEl.value = r.seq_no || '';
      seqEl.readOnly = false;
      seqEl.placeholder = '自動';
    }
    this._fillForm(r);
    document.getElementById('svrModal').classList.add('open');
    this.onTypeChange();
  },

  closeModal() {
    document.getElementById('svrModal')?.classList.remove('open');
  },

  async saveModal() {
    const p = App.currentProject;
    if (!p) { toast('請先選擇項目', 'warning'); return; }
    const data = this._readForm();
    if (!data.sc_no) { toast('請選擇判項編號', 'warning'); return; }
    if (!data.amount) {
      toast(data.record_type === 'vo' ? '請輸入變更金額' : '請輸入扣款金額', 'warning');
      return;
    }

    const id = document.getElementById('svrModalId').value;
    try {
      let recordId = id;
      if (id) {
        await api('PUT', `/sc-vo-records/${id}`, data);
        toast('已更新', 'success');
      } else {
        const res = await api('POST', `/projects/${p.id}/sc-vo-records`, data);
        recordId = res?.id;
        toast('已新增', 'success');
      }
      if (recordId && data.record_type === 'vo') {
        await this._uploadPendingFiles(recordId);
      }
      this.closeModal();
      await this.load();
      if (App.currentProject) {
        App.scList = await api('GET', `/projects/${App.currentProject.id}/subcontractors`) || [];
        Payments.populateScFilter?.();
      }
    } catch (e) {
      toast(e.message || '儲存失敗', 'error');
    }
  },

  async delete(id) {
    if (!confirm('確認刪除此記錄？')) return;
    try {
      await api('DELETE', `/sc-vo-records/${id}`);
      toast('已刪除', 'success');
      await this.load();
      if (App.currentProject) {
        App.scList = await api('GET', `/projects/${App.currentProject.id}/subcontractors`) || [];
        Payments.populateScFilter?.();
      }
    } catch (e) {}
  },

  exportCsv() {
    if (!this.filtered.length) { toast('沒有資料可匯出', 'warning'); return; }
    const headers = [
      '序號', '類型', '判項編號', '公司名稱(英)', '公司名稱(中)',
      '變更工程編號', '變更內容', '變更金額', '審批表',
      '扣款編號', '扣款內容', '扣款金額',
      '發票日期', '發票號碼', '報價單號碼', '主合約變更編號',
      'OA參考', 'OA編號', '工程/服務描述', '備注',
    ];
    const rows = this.filtered.map(r => {
      const isVo = r.record_type === 'vo';
      const amt = parseFloat(r.amount) || 0;
      const company = this._scCompany(r.sc_no);
      return [
        r.seq_no,
        isVo ? '變更工程' : '扣款',
        r.sc_no,
        r.company_name_en || company,
        r.company_name_zh,
        isVo ? (r.ref_no || '') : '',
        isVo ? (r.description || '') : '',
        isVo ? fmtNumPlain(amt) : '',
        isVo ? (r.approval_attachment_name || '') : '',
        !isVo ? (r.ref_no || '') : '',
        !isVo ? (r.description || '') : '',
        !isVo ? fmtNumPlain(Math.abs(amt)) : '',
        r.invoice_date,
        r.invoice_no,
        r.quotation_no,
        r.main_contract_vo_no,
        r.oa_ref,
        r.oa_no,
        r.service_description,
        r.remark,
      ];
    });
    const code = App.currentProject?.project_code || 'project';
    downloadCsv([headers, ...rows], `sc_vo_reg_${code}_${new Date().toISOString().slice(0, 10)}.csv`);
  },

  tplCatalog: [],
  tplTab: 'sc_vo',
  _tplEditingCode: null,

  invalidateTemplateCaches() {
    this.templates = [];
    if (typeof Payments !== 'undefined') {
      Payments._scVoTemplates = null;
      Payments._standardLineTemplates = null;
    }
  },

  async openTplManager() {
    this.tplTab = 'sc_vo';
    this.closeTplForm();
    document.getElementById('svrTplModal')?.classList.add('open');
    this._syncTplTabs();
    await this.loadTplCatalog();
  },

  closeTplManager() {
    document.getElementById('svrTplModal')?.classList.remove('open');
    this.closeTplForm();
  },

  setTplTab(source) {
    this.tplTab = source;
    this._syncTplTabs();
    this.closeTplForm();
    this.renderTplManager();
  },

  _syncTplTabs() {
    document.querySelectorAll('.svr-tpl-tab').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.tab === this.tplTab);
    });
  },

  async loadTplCatalog() {
    this.tplCatalog = await api('GET', '/sc-vo-templates?manage=1', null, { silent: true }) || [];
    this.renderTplManager();
  },

  _tplRowsForTab() {
    return this.tplCatalog
      .filter(t => t.source === this.tplTab)
      .sort((a, b) => (a.sort_order || 0) - (b.sort_order || 0) || String(a.code).localeCompare(String(b.code)));
  },

  renderTplManager() {
    const head = document.getElementById('svrTplTableHead');
    const body = document.getElementById('svrTplTableBody');
    if (!head || !body) return;
    const isReg = this.tplTab === 'sc_vo';
    if (isReg) {
      head.innerHTML = `<tr>
        <th>代碼</th><th>類型</th><th>參考編號</th><th>描述</th><th>計算書標籤</th><th>排序</th><th>狀態</th><th>操作</th>
      </tr>`;
    } else {
      head.innerHTML = `<tr>
        <th>代碼</th><th>加/減</th><th>計算書標籤</th><th>描述</th><th>排序</th><th>狀態</th><th>操作</th>
      </tr>`;
    }
    const rows = this._tplRowsForTab();
    if (!rows.length) {
      body.innerHTML = `<tr><td colspan="${isReg ? 8 : 7}"><div class="empty-state" style="padding:32px">尚無範本 · 按「新增範本」</div></td></tr>`;
      return;
    }
    body.innerHTML = rows.map(t => {
      const active = t.is_active !== false;
      const status = active
        ? '<span class="badge badge-success">啟用</span>'
        : '<span class="badge badge-muted">停用</span>';
      const builtin = t.is_builtin ? '<span class="badge badge-muted" style="margin-left:4px">內建</span>' : '';
      const codeEsc = escHtml(t.code);
      const editBtn = `<button type="button" class="btn btn-icon btn-secondary btn-sm" title="編輯" onclick="ScVoReg.openTplForm('${codeEsc}')">✏️</button>`;
      const delBtn = t.is_builtin
        ? ''
        : `<button type="button" class="btn btn-icon btn-danger btn-sm" title="刪除" onclick="ScVoReg.deleteTpl('${codeEsc}')">🗑️</button>`;
      const toggleBtn = active
        ? `<button type="button" class="btn btn-icon btn-secondary btn-sm" title="停用" onclick="ScVoReg.toggleTplActive('${codeEsc}', 0)">🚫</button>`
        : `<button type="button" class="btn btn-icon btn-secondary btn-sm" title="啟用" onclick="ScVoReg.toggleTplActive('${codeEsc}', 1)">✅</button>`;
      if (isReg) {
        const type = t.record_type === 'vo'
          ? '<span class="badge badge-success">VO</span>'
          : '<span class="badge badge-warning">扣款</span>';
        return `<tr class="${active ? '' : 'svr-tpl-row-off'}">
          <td class="td-mono">${codeEsc}${builtin}</td>
          <td>${type}</td>
          <td class="td-mono">${escHtml(t.ref_no || '—')}</td>
          <td>${escHtml(t.description || '—')}</td>
          <td class="td-muted">${escHtml(t.cert_label || '—')}</td>
          <td>${t.sort_order ?? 0}</td>
          <td>${status}</td>
          <td><div class="svr-tpl-actions">${editBtn}${toggleBtn}${delBtn}</div></td>
        </tr>`;
      }
      const dir = t.direction === 'add'
        ? '<span class="badge badge-success">加</span>'
        : '<span class="badge badge-warning">減</span>';
      return `<tr class="${active ? '' : 'svr-tpl-row-off'}">
        <td class="td-mono">${codeEsc}${builtin}</td>
        <td>${dir}</td>
        <td>${escHtml(t.cert_label || '—')}</td>
        <td class="td-muted">${escHtml(t.description || '—')}</td>
        <td>${t.sort_order ?? 0}</td>
        <td>${status}</td>
        <td><div class="svr-tpl-actions">${editBtn}${toggleBtn}${delBtn}</div></td>
      </tr>`;
    }).join('');
  },

  openTplForm(code) {
    const panel = document.getElementById('svrTplFormPanel');
    if (!panel) return;
    const isReg = this.tplTab === 'sc_vo';
    const typeSel = document.getElementById('svrTplType');
    const typeLabel = document.getElementById('svrTplTypeLabel');
    const refRow = document.getElementById('svrTplRefRow');
    if (typeSel) {
      if (isReg) {
        typeLabel.textContent = '類型';
        typeSel.innerHTML = `
          <option value="vo">變更工程 (VO)</option>
          <option value="deduction">扣款</option>`;
      } else {
        typeLabel.textContent = '加/減';
        typeSel.innerHTML = `
          <option value="add">加項</option>
          <option value="ded">減項</option>`;
      }
    }
    if (refRow) refRow.style.display = isReg ? '' : 'none';
    document.getElementById('svrTplFormMode').value = code ? 'edit' : 'new';
    document.getElementById('svrTplFormTitle').textContent = code ? '編輯範本' : '新增範本';
    this._tplEditingCode = code || null;
    const codeEl = document.getElementById('svrTplCode');
    const hint = document.getElementById('svrTplCodeHint');
    if (code) {
      const t = this.tplCatalog.find(x => x.code === code);
      if (!t) return;
      codeEl.value = t.code;
      codeEl.readOnly = true;
      if (hint) hint.textContent = t.is_builtin ? '內建範本：代碼不可改' : '代碼不可改';
      if (typeSel) typeSel.value = isReg ? (t.record_type || 'deduction') : (t.direction || 'ded');
      document.getElementById('svrTplRefNo').value = t.ref_no || '';
      document.getElementById('svrTplDescription').value = t.description || '';
      document.getElementById('svrTplCertLabel').value = t.cert_label || '';
      document.getElementById('svrTplSort').value = t.sort_order ?? 0;
      document.getElementById('svrTplActive').checked = t.is_active !== false;
    } else {
      codeEl.value = '';
      codeEl.readOnly = false;
      if (hint) hint.textContent = '小寫英數與底線；儲存後不可改';
      if (typeSel) typeSel.value = isReg ? 'deduction' : 'ded';
      document.getElementById('svrTplRefNo').value = '';
      document.getElementById('svrTplDescription').value = '';
      document.getElementById('svrTplCertLabel').value = '';
      document.getElementById('svrTplSort').value = this._tplRowsForTab().length;
      document.getElementById('svrTplActive').checked = true;
    }
    panel.style.display = '';
    panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  },

  closeTplForm() {
    document.getElementById('svrTplFormPanel').style.display = 'none';
    this._tplEditingCode = null;
  },

  _readTplFormPayload() {
    const isReg = this.tplTab === 'sc_vo';
    const typeVal = document.getElementById('svrTplType')?.value;
    const payload = {
      code: document.getElementById('svrTplCode')?.value?.trim(),
      source: this.tplTab,
      description: document.getElementById('svrTplDescription')?.value?.trim() || null,
      cert_label: document.getElementById('svrTplCertLabel')?.value?.trim() || null,
      sort_order: parseInt(document.getElementById('svrTplSort')?.value, 10) || 0,
      is_active: document.getElementById('svrTplActive')?.checked,
    };
    if (isReg) {
      payload.record_type = typeVal;
      payload.ref_no = document.getElementById('svrTplRefNo')?.value?.trim() || null;
    } else {
      payload.direction = typeVal;
    }
    return payload;
  },

  async saveTplForm() {
    const payload = this._readTplFormPayload();
    if (!payload.code) {
      toast('請輸入範本代碼', 'warning');
      return;
    }
    if (this.tplTab === 'cert_standard' && !payload.cert_label) {
      toast('糧款標準行請填計算書標籤', 'warning');
      return;
    }
    const mode = document.getElementById('svrTplFormMode')?.value;
    try {
      if (mode === 'edit' && this._tplEditingCode) {
        await api('PUT', `/sc-vo-templates/${encodeURIComponent(this._tplEditingCode)}`, payload);
        toast('範本已更新', 'success');
      } else {
        await api('POST', '/sc-vo-templates', payload);
        toast('範本已新增', 'success');
      }
      this.invalidateTemplateCaches();
      this.closeTplForm();
      await this.loadTplCatalog();
      await this.ensureTemplates();
      this.renderQuickAdd();
      this.populateTemplateSelect();
    } catch (e) {
      toast(e.message || '儲存失敗', 'error');
    }
  },

  async toggleTplActive(code, active) {
    const t = this.tplCatalog.find(x => x.code === code);
    if (!t) return;
    try {
      await api('PUT', `/sc-vo-templates/${encodeURIComponent(code)}`, {
        ...t,
        is_active: !!active,
      });
      this.invalidateTemplateCaches();
      await this.loadTplCatalog();
      await this.ensureTemplates();
      this.renderQuickAdd();
      this.populateTemplateSelect();
      toast(active ? '已啟用' : '已停用', 'success');
    } catch (e) {
      toast(e.message || '操作失敗', 'error');
    }
  },

  async deleteTpl(code) {
    if (!confirm(`確認刪除範本「${code}」？`)) return;
    try {
      await api('DELETE', `/sc-vo-templates/${encodeURIComponent(code)}`);
      toast('已刪除', 'success');
      this.invalidateTemplateCaches();
      await this.loadTplCatalog();
      await this.ensureTemplates();
      this.renderQuickAdd();
      this.populateTemplateSelect();
    } catch (e) {
      toast(e.message || '刪除失敗', 'error');
    }
  },
};
