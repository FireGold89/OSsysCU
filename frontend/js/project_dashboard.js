/* ─── project_dashboard.js — 項目概覽（QS 欄位 · 唯讀無框） ─────── */
const ProjectDashboard = {
  LAYOUT_KEY: 'qs_proj_dash_layout',
  _layoutInited: false,
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

  _normalizeLayoutMode(raw) {
    const m = (raw || '').trim().toLowerCase();
    if (m === 'ux') return 'classic';
    if (m === 'pro' || m === 'fresh') return m;
    return 'classic';
  },

  _projectNameFields(p) {
    let nameZh = p.project_name_zh || '';
    let nameEn = p.project_name_en || '';
    if (!nameZh && !nameEn && p.project_name) {
      const parts = projectNameParts(p);
      nameZh = parts.zh;
      nameEn = parts.en;
    }
    return { nameZh, nameEn };
  },

  initLayoutToggle() {
    if (this._layoutInited) return;
    this._layoutInited = true;
    let saved = localStorage.getItem(this.LAYOUT_KEY);
    if (saved === 'ux') {
      saved = 'classic';
      localStorage.setItem(this.LAYOUT_KEY, 'classic');
    }
    this.setLayout(this._normalizeLayoutMode(saved), { persist: false });
  },

  setLayout(mode, { persist = true } = {}) {
    const layout = this._normalizeLayoutMode(mode);
    const isPro = layout === 'pro';
    const isFresh = layout === 'fresh';
    const classic = document.getElementById('projectDashClassic');
    const pro = document.getElementById('projectDashPro');
    const card = document.getElementById('projectDashCard');
    const btnClassic = document.getElementById('projDashLayoutClassic');
    const btnFresh = document.getElementById('projDashLayoutFresh');
    const btnPro = document.getElementById('projDashLayoutPro');
    const sub = document.getElementById('projectDashSubtitle');
    if (classic) {
      classic.style.display = isPro ? 'none' : '';
      classic.hidden = isPro;
      classic.classList.toggle('proj-dash-theme-fresh', isFresh);
    }
    if (card) card.dataset.projDashLayout = layout;
    if (pro) {
      pro.style.display = isPro ? '' : 'none';
      pro.hidden = !isPro;
    }
    if (btnClassic) {
      btnClassic.classList.toggle('active', layout === 'classic');
      btnClassic.setAttribute('aria-selected', layout === 'classic' ? 'true' : 'false');
    }
    if (btnFresh) {
      btnFresh.classList.toggle('active', isFresh);
      btnFresh.setAttribute('aria-selected', isFresh ? 'true' : 'false');
    }
    if (btnPro) {
      btnPro.classList.toggle('active', isPro);
      btnPro.setAttribute('aria-selected', isPro ? 'true' : 'false');
    }
    if (sub) {
      if (isPro) sub.textContent = '專業概覽 · 重點 KPI 與分區摘要';
      else if (isFresh) sub.textContent = 'QS 項目資料 · 清新版（欄位與原主題相同）';
      else sub.textContent = 'QS 項目資料 · 與工程項目表單相同欄位';
    }
    if (persist) localStorage.setItem(this.LAYOUT_KEY, layout);
  },

  _syncProContractCalc() {
    const src = document.getElementById('pdContractCalc');
    const dst = document.getElementById('pdContractCalcPro');
    if (src && dst) dst.innerHTML = src.innerHTML;
  },

  _proHeroChipsHtml(p) {
    const items = [];
    const push = (label, val) => {
      const s = val == null || val === '' ? '' : String(val).trim();
      if (!s || s === '—') return;
      items.push(
        `<span class="pd-pro-chip"><span class="pd-pro-chip-k">${escHtml(label)}</span>${escHtml(s)}</span>`,
      );
    };
    push('工程分類', this._categoryText(p));
    push('Job No.', p.job_no);
    push('會計編號', p.account_code);
    return items.length ? items.join('') : '';
  },

  _renderProLayout(p, facDates, merged) {
    const code = p.quotation_no || p.project_code || '—';
    const { nameZh, nameEn } = this._projectNameFields(p);
    this._setText('pdProCode', code);
    this._setText('pdProNameZh', nameZh || '—');
    this._setText('pdProNameEn', nameEn || '—');
    this._setHtml('pdProStatus', p.status ? projectStatusBadgeHtml(p.status) : '—');
    const chipsEl = document.getElementById('pdProHeroChips');
    if (chipsEl) {
      const chips = this._proHeroChipsHtml(p);
      chipsEl.innerHTML = chips;
      chipsEl.hidden = !chips;
    }
    this._setText('pdProKpiContract', this._dashMoney(p.contract_amount));
    this._setText('pdProKpiTender', this._dashMoney(p.tender_sum));
    this._setText('pdProKpiProfit', this._dashPct(p.anticipated_profit_pct));
    const days = Projects._constructionPeriodDisplay(p);
    this._setText('pdProKpiDays', days !== '—' ? `${days} 日` : '—');
    this._setText('pdProMc', p.main_contractor);
    this._setText('pdProClient', p.client);
    this._setText('pdProClient2', p.client_secondary);
    this._setHtml('pdProMpCodes', this._mpCodesHtml(p));
    this._setText('pdProMcCommence', this._dashDate(p.main_contract_commencement_date));
    this._setText('pdProMpCommence', this._dashDate(p.mp_commencement_date || p.start_date));
    this._setText('pdProCompletion', this._dashDate(p.project_completion_date));
    this._setText('pdProExtended', this._dashDate(facDates.extendedCompletionDate));
    this._setText('pdProPcCert', this._dashDate(facDates.pcCertDate));
    this._setText('pdProDlpCert', this._dashDate(facDates.warrantyCompleteDate));
    this._setText('pdProMpFac', this._dashDate(facDates.mpFacSignedDate));
    this._setText('pdProDlpMonths', p.dlp_period_months != null && p.dlp_period_months !== ''
      ? `${p.dlp_period_months} 月` : '—');
    this._setText('pdProPerson', p.person_in_charge || p.project_manager);
    this._setText('pdProQs', p.qs_in_charge);
    this._setText(
      'pdProRetention',
      typeof Projects.retentionPctSummaryDisplay === 'function'
        ? Projects.retentionPctSummaryDisplay(p)
        : '—',
    );
    const refundText = typeof Projects.retentionRefundDisplay === 'function'
      ? Projects.retentionRefundDisplay(p)
      : '—';
    this._setText('pdProRetentionRefund', refundText || '—');
    this._setText('pdProLabour', this._dashMoney(p.labour_allocation));
    const notes = (p.notes || '').trim();
    const notesEl = document.getElementById('pdProNotes');
    if (notesEl) {
      notesEl.textContent = notes || '—';
      notesEl.classList.toggle('is-empty', !notes);
    }
    if (typeof ProjIsoAttach !== 'undefined') {
      this._setHtml('pdProDocsMainLoa', ProjIsoAttach.readonlyHtml(ProjIsoAttach.docsForGroup(merged, 'mainLoa')));
      this._setHtml('pdProDocsSotSor', ProjIsoAttach.readonlyHtml(ProjIsoAttach.docsForGroup(merged, 'sotSor')));
    }
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
    this.initLayoutToggle();

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

    const summaryP = typeof App.fetchProjectSummary === 'function'
      ? App.fetchProjectSummary(p.id, { silent: true }).catch(() => null)
      : api('GET', `/reports/summary/${p.id}`, null, { silent: true }).catch(() => null);

    const [board, legacyRaw, facData, summaryEarly] = await Promise.all([
      api('GET', `/projects/${p.id}/iso-documents`, null, { silent: true }).catch(() => null),
      api('GET', `/projects/${p.id}/documents`, null, { silent: true }).catch(() => []),
      api('GET', `/projects/${p.id}/main-con-fac`, null, { silent: true }).catch(() => null),
      summaryP,
    ]);
    if (switchSeq != null && switchSeq !== App._projectSwitchSeq) return;

    let merged = [];
    try {
      const mainFiles = board?.main_files || {};
      const legacy = legacyRaw || [];
      const legacySot = legacy.filter((d) => d.doc_category === 'attachment3_sot_sor');
      merged = typeof ProjIsoAttach !== 'undefined'
        ? ProjIsoAttach.mergeDocs(legacySot, mainFiles, { isoOnly: true })
        : legacySot;
    } catch (_) {
      merged = [];
    }

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
    this._renderProLayout(p, facDates, merged);

    const calcHost = document.getElementById('pdContractCalc');
    if (calcHost) {
      try {
        const summary = summaryEarly
          || await (typeof App.fetchProjectSummary === 'function'
            ? App.fetchProjectSummary(p.id, { silent: true })
            : api('GET', `/reports/summary/${p.id}`, null, { silent: true }));
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
    this._syncProContractCalc();
  },

  async load(switchSeq) {
    const p = App.currentProject;
    await this.render(p, switchSeq);
  },
};
