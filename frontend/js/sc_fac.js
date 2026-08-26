/* ─── sc_fac.js — 分判最終結算（PPT p20–21 · 每判項 PDF） ─── */
const ScFac = {
  _items: [],
  _header: null,
  _previewScId: null,
  _appVersion: '',
  _contractRegistry: null,
  _alignment: null,

  async _loadAppVersion() {
    try {
      const r = await api('GET', '/system/status');
      this._appVersion = r?.app_version || '';
    } catch (e) {
      this._appVersion = '';
    }
  },

  THEMES: [
    { id: 'mepork_grid', label: '清新格線' },
    { id: 'classic', label: '傳統會計（PPT 第20頁）' },
  ],
  THEME_STORAGE_KEY: 'qs_sc_fac_theme',
  DOCX_STORAGE_KEY: 'qs_sc_fac_show_docx',
  APPENDIX_VO_EMPTY_KEY: 'qs_sc_fac_appendix_vo_empty',
  APPENDIX_CONTRA_EMPTY_KEY: 'qs_sc_fac_appendix_contra_empty',

  showDocxExport() {
    return localStorage.getItem(this.DOCX_STORAGE_KEY) === '1';
  },

  enableDocxExport() {
    localStorage.setItem(this.DOCX_STORAGE_KEY, '1');
    this.render();
    toast('已顯示 Word 匯出', 'success');
  },

  disableDocxExport() {
    localStorage.removeItem(this.DOCX_STORAGE_KEY);
    this.render();
    toast('已隱藏 Word 匯出', 'success');
  },

  getTheme() {
    const saved = localStorage.getItem(this.THEME_STORAGE_KEY);
    return this.THEMES.some(t => t.id === saved) ? saved : 'mepork_grid';
  },

  setTheme(theme) {
    if (this.THEMES.some(t => t.id === theme)) {
      localStorage.setItem(this.THEME_STORAGE_KEY, theme);
    }
  },

  themeLabel(theme) {
    return this.THEMES.find(t => t.id === theme)?.label || theme;
  },

  getPrintEmptyVo() {
    return localStorage.getItem(this.APPENDIX_VO_EMPTY_KEY) === '1';
  },

  getPrintEmptyContra() {
    return localStorage.getItem(this.APPENDIX_CONTRA_EMPTY_KEY) === '1';
  },

  setPrintEmptyVo(on) {
    if (on) localStorage.setItem(this.APPENDIX_VO_EMPTY_KEY, '1');
    else localStorage.removeItem(this.APPENDIX_VO_EMPTY_KEY);
  },

  setPrintEmptyContra(on) {
    if (on) localStorage.setItem(this.APPENDIX_CONTRA_EMPTY_KEY, '1');
    else localStorage.removeItem(this.APPENDIX_CONTRA_EMPTY_KEY);
  },

  onAppendixEmptyChange(which, checked) {
    if (which === 'vo') this.setPrintEmptyVo(checked);
    else this.setPrintEmptyContra(checked);
    this.render();
  },

  _appendixViewerOptions(scId) {
    const item = (this._items || []).find(x => x.sc_id == scId);
    if (!item) return null;
    const opts = {};
    if (!item.has_appendix_vo) {
      opts.vo = { checked: this.getPrintEmptyVo(), label: '附錄 I（無 VO 時仍列印）' };
    }
    if (!item.has_appendix_contra) {
      opts.contra = { checked: this.getPrintEmptyContra(), label: '附錄 II（無 Contra 時仍列印）' };
    }
    return (opts.vo || opts.contra) ? opts : null;
  },

  _resolveAppendixPages(scId) {
    const item = (this._items || []).find(x => x.sc_id == scId);
    if (!item) return { vo: false, contra: false };
    return {
      vo: !!item.has_appendix_vo || this.getPrintEmptyVo(),
      contra: !!item.has_appendix_contra || this.getPrintEmptyContra(),
    };
  },

  _appendixPagesSubtitle(includeVo, includeContra, scId) {
    const item = (this._items || []).find(x => x.sc_id == scId);
    const pages = ['P1 結算'];
    const skipped = [];
    if (includeVo) {
      const blank = item && !item.has_appendix_vo && this.getPrintEmptyVo();
      pages.push(blank ? '附錄 I（空白附錄）' : '附錄 I');
    } else {
      skipped.push('附錄 I 不列印');
    }
    if (includeContra) {
      const blank = item && !item.has_appendix_contra && this.getPrintEmptyContra();
      pages.push(blank ? '附錄 II（空白附錄）' : '附錄 II');
    } else {
      skipped.push('附錄 II 不列印');
    }
    let s = `列印 ${pages.length} 頁：${pages.join(' · ')}`;
    if (skipped.length) s += `（${skipped.join(' · ')}）`;
    return s;
  },

  _appendixOptionsHtml(items) {
    const anyMissingVo = (items || []).some(r => !r.has_appendix_vo);
    const anyMissingContra = (items || []).some(r => !r.has_appendix_contra);
    if (!anyMissingVo && !anyMissingContra) return '';
    const voChk = this.getPrintEmptyVo() ? ' checked' : '';
    const contraChk = this.getPrintEmptyContra() ? ' checked' : '';
    const activeHint = (this.getPrintEmptyVo() || this.getPrintEmptyContra())
      ? '<span class="sc-fac-appendix-active">已啟用空白附錄 — 預覽會額外列印勾選的附錄頁</span>'
      : '';
    const voLine = anyMissingVo
      ? `<label class="sc-fac-appendix-opt"><input type="checkbox"${voChk} onchange="ScFac.onAppendixEmptyChange('vo', this.checked)"> 附錄 I（無 VO 時仍列印）</label>`
      : '';
    const contraLine = anyMissingContra
      ? `<label class="sc-fac-appendix-opt"><input type="checkbox"${contraChk} onchange="ScFac.onAppendixEmptyChange('contra', this.checked)"> 附錄 II（無 Contra 時仍列印）</label>`
      : '';
    return `
      <div class="sc-fac-appendix-bar${activeHint ? ' sc-fac-appendix-bar-on' : ''}">
        <span class="sc-fac-appendix-label">空白附錄</span>
        ${voLine}${contraLine}
        ${activeHint}
        <span class="sc-fac-appendix-hint">有 VO／扣款資料時會自動列印附錄</span>
      </div>`;
  },

  _appendixQuery(scId) {
    const item = (this._items || []).find(x => x.sc_id == scId);
    if (!item) return '';
    const q = [];
    if (!item.has_appendix_vo && this.getPrintEmptyVo()) q.push('appendix_vo=1');
    if (!item.has_appendix_contra && this.getPrintEmptyContra()) q.push('appendix_contra=1');
    return q.length ? `&${q.join('&')}` : '';
  },

  _alignBadge(status) {
    const map = {
      aligned: '<span class="sc-contract-badge sc-contract-aligned" title="已對齊 MS/C">✓</span>',
      missing: '<span class="sc-contract-badge sc-contract-missing" title="缺 MS/C 編號">!</span>',
      na: '<span class="sc-contract-badge sc-contract-na" title="無需 MS/C（O/M 等）">—</span>',
    };
    return map[status] || '';
  },

  _contractRegistryBar() {
    const reg = this._contractRegistry || {};
    const al = this._alignment || {};
    const last = reg.last_import;
    const imported = last?.imported_at
      ? `上次同步 ${escHtml(String(last.imported_at).slice(0, 16))}`
      : '尚未同步';
    const count = reg.row_count != null ? reg.row_count : '—';
    const orphanHint = al.excel_unlinked > 0
      ? `<span class="sc-contract-orphan-hint">Excel 有 ${al.excel_unlinked} 筆本項目尚未建判項</span>`
      : '';
    const orphanList = (al.orphans || []).length
      ? `<details class="sc-contract-orphan-details"><summary>未建判項 MS/C 示例</summary><ul>${al.orphans.map(o =>
          `<li><code>${escHtml(o.sub_contract_no)}</code> ${escHtml(o.company || '')}</li>`
        ).join('')}</ul></details>`
      : '';
    return `
      <div class="sc-contract-registry-bar">
        <span class="sc-contract-registry-label">分判合約編號</span>
        <span class="sc-contract-registry-meta">資料庫 ${escHtml(String(count))} 筆 · ${imported}</span>
        <button type="button" class="btn btn-secondary btn-sm" onclick="ScFac.syncContractRegistry()">🔄 同步 Ref Excel</button>
        <button type="button" class="btn btn-secondary btn-sm" onclick="App.navigate('sc-contract-registry')">🔗 分判合約編號</button>
        <span class="sc-contract-align-summary">
          已對齊 <strong>${al.aligned || 0}</strong> ·
          缺 MS/C <strong class="${al.missing ? 'sc-contract-warn' : ''}">${al.missing || 0}</strong> ·
          無需 <strong>${al.na || 0}</strong>
        </span>
        ${orphanHint}
        ${orphanList}
      </div>`;
  },

  async syncContractRegistry() {
    showLoading('正在同步分判合約編號…');
    try {
      const r = await api('POST', '/sc-contract-registry/sync');
      toast(`已同步 ${r.rows_read || 0} 筆（新增 ${r.rows_new || 0} · 更新 ${r.rows_updated || 0}）`, 'success');
      await this.load();
    } catch (e) {
      toast(e.message || '同步失敗', 'error');
    } finally {
      hideLoading();
    }
  },

  _parseScFacPayload(data) {
    if (Array.isArray(data)) {
      this._items = data;
      this._contractRegistry = null;
      this._alignment = null;
      return;
    }
    this._items = data?.items || [];
    this._contractRegistry = data?.contract_registry || null;
    this._alignment = data?.alignment || null;
  },

  _themeSelectHtml(id, onChange) {
    const cur = this.getTheme();
    const opts = this.THEMES.map(t =>
      `<option value="${escHtml(t.id)}"${t.id === cur ? ' selected' : ''}>${escHtml(t.label)}</option>`
    ).join('');
    return `
      <div class="sc-fac-theme-bar">
        <label for="${id}">打印主題</label>
        <select id="${id}" class="form-input" onchange="${onChange}(this.value)">${opts}</select>
      </div>`;
  },

  async load() {
    const root = document.getElementById('scFacContent');
    if (!root) return;
    const p = App.currentProject;
    if (!p) {
      root.innerHTML = `<div class="empty-state" style="padding:48px"><div class="empty-icon">📁</div><div class="empty-title">請先選擇項目</div></div>`;
      return;
    }
    root.innerHTML = `<div class="empty-state" style="padding:40px"><div class="spinner"></div><div class="empty-sub">載入中…</div></div>`;
    try {
      await this._loadAppVersion();
      const [facPayload, fac] = await Promise.all([
        api('GET', `/projects/${p.id}/sc-fac`),
        api('GET', `/projects/${p.id}/main-con-fac`).catch(() => null),
      ]);
      this._parseScFacPayload(facPayload);
      this._header = fac?.header || null;
      this.render();
    } catch (e) {
      root.innerHTML = `<div class="empty-state" style="padding:40px"><div class="empty-title">載入失敗</div></div>`;
    }
  },

  onThemeChange(theme) {
    this.setTheme(theme);
    this.render();
  },

  _projectHero() {
    const h = this._header;
    const p = App.currentProject;
    let nameZh = '';
    let nameEn = '';
    let contractNo = '—';
    if (h) {
      contractNo = h.contract_no || '—';
      nameZh = (h.project_name_zh || '').trim();
      nameEn = (h.project_name_en || '').trim();
    } else if (p) {
      const parts = projectNameParts(p);
      nameZh = parts.zh;
      nameEn = parts.en;
      contractNo = p.mp_contract_code || p.project_code || '—';
    }
    const worksMain = nameZh || nameEn || h?.contract_works || p?.project_code || '—';
    const worksSub = nameZh && nameEn ? nameEn : '';
    return `
      <div class="mcf-header card" style="margin-bottom:16px">
        <div class="card-header">
          <div class="card-title">主合約 · ${escHtml(contractNo)}</div>
          <button type="button" class="btn btn-secondary btn-sm" onclick="Projects.openEdit(App.currentProject.id)">✏️ 編輯工程項目</button>
        </div>
        <div class="card-body">
          <div class="mcf-works">${escHtml(worksMain)}</div>
          ${worksSub ? `<div class="mcf-works-en">${escHtml(worksSub)}</div>` : ''}
        </div>
      </div>`;
  },

  render() {
    const root = document.getElementById('scFacContent');
    if (!root) return;
    const items = this._items || [];
    const hero = this._projectHero();
    const themeBar = this._themeSelectHtml('scFacThemeSelect', 'ScFac.onThemeChange');
    const appendixBar = this._appendixOptionsHtml(items);
    const contractBar = this._contractRegistryBar();
    const curTheme = this.getTheme();
    const ver = this._appVersion ? ` · 後端 ${escHtml(this._appVersion)}` : '';
    const classicHint = curTheme === 'classic'
      ? '<span style="color:var(--primary)">目前主題：<strong>傳統會計</strong>（P2 八欄 VO · P3 Contra 四欄）</span>'
      : '<span style="color:#b45309">PPT 對照版面請先改選 <strong>傳統會計（PPT 第20頁）</strong> 再預覽</span>';

    if (!items.length) {
      root.innerHTML = `${hero}
      <div class="empty-state" style="padding:48px">
        <div class="empty-icon">📋</div>
        <div class="empty-title">暫無可結算判項</div>
        <div class="empty-sub">請先在分判付款登記新增判項</div>
      </div>`;
      return;
    }
    const showDocx = this.showDocxExport();
    const rows = items.map(r => {
      const co = escHtml(r.company_name_zh || r.company_name_en || '—');
      const docxBtn = showDocx
        ? `<button type="button" class="btn btn-secondary btn-sm" onclick="ScFac.downloadDocx(${r.sc_id})">📝 匯出 Word</button>`
        : '';
      const subNo = r.sub_contract_no && r.sub_contract_no !== '—'
        ? escHtml(r.sub_contract_no)
        : '<span class="text-muted">—</span>';
      const alignBadge = this._alignBadge(r.contract_align);
      return `<tr>
        <td>${fmtRefNo(r.sc_no)}</td>
        <td>${co}</td>
        <td class="sc-contract-no-cell">${subNo} ${alignBadge}</td>
        <td class="td-amount">${fmtAcct(r.original_sum)}</td>
        <td class="td-amount">${fmtAcct(r.variations)}</td>
        <td class="td-amount">${fmtAcct(r.final_sum)}</td>
        <td class="td-amount">${fmtAcct(r.total_paid)}</td>
        <td class="td-amount ${r.outstanding < 0 ? 'negative' : ''}">${fmtAcct(r.outstanding)}</td>
        <td class="td-actions">
          <button type="button" class="btn btn-primary btn-sm" onclick="ScFac.previewPdf(${r.sc_id})">👁 預覽</button>
          ${docxBtn}
        </td>
      </tr>`;
    }).join('');
    const docxHint = showDocx
      ? '<strong>匯出 Word</strong>：可於 Word 微調後交回對照 PDF。<br>'
      : '';

    root.innerHTML = `
      ${hero}
      <div class="card" style="margin-bottom:16px">
        <div class="card-header">
          <div class="card-title">分判最終結算 · SC Final Account</div>
          <div style="font-size:11px;color:var(--text-muted)">每判項 PDF · P1 結算＋附錄（有資料自動加入 · 1–3 頁）${ver}</div>
        </div>
        <div class="card-body" style="font-size:12px;color:var(--text-muted);line-height:1.6">
          ${themeBar}
          ${contractBar}
          ${appendixBar}
          ${classicHint}<br>
          <strong>清新格線</strong>：格線版 · <strong>傳統會計</strong>：PPT 對照版。<br>
          預覽每次重新生成；若未更新請 <strong>Ctrl+F5</strong> 強制重新整理。<br>
          ${docxHint}
        </div>
      </div>
      <div class="card">
        <div class="table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th>判項</th>
                <th>分判商</th>
                <th>MS/C 合約編號</th>
                <th class="td-amount">合約價</th>
                <th class="td-amount">VO</th>
                <th class="td-amount">結算總額</th>
                <th class="td-amount">已付</th>
                <th class="td-amount">剩餘</th>
                <th></th>
              </tr>
            </thead>
            <tbody>${rows}</tbody>
          </table>
        </div>
      </div>`;
  },

  _pdfMeta(scId) {
    const p = App.currentProject;
    const item = (this._items || []).find(x => x.sc_id == scId);
    const scNo = item?.sc_no || scId;
    const safe = String(scNo).replace(/[^\w\-]+/g, '_');
    const base = `${API}/projects/${p.id}/subcontractors/${scId}/sc-fac/pdf`;
    return { p, scNo, safe, base, filename: `SC_FAC_${safe}.pdf` };
  },

  _pdfUrl(base, inline, theme, scId) {
    const th = theme || this.getTheme();
    const mode = inline ? 'inline=1' : 'download=1';
    const apx = scId != null ? this._appendixQuery(scId) : '';
    return `${base}?${mode}&theme=${encodeURIComponent(th)}${apx}&_t=${Date.now()}`;
  },

  async _fetchPdfBlob(scId, theme) {
    const meta = this._pdfMeta(scId);
    if (!meta.p) throw new Error('請先選擇項目');
    const url = this._pdfUrl(meta.base, true, theme, scId);
    const r = await fetch(url);
    const ct = r.headers.get('Content-Type') || '';
    if (!r.ok) {
      let msg = `載入失敗（HTTP ${r.status}）`;
      if (ct.includes('application/json')) {
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
    return {
      meta,
      blob: await r.blob(),
      serverVersion: r.headers.get('X-App-Version') || '',
      appendixVo: r.headers.get('X-SC-FAC-Appendix-Vo') === '1',
      appendixContra: r.headers.get('X-SC-FAC-Appendix-Contra') === '1',
    };
  },

  async _openPreview(scId, theme, { showLoadingOverlay = true } = {}) {
    if (showLoadingOverlay) showLoading('正在載入預覽…');
    else DocViewer.setLoading(true);
    try {
      const { meta, blob, serverVersion, appendixVo, appendixContra } = await this._fetchPdfBlob(scId, theme);
      const verTag = serverVersion ? ` · ${serverVersion}` : '';
      const title = `分判最終結算 · ${meta.scNo} · ${this.themeLabel(theme)}${verTag}`;
      const subtitle = this._appendixPagesSubtitle(appendixVo, appendixContra, scId);
      const viewerOpts = {
        kind: 'pdf',
        subtitle,
        downloadUrl: this._pdfUrl(meta.base, false, theme, scId),
        downloadName: meta.filename,
        themes: this.THEMES,
        theme,
        appendixOptions: this._appendixViewerOptions(scId),
        onThemeChange: async (next) => {
          this.setTheme(next);
          const sel = document.getElementById('scFacThemeSelect');
          if (sel) sel.value = next;
          await this._openPreview(scId, next, { showLoadingOverlay: false });
        },
        onAppendixChange: async (which, checked) => {
          this.onAppendixEmptyChange(which, checked);
          await this._openPreview(scId, this.getTheme(), { showLoadingOverlay: false });
        },
      };
      await DocViewer.openBlob(blob, title, viewerOpts);
    } finally {
      if (showLoadingOverlay) hideLoading();
      else DocViewer.setLoading(false);
    }
  },

  async previewPdf(scId) {
    this._previewScId = scId;
    const theme = this.getTheme();
    await this._openPreview(scId, theme);
  },

  _docxUrl(base, theme) {
    const th = theme || this.getTheme();
    return `${base.replace(/\/pdf$/, '/docx')}?theme=${encodeURIComponent(th)}&_t=${Date.now()}`;
  },

  async downloadDocx(scId) {
    const meta = this._pdfMeta(scId);
    if (!meta.p) return;
    const theme = this.getTheme();
    const url = this._docxUrl(meta.base, theme);
    showLoading('正在生成 Word…');
    try {
      const r = await fetch(url);
      const ct = r.headers.get('Content-Type') || '';
      if (!r.ok) {
        let msg = `匯出失敗（HTTP ${r.status}）`;
        if (ct.includes('application/json')) {
          try {
            const j = await r.json();
            if (j.error) msg = j.error;
          } catch (e) { /* ignore */ }
        }
        throw new Error(msg);
      }
      const blob = await r.blob();
      const blobUrl = URL.createObjectURL(blob);
      const suffix = theme === 'classic' ? '_classic' : '';
      const a = document.createElement('a');
      a.href = blobUrl;
      a.download = meta.filename.replace('.pdf', `${suffix}.docx`);
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(blobUrl);
      toast(`已匯出 ${meta.scNo} Word（${this.themeLabel(theme)}）`, 'success');
    } catch (e) {
      toast(e.message || 'Word 匯出失敗', 'error');
    } finally {
      hideLoading();
    }
  },
};
