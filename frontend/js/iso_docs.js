/**
 * iso_docs.js — ISO 文件登記（主合約／分判附件）
 */
const IsoDocs = {
  /** 主合約金額 ≥ 此值時，美博／港澳招投標會議記錄為必填 */
  MAIN_TMC_REQUIRED_AMOUNT: 10_000_000,
  _board: null,
  _uploadCtx: null,
  _linkCtx: null,
  _versionsCtx: null,
  _loadSeq: 0,
  _view: 'main',
  _mainSubTab: 'contract',
  _dragBound: false,
  /** 暫隱藏頂部「ISO 附件完成度」卡片 */
  _SHOW_PROGRESS: false,

  /** 主合約分 Tab 槽位（Sprint B） */
  MAIN_SLOT_GROUPS: {
    contract: ['main_contract_loa', 'supplemental_optional'],
    tender: ['partner_list', 'mou_nda', 'mepo_tmc', 'hkmo_tmc', 'tender_signoff', 'other'],
  },

  MAIN_COLS: [
    { slot: null, label: '主合約', kind: 'label', sticky: 0 },
    { slot: null, label: '合約金額', kind: 'amount_main', sticky: 1 },
    { slot: 'main_contract_loa', label: '主合約或LOA', short: '主合約/LOA' },
    { slot: null, label: '補充合約金額', kind: 'amount_supp' },
    { slot: 'supplemental_optional', label: '補充合約或 Optional 工程(如有)', short: '補充/Optional', optional: true },
    { slot: 'partner_list', label: '工程及管理投標合作伙伴名單確定表(如有)', short: '合作伙伴名單', optional: true },
    { slot: 'mou_nda', label: '合作備忘錄及保密協議(如有)', short: '合作備忘錄及保密協議', optional: true },
    { slot: 'mepo_tmc', label: '美博招投標會議記錄(如有)', short: '美博招投標會議記錄', optional: true },
    { slot: 'hkmo_tmc', label: '港澳招投標會議記錄(如有)', short: '港澳招投標會議記錄', optional: true },
    { slot: 'tender_signoff', label: '投標會簽表', short: '投標會簽' },
    { slot: 'other', label: '其他', short: '其他', optional: true },
  ],

  /** 分判 ISO 槽位定義（實際顯示依合約金額 tier） */
  SC_FILE_COLS: [
    { slot: 'sc_contract', label: '分判合約', short: '分判合約' },
    { slot: 'tender_confirm', label: '參與投標確認單', short: '參與投標確認單' },
    { slot: 'tender_collect', label: '領取標書記錄', short: '領取標書記錄' },
    { slot: 'integrity_declaration', label: '誠信及反圍標', short: '誠信及反圍標' },
    { slot: 'tender_opening', label: '開標記錄', short: '開標記錄' },
    { slot: 'contract_signoff', label: '合約會簽表', short: '合約會簽' },
    { slot: 'mepo_tmc', label: '美博招投標會議記錄', short: '美博招投標會議記錄' },
    { slot: 'hkmo_tmc', label: '港澳招投標會議記錄', short: '港澳招投標會議記錄' },
  ],

  SC_COLS: [
    { slot: null, label: '分判商', kind: 'label', sticky: 0 },
    { slot: null, label: '合約金額', kind: 'amount', sticky: 1 },
  ],

  _fileSlots(cols) {
    return cols.filter(c => c.slot);
  },

  _colBySlot(slot, cols) {
    return cols.find(c => c.slot === slot);
  },

  _scAmount(sc) {
    const v = sc?.contract_amount ?? sc?.contract_sum ?? 0;
    const n = Number(v);
    return Number.isFinite(n) ? n : 0;
  },

  /** 依合約金額決定需提交之分判 ISO 槽位 */
  _scTierSlots(amount) {
    const a = Number(amount) || 0;
    if (a < 100000) return [];
    if (a < 300000) return ['contract_signoff'];
    if (a < 1000000) {
      return ['sc_contract', 'tender_confirm', 'tender_collect', 'integrity_declaration', 'contract_signoff'];
    }
    if (a < 3000000) {
      return ['sc_contract', 'tender_confirm', 'tender_collect', 'integrity_declaration', 'tender_opening', 'contract_signoff'];
    }
    return [
      'sc_contract', 'tender_confirm', 'tender_collect', 'integrity_declaration',
      'tender_opening', 'contract_signoff', 'mepo_tmc', 'hkmo_tmc',
    ];
  },

  _scColsForAmount(amount) {
    const order = this.SC_FILE_COLS;
    const slots = new Set(this._scTierSlots(amount));
    return order.filter(c => slots.has(c.slot));
  },

  _scColsUnion(rows) {
    const seen = new Set();
    const out = [];
    (rows || []).forEach(sc => {
      this._scTierSlots(this._scAmount(sc)).forEach(slot => {
        if (seen.has(slot)) return;
        seen.add(slot);
        const col = this._colBySlot(slot, this.SC_FILE_COLS);
        if (col) out.push(col);
      });
    });
    return out;
  },

  _scSlotLabels(slots) {
    return (slots || [])
      .map((slot) => this._colBySlot(slot, this.SC_FILE_COLS)?.short || slot)
      .filter(Boolean);
  },

  _mainTierHint(amount) {
    const a = Number(amount) || 0;
    const needTmc = a >= this.MAIN_TMC_REQUIRED_AMOUNT;
    const amtText = typeof fmt === 'function' ? fmt(a) : `HK$${a}`;
    if (needTmc) {
      return `本項目主合約 ${amtText}（≥ HK$10,000,000）→ 「招標／會議」分頁之美博招投標會議記錄、港澳招投標會議記錄為 <strong>必填</strong>。`;
    }
    if (a > 0) {
      return `本項目主合約 ${amtText}（&lt; HK$10,000,000）→ 美博／港澳招投標會議記錄為 <strong>選填</strong>（如有）。`;
    }
    return '請先確認項目主合約金額；≥ HK$10,000,000 時美博／港澳招投標會議記錄為必填。';
  },

  _renderRulesGuide(b) {
    const host = document.getElementById('isoDocsRulesGuideBody');
    if (!host) return;
    const mainAmt = this._mainContractAmount(b);
    const scTiers = [
      { range: '小於 HK$100,000', slots: this._scTierSlots(0) },
      { range: 'HK$100,000 以上至 HK$300,000 未滿', slots: this._scTierSlots(100000) },
      { range: 'HK$300,000 以上至 HK$1,000,000 未滿', slots: this._scTierSlots(300000) },
      { range: 'HK$1,000,000 以上至 HK$3,000,000 未滿', slots: this._scTierSlots(1000000) },
      { range: 'HK$3,000,000 或以上', slots: this._scTierSlots(3000000) },
    ];
    const scTierHtml = scTiers.map((t) => {
      const labels = this._scSlotLabels(t.slots);
      const docs = labels.length
        ? labels.map((l) => `<span class="iso-rules-tag">${escHtml(l)}</span>`).join('')
        : '<span class="iso-rules-muted">無需提交 ISO 文件</span>';
      return `<li><span class="iso-rules-range">${escHtml(t.range)}</span><div class="iso-rules-tags">${docs}</div></li>`;
    }).join('');

    host.innerHTML = `
      <p class="iso-rules-current">${this._mainTierHint(mainAmt)}</p>
      <p class="iso-rules-lead">系統依<strong>主合約</strong>或<strong>分判商合約金額</strong>自動顯示槽位；標示「選填」者可不上傳；未出現的欄位代表該金額 tier 無需提交。</p>
      <div class="iso-rules-cols">
        <section class="iso-rules-section">
          <h4>主合約 · 合約文件</h4>
          <ul class="iso-rules-list">
            <li><strong>必填</strong>：主合約或 LOA</li>
            <li><strong>選填</strong>：補充合約或 Optional 工程（如有）</li>
          </ul>
        </section>
        <section class="iso-rules-section">
          <h4>主合約 · 招標／會議</h4>
          <ul class="iso-rules-list">
            <li><strong>必填</strong>：投標會簽表</li>
            <li><strong>選填</strong>：工程及管理投標合作伙伴名單、合作備忘錄及保密協議、其他（如有）</li>
            <li>主合約 <strong>≥ HK$10,000,000</strong>：<strong>必填</strong> 美博招投標會議記錄、港澳招投標會議記錄</li>
            <li>主合約 <strong>&lt; HK$10,000,000</strong>：上述兩項為 <strong>選填</strong>（如有）</li>
          </ul>
        </section>
        <section class="iso-rules-section iso-rules-section-wide">
          <h4>分判商 · 依分判合約金額（每判項獨立計算）</h4>
          <ul class="iso-rules-tier-list">${scTierHtml}</ul>
          <p class="iso-rules-foot">分判列表僅顯示 SC 類主判項（不含 M／O 物料及其他支出）；<strong>≥ HK$300,000</strong> 的判項排序優先。各判項只顯示該 tier 需提交之欄位。</p>
        </section>
      </div>
      <p class="iso-rules-legend"><span class="iso-rules-legend-req">必填</span> 缺件會計入 ISO 完成度 · <span class="iso-rules-legend-opt">選填</span> 可留空 · 可上傳 PDF／圖片或填 SharePoint 連結</p>`;
  },

  _sortScRows(rows) {
    return [...(rows || [])].sort((a, b) => {
      const aa = this._scAmount(a);
      const ba = this._scAmount(b);
      const aHi = aa >= 300000;
      const bHi = ba >= 300000;
      if (aHi !== bHi) return aHi ? -1 : 1;
      return ba - aa;
    });
  },

  _mainContractAmount(source) {
    const p = source?.project || (typeof App !== 'undefined' ? App.currentProject : null) || {};
    const n = Number(p.contract_amount);
    return Number.isFinite(n) ? n : 0;
  },

  _mainColTier(col, amount) {
    if (!col?.slot) return col;
    if (col.slot !== 'mepo_tmc' && col.slot !== 'hkmo_tmc') return col;
    const required = amount >= this.MAIN_TMC_REQUIRED_AMOUNT;
    const stripOptional = (s) => (s || '').replace(/\(如有\)/g, '').trim();
    return {
      ...col,
      optional: !required,
      label: required ? stripOptional(col.label) : col.label,
    };
  },

  _mainColsResolved(board) {
    const amount = this._mainContractAmount(board || this._board);
    return this.MAIN_COLS.map((c) => this._mainColTier(c, amount));
  },

  _mainColsForGroup(group, board = null) {
    const slots = this.MAIN_SLOT_GROUPS[group] || [];
    const amount = this._mainContractAmount(board || this._board);
    return slots
      .map(s => this._colBySlot(s, this.MAIN_COLS))
      .filter(Boolean)
      .map(c => this._mainColTier(c, amount));
  },

  setView(view) {
    this._view = view === 'sc' ? 'sc' : 'main';
    try { sessionStorage.setItem('iso_docs_view', this._view); } catch (e) { /* ignore */ }
    document.getElementById('isoTabMain')?.classList.toggle('active', this._view === 'main');
    document.getElementById('isoTabSc')?.classList.toggle('active', this._view === 'sc');
    const mainPanel = document.getElementById('isoMainPanel');
    const scPanel = document.getElementById('isoScPanel');
    if (mainPanel) mainPanel.hidden = this._view !== 'main';
    if (scPanel) scPanel.hidden = this._view !== 'sc';
  },

  setMainSubTab(tab) {
    this._mainSubTab = tab === 'tender' ? 'tender' : 'contract';
    try { sessionStorage.setItem('iso_docs_main_sub', this._mainSubTab); } catch (e) { /* ignore */ }
    document.getElementById('isoSubTabContract')?.classList.toggle('active', this._mainSubTab === 'contract');
    document.getElementById('isoSubTabTender')?.classList.toggle('active', this._mainSubTab === 'tender');
    if (this._board) this._renderMainGrid(this._board);
  },

  _fileList(fileOrList) {
    if (!fileOrList) return [];
    return Array.isArray(fileOrList) ? fileOrList : [fileOrList];
  },

  _singleHasFile(file) {
    if (!file) return false;
    if (file.storage_type === 'link') return !!(file.external_url || '').trim();
    return !!(file.file_path || '').trim();
  },

  _hasFile(fileOrList) {
    return this._fileList(fileOrList).some(f => this._singleHasFile(f));
  },

  _computeStats(b) {
    const mainSlots = this._fileSlots(this._mainColsResolved(b));
    const mainFiles = b.main_files || {};
    const rows = b.subcontractors || [];

    let mainDone = 0;
    let mainRequiredDone = 0;
    let mainRequiredTotal = 0;
    mainSlots.forEach(col => {
      const ok = this._hasFile(mainFiles[col.slot]);
      if (ok) mainDone += 1;
      if (!col.optional) {
        mainRequiredTotal += 1;
        if (ok) mainRequiredDone += 1;
      }
    });

    let scDone = 0;
    let scRequiredDone = 0;
    let scRequiredTotal = 0;
    let scTotal = 0;
    rows.forEach(sc => {
      const rs = this._scRowStats(sc);
      scDone += rs.done;
      scRequiredDone += rs.requiredDone;
      scRequiredTotal += rs.requiredTotal;
      scTotal += rs.total;
    });

    const mainTotal = mainSlots.length;
    const totalDone = mainDone + scDone;
    const totalSlots = mainTotal + scTotal;
    const requiredDone = mainRequiredDone + scRequiredDone;
    const requiredTotal = mainRequiredTotal + scRequiredTotal;
    const missingRequired = requiredTotal - requiredDone;
    const pct = totalSlots ? Math.round((totalDone / totalSlots) * 100) : 0;

    return {
      mainDone, mainTotal, mainRequiredDone, mainRequiredTotal,
      scDone, scTotal, scRows: rows.length,
      scRequiredDone, scRequiredTotal,
      totalDone, totalSlots, requiredDone, requiredTotal,
      missingRequired, pct,
    };
  },

  _scRowStats(sc) {
    const scSlots = this._scColsForAmount(this._scAmount(sc));
    const files = sc.files || {};
    let done = 0;
    let requiredDone = 0;
    const requiredTotal = scSlots.length;
    scSlots.forEach(col => {
      const ok = this._hasFile(files[col.slot]);
      if (ok) {
        done += 1;
        requiredDone += 1;
      }
    });
    return { done, total: scSlots.length, requiredDone, requiredTotal };
  },

  _filterScList(list) {
    return (list || []).filter(r => {
      if (r.is_excluded) return false;
      const scNo = (r.sc_no || '').trim().toUpperCase();
      if (scNo.startsWith('M-') || /^M\d/.test(scNo)) return false;
      if (scNo.startsWith('O-') || /^O\d/.test(scNo)) return false;
      const parent = (r.parent_sc_no || '').trim().toUpperCase();
      if (parent && parent !== scNo) return false;
      return true;
    });
  },

  _boardFromCache(prevFiles = null) {
    const p = App.currentProject || {};
    const prev = prevFiles || this._board || {};
    const mainFiles = prev.main_files || {};
    const prevSc = {};
    (prev.subcontractors || []).forEach(s => { prevSc[s.id] = s.files || {}; });
    const projectUrl = (p.doc_library_url || '').trim() || null;

    return {
      project: {
        id: p.id,
        project_code: p.project_code,
        project_name_zh: p.project_name_zh || p.project_name_en,
        contract_amount: p.contract_amount,
        supplemental_contract_amount: p.supplemental_contract_amount || 0,
        doc_library_url: projectUrl,
      },
      doc_library: {
        project_url: projectUrl,
        global_url: this._globalDocUrl || null,
      },
      main_files: mainFiles,
      subcontractors: this._filterScList(App.scList).map(sc => ({
        id: sc.id,
        sc_no: sc.sc_no,
        company_name_zh: sc.company_name_zh || sc.company_name_en || sc.sc_no,
        contract_amount: sc.contract_sum || sc.contract_amount || 0,
        files: prevSc[sc.id] || {},
      })),
      _filesPending: true,
    };
  },

  _safeHref(url) {
    const s = (url || '').trim();
    if (!s || !/^https?:\/\//i.test(s)) return null;
    return s.replace(/"/g, '&quot;');
  },

  _thCell(col) {
    const sticky = col.sticky != null ? ` iso-sticky-col iso-sticky-${col.sticky}` : '';
    const opt = col.optional ? ' iso-th-optional' : '';
    const text = escHtml(col.short || col.label);
    const tip = escHtml(col.label + (col.optional ? ' · 選填' : ' · 必填'));
    return `<th class="iso-th${sticky}${opt}" title="${tip}">${text}</th>`;
  },

  _tdSticky(col, inner) {
    const amtKinds = ['amount_main', 'amount_supp', 'amount'];
    let cls = '';
    if (col.kind === 'label') cls = 'iso-label-cell';
    else if (amtKinds.includes(col.kind)) cls = 'iso-amt-cell';
    const sticky = col.sticky != null ? ` iso-sticky-col iso-sticky-${col.sticky}` : '';
    if (!cls && col.sticky == null) return inner;
    return `<td class="${cls}${sticky}">${inner}</td>`;
  },

  _formatUploadDate(raw) {
    if (!raw) return '';
    const s = String(raw).trim();
    const d = s.length >= 10 ? s.slice(0, 10) : s;
    return d;
  },

  _renderLibraryBar(b) {
    const el = document.getElementById('isoDocsLibraryBar');
    if (!el) return;
    const lib = b.doc_library || {};
    const projectHref = this._safeHref(lib.project_url);
    const globalHref = this._safeHref(lib.global_url);
    if (!projectHref && !globalHref) {
      el.hidden = true;
      el.innerHTML = '';
      return;
    }
    el.hidden = false;
    const parts = [];
    if (projectHref) {
      parts.push(
        `<a class="btn btn-primary btn-sm" href="${projectHref}" target="_blank" rel="noopener noreferrer">開本項目文件庫</a>`
      );
    }
    if (globalHref) {
      parts.push(
        `<a class="btn btn-secondary btn-sm" href="${globalHref}" target="_blank" rel="noopener noreferrer">開公司文件庫</a>`
      );
    }
    el.innerHTML = parts.join('');
  },

  _renderProgress(b) {
    const el = document.getElementById('isoDocsProgress');
    if (!el) return;
    if (!this._SHOW_PROGRESS) {
      el.hidden = true;
      el.innerHTML = '';
      return;
    }
    if (b._filesPending) {
      el.hidden = true;
      return;
    }
    el.hidden = false;
    const s = this._computeStats(b);
    const barCls = s.pct >= 100 ? 'iso-progress-bar-fill iso-progress-complete'
      : s.pct >= 60 ? 'iso-progress-bar-fill'
        : 'iso-progress-bar-fill iso-progress-low';
    const missCls = s.missingRequired > 0 ? 'iso-stat-warn' : 'iso-stat-ok';

    el.innerHTML = `
      <div class="iso-progress-top">
        <div class="iso-progress-title">ISO 附件完成度</div>
        <div class="iso-progress-pct">${s.pct}%</div>
      </div>
      <div class="iso-progress-bar" role="progressbar" aria-valuenow="${s.pct}" aria-valuemin="0" aria-valuemax="100">
        <div class="${barCls}" style="width:${s.pct}%"></div>
      </div>
      <div class="iso-progress-stats">
        <div class="iso-stat"><span class="iso-stat-label">主合約</span><strong>${s.mainDone}/${s.mainTotal}</strong></div>
        <div class="iso-stat"><span class="iso-stat-label">分判（${s.scRows} 判項）</span><strong>${s.scDone}/${s.scTotal || 0}</strong></div>
        <div class="iso-stat"><span class="iso-stat-label">必填缺件</span><strong class="${missCls}">${s.missingRequired}</strong></div>
        <div class="iso-stat"><span class="iso-stat-label">必填已齊</span><strong>${s.requiredDone}/${s.requiredTotal}</strong></div>
      </div>`;
  },

  async load() {
    const pid = App.currentProject?.id;
    const noProj = document.getElementById('isoDocsNoProject');
    const content = document.getElementById('isoDocsContent');
    if (!pid) {
      if (noProj) noProj.style.display = '';
      if (content) content.style.display = 'none';
      return;
    }
    if (noProj) noProj.style.display = 'none';
    if (content) content.style.display = '';

    const seq = ++this._loadSeq;

    if (this._globalDocUrl === undefined) {
      try {
        const s = await api('GET', '/app-config', null, { silent: true });
        this._globalDocUrl = (s?.doc_library_url || '').trim() || null;
      } catch {
        this._globalDocUrl = null;
      }
    }
    if (seq !== this._loadSeq) return;

    this._board = this._boardFromCache();
    this.render();

    try {
      const data = await api('GET', `/projects/${pid}/iso-documents`, null, { silent: true });
      if (seq !== this._loadSeq) return;
      this._board = data;
      this.render();
    } catch (e) {
      if (seq !== this._loadSeq) return;
      this._board._filesPending = false;
      this._board._loadError = e.message || '無法載入附件';
      this.render();
      toast(this._board._loadError + '（表格已顯示，可稍後重新整理）', 'warning');
    }
  },

  render() {
    const b = this._board;
    if (!b) return;

    try {
      const savedView = sessionStorage.getItem('iso_docs_view');
      if (savedView === 'main' || savedView === 'sc') this._view = savedView;
      const savedSub = sessionStorage.getItem('iso_docs_main_sub');
      if (savedSub === 'contract' || savedSub === 'tender') this._mainSubTab = savedSub;
    } catch (e) { /* ignore */ }

    b.subcontractors = this._sortScRows(b.subcontractors);

    this._renderLibraryBar(b);
    this._renderProgress(b);
    this._renderRulesGuide(b);
    this.setView(this._view);
    this.setMainSubTab(this._mainSubTab);
    this._renderMainMeta(b);
    this._renderMainGrid(b);
    this._renderScCards(b);
    this._renderMainTable(b);
    this._renderScTable(b);
    this._bindDragDrop();

    const filterNote = document.getElementById('isoDocsFilterNote');
    if (filterNote) {
      const n = (b.subcontractors || []).length;
      filterNote.textContent = n
        ? `分判顯示 SC 類主判項 ${n} 項 · ≥30萬優先 · 附件依合約金額自動顯示`
        : '';
    }

    const hint = document.getElementById('isoDocsHint');
    if (hint) {
      if (b._loadError) {
        hint.textContent = `⚠️ ${b._loadError} · 請重新啟動後端或 Ctrl+F5 後再試`;
        hint.classList.add('iso-docs-hint-warn');
      } else if (b._filesPending) {
        hint.textContent = '主合約及分判招標／合約 ISO 附件 · 附件列表載入中…';
        hint.classList.remove('iso-docs-hint-warn');
      } else {
        hint.textContent = '可拖放 PDF／圖片到各槽位 · 上傳、填連結或點檔名預覽 · 換檔保留舊版 · 下方可展開寬表格檢視';
        hint.classList.remove('iso-docs-hint-warn');
      }
    }
  },

  _renderMainMeta(b) {
    const el = document.getElementById('isoMainMeta');
    if (!el) return;
    const p = b.project || {};
    el.innerHTML = `
      <div class="iso-meta-row">
        <div class="iso-meta-item"><span class="iso-meta-label">項目</span><strong>${escHtml(p.project_code || '—')}</strong>
          ${p.project_name_zh ? `<div class="iso-cell-sub">${escHtml(p.project_name_zh)}</div>` : ''}</div>
        <div class="iso-meta-item"><span class="iso-meta-label">合約金額</span><strong>${fmt(p.contract_amount)}</strong></div>
        <div class="iso-meta-item"><span class="iso-meta-label">補充合約金額</span>${this._suppAmountCell(p)}</div>
      </div>`;
  },

  _renderMainGrid(b) {
    const el = document.getElementById('isoMainGrid');
    if (!el) return;
    const cols = this._mainColsForGroup(this._mainSubTab, b);
    const pending = b._filesPending;
    if (!cols.length) {
      el.innerHTML = '';
      return;
    }
    el.innerHTML = cols.map(col => {
      const file = b.main_files?.[col.slot];
      return this._slotTile('main', null, col, file, pending);
    }).join('');
  },

  _renderScCards(b) {
    const el = document.getElementById('isoScCards');
    if (!el) return;
    const rows = b.subcontractors || [];
    const pending = b._filesPending;

    if (!rows.length) {
      el.innerHTML = `<div class="iso-sc-empty">尚無分判資料 · 請先在「分判商登記」新增判項</div>`;
      return;
    }

    el.innerHTML = rows.map(sc => {
      const slots = this._scColsForAmount(this._scAmount(sc));
      const rs = this._scRowStats(sc);
      const pct = rs.total ? Math.round((rs.done / rs.total) * 100) : 0;
      const badgeCls = rs.requiredDone >= rs.requiredTotal ? 'iso-row-badge iso-row-badge-ok' : 'iso-row-badge iso-row-badge-warn';
      const badge = pending || !rs.total ? '' : `<span class="${badgeCls}" title="附件 ${rs.done}/${rs.total}">${pct}%</span>`;
      const tiles = slots.length
        ? slots.map(col => this._slotTile('subcontractor', sc.id, col, sc.files?.[col.slot], pending)).join('')
        : '<div class="iso-sc-empty-tier">無需提交 ISO 文件（合約金額 HK$100,000 以下）</div>';
      return `<article class="iso-sc-card">
        <header class="iso-sc-card-head">
          <div><strong>${escHtml(sc.company_name_zh || '—')}</strong>
            ${sc.sc_no ? `<div class="iso-cell-sub">${escHtml(sc.sc_no)}</div>` : ''}</div>
          <div class="iso-sc-card-meta">${badge}<span class="iso-sc-amt">${fmt(sc.contract_amount)}</span></div>
        </header>
        <div class="iso-slot-grid iso-slot-grid-compact">${tiles}</div>
      </article>`;
    }).join('');
  },

  _slotTile(scope, scId, col, file, pending) {
    const scAttr = scId != null ? String(scId) : '';
    const cellCls = this._fileCellClass(file, col);
    const body = this._fileCell(scope, scId, col.slot, file, pending, col.optional);
    const optTag = col.optional ? '<span class="iso-slot-opt">選填</span>' : '';
    const pendingCls = pending && !this._hasFile(file) ? ' iso-cell-pending' : '';
    return `<div class="iso-slot-tile${cellCls}${pendingCls}"
      data-iso-scope="${scope}"
      data-iso-slot="${col.slot}"
      data-iso-sc-id="${scAttr}"
      title="${escHtml(col.label)}">
      <div class="iso-slot-head">
        <span class="iso-slot-label">${escHtml(col.short || col.label)}</span>${optTag}
      </div>
      <div class="iso-slot-body">${body}</div>
      <div class="iso-slot-drop-hint">拖放檔案至此</div>
    </div>`;
  },

  _bindDragDrop() {
    if (this._dragBound) return;
    this._dragBound = true;
    const onDragOver = (e) => {
      const tile = e.target.closest('.iso-slot-tile');
      if (!tile || tile.classList.contains('iso-cell-pending')) return;
      e.preventDefault();
      tile.classList.add('iso-drop-hover');
    };
    const onDragLeave = (e) => {
      const tile = e.target.closest('.iso-slot-tile');
      if (tile) tile.classList.remove('iso-drop-hover');
    };
    const onDrop = (e) => {
      const tile = e.target.closest('.iso-slot-tile');
      if (!tile) return;
      e.preventDefault();
      tile.classList.remove('iso-drop-hover');
      const files = [...(e.dataTransfer?.files || [])];
      if (!files.length) return;
      const scope = tile.dataset.isoScope;
      const slot = tile.dataset.isoSlot;
      const scRaw = tile.dataset.isoScId;
      const scId = scRaw ? parseInt(scRaw, 10) : null;
      this.uploadFiles(files, { scope, slot, scId: Number.isFinite(scId) ? scId : null });
    };
    ['isoMainGrid', 'isoScCards'].forEach(id => {
      const root = document.getElementById(id);
      if (!root) return;
      root.addEventListener('dragover', onDragOver);
      root.addEventListener('dragleave', onDragLeave);
      root.addEventListener('drop', onDrop);
    });
  },

  _renderMainTable(b) {
    const el = document.getElementById('isoMainTable');
    if (!el) return;
    const p = b.project || {};
    const label = escHtml(p.project_code || '—');
    const name = p.project_name_zh ? `<div class="iso-cell-sub">${escHtml(p.project_name_zh)}</div>` : '';
    const mainAmt = fmt(p.contract_amount);
    const suppAmt = this._suppAmountCell(p);
    const pending = b._filesPending ? ' iso-cell-pending' : '';

    const mainCols = this._mainColsResolved(b);
    const head = `<thead><tr>${mainCols.map(c => this._thCell(c)).join('')}</tr></thead>`;

    const cells = mainCols.map(col => {
      if (col.kind === 'label') {
        return this._tdSticky(col, `${label}${name}`);
      }
      if (col.kind === 'amount_main') {
        return this._tdSticky(col, mainAmt);
      }
      if (col.kind === 'amount_supp') {
        return this._tdSticky(col, suppAmt);
      }
      const file = b.main_files?.[col.slot];
      return `<td class="iso-file-cell${pending}${this._fileCellClass(file, col)}">${this._fileCell('main', null, col.slot, file, b._filesPending, col.optional)}</td>`;
    }).join('');

    el.innerHTML = `${head}<tbody><tr>${cells}</tr></tbody>`;
    AmountInput.init(el);
  },

  _suppAmountCell(p) {
    const val = p.supplemental_contract_amount ?? 0;
    const pid = p.id;
    return `<input type="number" class="iso-amt-input" step="0.01" min="0"
      value="${val != null && val !== '' ? fmtInputNum(val) : ''}" placeholder="0"
      onchange="IsoDocs.saveSupplemental(${pid}, this.value)"
      title="補充合約金額（可編輯）">`;
  },

  async saveSupplemental(projectId, raw) {
    const amount = parseAmtOrZero(raw);
    try {
      this._board = await api('PATCH', `/projects/${projectId}/iso-meta`, {
        supplemental_contract_amount: amount,
      }, { silent: true });
      this.render();
      toast('已儲存補充合約金額', 'success');
    } catch (e) {
      toast(e.message || '儲存失敗', 'error');
    }
  },

  _renderScTable(b) {
    const el = document.getElementById('isoScTable');
    if (!el) return;
    const rows = b.subcontractors || [];
    const pending = b._filesPending ? ' iso-cell-pending' : '';
    const stickyCols = this.SC_COLS.filter(c => c.kind);
    const fileCols = this._scColsUnion(rows);
    const colCount = stickyCols.length + Math.max(fileCols.length, 1);
    const head = `<thead><tr>${stickyCols.map(c => this._thCell(c)).join('')}${fileCols.map(c => this._thCell(c)).join('')}</tr></thead>`;

    if (!rows.length) {
      el.innerHTML = `${head}<tbody><tr><td colspan="${colCount}" class="td-muted" style="padding:20px;text-align:center">尚無分判資料 · 請先在「分判商登記」新增判項</td></tr></tbody>`;
      return;
    }

    const body = rows.map(sc => {
      const tierSlots = new Set(this._scTierSlots(this._scAmount(sc)));
      const rs = this._scRowStats(sc);
      const pct = rs.total ? Math.round((rs.done / rs.total) * 100) : 0;
      const badgeCls = rs.requiredDone >= rs.requiredTotal ? 'iso-row-badge iso-row-badge-ok' : 'iso-row-badge iso-row-badge-warn';
      const stickyCells = stickyCols.map(col => {
        if (col.kind === 'label') {
          const sub = sc.sc_no ? `<div class="iso-cell-sub">${escHtml(sc.sc_no)}</div>` : '';
          const badge = b._filesPending || !rs.total ? '' : `<span class="${badgeCls}" title="附件 ${rs.done}/${rs.total} · 必填 ${rs.requiredDone}/${rs.requiredTotal}">${pct}%</span>`;
          return this._tdSticky(col, `<div class="iso-label-wrap">${escHtml(sc.company_name_zh || '—')}${badge}</div>${sub}`);
        }
        if (col.kind === 'amount') {
          return this._tdSticky(col, fmt(sc.contract_amount));
        }
        return '';
      }).join('');

      if (!tierSlots.size) {
        const span = Math.max(fileCols.length, 1);
        return `<tr>${stickyCells}<td colspan="${span}" class="td-muted iso-file-cell-na">無需提交 ISO 文件</td></tr>`;
      }

      const fileCells = (fileCols.length ? fileCols : this._scColsForAmount(this._scAmount(sc))).map(col => {
        if (!tierSlots.has(col.slot)) {
          return '<td class="iso-file-cell iso-file-cell-na">—</td>';
        }
        const file = sc.files?.[col.slot];
        return `<td class="iso-file-cell${pending}${this._fileCellClass(file, col)}">${this._fileCell('subcontractor', sc.id, col.slot, file, b._filesPending, false)}</td>`;
      }).join('');
      return `<tr>${stickyCells}${fileCells}</tr>`;
    }).join('');

    el.innerHTML = `${head}<tbody>${body}</tbody>`;
  },

  _fileCellClass(file, col) {
    if (this._hasFile(file)) return ' iso-file-cell-done';
    if (col && col.optional) return ' iso-file-cell-optional';
    return ' iso-file-cell-missing';
  },

  async uploadFiles(files, ctx) {
    const list = (files || []).filter(Boolean);
    if (!list.length || !ctx) return;
    const pid = App.currentProject?.id;
    if (!pid) {
      toast('請先選擇項目', 'warning');
      return;
    }
    const valid = list.filter(f => /\.(pdf|png|jpe?g|gif|webp)$/i.test(f.name));
    if (!valid.length) {
      toast('只支援 PDF 或圖片格式', 'warning');
      return;
    }
    if (valid.length < list.length) {
      toast('部分檔案格式不支援，已略過', 'warning');
    }

    showLoading(valid.length > 1 ? `上傳 ISO 文件（0/${valid.length}）…` : '上傳 ISO 文件…');
    let ok = 0;
    try {
      for (const file of valid) {
        const fd = new FormData();
        fd.append('file', file);
        fd.append('scope', ctx.scope);
        fd.append('doc_slot', ctx.slot);
        if (ctx.scId) fd.append('subcontractor_id', String(ctx.scId));
        const res = await fetch(`${API}/projects/${pid}/iso-documents/upload`, { method: 'POST', body: fd });
        const json = await res.json();
        if (!json.success) throw new Error(json.error || '上傳失敗');
        ok += 1;
        if (valid.length > 1) showLoading(`上傳 ISO 文件（${ok}/${valid.length}）…`);
      }
      toast(ok > 1 ? `已上傳 ${ok} 個文件` : '文件已上傳', 'success');
      if (typeof LoadPerf !== 'undefined') LoadPerf.notifyProjectMutated(pid);
      await this.load();
    } catch (e) {
      toast(e.message || '上傳失敗', 'error');
      if (ok > 0) await this.load();
    } finally {
      hideLoading();
    }
  },

  async uploadFile(file, ctx) {
    await this.uploadFiles([file], ctx);
  },

  _fileItemHtml(file, scope, slot, scId) {
    const isLink = file.storage_type === 'link';
    const name = escHtml(file.link_label || file.original_filename || (isLink ? '外部連結' : file.file_path));
    const date = this._formatUploadDate(file.updated_at || file.created_at);
    const dateHtml = date ? `<span class="iso-file-date">${escHtml(date)}</span>` : '';
    let linkHtml;
    if (isLink) {
      const href = this._safeHref(file.external_url);
      linkHtml = href
        ? `<a class="iso-file-link" href="${href}" target="_blank" rel="noopener noreferrer" onclick="event.stopPropagation()">🔗 ${name}</a>`
        : `<span class="iso-file-link">${name}</span>`;
    } else {
      const path = (file.file_path || '').replace(/"/g, '&quot;');
      linkHtml = `<button type="button" class="iso-file-link" onclick="event.stopPropagation(); DocViewer.open('${path}', '${name}')">📄 ${name}</button>`;
    }
    return `<div class="iso-file-item iso-file-item-done">
      ${linkHtml}
      ${dateHtml}
      <div class="iso-file-actions">
        <button type="button" class="iso-file-action iso-file-del" title="刪除" onclick="event.stopPropagation(); IsoDocs.deleteFile(${file.id})">×</button>
      </div>
    </div>`;
  },

  _fileCell(scope, scId, slot, fileOrList, pending, optional) {
    if (pending && !this._hasFile(fileOrList)) {
      return '<span class="iso-file-placeholder">…</span>';
    }
    const files = this._fileList(fileOrList).filter(f => this._singleHasFile(f));
    if (files.length) {
      const verCount = files.reduce((n, f) => n + (f.version_count || 0), 0);
      const verBtn = verCount > 0
        ? `<button type="button" class="iso-file-action iso-file-ver" title="歷史版本 (${verCount})" onclick="event.stopPropagation(); IsoDocs.showVersions('${scope}', '${slot}', ${scId || 'null'})">📚</button>`
        : '';
      const items = files.map(f => this._fileItemHtml(f, scope, slot, scId)).join('');
      return `<div class="iso-file-stack">
        ${items}
        <div class="iso-file-stack-actions">
          ${verBtn}
          <button type="button" class="iso-file-action" title="新增文件" onclick="event.stopPropagation(); IsoDocs.pickUpload('${scope}', '${slot}', ${scId || 'null'})">＋</button>
          <button type="button" class="iso-file-action" title="填連結" onclick="event.stopPropagation(); IsoDocs.openLinkModal('${scope}', '${slot}', ${scId || 'null'})">🔗</button>
        </div>
      </div>`;
    }
    const label = optional ? '選填' : '待上傳';
    return `<div class="iso-empty-actions">
      <button type="button" class="iso-upload-btn${optional ? ' iso-upload-optional' : ''}" onclick="event.stopPropagation(); IsoDocs.pickUpload('${scope}', '${slot}', ${scId || 'null'})">${label}</button>
      <button type="button" class="iso-link-btn" onclick="event.stopPropagation(); IsoDocs.openLinkModal('${scope}', '${slot}', ${scId || 'null'})">填連結</button>
    </div>`;
  },

  pickUpload(scope, slot, scId) {
    if (!App.currentProject?.id) {
      toast('請先選擇項目', 'warning');
      return;
    }
    this._uploadCtx = { scope, slot, scId: scId || null };
    document.getElementById('isoDocFileInput')?.click();
  },

  async onFileSelected(event) {
    const files = [...(event.target?.files || [])];
    if (event.target) event.target.value = '';
    const ctx = this._uploadCtx;
    this._uploadCtx = null;
    if (!files.length || !ctx) return;
    await this.uploadFiles(files, ctx);
  },

  async deleteFile(docId) {
    if (!confirm('刪除此 ISO 附件？（舊版仍可在歷史版本中查閱）')) return;
    try {
      await api('DELETE', `/iso-documents/${docId}`, null, { silent: true });
      toast('已刪除', 'success');
      await this.load();
    } catch (e) {
      toast(e.message || '刪除失敗', 'error');
    }
  },

  openLinkModal(scope, slot, scId) {
    if (!App.currentProject?.id) {
      toast('請先選擇項目', 'warning');
      return;
    }
    this._linkCtx = { scope, slot, scId: scId || null };
    const urlEl = document.getElementById('isoLinkUrl');
    const labelEl = document.getElementById('isoLinkLabel');
    if (urlEl) urlEl.value = '';
    if (labelEl) labelEl.value = '';
    document.getElementById('isoLinkModal')?.classList.add('open');
    urlEl?.focus();
  },

  closeLinkModal() {
    this._linkCtx = null;
    document.getElementById('isoLinkModal')?.classList.remove('open');
  },

  async saveLink() {
    const ctx = this._linkCtx;
    const pid = App.currentProject?.id;
    if (!ctx || !pid) return;
    const url = (document.getElementById('isoLinkUrl')?.value || '').trim();
    const label = (document.getElementById('isoLinkLabel')?.value || '').trim();
    if (!url) {
      toast('請輸入連結 URL', 'warning');
      return;
    }
    if (!/^https?:\/\//i.test(url)) {
      toast('連結須以 http:// 或 https:// 開頭', 'warning');
      return;
    }
    showLoading('儲存連結…');
    try {
      const body = {
        scope: ctx.scope,
        doc_slot: ctx.slot,
        external_url: url,
        link_label: label || null,
      };
      if (ctx.scId) body.subcontractor_id = ctx.scId;
      await api('POST', `/projects/${pid}/iso-documents/link`, body);
      toast('連結已儲存', 'success');
      this.closeLinkModal();
      await this.load();
    } catch (e) {
      toast(e.message || '儲存失敗', 'error');
    } finally {
      hideLoading();
    }
  },

  async showVersions(scope, slot, scId) {
    const pid = App.currentProject?.id;
    if (!pid) return;
    this._versionsCtx = { scope, slot, scId: scId || null };
    const modal = document.getElementById('isoVersionsModal');
    const listEl = document.getElementById('isoVersionsList');
    const titleEl = document.getElementById('isoVersionsTitle');
    if (!modal || !listEl) return;

    const col = this._colBySlot(slot, scope === 'main' ? this.MAIN_COLS : this.SC_COLS);
    if (titleEl) titleEl.textContent = col?.label || slot;
    listEl.innerHTML = '<div class="iso-versions-loading">載入中…</div>';
    document.getElementById('isoVersionsModal')?.classList.add('open');

    try {
      const qs = new URLSearchParams({ scope, doc_slot: slot });
      if (scId) qs.set('subcontractor_id', String(scId));
      const data = await api('GET', `/projects/${pid}/iso-documents/versions?${qs}`, null, { silent: true });
      const versions = data?.versions || [];
      if (!versions.length) {
        listEl.innerHTML = '<div class="iso-versions-empty">尚無歷史版本</div>';
        return;
      }
      listEl.innerHTML = versions.map(v => this._versionRow(v)).join('');
    } catch (e) {
      listEl.innerHTML = `<div class="iso-versions-empty">⚠️ ${escHtml(e.message || '載入失敗')}</div>`;
    }
  },

  closeVersionsModal() {
    this._versionsCtx = null;
    document.getElementById('isoVersionsModal')?.classList.remove('open');
  },

  _versionRow(v) {
    const date = this._formatUploadDate(v.archived_at);
    const isLink = v.storage_type === 'link' || (v.external_url && !v.file_path);
    const name = escHtml(v.original_filename || v.link_label || (isLink ? '外部連結' : v.file_path || '—'));
    let openHtml;
    if (isLink) {
      const href = this._safeHref(v.external_url);
      openHtml = href
        ? `<a class="iso-file-link" href="${href}" target="_blank" rel="noopener noreferrer">🔗 ${name}</a>`
        : `<span>${name}</span>`;
    } else if (v.file_path) {
      const path = (v.file_path || '').replace(/"/g, '&quot;');
      openHtml = `<button type="button" class="iso-file-link" onclick="DocViewer.open('${path}', '${name}')">📄 ${name}</button>`;
    } else {
      openHtml = `<span>${name}</span>`;
    }
    return `<div class="iso-version-row">
      <div class="iso-version-main">${openHtml}</div>
      <div class="iso-version-date">${escHtml(date)}</div>
    </div>`;
  },
};
