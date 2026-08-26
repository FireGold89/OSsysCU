/**
 * iso_docs.js — ISO 文件登記（主合約／分判附件）
 */
const IsoDocs = {
  _board: null,
  _uploadCtx: null,
  _linkCtx: null,
  _versionsCtx: null,
  _loadSeq: 0,
  _view: 'main',
  _mainSubTab: 'contract',
  _dragBound: false,

  /** 主合約分 Tab 槽位（Sprint B） */
  MAIN_SLOT_GROUPS: {
    contract: ['main_contract_loa', 'supplemental_optional'],
    tender: ['partner_list', 'mou', 'nda', 'mepo_tmc', 'hkmo_tmc', 'tender_signoff', 'other'],
  },

  MAIN_COLS: [
    { slot: null, label: '主合約', kind: 'label', sticky: 0 },
    { slot: null, label: '合約金額', kind: 'amount_main', sticky: 1 },
    { slot: 'main_contract_loa', label: '主合約或LOA', short: '主合約/LOA' },
    { slot: null, label: '補充合約金額', kind: 'amount_supp' },
    { slot: 'supplemental_optional', label: '補充合約或 Optional 工程(如有)', short: '補充/Optional', optional: true },
    { slot: 'partner_list', label: '工程及管理投標合作伙伴名單確定表(如有)', short: '合作伙伴名單', optional: true },
    { slot: 'mou', label: '合作備忘錄(如有)', short: 'MOU', optional: true },
    { slot: 'nda', label: '保密協議(如有)', short: 'NDA', optional: true },
    { slot: 'mepo_tmc', label: '美博招投標管理委員會會議記錄(如有)', short: '美博 TMC', optional: true },
    { slot: 'hkmo_tmc', label: '港澳公司招投標管理委員會會議記錄(如有)', short: '港澳 TMC', optional: true },
    { slot: 'tender_signoff', label: '投標會簽表', short: '投標會簽' },
    { slot: 'other', label: '其他', short: '其他', optional: true },
  ],

  SC_COLS: [
    { slot: null, label: '分判商', kind: 'label', sticky: 0 },
    { slot: null, label: '合約金額', kind: 'amount', sticky: 1 },
    { slot: 'tender_confirm', label: '參與投標承判確認單', short: '承判確認' },
    { slot: 'tender_collect', label: '領取標書記錄', short: '領取標書' },
    { slot: 'tender_opening', label: '開標記錄(如有)', short: '開標記錄', optional: true },
    { slot: 'mepo_tmc', label: '美博招投標管理委員會會議記錄(如有)', short: '美博 TMC', optional: true },
    { slot: 'hkmo_tmc', label: '港澳公司招投標管理委員會會議記錄(如有)', short: '港澳 TMC', optional: true },
    { slot: 'contract_signoff', label: '合約會簽表', short: '合約會簽' },
    { slot: 'other', label: '其他', short: '其他', optional: true },
  ],

  _fileSlots(cols) {
    return cols.filter(c => c.slot);
  },

  _colBySlot(slot, cols) {
    return cols.find(c => c.slot === slot);
  },

  _mainColsForGroup(group) {
    const slots = this.MAIN_SLOT_GROUPS[group] || [];
    return slots.map(s => this._colBySlot(s, this.MAIN_COLS)).filter(Boolean);
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

  _hasFile(file) {
    if (!file) return false;
    if (file.storage_type === 'link') return !!(file.external_url || '').trim();
    return !!(file.file_path || '').trim();
  },

  _computeStats(b) {
    const mainSlots = this._fileSlots(this.MAIN_COLS);
    const scSlots = this._fileSlots(this.SC_COLS);
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
    let scRequiredTotal = rows.length * scSlots.filter(c => !c.optional).length;
    rows.forEach(sc => {
      const files = sc.files || {};
      scSlots.forEach(col => {
        const ok = this._hasFile(files[col.slot]);
        if (ok) scDone += 1;
        if (!col.optional && ok) scRequiredDone += 1;
      });
    });

    const mainTotal = mainSlots.length;
    const scTotal = rows.length * scSlots.length;
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
    const scSlots = this._fileSlots(this.SC_COLS);
    const files = sc.files || {};
    let done = 0;
    let requiredDone = 0;
    let requiredTotal = scSlots.filter(c => !c.optional).length;
    scSlots.forEach(col => {
      const ok = this._hasFile(files[col.slot]);
      if (ok) done += 1;
      if (!col.optional && ok) requiredDone += 1;
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
        const s = await api('GET', '/settings', null, { silent: true });
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

    this._renderLibraryBar(b);
    this._renderProgress(b);
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
        ? `分判顯示 SC 類主判項 ${n} 項（不含 M-/O- 物料及其他、已排除項）`
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
    const cols = this._mainColsForGroup(this._mainSubTab);
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
    const slots = this._fileSlots(this.SC_COLS);
    const pending = b._filesPending;

    if (!rows.length) {
      el.innerHTML = `<div class="iso-sc-empty">尚無分判資料 · 請先在「分判合約登記表」新增判項</div>`;
      return;
    }

    el.innerHTML = rows.map(sc => {
      const rs = this._scRowStats(sc);
      const pct = rs.total ? Math.round((rs.done / rs.total) * 100) : 0;
      const badgeCls = rs.requiredDone >= rs.requiredTotal ? 'iso-row-badge iso-row-badge-ok' : 'iso-row-badge iso-row-badge-warn';
      const badge = pending ? '' : `<span class="${badgeCls}" title="附件 ${rs.done}/${rs.total}">${pct}%</span>`;
      const tiles = slots.map(col => {
        const file = sc.files?.[col.slot];
        return this._slotTile('subcontractor', sc.id, col, file, pending);
      }).join('');
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
      const file = e.dataTransfer?.files?.[0];
      if (!file) return;
      const scope = tile.dataset.isoScope;
      const slot = tile.dataset.isoSlot;
      const scRaw = tile.dataset.isoScId;
      const scId = scRaw ? parseInt(scRaw, 10) : null;
      this.uploadFile(file, { scope, slot, scId: Number.isFinite(scId) ? scId : null });
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

    const head = `<thead><tr>${this.MAIN_COLS.map(c => this._thCell(c)).join('')}</tr></thead>`;

    const cells = this.MAIN_COLS.map(col => {
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
  },

  _suppAmountCell(p) {
    const val = p.supplemental_contract_amount ?? 0;
    const pid = p.id;
    return `<input type="number" class="iso-amt-input" step="0.01" min="0"
      value="${Number(val) || ''}" placeholder="0"
      onchange="IsoDocs.saveSupplemental(${pid}, this.value)"
      title="補充合約金額（可編輯）">`;
  },

  async saveSupplemental(projectId, raw) {
    const amount = parseFloat(raw) || 0;
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
    const head = `<thead><tr>${this.SC_COLS.map(c => this._thCell(c)).join('')}</tr></thead>`;

    if (!rows.length) {
      el.innerHTML = `${head}<tbody><tr><td colspan="${this.SC_COLS.length}" class="td-muted" style="padding:20px;text-align:center">尚無分判資料 · 請先在「分判合約登記表」新增判項</td></tr></tbody>`;
      return;
    }

    const body = rows.map(sc => {
      const rs = this._scRowStats(sc);
      const pct = rs.total ? Math.round((rs.done / rs.total) * 100) : 0;
      const badgeCls = rs.requiredDone >= rs.requiredTotal ? 'iso-row-badge iso-row-badge-ok' : 'iso-row-badge iso-row-badge-warn';
      const cells = this.SC_COLS.map(col => {
        if (col.kind === 'label') {
          const sub = sc.sc_no ? `<div class="iso-cell-sub">${escHtml(sc.sc_no)}</div>` : '';
          const badge = b._filesPending ? '' : `<span class="${badgeCls}" title="附件 ${rs.done}/${rs.total} · 必填 ${rs.requiredDone}/${rs.requiredTotal}">${pct}%</span>`;
          return this._tdSticky(col, `<div class="iso-label-wrap">${escHtml(sc.company_name_zh || '—')}${badge}</div>${sub}`);
        }
        if (col.kind === 'amount') {
          return this._tdSticky(col, fmt(sc.contract_amount));
        }
        const file = sc.files?.[col.slot];
        return `<td class="iso-file-cell${pending}${this._fileCellClass(file, col)}">${this._fileCell('subcontractor', sc.id, col.slot, file, b._filesPending, col.optional)}</td>`;
      }).join('');
      return `<tr>${cells}</tr>`;
    }).join('');

    el.innerHTML = `${head}<tbody>${body}</tbody>`;
  },

  _fileCellClass(file, col) {
    if (this._hasFile(file)) return ' iso-file-cell-done';
    if (col && col.optional) return ' iso-file-cell-optional';
    return ' iso-file-cell-missing';
  },

  async uploadFile(file, ctx) {
    if (!file || !ctx) return;
    const pid = App.currentProject?.id;
    if (!pid) {
      toast('請先選擇項目', 'warning');
      return;
    }
    const okExt = /\.(pdf|png|jpe?g|gif|webp)$/i.test(file.name);
    if (!okExt) {
      toast('只支援 PDF 或圖片格式', 'warning');
      return;
    }

    showLoading('上傳 ISO 文件…');
    try {
      const fd = new FormData();
      fd.append('file', file);
      fd.append('scope', ctx.scope);
      fd.append('doc_slot', ctx.slot);
      if (ctx.scId) fd.append('subcontractor_id', String(ctx.scId));

      const res = await fetch(`${API}/projects/${pid}/iso-documents/upload`, { method: 'POST', body: fd });
      const json = await res.json();
      if (!json.success) throw new Error(json.error || '上傳失敗');
      toast('文件已上傳', 'success');
      await this.load();
    } catch (e) {
      toast(e.message || '上傳失敗', 'error');
    } finally {
      hideLoading();
    }
  },

  _fileCell(scope, scId, slot, file, pending, optional) {
    if (pending && !file) {
      return '<span class="iso-file-placeholder">…</span>';
    }
    if (this._hasFile(file)) {
      const isLink = file.storage_type === 'link';
      const name = escHtml(file.link_label || file.original_filename || (isLink ? '外部連結' : file.file_path));
      const date = this._formatUploadDate(file.updated_at || file.created_at);
      const dateHtml = date ? `<span class="iso-file-date">${escHtml(date)}</span>` : '';
      const verCount = file.version_count || 0;
      const verBtn = verCount > 0
        ? `<button type="button" class="iso-file-action" title="歷史版本 (${verCount})" onclick="event.stopPropagation(); IsoDocs.showVersions('${scope}', '${slot}', ${scId || 'null'})">📚</button>`
        : '';
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
          ${verBtn}
          <button type="button" class="iso-file-action" title="更換" onclick="event.stopPropagation(); IsoDocs.pickUpload('${scope}', '${slot}', ${scId || 'null'})">↻</button>
          <button type="button" class="iso-file-action" title="填連結" onclick="event.stopPropagation(); IsoDocs.openLinkModal('${scope}', '${slot}', ${scId || 'null'})">🔗</button>
          <button type="button" class="iso-file-action iso-file-del" title="刪除" onclick="event.stopPropagation(); IsoDocs.deleteFile(${file.id})">×</button>
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
    const file = event.target?.files?.[0];
    if (event.target) event.target.value = '';
    const ctx = this._uploadCtx;
    this._uploadCtx = null;
    if (!file || !ctx) return;
    await this.uploadFile(file, ctx);
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
