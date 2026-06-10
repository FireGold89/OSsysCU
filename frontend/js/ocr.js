/* ─── ocr.js — 發票單、報價單識別 v2（分流儲存）────────────── */
const OCR = {
  currentPdfPath: null,
  currentOcrId: null,
  currentOriginalFilename: null,
  lineItems: [],
  docType: 'unknown',
  docTypeConfidence: 0,
  _scSuggestions: [],
  _newScManual: false,
  _prefixPicked: false,

  populateScOptions() {
    const sel = document.getElementById('ocrScNo');
    const cur = sel?.value;
    if (!sel) return;
    sel.innerHTML = '<option value="">— 選擇參考編號 —</option>';
    (App.scList || []).forEach(sc => {
      const opt = document.createElement('option');
      opt.value = sc.sc_no;
      opt.textContent = `${sc.sc_no} — ${sc.company_name_en || sc.company_name_zh || ''}`.substring(0, 45);
      sel.appendChild(opt);
    });
    if (cur) sel.value = cur;
  },

  onDragOver(e) {
    e.preventDefault();
    document.getElementById('dropZone').classList.add('drag-over');
  },

  onDragLeave(e) {
    document.getElementById('dropZone').classList.remove('drag-over');
  },

  onDrop(e) {
    e.preventDefault();
    document.getElementById('dropZone').classList.remove('drag-over');
    const file = e.dataTransfer.files[0];
    if (file) this.processFile(file);
  },

  onFileSelect(e) {
    const file = e.target.files[0];
    if (file) this.processFile(file);
  },

  /* ── 項目明細表格 ── */
  renderLineItems(items) {
    this.lineItems = (items || []).map((it, i) => ({
      no: it.no || String(i + 1),
      description: it.description || '',
      qty: it.qty != null ? String(it.qty) : '',
      unit: it.unit || '',
      unit_price: it.unit_price != null && it.unit_price !== '' ? it.unit_price : '',
      amount: it.amount != null && it.amount !== '' ? it.amount : '',
    }));

    const tbody = document.getElementById('ocrItemsBody');
    if (!this.lineItems.length) {
      tbody.innerHTML = '<tr><td colspan="7" class="ocr-items-empty">未識別到項目明細，可手動新增</td></tr>';
      this.syncDescription();
      return;
    }

    tbody.innerHTML = this.lineItems.map((it, idx) => `
      <tr data-idx="${idx}">
        <td><input type="text" value="${this.esc(it.no)}" data-field="no" oninput="OCR.onItemChange(${idx})"></td>
        <td><input type="text" value="${this.esc(it.description)}" data-field="description" oninput="OCR.onItemChange(${idx})"></td>
        <td><input type="text" value="${this.esc(it.qty)}" data-field="qty" oninput="OCR.onItemChange(${idx})"></td>
        <td><input type="text" value="${this.esc(it.unit)}" data-field="unit" oninput="OCR.onItemChange(${idx})"></td>
        <td><input type="number" value="${it.unit_price}" data-field="unit_price" step="0.01" oninput="OCR.onItemChange(${idx})"></td>
        <td><input type="number" value="${it.amount}" data-field="amount" step="0.01" oninput="OCR.onItemChange(${idx})"></td>
        <td><button type="button" class="btn-del" onclick="OCR.removeLineItem(${idx})" title="刪除">×</button></td>
      </tr>
    `).join('');

    this.syncDescription();
  },

  esc(s) {
    return String(s ?? '')
      .replace(/&/g, '&amp;')
      .replace(/"/g, '&quot;')
      .replace(/</g, '&lt;');
  },

  readLineItemsFromDom() {
    const rows = document.querySelectorAll('#ocrItemsBody tr[data-idx]');
    const items = [];
    rows.forEach((row, i) => {
      const get = (field) => row.querySelector(`[data-field="${field}"]`)?.value?.trim() ?? '';
      const desc = get('description');
      if (!desc && !get('amount')) return;
      items.push({
        no: get('no') || String(i + 1),
        description: desc,
        qty: get('qty'),
        unit: get('unit'),
        unit_price: get('unit_price'),
        amount: get('amount'),
      });
    });
    this.lineItems = items;
    return items;
  },

  onItemChange(idx) {
    this.readLineItemsFromDom();
    this.syncDescription();
  },

  addLineItem() {
    const tbody = document.getElementById('ocrItemsBody');
    if (tbody.querySelector('.ocr-items-empty')) {
      tbody.innerHTML = '';
    }
    const n = this.lineItems.length + 1;
    this.lineItems.push({ no: String(n), description: '', qty: '', unit: '', unit_price: '', amount: '' });
    this.renderLineItems(this.lineItems);
  },

  removeLineItem(idx) {
    this.lineItems.splice(idx, 1);
    this.renderLineItems(this.lineItems.length ? this.lineItems : []);
  },

  fmtNum(v) {
    const n = parseFloat(v);
    if (isNaN(n)) return '';
    return n.toLocaleString('en-HK', { minimumFractionDigits: FMT_DECIMALS, maximumFractionDigits: FMT_DECIMALS });
  },

  parseRawLineItems(text) {
    if (!text) return [];
    const t = text.replace(/\r\n/g, '\n');
    const items = [];
    const re = /([A-Za-z][A-Za-z0-9,\s\-.+&/]{6,}?)\s*(\d{1,6})\s*[個个]\s*(\d{1,7})[-.]?\s*(\d{3,9})[-.]?/gi;
    let m;
    while ((m = re.exec(t)) !== null) {
      const desc = m[1].replace(/\s+/g, ' ').trim();
      if (/^(Tel|Fax|QUANTITY|UNIT|AMOUNT)/i.test(desc)) continue;
      items.push({
        no: String(items.length + 1),
        description: desc,
        qty: m[2],
        unit: '個',
        unit_price: m[3],
        amount: m[4],
      });
    }
    return items;
  },

  parseDescriptionTable(text) {
    const lines = (text || '').split('\n').map(l => l.trim()).filter(Boolean);
    const headerIdx = lines.findIndex(l => l.includes('項目描述') || l.includes('\t'));
    if (headerIdx < 0) return [];
    const items = [];
    for (let i = headerIdx + 1; i < lines.length; i++) {
      const parts = lines[i].split('\t');
      if (parts.length < 2) continue;
      const desc = parts[1] || parts[0];
      if (!desc || desc.length < 2) continue;
      items.push({
        no: parts[0] || String(items.length + 1),
        description: desc,
        qty: parts[2] || '',
        unit: parts[3] || '',
        unit_price: parts[4] || '',
        amount: parts[5] || '',
      });
    }
    return items;
  },

  buildDescriptionText(items) {
    if (!items.length) return '';
    const title = items.length === 1
      ? items[0].description
      : `工程/服務項目（共 ${items.length} 項）`;
    const lines = [
      title,
      '',
      '項次\t項目描述\t數量\t單位\t單價(HK$)\t金額(HK$)',
    ];
    items.forEach((it, i) => {
      lines.push([
        it.no || String(i + 1),
        it.description || '',
        it.qty || '',
        it.unit || '',
        this.fmtNum(it.unit_price),
        this.fmtNum(it.amount),
      ].join('\t'));
    });
    return lines.join('\n');
  },

  syncDescription() {
    const items = this.lineItems;
    const totalEl = document.getElementById('ocrItemsTotal');
    let sum = 0;
    items.forEach(it => {
      const a = parseFloat(it.amount);
      if (!isNaN(a)) sum += a;
    });
    if (totalEl) {
      totalEl.innerHTML = items.length
        ? `明細合計: <strong>${fmt(sum)}</strong> (${items.length} 項)`
        : '';
    }
    document.getElementById('ocrDescription').value = this.buildDescriptionText(items);
    if (sum > 0 && !document.getElementById('ocrAmount').value) {
      document.getElementById('ocrAmount').value = fmtInputNum(sum);
    }
    this.validateAmountMismatch();
  },

  getDocType() {
    const picked = document.querySelector('input[name="ocrDocType"]:checked');
    return picked ? picked.value : this.docType;
  },

  setDocType(type, confidence = 0) {
    this.docType = type || 'unknown';
    this.docTypeConfidence = confidence || 0;
    const bar = document.getElementById('ocrDocTypeBar');
    const badge = document.getElementById('ocrDocTypeBadge');
    const confEl = document.getElementById('ocrDocTypeConf');
    if (bar) bar.style.display = '';
    const labels = { invoice: '發票單', quotation: '報價單', unknown: '待確認' };
    const badges = { invoice: 'success', quotation: 'info', unknown: 'warning' };
    if (badge) {
      badge.textContent = labels[this.docType] || '待確認';
      badge.className = `badge badge-${badges[this.docType] || 'muted'}`;
    }
    if (confEl) {
      confEl.textContent = this.docType !== 'unknown'
        ? `信心 ${this.docTypeConfidence.toFixed(0)}%` : '請選擇文件類型';
    }
    const radio = document.querySelector(`input[name="ocrDocType"][value="${this.docType}"]`);
    if (radio) radio.checked = true;
    else if (this.docType === 'unknown') {
      document.querySelectorAll('input[name="ocrDocType"]').forEach(r => { r.checked = false; });
    }
    this.updateDocTypeFields();
  },

  onDocTypeChange() {
    this.docType = this.getDocType();
    this.updateDocTypeFields();
    this.checkDuplicateInvoice();
  },

  onScChange() {
    this.updateDocTypeFields();
  },

  onScPrefixChange() {
    this._prefixPicked = true;
    this._newScManual = false;
    this.suggestNextScNo();
  },

  updateDocTypeFields() {
    const type = this.getDocType();
    const hasSc = !!document.getElementById('ocrScNo')?.value;
    const grp = document.getElementById('ocrNewScGroup');
    const showNew = type === 'quotation' && !hasSc;
    if (grp) grp.style.display = showNew ? '' : 'none';
    if (showNew) this.suggestNextScNo();

    const invRow = document.getElementById('ocrInvoiceRow');
    const quotRow = document.getElementById('ocrQuotationRow');
    if (invRow) invRow.style.display = type === 'quotation' ? 'none' : '';
    if (quotRow) quotRow.style.display = type === 'invoice' ? 'none' : '';
  },

  _normCompany(name) {
    return String(name || '').trim().toLowerCase().replace(/\s+/g, ' ');
  },

  _companyMatchesSc(sc, company) {
    const norm = this._normCompany(company);
    if (!norm) return false;
    for (const field of ['company_name_en', 'company_name_zh']) {
      const val = this._normCompany(sc[field]);
      if (!val) continue;
      if (norm === val || norm.includes(val) || val.includes(norm)) return true;
    }
    return false;
  },

  _parseScNo(scNo) {
    const m = String(scNo || '').trim().match(/^(SC|M|O)-(\d+)(?:\.(\d+))?(.*)$/i);
    if (!m) return null;
    const tail = (m[4] || '').trim().toUpperCase();
    const letter = tail && /^[A-Z]{1,2}$/.test(tail) ? tail : null;
    return {
      prefix: m[1].toUpperCase(),
      main: parseInt(m[2], 10),
      sub: m[3] != null ? parseInt(m[3], 10) : null,
      letter,
    };
  },

  _suggestNextScNoClient(prefix, company) {
    const list = App.scList || [];
    prefix = (prefix || 'SC').toUpperCase();
    if (!['SC', 'M', 'O'].includes(prefix)) prefix = 'SC';

    const allNos = list
      .map(s => (s.sc_no || '').trim())
      .filter(no => no.toUpperCase().startsWith(prefix + '-'));

    const companyNos = company
      ? list.filter(s => this._companyMatchesSc(s, company))
        .map(s => (s.sc_no || '').trim())
        .filter(no => no.toUpperCase().startsWith(prefix + '-'))
      : [];

    if (companyNos.length) {
      const base = companyNos[0];
      const parent = deriveParentScNo(base) || base;
      const siblings = allNos.filter(no => no === parent || deriveParentScNo(no) === parent);
      const letters = [];
      const subs = [];
      const parentParsed = this._parseScNo(parent);
      siblings.forEach(no => {
        const p = this._parseScNo(no);
        if (!p) return;
        if (p.letter) letters.push(p.letter);
        if (p.sub != null) subs.push(p.sub);
      });

      if (letters.length && parentParsed) {
        const nxt = String.fromCharCode(Math.max(...letters.map(c => c.charCodeAt(0))) + 1);
        return {
          sc_no: `${parentParsed.prefix}-${String(parentParsed.main).padStart(3, '0')}${nxt}`,
          reason: `同公司已有 ${base}，延續字母後綴`,
        };
      }
      if (subs.length && parentParsed) {
        return {
          sc_no: `${parentParsed.prefix}-${String(parentParsed.main).padStart(3, '0')}.${Math.max(...subs) + 1}`,
          reason: `同公司已有 ${base}，延續子編號`,
        };
      }
      if (parentParsed && base === parent) {
        return {
          sc_no: `${parentParsed.prefix}-${String(parentParsed.main).padStart(3, '0')}A`,
          reason: `同公司已有 ${parent}，加字母後綴`,
        };
      }
      if (parentParsed) {
        return {
          sc_no: `${parentParsed.prefix}-${String(parentParsed.main).padStart(3, '0')}.1`,
          reason: `同公司已有 ${base}，新增子編號`,
        };
      }
    }

    const mainNums = allNos.map(no => this._parseScNo(no)?.main).filter(n => n != null);
    const nextMain = mainNums.length ? Math.max(...mainNums) + 1 : 1;
    return {
      sc_no: `${prefix}-${String(nextMain).padStart(3, '0')}`,
      reason: '新分包商，使用下一個主編號',
    };
  },

  _suggestScMatchesClient(hints) {
    const list = App.scList || [];
    if (!list.length) return [];
    const qNo = (hints.quotation_no || '').trim().toLowerCase();
    const company = (hints.company || '').trim().toLowerCase();
    const scHint = (hints.sc_no || '').trim().toUpperCase();
    const amount = parseFloat(hints.amount) || 0;
    const results = [];

    list.forEach(sc => {
      let score = 0;
      const reasons = [];
      const scNo = (sc.sc_no || '').toUpperCase();
      if (scHint && scNo === scHint) { score += 120; reasons.push('參考編號相符'); }
      if (qNo && sc.quotation_no) {
        const sq = String(sc.quotation_no).trim().toLowerCase();
        if (qNo === sq || qNo.includes(sq) || sq.includes(qNo)) {
          score += 100;
          reasons.push('報價單號相符');
        }
      }
      if (company) {
        for (const field of ['company_name_en', 'company_name_zh']) {
          const val = (sc[field] || '').trim().toLowerCase();
          if (!val) continue;
          if (company === val || company.includes(val) || val.includes(company)) {
            score += 40;
            reasons.push('公司名稱相符');
            break;
          }
        }
      }
      if (amount > 0 && sc.contract_amount) {
        const ca = parseFloat(sc.contract_amount) || 0;
        if (ca > 0 && Math.abs(ca - amount) / ca < 0.05) {
          score += 25;
          reasons.push('金額接近合同');
        }
      }
      if (score > 0) {
        results.push({
          sc_id: sc.id,
          sc_no: sc.sc_no,
          company_name_en: sc.company_name_en,
          company_name_zh: sc.company_name_zh,
          quotation_no: sc.quotation_no,
          contract_amount: sc.contract_amount,
          score,
          reasons,
        });
      }
    });
    return results.sort((a, b) => b.score - a.score).slice(0, 5);
  },

  _guessPrefixFromCompany(company) {
    const norm = (company || '').trim().toLowerCase();
    if (!norm) return null;
    for (const sc of App.scList || []) {
      const en = (sc.company_name_en || '').toLowerCase();
      const zh = (sc.company_name_zh || '').toLowerCase();
      const hit = (en && (norm === en || norm.includes(en) || en.includes(norm)))
        || (zh && (norm === zh || norm.includes(zh) || zh.includes(norm)));
      if (hit) {
        const m = (sc.sc_no || '').match(/^(SC|M|O)-/i);
        if (m) return m[1].toUpperCase();
      }
    }
    return null;
  },

  suggestNextScNo() {
    const grp = document.getElementById('ocrNewScGroup');
    if (!grp || grp.style.display === 'none' || this._newScManual) return;

    const company = document.getElementById('ocrCompany')?.value?.trim() || '';
    const prefixEl = document.getElementById('ocrScPrefix');
    const guessed = this._guessPrefixFromCompany(company);
    if (guessed && prefixEl && !this._prefixPicked) {
      prefixEl.value = guessed;
    }
    const prefix = prefixEl?.value || 'SC';
    const input = document.getElementById('ocrNewScNo');
    const hint = document.getElementById('ocrNewScHint');
    if (!input) return;

    const res = this._suggestNextScNoClient(prefix, company);
    if (res?.sc_no) {
      input.value = res.sc_no;
      if (hint) {
        hint.textContent = res.reason
          ? `💡 ${res.reason}（可手動修改）`
          : '依公司名稱與分類自動建議；可手動修改';
      }
    }
  },

  validateAmountMismatch() {
    const warn = document.getElementById('ocrAmountWarn');
    if (!warn) return;
    let sum = 0;
    this.lineItems.forEach(it => {
      const a = parseFloat(it.amount);
      if (!isNaN(a)) sum += a;
    });
    const head = parseFloat(document.getElementById('ocrAmount')?.value);
    if (sum > 0 && !isNaN(head) && Math.abs(sum - head) > 0.02) {
      warn.style.display = '';
      warn.textContent = `⚠️ 明細合計 ${fmt(sum)} 與表頭金額 ${fmt(head)} 不一致，請核對後再儲存`;
      return false;
    }
    warn.style.display = 'none';
    return true;
  },

  fetchScSuggestions() {
    const hints = {
      quotation_no: document.getElementById('ocrQuotationNo')?.value,
      company: document.getElementById('ocrCompany')?.value,
      amount: document.getElementById('ocrAmount')?.value,
    };
    this._scSuggestions = this._suggestScMatchesClient(hints);
    this.renderScSuggestions();
  },

  renderScSuggestions() {
    const el = document.getElementById('ocrScSuggest');
    if (!el) return;
    if (!this._scSuggestions.length) {
      el.style.display = 'none';
      return;
    }
    const top = this._scSuggestions[0];
    const reasons = (top.reasons || []).join(' · ');
    el.style.display = '';
    const isQuot = this.getDocType() === 'quotation';
    if (isQuot) {
      el.innerHTML = `💡 同公司已有合同 <strong>${top.sc_no}</strong>（${reasons}）。
        報價單請用下方<strong>新建參考編號</strong>新增，勿選現有編號以免覆蓋舊資料。`;
      return;
    }
    el.innerHTML = `💡 建議關聯：<strong>${top.sc_no}</strong> ${top.company_name_en || top.company_name_zh || ''}（${reasons}）
      <button type="button" class="btn btn-secondary btn-sm" onclick="OCR.applyScSuggestion('${top.sc_no.replace(/'/g, "\\'")}')">關聯現有</button>`;
  },

  applyScSuggestion(scNo) {
    if (this.getDocType() === 'quotation') {
      toast('報價單請使用新建參考編號，勿關聯現有合同', 'warning');
      return;
    }
    if (!confirm(`確定關聯現有合同「${scNo}」？（發票付款用）`)) return;
    const sel = document.getElementById('ocrScNo');
    if (sel) {
      sel.value = scNo;
      this.onScChange();
    }
  },

  async checkDuplicateInvoice() {
    const warn = document.getElementById('ocrDupWarn');
    const p = App.currentProject;
    const invNo = document.getElementById('ocrInvoiceNo')?.value?.trim();
    if (!warn || !p || !invNo || this.getDocType() !== 'invoice') {
      if (warn) warn.style.display = 'none';
      return false;
    }
    try {
      const res = await api('GET', `/projects/${p.id}/payments/check-invoice?invoice_no=${encodeURIComponent(invNo)}`);
      if (res?.exists) {
        const ex = res.payment || {};
        warn.style.display = '';
        warn.textContent = `⚠️ 發票號「${invNo}」已存在（${ex.sc_no || '—'} · ${fmt(ex.paid_amount)}）`;
        return true;
      }
    } catch (e) {}
    warn.style.display = 'none';
    return false;
  },

  _enableSaveButtons(enabled) {
    ['ocrSaveQuotBtn', 'ocrSaveInvBtn'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.disabled = !enabled;
    });
  },

  _bindOcrWatchers() {
    const onChange = () => {
      this.validateAmountMismatch();
      if (this.getDocType() === 'invoice') this.checkDuplicateInvoice();
    };
    ['ocrInvoiceNo', 'ocrQuotationNo', 'ocrAmount', 'ocrCompany'].forEach(id => {
      const el = document.getElementById(id);
      if (el && !el.dataset.ocrWatch) {
        el.dataset.ocrWatch = '1';
        el.addEventListener('input', onChange);
        el.addEventListener('change', onChange);
      }
    });
    const companyEl = document.getElementById('ocrCompany');
    if (companyEl && !companyEl.dataset.ocrScSuggest) {
      companyEl.dataset.ocrScSuggest = '1';
      companyEl.addEventListener('input', () => {
        this._newScManual = false;
        this.suggestNextScNo();
      });
    }
  },

  async processFile(file) {
    const ext = file.name.split('.').pop().toLowerCase();
    if (!['pdf', 'png', 'jpg', 'jpeg'].includes(ext)) {
      toast('請上傳PDF、PNG或JPG文件', 'warning');
      return;
    }

    const progress = document.getElementById('ocrProgress');
    const progressBar = document.getElementById('ocrProgressBar');
    const progressText = document.getElementById('ocrProgressText');
    progress.style.display = '';
    progressBar.style.width = '20%';
    progressText.textContent = '上傳文件中...';

    document.getElementById('ocrRawText').style.display = 'none';
    this._enableSaveButtons(false);
    this.clearForm();

    const formData = new FormData();
    formData.append('file', file);
    if (App.currentProject?.id) {
      formData.append('project_id', App.currentProject.id);
    }
    this.currentOriginalFilename = file.name;

    try {
      progressBar.style.width = '40%';
      progressText.textContent = `正在分析「${file.name}」...`;

      const r = await fetch(`${API}/ocr/upload`, { method: 'POST', body: formData });
      progressBar.style.width = '80%';
      progressText.textContent = '提取項目明細...';

      const json = await r.json();
      progressBar.style.width = '100%';

      if (!json.success) {
        toast('OCR失敗: ' + json.error, 'error');
        progress.style.display = 'none';
        return;
      }

      setTimeout(() => { progress.style.display = 'none'; }, 500);

      const data = json.data;
      this.currentPdfPath = data.pdf_path;
      this.currentOcrId = data.ocr_id || null;

      const rawTextEl = document.getElementById('ocrRawText');
      const previewEl = document.getElementById('ocrPreviewText');
      const methodBadge = document.getElementById('ocrMethodBadge');

      rawTextEl.style.display = '';
      previewEl.textContent = data.raw_text || '（無可識別文字）';

      const methodLabels = {
        gemini: 'Gemini Vision AI',
        quark_handwritten: '夸克 AI 手寫識別',
        quark_general: '夸克 AI 通用識別',
        quark_invoice: '夸克 商業發票識別',
        rapidocr: 'RapidOCR 本地識別',
        pymupdf: 'PyMuPDF 文字提取',
        pdfplumber: 'PDF 文字提取',
        failed: '識別失敗',
      };
      methodBadge.textContent = methodLabels[data.method] || data.method;
      methodBadge.className = `ocr-method-badge ${data.method}`;

      if (data.extracted) {
        const ex = data.extracted;
        document.getElementById('ocrInvoiceNo').value = ex.invoice_no || '';
        document.getElementById('ocrInvoiceDate').value = ex.invoice_date || '';
        document.getElementById('ocrQuotationNo').value = ex.quotation_no || '';
        document.getElementById('ocrQuotationDate').value =
          ex.quotation_date || ex.invoice_date || '';
        document.getElementById('ocrAmount').value = ex.total_amount || ex.amount || '';
        document.getElementById('ocrCompany').value = ex.company_name_en || ex.company_name_zh || '';

        const items = ex.line_items || [];
        if (items.length) {
          this.renderLineItems(items);
          toast(`已識別 ${items.length} 項工程/服務明細`, 'success');
        } else if (ex.description && ex.description.includes('\t')) {
          // 已格式化的明細表格文字
          const parsed = this.parseDescriptionTable(ex.description);
          if (parsed.length) {
            this.renderLineItems(parsed);
            toast(`已從描述解析 ${parsed.length} 項明細`, 'info');
          } else {
            this.renderLineItems([]);
          }
        } else {
          const fromRaw = this.parseRawLineItems(data.raw_text || '');
          if (fromRaw.length) {
            this.renderLineItems(fromRaw);
            toast(`已從 OCR 文字解析 ${fromRaw.length} 項明細`, 'success');
          } else {
            this.renderLineItems([]);
            if (ex.total_amount || ex.amount) {
              toast('已識別總額，項目明細請手動新增或設定 Gemini API Key 作備用', 'warning');
            }
          }
        }
      }

      if (data.extracted) {
        const ex = data.extracted;
        this.setDocType(ex.document_type || 'unknown', ex.document_type_confidence || 0);
        this.updateDocTypeFields();
      }
      this._enableSaveButtons(true);
      this._bindOcrWatchers();
      this.fetchScSuggestions();
      this.validateAmountMismatch();
      await this.checkDuplicateInvoice();

      if (data.error) {
        toast(data.error, 'warning');
      }

      const method = data.method;
      if (method === 'gemini') {
        toast('Gemini OCR 完成，請確認項目明細', 'success');
      } else if (method === 'quark_handwritten' || method === 'quark_general') {
        toast('夸克 AI 識別完成，請確認項目明細', 'success');
      } else if (method === 'quark_invoice') {
        toast('夸克商業發票識別完成，請確認項目明細', 'success');
      } else if (method === 'rapidocr') {
        toast('RapidOCR 完成，請確認項目明細', 'success');
      } else if (method === 'pdfplumber' || method === 'pymupdf') {
        toast('PDF 文字提取完成，請確認項目明細', 'info');
      }

    } catch (e) {
      progress.style.display = 'none';
      toast('OCR錯誤: ' + e.message, 'error');
    }
  },

  clearForm() {
    ['ocrInvoiceNo', 'ocrInvoiceDate', 'ocrQuotationNo', 'ocrQuotationDate', 'ocrAmount', 'ocrCompany', 'ocrDescription', 'ocrRemark', 'ocrNewScNo'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.value = '';
    });
    const prefixEl = document.getElementById('ocrScPrefix');
    if (prefixEl) prefixEl.value = 'SC';
    const hintEl = document.getElementById('ocrNewScHint');
    if (hintEl) hintEl.textContent = '依公司名稱與分類自動建議；可手動修改';
    this.lineItems = [];
    this._scSuggestions = [];
    this._newScManual = false;
    this._prefixPicked = false;
    this.docType = 'unknown';
    document.getElementById('ocrItemsBody').innerHTML =
      '<tr><td colspan="7" class="ocr-items-empty">上傳發票單或報價單後自動識別項目明細</td></tr>';
    document.getElementById('ocrItemsTotal').innerHTML = '';
    const bar = document.getElementById('ocrDocTypeBar');
    if (bar) bar.style.display = 'none';
    ['ocrAmountWarn', 'ocrDupWarn', 'ocrScSuggest'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.style.display = 'none';
    });
    const newGrp = document.getElementById('ocrNewScGroup');
    if (newGrp) newGrp.style.display = 'none';
    document.querySelectorAll('input[name="ocrDocType"]').forEach(r => { r.checked = false; });
    const invRow = document.getElementById('ocrInvoiceRow');
    const quotRow = document.getElementById('ocrQuotationRow');
    if (invRow) invRow.style.display = '';
    if (quotRow) quotRow.style.display = '';
  },

  _readCommonFields() {
    this.readLineItemsFromDom();
    const scNo = document.getElementById('ocrScNo').value.trim();
    const newScNo = document.getElementById('ocrNewScNo').value.trim();
    const effectiveScNo = scNo || newScNo;
    const sc = App.scList.find(s => s.sc_no === effectiveScNo);
    const amount = parseFloat(document.getElementById('ocrAmount').value) || 0;
    const company = document.getElementById('ocrCompany').value.trim();
    const description = this.buildDescriptionText(this.lineItems)
      || document.getElementById('ocrDescription').value
      || sc?.description
      || null;
    return { scNo, newScNo, effectiveScNo, sc, amount, company, description };
  },

  async saveAsQuotation() {
    const p = App.currentProject;
    if (!p) { toast('請先選擇項目', 'warning'); return; }
    if (this.getDocType() === 'invoice') {
      if (!confirm('系統判斷為發票單，仍要儲存為報價（合同項目）？')) return;
    }
    if (!this.validateAmountMismatch()) {
      if (!confirm('明細合計與表頭金額不一致，仍要儲存？')) return;
    }
    const { scNo, newScNo, effectiveScNo, sc, amount, company, description } = this._readCommonFields();
    if (!effectiveScNo) { toast('請選擇參考編號或輸入新建編號', 'warning'); return; }
    if (scNo && sc && !newScNo) {
      const paid = parseFloat(sc.total_paid) || 0;
      const msg = `「${scNo}」為現有合同（金額 ${fmt(sc.contract_amount)}${paid ? `，已付 ${fmt(paid)}` : ''}）。\n\n儲存將覆蓋原有報價資料。\n若要新增，請清空「關聯參考編號」並使用「新建參考編號」。\n\n確定要覆蓋？`;
      if (!confirm(msg)) return;
    }
    if (!amount) { toast('請輸入報價金額', 'warning'); return; }
    const quotNo = document.getElementById('ocrQuotationNo').value.trim() || null;
    const quotDate = document.getElementById('ocrQuotationDate').value || null;
    const isZh = /[\u4e00-\u9fff]/.test(company);
    const data = {
      project_id: p.id,
      sc_no: effectiveScNo,
      quotation_no: quotNo,
      company_name_en: isZh ? (sc?.company_name_en || null) : (company || sc?.company_name_en || null),
      company_name_zh: isZh ? (company || sc?.company_name_zh || null) : (sc?.company_name_zh || null),
      description,
      contract_sum: amount,
      vo_amount: sc?.vo_amount || 0,
      contract_amount: amount + (parseFloat(sc?.vo_amount) || 0),
      quotation_date: quotDate,
      quotation_saved: this.currentPdfPath || null,
      original_filename: this.currentOriginalFilename || null,
      ocr_id: this.currentOcrId || null,
      payment_note: document.getElementById('ocrRemark').value || null,
      oa_status: sc?.oa_status || null,
      oa_ref: sc?.oa_ref || null,
      oa_no: sc?.oa_no || null,
      oa_date: sc?.oa_date || null,
      is_excluded: sc?.is_excluded || 0,
    };
    try {
      await api('POST', '/subcontractors', data);
      toast(`報價已寫入合同項目 ${effectiveScNo}`, 'success');
      App.scList = await api('GET', `/projects/${p.id}/subcontractors`) || [];
      this.populateScOptions();
      this.reset();
      setTimeout(() => { App.navigate('subcontractors'); SC.load(); Dashboard.load(); }, 400);
    } catch (e) {}
  },

  async saveAsInvoice() {
    const p = App.currentProject;
    if (!p) { toast('請先選擇項目', 'warning'); return; }
    if (this.getDocType() === 'quotation') {
      if (!confirm('系統判斷為報價單，仍要儲存為發票（付款記錄）？')) return;
    }
    if (!this.validateAmountMismatch()) {
      if (!confirm('明細合計與表頭金額不一致，仍要儲存？')) return;
    }
    const { scNo, sc, amount, company, description } = this._readCommonFields();
    if (!scNo) { toast('發票單須選擇關聯參考編號', 'warning'); return; }
    const invNo = document.getElementById('ocrInvoiceNo').value.trim();
    if (!invNo) { toast('請輸入發票號碼', 'warning'); return; }
    if (await this.checkDuplicateInvoice()) { toast('此發票號已存在，請檢查', 'error'); return; }
    if (!amount) { toast('請輸入付款金額', 'warning'); return; }
    const contractAmt = parseFloat(sc?.contract_amount) || 0;
    const totalPaid = parseFloat(sc?.total_paid) || 0;
    if (contractAmt > 0 && totalPaid + amount > contractAmt + 0.02) {
      if (!confirm(`累計已付將超過合同金額 ${fmt(contractAmt)}，仍要儲存？`)) return;
    }
    const data = {
      project_id: p.id,
      sc_id: sc?.id || null,
      seq_no: null,
      invoice_date: document.getElementById('ocrInvoiceDate').value || null,
      invoice_no: invNo,
      quotation_no: document.getElementById('ocrQuotationNo').value.trim() || sc?.quotation_no || null,
      sc_no: scNo,
      company_name_en: sc?.company_name_en || company || null,
      company_name_zh: sc?.company_name_zh || null,
      description,
      contract_amount: contractAmt,
      paid_amount: amount,
      remainder_amount: contractAmt - totalPaid - amount,
      oa_ref: null, oa_no: null, mc_ip_no: null, bc_to_sub: null, sub_ip_no: null,
      remark: document.getElementById('ocrRemark').value || null,
      pdf_path: this.currentPdfPath,
      ocr_id: this.currentOcrId || null,
      ocr_status: 'ocr_verified',
    };
    try {
      await api('POST', '/payments', data);
      toast('發票已儲存為付款記錄', 'success');
      this.reset();
      setTimeout(() => { App.navigate('payments'); Payments.load(); Dashboard.load(); }, 400);
    } catch (e) {}
  },

  reset() {
    this.currentPdfPath = null;
    this.currentOcrId = null;
    this.currentOriginalFilename = null;
    this.clearForm();
    document.getElementById('ocrScNo').value = '';
    document.getElementById('ocrRawText').style.display = 'none';
    document.getElementById('ocrProgress').style.display = 'none';
    this._enableSaveButtons(false);
    document.getElementById('pdfFileInput').value = '';
  },
};
