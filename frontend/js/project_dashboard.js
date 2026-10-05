/* ─── project_dashboard.js — 項目概覽（QS 欄位 · 唯讀無框） ─────── */
const ProjectDashboard = {
  _setText(id, val) {
    const el = document.getElementById(id);
    if (!el) return;
    const s = val == null || val === '' ? '—' : String(val);
    el.textContent = s;
  },

  _setHtml(id, html) {
    const el = document.getElementById(id);
    if (!el) return;
    el.innerHTML = html || '—';
  },

  _dashDate(val) {
    if (!val) return '—';
    return fmtDate(val) || val;
  },

  _dashMoney(val) {
    const n = parseFloat(val);
    if (val == null || val === '' || Number.isNaN(n)) return '—';
    return fmt(n);
  },

  _dashPct(val) {
    if (val == null || val === '') return '—';
    const n = parseFloat(val);
    if (Number.isNaN(n)) return '—';
    return `${n.toFixed(FMT_DECIMALS)}%`;
  },

  _categoryText(p) {
    const l1 = p.category_l1_label || p.category_l1_code || '';
    const l2 = p.category_l2_label || p.category_l2_code || '';
    if (l1 && l2) return `${l1} · ${l2}`;
    return l2 || l1 || '—';
  },

  _mpCodesHtml(p) {
    const codes = Projects._mpCodesFromRow(p);
    if (!codes.length) return '—';
    return codes.map((code, i) => {
      const tag = i === 0 ? '<span class="proj-dash-mp-primary">主</span> ' : '';
      return `<span class="proj-dash-mp-chip">${tag}${escHtml(code)}</span>`;
    }).join(' ');
  },

  async render(p, switchSeq) {
    const noEl = document.getElementById('dashboardNoProject');
    const card = document.getElementById('projectDashCard');
    if (!p?.id) {
      if (noEl) noEl.style.display = '';
      if (card) card.style.display = 'none';
      return;
    }
    if (switchSeq != null && switchSeq !== App._projectSwitchSeq) return;

    if (noEl) noEl.style.display = 'none';
    if (card) card.style.display = '';

    const code = p.quotation_no || p.project_code || '—';
    this._setText('projectDashTitle', code);
    this._setText('pdCode', code);
    this._setHtml('pdStatus', p.status ? projectStatusBadgeHtml(p.status) : '—');

    let nameZh = p.project_name_zh || '';
    let nameEn = p.project_name_en || '';
    if (!nameZh && !nameEn && p.project_name) {
      const parts = projectNameParts(p);
      nameZh = parts.zh;
      nameEn = parts.en;
    }
    this._setText('pdNameZh', nameZh);
    this._setText('pdNameEn', nameEn);
    this._setHtml('pdMpCodes', this._mpCodesHtml(p));
    this._setText('pdJobNo', p.job_no);
    this._setText('pdCategory', this._categoryText(p));
    this._setText('pdAccountCode', p.account_code);
    this._setText('pdMc', p.main_contractor);
    this._setText('pdClient', p.client);
    this._setText('pdClient2', p.client_secondary);
    this._setText('pdTenderSum', this._dashMoney(p.tender_sum));
    this._setText('pdAmt', this._dashMoney(p.contract_amount));
    this._setText('pdAnticipatedProfitPct', this._dashPct(p.anticipated_profit_pct));
    this._setText('pdMcCommence', this._dashDate(p.main_contract_commencement_date));
    this._setText('pdCompletionDate', this._dashDate(p.project_completion_date));
    this._setText('pdMpCommence', this._dashDate(p.mp_commencement_date || p.start_date));
    this._setText('pdDlpMonths', p.dlp_period_months != null && p.dlp_period_months !== '' ? String(p.dlp_period_months) : '—');
    this._setText('pdPerson', p.person_in_charge || p.project_manager);
    this._setText('pdQs', p.qs_in_charge);
    this._setText('pdConstructionDays', Projects._constructionPeriodDisplay(p));
    this._setText(
      'pdRetentionSummary',
      typeof Projects.retentionPctSummaryDisplay === 'function'
        ? Projects.retentionPctSummaryDisplay(p)
        : '—',
    );
    const refundEl = document.getElementById('pdRetentionRefund');
    if (refundEl) {
      const refundText = typeof Projects.retentionRefundDisplay === 'function'
        ? Projects.retentionRefundDisplay(p)
        : '—';
      refundEl.textContent = refundText || '—';
    }
    this._setText('pdLabour', this._dashMoney(p.labour_allocation));

    const notes = (p.notes || '').trim();
    const notesEl = document.getElementById('pdNotes');
    if (notesEl) {
      notesEl.textContent = notes || '—';
      notesEl.classList.toggle('is-empty', !notes);
    }

    let merged = [];
    try {
      let mainFiles = {};
      let legacySot = [];
      try {
        const board = await api('GET', `/projects/${p.id}/iso-documents`, null, { silent: true });
        mainFiles = board?.main_files || {};
      } catch (_) { /* ignore */ }
      try {
        const legacy = (await api('GET', `/projects/${p.id}/documents`, null, { silent: true })) || [];
        legacySot = legacy.filter((d) => d.doc_category === 'attachment3_sot_sor');
      } catch (_) { /* ignore */ }
      merged = typeof ProjIsoAttach !== 'undefined'
        ? ProjIsoAttach.mergeDocs(legacySot, mainFiles, { isoOnly: true })
        : legacySot;
    } catch (_) {
      merged = [];
    }
    if (switchSeq != null && switchSeq !== App._projectSwitchSeq) return;

    let facData = null;
    try {
      facData = await api('GET', `/projects/${p.id}/main-con-fac`, null, { silent: true });
    } catch (_) { /* ignore */ }
    if (switchSeq != null && switchSeq !== App._projectSwitchSeq) return;

    const facDates = typeof MainConFac !== 'undefined' && MainConFac.overviewDates
      ? MainConFac.overviewDates(facData, p)
      : {};
    this._setText('pdPcCertDate', this._dashDate(facDates.pcCertDate));
    this._setText('pdExtendedCompletion', this._dashDate(facDates.extendedCompletionDate));
    this._setText('pdDlpCertDate', this._dashDate(facDates.warrantyCompleteDate));
    this._setText('pdMpFacDate', this._dashDate(facDates.mpFacSignedDate));

    if (typeof ProjIsoAttach !== 'undefined') {
      this._setHtml('pdDocsMainLoa', ProjIsoAttach.readonlyHtml(ProjIsoAttach.docsForGroup(merged, 'mainLoa')));
      this._setHtml('pdDocsSotSor', ProjIsoAttach.readonlyHtml(ProjIsoAttach.docsForGroup(merged, 'sotSor')));
    }

    const calcHost = document.getElementById('pdContractCalc');
    if (calcHost) {
      try {
        const summary = await api('GET', `/reports/summary/${p.id}`, null, { silent: true });
        if (switchSeq != null && switchSeq !== App._projectSwitchSeq) return;
        const calc = summary?.contract_calc;
        if (calc && typeof contractCalcTableHtml === 'function') {
          calcHost.innerHTML = contractCalcTableHtml(calc);
        } else {
          calcHost.innerHTML = '<p class="form-hint">尚無結算資料</p>';
        }
      } catch (_) {
        if (switchSeq == null || switchSeq === App._projectSwitchSeq) {
          calcHost.innerHTML = '<p class="form-hint">載入失敗</p>';
        }
      }
    }
  },

  async load(switchSeq) {
    const p = App.currentProject;
    await this.render(p, switchSeq);
  },
};
