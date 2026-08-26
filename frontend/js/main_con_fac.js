/* ─── main_con_fac.js — 主合約最終結算（PPT p19） ─────────── */
const MainConFac = {
  _data: null,

  async load() {
    const p = App.currentProject;
    const root = document.getElementById('mcfContent');
    if (!root) return;
    if (!p) {
      root.innerHTML = `<div class="empty-state" style="padding:48px"><div class="empty-icon">📁</div><div class="empty-title">請先選擇項目</div></div>`;
      return;
    }
    root.innerHTML = `<div class="empty-state" style="padding:40px"><div class="spinner"></div><div class="empty-sub">載入中…</div></div>`;
    try {
      this._data = await api('GET', `/projects/${p.id}/main-con-fac`);
      this.render();
    } catch (e) {
      root.innerHTML = `<div class="empty-state" style="padding:40px"><div class="empty-title">載入失敗</div></div>`;
    }
  },

  _hint(source, autoVal) {
    if (source === 'manual') return '<span class="mcf-hint">手動</span>';
    if (source?.startsWith('auto')) {
      return `<span class="mcf-hint" title="可留空用手動覆寫">自動 ${fmt(autoVal)}</span>`;
    }
    return '';
  },

  _attachLink(att) {
    if (!att?.path) return '—';
    const name = escHtml(att.name || '檔案');
    return `<a href="${uploadUrl(att.path)}" target="_blank" rel="noopener" class="mcf-pdf-link">📄 ${name}</a>`;
  },

  render() {
    const root = document.getElementById('mcfContent');
    const d = this._data;
    if (!root || !d) return;
    const s = d.settlement;
    const h = d.header;
    const kd = d.key_dates;
    const ed = d.editable || {};
    const retentionRows = (kd.retention_rows || []).map(r =>
      this._dateRow(`${r.label} ${r.label_en}`, r.date, r.note)
    ).join('');
    const dlpNoteParts = [];
    if (kd.retention_pct_display) {
      let s = `合約保固金 ${kd.retention_pct_display}`;
      if (kd.retention_max_pct_display) s += ` · 上限 ${kd.retention_max_pct_display}`;
      dlpNoteParts.push(s);
    }
    if (kd.retention_dlp_hint) dlpNoteParts.push(kd.retention_dlp_hint);
    const dlpNote = dlpNoteParts.join(' · ');
    const nameZh = (h.project_name_zh || '').trim();
    const nameEn = (h.project_name_en || '').trim();
    const worksMain = nameZh || nameEn || h.contract_works || '—';
    const worksSub = nameZh && nameEn ? nameEn : '';

    root.innerHTML = `
      <div class="mcf-header card" style="margin-bottom:16px">
        <div class="card-header">
          <div class="card-title">主合約 · ${escHtml(h.contract_no || '—')}</div>
          <button type="button" class="btn btn-secondary btn-sm" onclick="Projects.openEdit(App.currentProject.id)">✏️ 編輯工程項目</button>
        </div>
        <div class="card-body">
          <div class="mcf-works">${escHtml(worksMain)}</div>
          ${worksSub ? `<div class="mcf-works-en">${escHtml(worksSub)}</div>` : ''}
        </div>
      </div>

      <form id="mcfForm" onsubmit="MainConFac.save(event)">
        <div class="card" style="margin-bottom:16px">
          <div class="card-header">
            <div class="card-title">工程帳目總結算</div>
            <div style="font-size:11px;color:var(--text-muted)">Project Account Final Settlement · H=(A)…(G)</div>
          </div>
          <div class="table-wrap mcf-table-wrap">
            <table class="mcf-table">
              <tbody>
                ${this._row('A', '主合約總額 Original Contract Sum', s.a_original, { readonly: true })}
                ${this._rowInput('B', '重新測量調整 Remeasurement Adjustment', 'fac_remeasurement_b', ed.fac_remeasurement_b ?? s.b_remeasurement)}
                ${this._row('C', '補充合約 Supplemental Agreement', s.c_supplemental, { readonly: true, hint: 'Cover Page' })}
                ${this._rowInput('D', '變更工程總額 Variations', 'fac_variations_d_override', ed.fac_variations_d_override ?? '', { placeholder: fmtInputNum(s.d_auto), hint: this._hint(s.d_source, s.d_auto) })}
                ${this._rowInput('E', '暫定工程量調整 Adjustment of Provisional Quantities', 'fac_provisional_qty_e', ed.fac_provisional_qty_e ?? s.e_provisional_qty)}
                ${this._rowInput('F', '暫定金額調整 Adjustment of Provisional Sums', 'fac_provisional_sums_f', ed.fac_provisional_sums_f ?? s.f_provisional_sums)}
                ${this._rowInput('G', '物價波動調整 Fluctuations Adjustment', 'fac_fluctuations_g', ed.fac_fluctuations_g ?? s.g_fluctuations)}
                ${this._row('H', '結算工程總額 Final Contract Sum', s.h_final_sum, { total: true, formula: '(A)+(B)+(C)+(D)+(E)+(F)+(G)' })}
                ${this._rowInput('I', '(減) 已支付工程額 Total Value Previous Paid', 'fac_total_paid_i_override', ed.fac_total_paid_i_override ?? '', { placeholder: fmtInputNum(s.i_auto), hint: this._hint(s.i_source, s.i_auto), less: true, extra: `<input type="date" class="form-input mcf-asat" name="fac_paid_as_at_date" value="${escHtml(ed.fac_paid_as_at_date || s.i_as_at || '')}" title="as at 日期">` })}
                ${this._rowInput('J', '(減) 扣款費用 Contra Charge', 'fac_contra_charge_j_override', ed.fac_contra_charge_j_override ?? '', { placeholder: fmtInputNum(s.j_auto), hint: this._hint(s.j_source, s.j_auto), less: true })}
                ${this._row('K', '剩餘應付工程額 Outstanding Balance', s.k_outstanding, { total: true, formula: '(H)−(I)−(J)' })}
              </tbody>
            </table>
          </div>
          <div class="mcf-upload-row">
            <label class="form-label">工程帳目總結算書 Final account statement</label>
            <div class="mcf-upload-cell">
              <input type="file" class="form-input" id="mcfStatementFile" accept=".pdf,.png,.jpg,.jpeg">
              <div id="mcfStatementExisting">${this._attachLink(d.attachments.statement)}</div>
            </div>
          </div>
        </div>

        <div class="card" style="margin-bottom:16px">
          <div class="card-header">
            <div class="card-title">工程完工關鍵日期總覽</div>
            <div style="font-size:11px;color:var(--text-muted)">Overview of Project Completion Key Dates</div>
          </div>
          <div class="table-wrap mcf-table-wrap">
            <table class="mcf-table mcf-dates-table">
              <tbody>
                ${this._dateRow('開工日期 Commencement Date', kd.commencement_date)}
                ${this._dateRow('合約完工日期 Date for Completion', kd.completion_date)}
                ${this._dateRow('工期 Contract Period', kd.contract_period_days ? `${kd.contract_period_days} days` : '—')}
                ${this._dateRow('保修期 Defect Liability Period', kd.dlp_days ? `${kd.dlp_days} days` : (kd.dlp_months ? `${kd.dlp_months} months` : '—'), dlpNote)}
                ${this._rowInputPlain('延期罰款單價 Rate of LAD', 'fac_lad_rate', ed.fac_lad_rate ?? kd.lad_rate, { money: true })}
                ${this._rowInputPlain('延期罰款限額 Maximum Sum of LAD', 'fac_lad_max', ed.fac_lad_max ?? kd.lad_max, { money: true })}
                ${this._dateRow('實際完工日期 Date of Practical Completion', kd.pc_cert_date)}
                ${retentionRows}
                ${this._dateRow('保修期開始日期 Commencement of DLP', kd.dlp_commencement_date)}
                ${this._rowInputPlain('測試和調試完成日期 Testing & Commissioning', 'fac_testing_commission_date', ed.fac_testing_commission_date ?? kd.testing_commission_date, { date: true })}
                ${this._rowInputPlain('修補缺陷完工日期 Make Good Defect', 'fac_make_good_date', ed.fac_make_good_date ?? kd.make_good_date, { date: true })}
                ${this._dateRow('MP 工程帳目總結算日 MP FAC Signed', kd.mp_fac_signed_date)}
              </tbody>
            </table>
          </div>
          <div class="form-row mcf-upload-row">
            <div class="form-group">
              <label class="form-label">實際完工證書 PC Certificate</label>
              <input type="file" class="form-input" id="mcfPcCertFile" accept=".pdf,.png,.jpg,.jpeg">
              <div id="mcfPcExisting">${this._attachLink(d.attachments.pc_cert)}</div>
            </div>
            <div class="form-group">
              <label class="form-label">修補缺陷完工證書 Make Good Certificate</label>
              <input type="file" class="form-input" id="mcfMgCertFile" accept=".pdf,.png,.jpg,.jpeg">
              <div id="mcfMgExisting">${this._attachLink(d.attachments.mg_cert)}</div>
            </div>
          </div>
        </div>

        <div style="display:flex;gap:8px;justify-content:flex-end">
          <button type="button" class="btn btn-secondary" onclick="MainConFac.load()">↺ 重設</button>
          <button type="submit" class="btn btn-primary">💾 儲存</button>
        </div>
      </form>`;
  },

  _row(code, label, amount, opts = {}) {
    const cls = opts.total ? 'mcf-row-total' : '';
    const val = opts.less && amount > 0 ? -Math.abs(amount) : amount;
    const amtCls = val < 0 ? 'negative' : '';
    const formula = opts.formula ? `<span class="mcf-formula">${escHtml(opts.formula)}</span>` : '';
    return `<tr class="${cls}">
      <td class="mcf-label">${escHtml(label)} ${formula}</td>
      <td class="mcf-code">${code}</td>
      <td class="mcf-amt td-amount ${amtCls}">${fmtAcct(val)}</td>
    </tr>`;
  },

  _rowInput(code, label, name, value, opts = {}) {
    const hint = opts.hint || '';
    const extra = opts.extra || '';
    return `<tr>
      <td class="mcf-label">${escHtml(label)} ${hint}</td>
      <td class="mcf-code">${code}</td>
      <td class="mcf-amt-input">
        <div class="mcf-input-wrap">
          <input type="number" step="0.01" class="form-input" name="${name}" value="${value !== '' && value != null ? fmtInputNum(value) : ''}" placeholder="${escHtml(opts.placeholder || '0')}">
          ${extra}
        </div>
      </td>
    </tr>`;
  },

  _rowInputPlain(label, name, value, opts = {}) {
    const type = opts.date ? 'date' : (opts.money ? 'number' : 'text');
    const step = opts.money ? ' step="0.01"' : '';
    const val = value != null && value !== '' ? (opts.date ? String(value).slice(0, 10) : (opts.money ? fmtInputNum(value) : escHtml(String(value)))) : '';
    return `<tr>
      <td class="mcf-label" colspan="2">${escHtml(label)}</td>
      <td><input type="${type}" class="form-input" name="${name}" value="${val}"${step}></td>
    </tr>`;
  },

  _dateRow(label, value, note = '') {
    const v = value ? fmtDate(String(value).slice(0, 10)) : '—';
    const n = note ? ` <span class="mcf-hint">${escHtml(note)}</span>` : '';
    return `<tr>
      <td class="mcf-label" colspan="2">${escHtml(label)}${n}</td>
      <td class="td-muted">${v}</td>
    </tr>`;
  },

  _readForm() {
    const form = document.getElementById('mcfForm');
    if (!form) return {};
    const fd = new FormData(form);
    const data = {};
    fd.forEach((v, k) => { data[k] = v; });
    return data;
  },

  async _upload(type, inputId) {
    const p = App.currentProject;
    const file = document.getElementById(inputId)?.files?.[0];
    if (!p || !file) return;
    const fd = new FormData();
    fd.append('file', file);
    fd.append('type', type);
    const res = await fetch(`${API}/projects/${p.id}/main-con-fac/upload`, { method: 'POST', body: fd });
    const json = await res.json();
    if (!res.ok || !json.success) throw new Error(json.error || '上傳失敗');
  },

  async save(ev) {
    ev.preventDefault();
    const p = App.currentProject;
    if (!p) return;
    try {
      await api('POST', `/projects/${p.id}/main-con-fac`, this._readForm());
      await this._upload('statement', 'mcfStatementFile');
      await this._upload('pc_cert', 'mcfPcCertFile');
      await this._upload('mg_cert', 'mcfMgCertFile');
      toast('已儲存', 'success');
      await this.load();
    } catch (e) {
      toast(e.message || '儲存失敗', 'error');
    }
  },
};
