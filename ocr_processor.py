"""
ocr_processor.py — PDF OCR 處理模組 v4

優先級（全部免費、無需管理員權限，pip install 即可）:
  1. pdfplumber + PyMuPDF  — 可搜尋文字型 PDF
  2. RapidOCR (ONNX)       — GitHub RapidAI/RapidOCR，繁簡中文+英文，純 CPU
  3. Gemini Vision         — 可選 API Key 備用

RapidOCR: https://github.com/RapidAI/RapidOCR
"""
import os
import re
import json
import base64
import pdfplumber
import fitz  # PyMuPDF
from datetime import datetime

# ─── 安全日誌（避免 Windows cp950 終端 emoji 導致初始化失敗）────────
def _log(msg):
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode('ascii', errors='replace').decode('ascii'))


# ─── 全域 RapidOCR 實例（懶載入）────────────────────────────
_rapid_ocr = None
_RAPID_OCR_MISSING = object()


def get_rapid_ocr():
    """懶載入 RapidOCR（只初始化一次）"""
    global _rapid_ocr
    if _rapid_ocr is _RAPID_OCR_MISSING:
        return None
    if _rapid_ocr is not None:
        return _rapid_ocr
    try:
        from rapidocr_onnxruntime import RapidOCR
        _rapid_ocr = RapidOCR()
        _log("[OCR] RapidOCR loaded (zh/en, CPU)")
    except ImportError:
        _log("[OCR] RapidOCR not installed: pip install rapidocr-onnxruntime")
        _rapid_ocr = _RAPID_OCR_MISSING
    except Exception as e:
        _log(f"[OCR] RapidOCR init failed: {e}")
        _rapid_ocr = _RAPID_OCR_MISSING
    return None if _rapid_ocr is _RAPID_OCR_MISSING else _rapid_ocr


# ─── PDF 文字提取 ────────────────────────────────────────────

def extract_text_from_pdf(pdf_path):
    """pdfplumber 文字提取"""
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except Exception as e:
        _log(f"[OCR] pdfplumber failed: {e}")
    return text.strip()


def extract_text_from_pdf_pymupdf(pdf_path):
    """PyMuPDF 文字提取（部分 PDF 比 pdfplumber 更準）"""
    text = ""
    try:
        doc = fitz.open(pdf_path)
        for page in doc:
            text += page.get_text("text") + "\n"
        doc.close()
    except Exception as e:
        _log(f"[OCR] pymupdf text failed: {e}")
    return text.strip()


def extract_pdf_text_combined(pdf_path):
    """合併兩種文字提取結果，取較長者"""
    t1 = extract_text_from_pdf(pdf_path)
    t2 = extract_text_from_pdf_pymupdf(pdf_path)
    if len(t2) > len(t1):
        return t2, 'pymupdf'
    return t1, 'pdfplumber'


def pdf_pages_to_images(pdf_path, max_pages=2, dpi=250):
    """將 PDF 每頁轉為高解析度 PNG bytes（300dpi 提升掃描件識別率）"""
    images = []
    try:
        doc = fitz.open(pdf_path)
        for i, page in enumerate(doc):
            if i >= max_pages:
                break
            mat = fitz.Matrix(dpi / 72, dpi / 72)
            pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
            images.append(pix.tobytes("png"))
        doc.close()
    except Exception as e:
        _log(f"[OCR] PDF to image failed: {e}")
    return images


# ─── RapidOCR 識別 ──────────────────────────────────────────

def ocr_with_rapidocr(image_bytes_list):
    """RapidOCR 識別圖像列表，返回 (full_text, error_msg)"""
    engine = get_rapid_ocr()
    if engine is None:
        return None, "RapidOCR 未安裝，請執行: pip install rapidocr-onnxruntime"

    all_lines = []
    try:
        for img_bytes in image_bytes_list:
            result = engine(img_bytes)
            if not result or not result[0]:
                continue

            boxes = result[0]
            try:
                def get_y_center(item):
                    box = item[0]
                    return (box[0][1] + box[2][1]) / 2
                boxes_sorted = sorted(boxes, key=get_y_center)
            except Exception:
                boxes_sorted = boxes

            for item in boxes_sorted:
                if len(item) >= 2:
                    text = str(item[1]).strip()
                    conf = float(item[2]) if len(item) >= 3 else 0.5
                    if conf > 0.25 and text:
                        all_lines.append(text)

        full_text = '\n'.join(all_lines)
        return (full_text, None) if full_text.strip() else (None, "未識別到文字")

    except Exception as e:
        return None, f"RapidOCR error: {e}"


# ─── Gemini Vision（備用）────────────────────────────────────

def ocr_with_gemini(image_bytes, api_key):
    """Gemini Vision API 結構化提取"""
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')

        img_b64 = base64.b64encode(image_bytes).decode('utf-8')
        prompt = """請仔細分析這張發票/報價單，以JSON格式提取以下資料。
如果找不到某欄位，填入null。

{
  "invoice_no": "發票號碼",
  "invoice_date": "日期(YYYY-MM-DD格式)",
  "quotation_no": "報價單號碼",
  "company_name_en": "公司英文名稱",
  "company_name_zh": "公司中文名稱",
  "description": "工程/服務摘要（一行）",
  "line_items": [
    {"no": "1", "description": "項目描述", "qty": "1", "unit": "nr", "unit_price": 1000, "amount": 1000}
  ],
  "total_amount": 金額數字(不含逗號和$符號),
  "raw_text": "完整原始文字"
}

只返回JSON，不要其他說明。"""

        response = model.generate_content([
            prompt,
            {"mime_type": "image/png", "data": img_b64}
        ])

        raw = response.text.strip()
        raw = re.sub(r'^```(?:json)?\s*', '', raw)
        raw = re.sub(r'\s*```$', '', raw)
        return json.loads(raw), None

    except Exception as e:
        return None, str(e)


# ─── 智能資料提取（規則引擎）────────────────────────────────

def structure_line_items_with_gemini(text, api_key):
    """規則解析失敗時，用 Gemini 從 OCR 文字提取項目明細（無需夸克 AI Agent）"""
    if not api_key or not text or len(text.strip()) < 20:
        return None
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = (
            '以下為發票/報價單 OCR 文字。請提取項目明細，以 JSON 返回，格式：\n'
            '{"line_items":[{"no":"1","description":"項目描述","qty":"數量",'
            '"unit":"單位","unit_price":數字,"amount":數字}],"total_amount":數字}\n'
            '注意：合計金額若出現 8138600 而明細為 138600，前導 8 可能是 $ 誤識。\n'
            '只返回 JSON，不要其他說明。\n\nOCR文字：\n' + text[:3500]
        )
        response = model.generate_content(prompt)
        raw = response.text.strip()
        raw = re.sub(r'^```(?:json)?\s*', '', raw)
        raw = re.sub(r'\s*```$', '', raw)
        data = json.loads(raw)
        items = data.get('line_items') or []
        if not items:
            return None
        total = data.get('total_amount')
        return {'line_items': items, 'total_amount': total}
    except Exception as e:
        _log(f'[OCR] Gemini line items failed: {e}')
        return None


def extract_invoice_data(text, pdf_path=None, gemini_api_key=None):
    """從 OCR 文字中智能提取發票/報價單資料"""
    text = _normalize_ocr_text(text or '')
    result = {
        'invoice_no': None, 'invoice_date': None, 'quotation_no': None,
        'company_name_en': None, 'company_name_zh': None,
        'description': None, 'amount': None, 'total_amount': None,
        'line_items': [],
        'raw_text': text
    }

    if not text:
        if pdf_path:
            _enrich_line_items(result, pdf_path, text)
        return result

    lines = [l.strip() for l in text.split('\n') if l.strip()]

    inv_patterns = [
        r'(?:Invoice\s*(?:No\.?|Number|#)|發票(?:號碼|編號|號)|Inv\.?\s*No\.?|INVOICE\s*NO\.?)[:\s:：#\-]*([A-Z0-9][A-Z0-9\-\/\.]+)',
        r'\bINV[\-\/]([A-Z0-9\-\/]+)',
        r'(?:I\.?O\.?\s*No\.?|Invoice)[:\s:：\-]*([A-Z0-9][A-Z0-9\-\/]{3,})',
    ]
    for pat in inv_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            result['invoice_no'] = m.group(1).strip()
            break

    quot_patterns = [
        r'(?:Quotation\s*(?:No\.?|Ref\.?|#)|報價(?:單號|號碼|編號|號)|Quot\.?\s*No\.?|QUO\.?\s*No\.?)[:\s:：#\-]*([A-Z0-9][A-Z0-9\-\/\.]+)',
        r'(?:Our\s*Ref\.?|我方參考)[:\s:：]*([A-Z0-9][A-Z0-9\-\/\.]+)',
        r'\b(Q[\-\/][A-Z0-9\-\/\.]+)',
        r'\b(QUO[\-\/][A-Z0-9\-\/]+)',
    ]
    for pat in quot_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            result['quotation_no'] = m.group(1).strip()
            break

    date_patterns = [
        r'(?:Date|日期|Invoice\s*Date|發票日期|Dated|Date:)[:\s:：]*(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})',
        r'(?:Date|日期)[:\s:：]*(\d{4}[\/\-\.]\d{1,2}[\/\-\.]\d{1,2})',
        r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日',
        r'\b(\d{2}\/\d{2}\/\d{4})\b',
        r'\b(\d{4}-\d{2}-\d{2})\b',
        r'\b(\d{2}-\d{2}-\d{4})\b',
    ]
    for pat in date_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            if '年' in pat:
                date_str = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
            else:
                date_str = normalize_date(m.group(1))
            result['invoice_date'] = date_str
            break

    en_company_keywords = ['LTD', 'LIMITED', 'CO.', 'COMPANY', 'ENGINEERING',
                           'CONSTRUCTION', 'SERVICES', 'CONSULTANT', 'CONSULTANCY',
                           'BROKERS', 'INSTITUTE', 'COUNCIL', 'BOARD', 'DEPARTMENT',
                           'INSPECTION', 'LIGHTING', 'ELECTRICAL']
    for line in lines:
        line_upper = line.upper()
        if (any(kw in line_upper for kw in en_company_keywords) and
                len(line) > 8 and re.search(r'[A-Z]', line)):
            if not re.match(r'^(?:Company|公司|From|To|Bill|Issued)', line, re.IGNORECASE):
                result['company_name_en'] = line.strip()
                break

    if not result['company_name_en']:
        m = re.search(
            r'(?:Company\s*Name|From|Bill\s*To|Issued\s*By)[:\s:：]+([A-Za-z][A-Za-z\s&\.\,\-\']+(?:Ltd\.?|Limited|Co\.?|Inc\.?))',
            text, re.IGNORECASE)
        if m:
            result['company_name_en'] = m.group(1).strip()

    zh_suffixes = ['有限公司', '工程公司', '建設公司', '顧問公司', '服務公司',
                   '貿易公司', '工業公司', '建築公司', '機電公司', '保險', '議會',
                   '基金會', '基金', '協會', '學院', '中心']
    for line in lines:
        for suffix in zh_suffixes:
            if suffix in line:
                m = re.search(r'([^\s\n:：]{2,25}' + re.escape(suffix) + r')', line)
                if m:
                    result['company_name_zh'] = m.group(1).strip()
                    break
        if result['company_name_zh']:
            break

    # 先嘗試從合計行提取（避免把明細金額當總計，或 $ 誤識為 8）
    total = _extract_total_amount(text)
    if total:
        result['total_amount'] = total
        result['amount'] = total
    else:
        amount_patterns = [
            r'(?:HK\$|HKD\s*\$?)\s*([\d,]+(?:\.\d{1,2})?)',
            r'\$\s*([\d,]+(?:\.\d{2})?)',
        ]
        amounts = []
        for pat in amount_patterns:
            for m in re.finditer(pat, text, re.IGNORECASE):
                val = _parse_number(m.group(1))
                if val and val > 10:
                    amounts.append(_fix_dollar_eight_amount(val, amounts))
        if amounts:
            result['total_amount'] = max(amounts)
            result['amount'] = max(amounts)

    desc_patterns = [
        r'(?:Description|工程描述|服務描述|工程內容|工作描述|Subject|Re:|RE:)[:\s:：]+([^\n]{5,120})',
        r'(?:For:|For\s+the|為了?)[:\s:：]+([^\n]{5,120})',
    ]
    for pat in desc_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            candidate = m.group(1).strip()
            if not _is_header_line(candidate):
                result['description'] = candidate
                break

    if not result.get('description'):
        for line in lines:
            if '報價' in line and len(line) > 4 and not _is_header_line(line):
                result['description'] = line.strip()
                break

    _enrich_line_items(result, pdf_path, text)
    if not result.get('line_items') and gemini_api_key:
        gem = structure_line_items_with_gemini(text, gemini_api_key)
        if gem and gem.get('line_items'):
            result['line_items'] = gem['line_items']
            result['description'] = format_description_from_items(
                gem['line_items'], result.get('description'))
            if gem.get('total_amount'):
                fixed = _fix_dollar_eight_amount(
                    gem['total_amount'],
                    [it.get('amount') for it in gem['line_items'] if it.get('amount')],
                )
                result['total_amount'] = fixed
                result['amount'] = fixed
    return result


# ─── 項目明細表格提取 ────────────────────────────────────────

HEADER_MAP = {
    'no': ('item', 'no', 'no.', 's/n', 'sn', '項次', '序號', '編號', '#'),
    'description': (
        'description', 'particulars', 'details', 'work', 'scope', 'services',
        '描述', '項目描述', '工程內容', '工程描述', '服務內容', '品名', '項目', '內容', '工作內容',
        '部位', '罩位', '位置', '貨品名稱', '貨品', 'product',
    ),
    'qty': ('qty', 'quantity', 'q\'ty', 'qnty', '數量', 'qty.', '工程量', '工程 量'),
    'unit': ('unit', 'uom', '單位'),
    'unit_price': ('rate', 'unit price', 'unit rate', 'u/p', 'price', '單價', 'unitprice'),
    'amount': ('amount', 'total', 'sum', 'amt', '金額', '合計', '小計'),
}

TOTAL_KEYWORDS = (
    'total', 'sub-total', 'subtotal', 'grand total', 'amount due', 'balance',
    '總計', '合計', '總金額', '應付', '小計', '結餘',
)


def _cell_str(val):
    if val is None:
        return ''
    return str(val).strip().replace('\n', ' ')


def _parse_number(val):
    if val is None:
        return None
    s = str(val).strip().replace(',', '').replace('$', '').replace('HK$', '').replace('HKD', '')
    s = re.sub(r'[\-\.]+$', '', s)  # OCR 尾隨符號如 138600- / 990-
    if not s or s in ('-', '—', 'N/A', 'n/a'):
        return None
    try:
        return float(s)
    except ValueError:
        m = re.search(r'([\d]+\.?\d*)', s)
        return float(m.group(1)) if m else None


def _fix_dollar_eight_amount(value, reference_amounts=None):
    """
    修正 OCR 將 $ 誤識別為前導數字 8 的情況
    例: $138,600 → 8138600
    """
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return value

    refs = [float(r) for r in (reference_amounts or []) if r is not None]
    s = str(int(v)) if v == int(v) else str(v).split('.')[0]

    if not s.startswith('8') or len(s) < 5:
        return v

    corrected = _parse_number(s[1:])
    if not corrected or corrected <= 0:
        return v

    for ref in refs:
        if abs(corrected - ref) < 1:
            return corrected

    if corrected < 5_000_000 and v >= corrected * 5:
        return corrected

    return v


def _extract_total_amount(text, reference_amounts=None):
    """從合計/總計行提取金額，並修正 $→8 誤識"""
    refs = reference_amounts or []
    total_patterns = [
        r'(?:合計|總計|總金額|應付|Total|Grand\s*Total|Amount\s*Due)[：:\s]*\$?\s*([\d,]+[\-\.]*)',
        r'(?:HK\$|HKD)\s*([\d,]+(?:\.\d{1,2})?)',
    ]
    found = []
    for pat in total_patterns:
        for m in re.finditer(pat, text, re.IGNORECASE):
            val = _parse_number(m.group(1))
            if val and val > 10:
                found.append(_fix_dollar_eight_amount(val, refs))

    if found:
        return found[-1]

    # 合計與金額分行：「合計：」下一行為數字
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    for i, line in enumerate(lines):
        if _is_total_line(line) and re.search(r'[：:]\s*$', line):
            if i + 1 < len(lines):
                val = _parse_number(lines[i + 1])
                if val and val > 10:
                    return _fix_dollar_eight_amount(val, refs)
    return None


def _match_col(header, keywords):
    h = header.lower().replace('\n', ' ')
    for kw in keywords:
        if kw in h:
            return True
    return False


def _map_table_columns(header_row):
    col_map = {}
    for idx, cell in enumerate(header_row):
        h = _cell_str(cell).lower()
        if not h:
            continue
        for field, keywords in HEADER_MAP.items():
            if field not in col_map and _match_col(h, keywords):
                col_map[field] = idx
                break
    return col_map


def _row_to_line_item(row, col_map, fallback_no=None):
    if not row or not any(_cell_str(c) for c in row):
        return None

    def get(field):
        idx = col_map.get(field)
        if idx is None or idx >= len(row):
            return ''
        return _cell_str(row[idx])

    desc = get('description')
    no = get('no') or (str(fallback_no) if fallback_no else '')
    qty = get('qty')
    unit = get('unit')
    unit_price = get('unit_price')
    amount = get('amount')

    # 若無 description 欄，合併非數字欄為描述
    if not desc and col_map:
        used = set(col_map.values())
        parts = [_cell_str(row[i]) for i in range(len(row)) if i not in used and _cell_str(row[i])]
        desc = ' '.join(parts).strip()

    # 單欄 fallback：整行文字 + 末尾金額
    if not desc and len(row) == 1:
        desc = _cell_str(row[0])

    amt_val = _parse_number(amount)
    up_val = _parse_number(unit_price)

    line = _cell_str(desc) or _cell_str(no)
    if not line:
        return None

    joined = ' '.join(_cell_str(c) for c in row).lower()
    if any(k in joined for k in TOTAL_KEYWORDS) and not qty:
        return None

    if amt_val is None and up_val is None and not qty:
        # 嘗試從行尾找金額
        m = re.search(r'([\d,]+\.\d{2})\s*$', ' '.join(_cell_str(c) for c in row))
        if m:
            amt_val = _parse_number(m.group(1))
        elif not re.search(r'[\d]', line):
            return None

    return {
        'no': no,
        'description': desc or line,
        'qty': qty,
        'unit': unit,
        'unit_price': up_val,
        'amount': amt_val,
    }


def extract_pdf_tables(pdf_path):
    """使用 pdfplumber 提取 PDF 表格行"""
    items = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                for table in (page.extract_tables() or []):
                    if not table or len(table) < 2:
                        continue
                    header_idx = None
                    col_map = {}
                    for i, row in enumerate(table[:5]):
                        trial = _map_table_columns(row)
                        if trial.get('description') or trial.get('amount'):
                            header_idx = i
                            col_map = trial
                            break
                    if header_idx is None:
                        col_map = _map_table_columns(table[0])
                        header_idx = 0
                    if not col_map:
                        continue
                    seq = 0
                    for row in table[header_idx + 1:]:
                        seq += 1
                        item = _row_to_line_item(row, col_map, fallback_no=seq)
                        if item:
                            items.append(item)
    except Exception as e:
        _log(f"[OCR] pdfplumber tables failed: {e}")
    return items


def _is_header_line(line):
    lower = line.lower()
    hits = 0
    for keywords in HEADER_MAP.values():
        if any(kw in lower for kw in keywords):
            hits += 1
    return hits >= 2


def _is_total_line(line):
    lower = line.lower().strip()
    return any(k in lower for k in TOTAL_KEYWORDS)


def _split_ocr_columns(line):
    """將 OCR 單行按多空格或 tab 分割"""
    parts = re.split(r'\t|\s{2,}', line.strip())
    return [p.strip() for p in parts if p.strip()]


def _is_invoice_col_header(line):
    lower = line.lower()
    return (
        '貨品' in line or '品名' in line
        or ('quantity' in lower and '數量' in line)
        or ('unit price' in lower and '單價' in line)
        or ('amount' in lower and '金額' in line)
    )


def _has_invoice_table_headers(text):
    lower = text.lower()
    has_qty = 'quantity' in lower or '數量' in text
    has_price = 'unit price' in lower or '單價' in text
    has_amt = ('amount' in lower and '金額' in text) or '金額' in text
    has_product = '貨品' in text or '品名' in text
    return (has_qty and has_price and has_amt) or (has_product and has_qty)


def _normalize_ocr_text(text):
    """統一換行，拆開黏連的數量/金額行（避免拆斷 8-Port 等描述）"""
    if not text:
        return ''
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    # 表頭關鍵字前換行
    for kw in (
        'QUANTITY', 'UNIT PRICE', 'AMOUNT', '貨品名稱', '货品名称',
        '合計', '合计', '總計', '总计', 'TOTAL',
    ):
        text = re.sub(rf'(?<!\n)({re.escape(kw)})', r'\n\1', text, flags=re.I)
    # 數量行：僅在空白後拆開（140個 / 140个）
    text = re.sub(r'(\s)(\d+\s*[個个pcsPCS])', r'\1\n\2', text)
    text = re.sub(r'([^\d\n\-])(\d+\s*[個个])(?=\s*\n|\s*\d)', r'\1\n\2', text)
    # 數量與單價黏連：140個990-
    text = re.sub(r'(\d+\s*[個个])\s*(\d{2,6}[\-\.]?)', r'\1\n\2', text)
    # 單價與金額黏連：990-138600-
    text = re.sub(r'(\d{2,6})[\-\.](\d{4,9}[\-\.]?)', r'\1\n\2', text)
    return text


def _ocr_text_lines(text):
    return [l.strip() for l in _normalize_ocr_text(text).split('\n') if l.strip()]


_COMPANY_SKIP = (
    '有限公司', '工程公司', '材料', '電器', 'Invoice', 'INVOICE', 'Date', 'DATE',
    'ELECTRICALS', 'ENGINEERING', 'LIMITED', 'LTD', 'CO.', 'Tel', 'Fax',
    '地址', '電話', '傳真', '報價', 'Quotation', 'SHUN SHING',
)


def _is_skippable_desc_line(line):
    if not line or len(line) < 3:
        return True
    if _is_header_line(line) or _is_total_line(line) or _is_invoice_col_header(line):
        return True
    if re.match(r'^\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}$', line):
        return True
    if re.match(r'^(Tel|Fax|TEL|FAX|Phone|Mobile|Attn|Attention)[\s:.]', line, re.I):
        return True
    if re.search(r'\(\d{3,4}\)', line) and re.search(r'Tel|Fax|電話|傳真|Lines', line, re.I):
        return True
    if re.search(r'^\d{3,4}\s*\d{4}\s*\d{4}', line):
        return True
    upper = line.upper()
    if 'QUOTATION' in upper or line.strip().upper() == 'QUOTATION':
        return True
    hits = sum(1 for m in _COMPANY_SKIP if m in line or m in upper)
    if hits >= 1 and not re.search(r'[,，]', line) and len(line) < 50:
        return True
    if _is_invoice_meta_line(line):
        return True
    return False


_DESC_FIELD_RE = re.compile(
    r'(?:DESCRIPTION|DESCRIPION|DESC(?:RIPTION)?|貨品名稱|货品名称|品名)\s*[:：]?\s*(.+)$',
    re.IGNORECASE,
)

_META_LINE_RE = [
    re.compile(r'^RECEIVER\s*[:：]', re.I),
    re.compile(r'^FROM\s*[:：]', re.I),
    re.compile(r'OUR\s*REF', re.I),
    re.compile(r'NO\.\s*OF\s*PAG', re.I),
    re.compile(r'頁數'),
    re.compile(r'收件人'),
    re.compile(r'寄件人'),
    re.compile(r'本公司備註'),
    re.compile(r'請在.*聯絡'),
    re.compile(r'Des\s*Voeux', re.I),
    re.compile(r'德輔道西'),
    re.compile(r'\bG/F\.', re.I),
    re.compile(r'Hong\s*Kong', re.I),
    re.compile(r'^\d{3,4}\s*\d{4}\s*\d{4}'),
]


def _is_invoice_meta_line(line):
    if not line:
        return True
    for pat in _META_LINE_RE:
        if pat.search(line):
            return True
    if re.match(r'^Q\d{4,}\s', line) and ('有限公司' in line or 'LIMITED' in line.upper()):
        return True
    return False


def _is_invoice_meta_chunk(text):
    if not text or len(text) < 2:
        return True
    if _is_invoice_meta_line(text):
        return True
    if re.search(r'有限公司|LIMITED|LTD\.?|Road|Street|Hong Kong|德輔|RECEIVER|FROM|OUR REF', text, re.I):
        return True
    if re.match(r'^Q\d{4,}$', text.strip()):
        return True
    return False


def _extract_description_from_line(line):
    """若該行含 Description/貨品名稱，只取欄位內容"""
    if not line:
        return None
    m = _DESC_FIELD_RE.search(line.strip())
    if m:
        val = m.group(1).strip(' ,.-')
        return val if len(val) >= 2 else None
    return None


def _clean_item_description(desc):
    """只保留 Description/貨品名稱 對應的產品描述，去掉地址、收件人等雜訊"""
    if not desc:
        return ''
    desc = re.sub(r'\s+', ' ', str(desc).strip())

    m = _DESC_FIELD_RE.search(desc)
    if m:
        cleaned = m.group(1).strip(' ,.-')
        if len(cleaned) >= 2:
            return cleaned

    chunks = [c.strip() for c in re.split(r'[,，]\s*', desc) if c.strip()]
    product_chunks = []
    for c in chunks:
        if _is_invoice_meta_chunk(c):
            continue
        c = re.sub(r'^Q\d{4,}\s*', '', c).strip()
        if len(c) >= 2 and not _is_invoice_meta_chunk(c):
            product_chunks.append(c)
    if product_chunks:
        return product_chunks[-1]

    desc = re.sub(r'^Q\d{4,}\s*', '', desc).strip()
    if _is_invoice_meta_chunk(desc):
        return ''
    return desc


def _append_desc_part(parts, line):
    """累加描述行：優先 Description/貨品名稱 欄位內容"""
    inline = _extract_description_from_line(line)
    if inline:
        parts.append(inline)
        return
    if _is_skippable_desc_line(line) or _is_invoice_meta_line(line):
        return
    if len(line) > 100 and _is_invoice_meta_chunk(line):
        return
    parts.append(line)


def parse_qty_price_amount_blocks(text):
    """
    不依表頭，掃描「數量 → 單價 → 金額」三行區塊（夸克垂直表格最穩定特徵）
    """
    lines = _ocr_text_lines(text)
    if not lines:
        return []

    qty_re = re.compile(r'^(\d+)\s*(個|个|pcs|pc|units?|nos?|套|件|台)?\.?$', re.I)
    num_re = re.compile(r'^(\d{1,9})[\-\.]*$')

    items = []
    i = 0
    while i < len(lines):
        if _is_total_line(lines[i]):
            break
        m_qty = qty_re.match(lines[i])
        if m_qty and i + 2 < len(lines):
            m_price = num_re.match(lines[i + 1])
            m_amt = num_re.match(lines[i + 2])
            if m_price and m_amt:
                qty = m_qty.group(1)
                unit = m_qty.group(2) or '個'
                unit_price = _parse_number(m_price.group(1))
                amount = _parse_number(m_amt.group(1))

                desc_lines = []
                j = i - 1
                while j >= 0:
                    if _is_total_line(lines[j]) or qty_re.match(lines[j]):
                        break
                    if _is_skippable_desc_line(lines[j]):
                        j -= 1
                        continue
                    if num_re.match(lines[j]) and j < i - 1:
                        break
                    desc_lines.insert(0, lines[j])
                    j -= 1

                cont = []
                k = i + 3
                while k < len(lines) and not _is_total_line(lines[k]):
                    if qty_re.match(lines[k]) and k + 2 < len(lines):
                        if num_re.match(lines[k + 1]) and num_re.match(lines[k + 2]):
                            break
                    if _is_skippable_desc_line(lines[k]):
                        k += 1
                        continue
                    if num_re.match(lines[k]):
                        break
                    cont.append(lines[k])
                    k += 1

                desc = _clean_item_description(' '.join(desc_lines + cont).strip())
                if desc and len(desc) > 3 and amount:
                    items.append({
                        'no': str(len(items) + 1),
                        'description': desc,
                        'qty': qty,
                        'unit': unit,
                        'unit_price': unit_price,
                        'amount': amount,
                    })
                i = k
                continue
        i += 1

    return items


def parse_stacked_invoice_items(text):
    """
    解析欄位垂直排列的發票表格（夸克 OCR 常見格式）
    描述、數量、單價、金額各占一行
    """
    if not text or not _has_invoice_table_headers(text):
        return []

    lines = _ocr_text_lines(text)
    header_idx = None
    for i, ln in enumerate(lines):
        if '貨品' in ln or ('quantity' in ln.lower() and '數量' in ln):
            header_idx = i
            break
    if header_idx is None:
        header_idx = next((i for i, ln in enumerate(lines) if _is_invoice_col_header(ln)), None)
    if header_idx is None:
        return []

    start = header_idx + 1
    while start < len(lines) and _is_invoice_col_header(lines[start]):
        start += 1

    qty_re = re.compile(r'^(\d+)\s*(個|个|pcs|pc|units?|nos?|套|件|台)?\.?$', re.I)
    num_re = re.compile(r'^(\d{1,9})[\-\.]*$')

    items = []
    desc_parts = []
    i = start

    while i < len(lines):
        line = lines[i]
        if _is_total_line(line):
            break

        m_qty = qty_re.match(line)
        if m_qty and i + 2 < len(lines):
            m_price = num_re.match(lines[i + 1])
            m_amt = num_re.match(lines[i + 2])
            if m_price and m_amt:
                qty = m_qty.group(1)
                unit = m_qty.group(2) or '個'
                unit_price = _parse_number(m_price.group(1))
                amount = _parse_number(m_amt.group(1))

                cont = []
                j = i + 3
                while j < len(lines) and not _is_total_line(lines[j]):
                    if qty_re.match(lines[j]) and j + 2 < len(lines):
                        if num_re.match(lines[j + 1]) and num_re.match(lines[j + 2]):
                            break
                    cont.append(lines[j])
                    j += 1

                desc = _clean_item_description(' '.join(desc_parts + cont).strip())
                desc_parts = []
                if not desc and cont:
                    desc = _clean_item_description(' '.join(cont).strip())
                if desc and len(desc) > 2:
                    items.append({
                        'no': str(len(items) + 1),
                        'description': desc,
                        'qty': qty,
                        'unit': unit,
                        'unit_price': unit_price,
                        'amount': amount,
                    })
                i = j
                continue

        _append_desc_part(desc_parts, line)
        i += 1

    return items


def parse_chinese_boq_items(text):
    """
    解析中文工程量清單（序號 / 部位 / 工程量）
    適用於外判商報價單掃描件，描述與工程量分行排列
    """
    if not text or '工程量' not in text:
        return []
    if not any(k in text for k in ('序號', '序号', '項次')):
        return []

    lines = [l.strip() for l in text.split('\n') if l.strip()]
    start = None
    for i, line in enumerate(lines):
        if '工程量' in line and len(line) <= 8:
            start = i + 1
            break
    if start is None:
        return []

    stop_keywords = ('總計', '总计', '合计', '以上工程', '包工料')

    def is_stop(s):
        return any(k in s for k in stop_keywords)

    def is_decimal_qty(s):
        return bool(re.match(r'^\d+\.\d+$', s))

    def is_count_qty(s):
        return bool(re.match(r'^\d{1,4}$', s))

    skip_headers = {'序號', '序号', '項次', '部位', '罩位', '位置', '工程量', '单位', '單位'}

    items = []
    seq = 0
    i = start

    def flush(desc_parts, qty, unit=''):
        nonlocal seq
        desc = re.sub(r'\s+', ' ', ' '.join(desc_parts)).strip()
        if not desc or len(desc) < 2 or is_stop(desc):
            return
        seq += 1
        q = str(qty)
        u = unit or ('m2' if is_decimal_qty(q) else 'nr')
        items.append({
            'no': str(seq),
            'description': desc,
            'qty': q,
            'unit': u,
            'unit_price': None,
            'amount': None,
        })

    while i < len(lines):
        line = lines[i]
        if is_stop(line) or line == 'PO':
            break
        if line in skip_headers or line == '工程公司':
            i += 1
            continue

        desc_parts = []
        while i < len(lines):
            line = lines[i]
            if is_stop(line) or line == 'PO':
                break
            if line in skip_headers:
                i += 1
                continue
            if is_decimal_qty(line):
                flush(desc_parts, line, 'm2')
                i += 1
                break
            if is_count_qty(line) and desc_parts:
                flush(desc_parts, line, 'nr')
                i += 1
                break
            if line in ('部)', ')') and desc_parts:
                desc_parts[-1] += line
                i += 1
                continue
            desc_parts.append(line)
            i += 1
        else:
            break

    return items


def parse_invoice_items_regex(text):
    """全文字 regex 備用解析（處理黏連行、簡繁混用）"""
    t = _normalize_ocr_text(text)
    items = []

    block_pat = re.compile(
        r'(?P<desc>[A-Za-z][A-Za-z0-9,\s\-\.+&/]{6,}?)\s*'
        r'(?P<qty>\d{1,6})\s*[個个]\s*'
        r'(?P<price>\d{1,7})[\-\.]?\s*'
        r'(?P<amt>\d{3,9})[\-\.]?',
        re.IGNORECASE,
    )
    for i, m in enumerate(block_pat.finditer(t), 1):
        desc = re.sub(r'\s+', ' ', m.group('desc')).strip(' ,-')
        if _is_skippable_desc_line(desc):
            continue
        items.append({
            'no': str(i),
            'description': desc,
            'qty': m.group('qty'),
            'unit': '個',
            'unit_price': _parse_number(m.group('price')),
            'amount': _parse_number(m.group('amt')),
        })

    if items:
        return items

    lines = _ocr_text_lines(t)
    for idx in range(len(lines) - 3):
        m_qty = re.match(r'^(\d+)\s*[個个]', lines[idx + 1])
        m_price = re.match(r'^(\d{1,7})[\-\.]*$', lines[idx + 2])
        m_amt = re.match(r'^(\d{3,9})[\-\.]*$', lines[idx + 3])
        if not (m_qty and m_price and m_amt):
            continue
        desc = lines[idx].strip()
        if _is_skippable_desc_line(desc) or len(desc) < 4:
            continue
        cont = []
        k = idx + 4
        while k < len(lines) and not _is_total_line(lines[k]):
            if re.match(r'^\d+\s*[個个]', lines[k]):
                break
            if not _is_skippable_desc_line(lines[k]):
                cont.append(lines[k])
            k += 1
        full_desc = _clean_item_description(' '.join([desc] + cont).strip())
        if not full_desc:
            continue
        items.append({
            'no': str(len(items) + 1),
            'description': full_desc,
            'qty': m_qty.group(1),
            'unit': '個',
            'unit_price': _parse_number(m_price.group(1)),
            'amount': _parse_number(m_amt.group(1)),
        })
    return items


def _sanitize_line_items(items):
    """確保 JSON / 前端可正確顯示"""
    clean = []
    for i, it in enumerate(items or []):
        if not it:
            continue
        desc = _clean_item_description(str(it.get('description') or '').strip())
        if not desc:
            continue
        clean.append({
            'no': str(it.get('no') or (i + 1)),
            'description': desc,
            'qty': str(it.get('qty') or ''),
            'unit': str(it.get('unit') or ''),
            'unit_price': it.get('unit_price') if it.get('unit_price') not in (None, '') else '',
            'amount': it.get('amount') if it.get('amount') not in (None, '') else '',
        })
    return clean


def parse_line_items_from_text(text):
    """從 OCR 純文字解析項目明細"""
    if not text:
        return []

    text = _normalize_ocr_text(text)

    blocks = parse_qty_price_amount_blocks(text)
    if blocks:
        return _sanitize_line_items(blocks)

    stacked = parse_stacked_invoice_items(text)
    if stacked:
        return _sanitize_line_items(stacked)

    regex_items = parse_invoice_items_regex(text)
    if regex_items:
        return _sanitize_line_items(regex_items)

    boq = parse_chinese_boq_items(text)
    if boq:
        return boq

    lines = [l.strip() for l in text.split('\n') if l.strip()]
    items = []
    in_table = False
    seq = 0

    for line in lines:
        if _is_header_line(line):
            in_table = True
            continue
        if in_table and _is_total_line(line):
            break
        if in_table:
            if _is_skippable_desc_line(line):
                continue
            parts = _split_ocr_columns(line)
            if len(parts) >= 3:
                col_map = {}
                # 嘗試: 項次 | 描述 | ... | 金額
                if re.match(r'^[\d]+[\.\)]?$', parts[0]):
                    col_map = {'no': 0, 'description': 1, 'amount': len(parts) - 1}
                    if len(parts) >= 5:
                        col_map.update({'qty': 2, 'unit': 3, 'unit_price': 4, 'amount': 5})
                    elif len(parts) == 4:
                        col_map.update({'qty': 2, 'amount': 3})
                else:
                    col_map = {'description': 0, 'amount': len(parts) - 1}
                item = _row_to_line_item(parts, col_map, fallback_no=seq + 1)
                if item:
                    seq += 1
                    items.append(item)
                    continue

        # 行尾金額模式: 描述 ... 1,234.56
        m = re.match(
            r'^(?:(\d+)[\.\)]\s*)?(.+?)\s+([\d,]+\.?\d*)\s*$',
            line
        )
        if m and not _is_total_line(line) and not _is_skippable_desc_line(line):
            desc = m.group(2).strip()
            if len(desc) > 3 and not _is_header_line(desc) and not _is_skippable_desc_line(desc):
                seq += 1
                items.append({
                    'no': m.group(1) or str(seq),
                    'description': desc,
                    'qty': '', 'unit': '',
                    'unit_price': None,
                    'amount': _parse_number(m.group(3)),
                })

    # 去重（相鄰相同描述）
    deduped = []
    seen = set()
    for it in items:
        key = (it.get('description', ''), it.get('amount'))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(it)
    return deduped[:50]


def format_description_from_items(items, summary=None):
    """將項目明細格式化為帶標題的表格文字（存入 description）"""
    if not items:
        return summary or ''

    if summary and _is_header_line(summary):
        summary = None

    if summary:
        title = summary
    elif len(items) == 1:
        title = items[0].get('description') or '工程/服務項目'
    else:
        title = f'工程/服務項目（共 {len(items)} 項）'

    def fmt_num(v):
        if v is None or v == '':
            return ''
        try:
            n = float(v)
            return f'{n:,.2f}' if n != int(n) else f'{int(n):,}'
        except (TypeError, ValueError):
            return str(v)

    rows = [
        title,
        '',
        '項次\t項目描述\t數量\t單位\t單價(HK$)\t金額(HK$)',
    ]
    for i, it in enumerate(items, 1):
        no = it.get('no') or str(i)
        rows.append('\t'.join([
            str(no),
            it.get('description') or '',
            str(it.get('qty') or ''),
            str(it.get('unit') or ''),
            fmt_num(it.get('unit_price')),
            fmt_num(it.get('amount')),
        ]))
    return '\n'.join(rows)


def _merge_text_line_items(extracted, text, pdf_path=None):
    """結構化結果缺少明細時，用 OCR 文字補充項目表格"""
    if not text:
        return extracted
    if extracted.get('line_items'):
        return extracted
    items = parse_line_items_from_text(text)
    if not items and pdf_path and str(pdf_path).lower().endswith('.pdf'):
        items = extract_pdf_tables(pdf_path)
    if not items:
        return extracted
    extracted['line_items'] = items
    extracted['description'] = format_description_from_items(
        items, extracted.get('description'))
    item_amounts = [it['amount'] for it in items if it.get('amount')]
    item_sum = sum(item_amounts) if item_amounts else 0
    if item_sum > 0:
        refs = item_amounts + ([item_sum] if len(item_amounts) > 1 else [])
        fixed = _fix_dollar_eight_amount(extracted.get('total_amount'), refs)
        if fixed and abs(fixed - (extracted.get('total_amount') or 0)) > 0.01:
            extracted['total_amount'] = fixed
            extracted['amount'] = fixed
        elif abs((extracted.get('total_amount') or 0) - item_sum) > 1:
            if (extracted.get('total_amount') or 0) > item_sum * 2:
                extracted['total_amount'] = item_sum
                extracted['amount'] = item_sum
        elif not extracted.get('total_amount'):
            extracted['total_amount'] = item_sum
            extracted['amount'] = item_sum
    return extracted


def _text_layer_usable(extracted):
    """PDF 文字層是否已含可用發票資料"""
    if not extracted:
        return False
    if extracted.get('line_items'):
        return True
    if extracted.get('total_amount') and extracted.get('company_name_en'):
        return True
    if extracted.get('total_amount') and extracted.get('company_name_zh'):
        return True
    return False


def _extracted_is_useful(extracted):
    """結構化識別是否取得可用欄位"""
    if not extracted:
        return False
    if extracted.get('line_items'):
        return True
    if extracted.get('total_amount'):
        return True
    if extracted.get('invoice_no') or extracted.get('invoice_date'):
        return True
    return False


def _enrich_line_items(result, pdf_path, text):
    """補充 line_items 並生成 description 表格"""
    items = []
    if text:
        items = parse_line_items_from_text(text)
    if not items and pdf_path and str(pdf_path).lower().endswith('.pdf'):
        items = extract_pdf_tables(pdf_path)

    result['line_items'] = _sanitize_line_items(items)
    items = result['line_items']
    if items:
        result['description'] = format_description_from_items(items, result.get('description'))
        item_amounts = [it['amount'] for it in items if it.get('amount')]
        item_sum = sum(item_amounts) if item_amounts else 0
        if item_sum > 0:
            refs = item_amounts + ([item_sum] if len(item_amounts) > 1 else [])
            fixed = _fix_dollar_eight_amount(result.get('total_amount'), refs)
            if fixed and abs(fixed - (result.get('total_amount') or 0)) > 0.01:
                result['total_amount'] = fixed
                result['amount'] = fixed
            elif abs((result.get('total_amount') or 0) - item_sum) > 1:
                if (result.get('total_amount') or 0) > item_sum * 2:
                    result['total_amount'] = item_sum
                    result['amount'] = item_sum
            elif not result.get('total_amount'):
                result['total_amount'] = item_sum
                result['amount'] = item_sum
    elif not result.get('description') and text:
        for line in text.split('\n'):
            line = line.strip()
            if (len(line) > 8 and not _is_header_line(line)
                    and not _is_total_line(line) and not _is_skippable_desc_line(line)):
                result['description'] = line[:200]
                break


def normalize_date(date_str):
    date_str = date_str.strip()
    formats = [
        '%d/%m/%Y', '%d-%m-%Y', '%d.%m.%Y',
        '%Y/%m/%d', '%Y-%m-%d', '%Y.%m.%d',
        '%d/%m/%y', '%d-%m-%y', '%m/%d/%Y',
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            if dt.year < 100:
                dt = dt.replace(year=dt.year + 2000)
            return dt.strftime('%Y-%m-%d')
        except ValueError:
            continue
    return date_str


# ─── 主處理函數 ──────────────────────────────────────────────

def process_pdf(pdf_path, api_key=None, quark_client_id=None, quark_client_key=None,
                quark_api_key=None, ocr_mode='auto'):
    """
    主 OCR 處理
    ocr_mode: auto | local | quark_handwritten | quark_general | quark_invoice
    返回: (extracted_data, raw_text, method_used, error)
    """
    filename = os.path.basename(pdf_path)
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    _log(f"\n[OCR] Processing: {filename}")

    raw_text = ''

    # 步驟1: PDF 文字層提取（僅在已有完整資料時跳過圖像 OCR）
    if ext == 'pdf':
        _log("[OCR] Step 1: PDF text layer (pdfplumber + pymupdf)...")
        raw_text, text_method = extract_pdf_text_combined(pdf_path)
        if raw_text and len(raw_text.strip()) > 50:
            extracted = extract_invoice_data(raw_text, pdf_path)
            if _text_layer_usable(extracted):
                _log(f"[OCR] Text layer OK via {text_method} ({len(raw_text)} chars)")
                return extracted, raw_text, text_method, None
            _log(f"[OCR] Text layer incomplete ({len(raw_text)} chars), using image OCR")
        else:
            _log(f"[OCR] Text layer insufficient ({len(raw_text)} chars), using image OCR")
    else:
        raw_text = ''

    # 步驟2: 轉換為高解析度圖像
    if ext == 'pdf':
        _log("[OCR] Step 2: PDF to images (300dpi)...")
        image_list = pdf_pages_to_images(pdf_path, max_pages=5, dpi=300)
    else:
        with open(pdf_path, 'rb') as f:
            image_list = [f.read()]

    if not image_list:
        return _empty_result(raw_text), raw_text, 'failed', '無法讀取 PDF 圖像'

    _log(f"[OCR] Prepared {len(image_list)} page(s)")

    quark_id = quark_client_id or ''
    quark_key = quark_client_key or ''
    quark_scene_key = (quark_api_key or '').strip()
    use_quark = ocr_mode != 'local' and quark_id and quark_key
    # 自動模式跳過商業發票 API（未開通套餐時很慢）；僅 quark_invoice 模式才嘗試
    use_quark_invoice = ocr_mode == 'quark_invoice' and use_quark
    use_quark_scene = ocr_mode == 'quark_invoice' and quark_scene_key
    quark_fatal = False
    q_err = None

    def _try_quark_commercial_invoice():
        from quark_ocr import (
            quark_recognize_commercial_invoice_images,
            quark_recognize_images,
            parse_overseas_invoice_data,
            QUARK_COMMERCIAL_INVOICE,
        )
        _log('[OCR] Step 3a: Quark RecognizeCommercialInvoice...')
        inv_data, inv_err = quark_recognize_commercial_invoice_images(
            image_list, quark_id, quark_key)
        if not inv_data:
            return None, None, inv_err
        extracted = parse_overseas_invoice_data(inv_data, QUARK_COMMERCIAL_INVOICE)
        q_text, _ = quark_recognize_images(
            image_list, quark_id, quark_key, QUARK_GENERAL)
        if q_text:
            extracted = _merge_text_line_items(extracted, q_text, pdf_path if ext == 'pdf' else None)
            if not extracted.get('raw_text') or extracted['raw_text'].startswith('{'):
                extracted['raw_text'] = q_text
        if extracted.get('line_items') and not extracted.get('description'):
            extracted['description'] = format_description_from_items(
                extracted['line_items'], extracted.get('description'))
        if not extracted.get('line_items'):
            return None, None, '商業發票 API 無項目明細，改用通用識別'
        if not _extracted_is_useful(extracted):
            return None, None, inv_err or '商業發票 API 未返回可用欄位'
        raw = extracted.get('raw_text') or ''
        _log(f'[OCR] Quark commercial invoice OK ({len(extracted.get("line_items") or [])} items)')
        return extracted, raw, None

    # 步驟3a: 夸克商業發票（Client ID/Key + RecognizeCommercialInvoice）
    if use_quark_invoice:
        extracted, raw, inv_err = _try_quark_commercial_invoice()
        if extracted:
            return extracted, raw, 'quark_invoice', None
        _log(f'[OCR] Quark commercial invoice failed: {inv_err}')

    # 步驟3a2: 備用 aiApiKey + scene（CLI 套餐，選填）
    if use_quark_scene:
        from quark_ocr import (
            quark_recognize_scene_images, parse_overseas_invoice_data, SCENE_COMMERCIAL_INVOICE
        )
        _log('[OCR] Step 3a2: Quark scene API (commercial-invoice-ocr)...')
        inv_data, scene_err = quark_recognize_scene_images(
            image_list, quark_scene_key, SCENE_COMMERCIAL_INVOICE)
        if inv_data:
            extracted = parse_overseas_invoice_data(inv_data, SCENE_COMMERCIAL_INVOICE)
            extracted = _merge_text_line_items(extracted, extracted.get('raw_text'))
            if extracted.get('line_items') and not extracted.get('description'):
                extracted['description'] = format_description_from_items(
                    extracted['line_items'], extracted.get('description'))
            raw = extracted.get('raw_text', '')
            return extracted, raw, 'quark_invoice', None
        _log(f'[OCR] Quark scene API failed: {scene_err}')

    # 步驟3b: 夸克 AI OCR（手寫/印刷中文識別率更高，需 Client ID/Key）
    if use_quark:
        from quark_ocr import (
            quark_recognize_images, QUARK_GENERAL, QUARK_HANDWRITTEN, is_quark_configured
        )
        quark_modes = []
        if ocr_mode == 'quark_handwritten':
            quark_modes = [(QUARK_HANDWRITTEN, 'quark_handwritten')]
        elif ocr_mode in ('quark_general', 'quark_invoice'):
            quark_modes = [(QUARK_GENERAL, 'quark_general')]
        else:
            # auto: 先印刷體，再手寫體
            quark_modes = [
                (QUARK_GENERAL, 'quark_general'),
                (QUARK_HANDWRITTEN, 'quark_handwritten'),
            ]

        from quark_ocr import is_quark_fatal_error
        for func_opt, method_name in quark_modes:
            if quark_fatal:
                break
            _log(f"[OCR] Step 3: Quark AI ({func_opt})...")
            q_text, q_err = quark_recognize_images(
                image_list, quark_id, quark_key, func_opt, max_pages=2)
            if q_text and len(q_text.strip()) > 10:
                _log(f"[OCR] Quark OK ({len(q_text)} chars)")
                extracted = extract_invoice_data(
                    q_text, pdf_path if ext == 'pdf' else None, gemini_api_key=api_key)
                if not extracted.get('line_items'):
                    _log('[OCR] No line items from rules, retry parse on raw text')
                    retry_items = parse_line_items_from_text(q_text)
                    if retry_items:
                        extracted['line_items'] = retry_items
                        extracted['description'] = format_description_from_items(
                            retry_items, extracted.get('description'))
                        _log(f'[OCR] Line items recovered ({len(retry_items)} items)')
                    else:
                        _log('[OCR] No line items, check Gemini fallback')
                return extracted, q_text, method_name, None
            if q_err:
                _log(f"[OCR] Quark insufficient: {q_err}")
            if is_quark_fatal_error(q_err):
                quark_fatal = True
                _log('[OCR] Quark auth/package error, skip remaining Quark attempts')

    # 步驟4: RapidOCR（本地免費）
    if ocr_mode not in ('quark_handwritten', 'quark_general', 'quark_invoice'):
        _log("[OCR] Step 4: RapidOCR (zh/en)...")
        rapid_text, rapid_err = ocr_with_rapidocr(image_list)
        if rapid_text and len(rapid_text.strip()) > 10:
            _log(f"[OCR] RapidOCR OK ({len(rapid_text)} chars)")
            extracted = extract_invoice_data(
                rapid_text, pdf_path if ext == 'pdf' else None, gemini_api_key=api_key)
            warn = None
            if quark_fatal and q_err:
                warn = f'{q_err}（已改用 RapidOCR，建議同步系統時間或檢查夸克憑證）'
            return extracted, rapid_text, 'rapidocr', warn
        _log(f"[OCR] RapidOCR insufficient: {rapid_err}")
    else:
        rapid_text, rapid_err = '', 'skipped (quark-only mode)'

    # 步驟5: Gemini Vision（可選）
    if api_key:
        _log("[OCR] Step 5: Gemini Vision...")
        try:
            structured, gemini_err = ocr_with_gemini(image_list[0], api_key)
            if structured:
                _log("[OCR] Gemini OK")
                if not structured.get('line_items'):
                    structured['line_items'] = []
                if structured.get('line_items') and not structured.get('description'):
                    structured['description'] = format_description_from_items(
                        structured['line_items'], structured.get('description'))
                raw = structured.get('raw_text', '')
                return structured, raw, 'gemini', None
            _log(f"[OCR] Gemini failed: {gemini_err}")
        except Exception as e:
            _log(f"[OCR] Gemini error: {e}")

    hint = rapid_err or '無法識別，請手動填入資料'
    if get_rapid_ocr() is None:
        hint = 'RapidOCR 未就緒，請執行: pip install rapidocr-onnxruntime'
    _log(f"[OCR] All methods failed: {hint}")
    return _empty_result(raw_text), raw_text or rapid_text or '', 'failed', hint


def _empty_result(raw_text=''):
    return {
        'invoice_no': None, 'invoice_date': None, 'quotation_no': None,
        'company_name_en': None, 'company_name_zh': None,
        'description': None, 'amount': None, 'total_amount': None,
        'line_items': [],
        'raw_text': raw_text
    }


def get_available_engines(quark_client_id=None, quark_client_key=None,
                        quark_api_key=None, gemini_api_key=None):
    engines = []
    try:
        import pdfplumber
        engines.append('pdfplumber (PDF 文字層 — 免費)')
    except ImportError:
        pass
    try:
        import fitz
        engines.append('PyMuPDF (PDF 文字層 — 免費)')
    except ImportError:
        pass

    from quark_ocr import is_quark_configured, is_quark_scene_configured
    if is_quark_configured(quark_client_id, quark_client_key):
        engines.append('夸克 AI 手寫識別 (RecognizeWritten — 推薦手寫中文)')
        engines.append('夸克 AI 通用識別 (RecognizeGeneralDocument)')
        engines.append('夸克 商業發票 (RecognizeCommercialInvoice — Client ID/Key)')
    else:
        engines.append('夸克 AI (未設定 — 到 scan.quark.cn/business 申請免費額度)')
    if is_quark_scene_configured(quark_api_key):
        engines.append('夸克 Scene API (commercial-invoice-ocr — 選填備用)')

    if get_rapid_ocr() is not None:
        engines.append('RapidOCR (本地中文 OCR — 免費)')
    else:
        try:
            from rapidocr_onnxruntime import RapidOCR
            engines.append('RapidOCR (已安裝)')
        except ImportError:
            engines.append('RapidOCR (未安裝)')

    if gemini_api_key:
        engines.append('Gemini Vision (已設定 API Key)')
    else:
        try:
            import google.generativeai
            engines.append('Gemini Vision (選用 API Key)')
        except ImportError:
            pass
    return engines


if __name__ == '__main__':
    import sys
    print("Engines:", get_available_engines())
    if len(sys.argv) > 1:
        data, text, method, err = process_pdf(sys.argv[1])
        print(f"Method: {method}")
        if err:
            print(f"Error: {err}")
        print(f"Text preview:\n{text[:500]}")
        for k, v in data.items():
            if k != 'raw_text' and v is not None:
                print(f"  {k}: {v}")
