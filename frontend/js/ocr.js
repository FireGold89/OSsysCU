/* ─── ocr.js — PDF OCR識別 + 項目明細表格 ───────────────── */
const OCR = {
  currentPdfPath: null,
  lineItems: [],

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
    return n.toLocaleString('en-HK', { minimumFractionDigits: 0, maximumFractionDigits: 2 });
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
      document.getElementById('ocrAmount').value = sum;
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
    document.getElementById('ocrSaveBtn').disabled = true;
    this.clearForm();

    const formData = new FormData();
    formData.append('file', file);

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

      document.getElementById('ocrSaveBtn').disabled = false;

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
    ['ocrInvoiceNo', 'ocrInvoiceDate', 'ocrQuotationNo', 'ocrAmount', 'ocrCompany', 'ocrDescription', 'ocrRemark'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.value = '';
    });
    this.lineItems = [];
    document.getElementById('ocrItemsBody').innerHTML =
      '<tr><td colspan="7" class="ocr-items-empty">上傳 PDF 後自動識別項目明細</td></tr>';
    document.getElementById('ocrItemsTotal').innerHTML = '';
  },

  async saveRecord() {
    const p = App.currentProject;
    if (!p) { toast('請先選擇項目', 'warning'); return; }

    this.readLineItemsFromDom();
    const scNo = document.getElementById('ocrScNo').value;
    const sc = App.scList.find(s => s.sc_no === scNo);
    const amount = parseFloat(document.getElementById('ocrAmount').value) || 0;
    const company = document.getElementById('ocrCompany').value;
    const description = this.buildDescriptionText(this.lineItems)
      || document.getElementById('ocrDescription').value
      || sc?.description
      || null;

    const data = {
      project_id: p.id,
      sc_id: sc?.id || null,
      seq_no: null,
      invoice_date: document.getElementById('ocrInvoiceDate').value || null,
      invoice_no: document.getElementById('ocrInvoiceNo').value || null,
      quotation_no: document.getElementById('ocrQuotationNo').value || null,
      sc_no: scNo || null,
      company_name_en: sc?.company_name_en || company || null,
      company_name_zh: sc?.company_name_zh || null,
      description,
      contract_amount: sc?.contract_amount || 0,
      paid_amount: amount,
      remainder_amount: (sc?.contract_amount || 0) - amount,
      oa_ref: null,
      oa_no: null,
      mc_ip_no: null,
      bc_to_sub: null,
      sub_ip_no: null,
      remark: document.getElementById('ocrRemark').value || null,
      pdf_path: this.currentPdfPath,
      ocr_status: 'ocr_verified',
    };

    try {
      await api('POST', '/payments', data);
      toast('付款記錄已儲存（含項目明細）', 'success');
      this.reset();
      setTimeout(() => {
        App.navigate('payments');
        Payments.load();
        Dashboard.load();
      }, 500);
    } catch (e) {}
  },

  reset() {
    this.currentPdfPath = null;
    this.clearForm();
    document.getElementById('ocrScNo').value = '';
    document.getElementById('ocrRawText').style.display = 'none';
    document.getElementById('ocrProgress').style.display = 'none';
    document.getElementById('ocrSaveBtn').disabled = true;
    document.getElementById('pdfFileInput').value = '';
  },
};
