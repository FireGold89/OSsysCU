"""
quark_ocr.py — 夸克掃描王 Vision OCR API
適用手寫中文、印刷體、表格識別、海外票據結構化識別
申請憑證: https://scan.quark.cn/business
海外票據: https://scan.quark.cn/blm/scank-business-docs-703/tech?id=14
"""
import hashlib
import json
import re
import time
import uuid

import requests

QUARK_API_URL = 'https://scan-business.quark.cn/vision'
SUCCESS_CODE = '00000'
TIMEOUT = 45

# 認證/套餐錯誤 — 同一請求內不應重複嘗試
QUARK_FATAL_CODES = frozenset({'A0201', 'A0202', 'A0210', 'A0211'})

# function_option 值（夸克開放平台 — Client ID/Key 簽名認證）
QUARK_GENERAL = 'RecognizeGeneralDocument'
QUARK_HANDWRITTEN = 'RecognizeWritten'
QUARK_TABLE = 'RecognizeTable'
QUARK_COMMERCIAL_INVOICE = 'RecognizeCommercialInvoice'

# scene 值（aiApiKey 認證 — 結構化票據識別）
SCENE_COMMERCIAL_INVOICE = 'commercial-invoice-ocr'
SCENE_TRAIN_TICKET = 'train-ticket-ocr'
SCENE_VAT_INVOICE = 'vat-invoice-ocr'

OVERSEAS_INVOICE_SCENES = {
    'commercial_invoice': SCENE_COMMERCIAL_INVOICE,
    'train_ticket': SCENE_TRAIN_TICKET,
    'vat_invoice': SCENE_VAT_INVOICE,
}


def _generate_signature(client_id, client_secret, business, sign_method, sign_nonce, timestamp):
    raw = f'{client_id}_{business}_{sign_method}_{sign_nonce}_{timestamp}_{client_secret}'
    return hashlib.sha3_256(raw.encode('utf-8')).hexdigest().lower()


def _quark_timestamp_ms(offset_ms=0):
    """夸克 API 要求 timestamp 與伺服器時間接近（毫秒）"""
    return int(time.time() * 1000) + offset_ms


def _build_signed_payload(image_bytes, client_id, client_secret, function_option,
                          return_image_info=False, data_type='image', timestamp_ms=None):
    import base64
    business = 'vision'
    sign_method = 'SHA3-256'
    sign_nonce = uuid.uuid4().hex
    ts = timestamp_ms if timestamp_ms is not None else _quark_timestamp_ms()
    req_id = uuid.uuid4().hex
    signature = _generate_signature(
        client_id, client_secret, business, sign_method, sign_nonce, ts
    )
    return {
        'dataBase64': base64.b64encode(image_bytes).decode('ascii'),
        'dataType': data_type,
        'serviceOption': 'ocr',
        'inputConfigs': json.dumps({'function_option': function_option}),
        'outputConfigs': json.dumps({'need_return_image': 'True' if return_image_info else 'False'}),
        'reqId': req_id,
        'clientId': client_id,
        'signMethod': sign_method,
        'signNonce': sign_nonce,
        'timestamp': ts,
        'signature': signature,
    }


def _format_quark_error(code, message):
    msg = message or '未知錯誤'
    if code == 'A0211':
        msg = '額度不足，請到夸克開發者後台開通對應套餐'
    elif code == 'A0210':
        msg = '未開通此能力套餐（no match order），請在後台購買或改用通用識別'
    elif code == 'A0202':
        msg = '時間戳無效（請同步 Windows 系統時間，或檢查 Client ID/Key）'
    return f'夸克 API: {msg} (code={code})'


def is_quark_fatal_error(err_msg):
    if not err_msg:
        return False
    return any(f'code={c}' in err_msg or f'code={c})' in err_msg for c in QUARK_FATAL_CODES)


def quark_recognize_raw(image_bytes, client_id, client_secret,
                        function_option=QUARK_GENERAL, return_image_info=False):
    """
    識別單張圖片，返回完整 data 字典
    返回: (data_dict, error_msg)
    """
    if not client_id or not client_secret:
        return None, '未設定夸克 Client ID / Client Key'

    last_err = None
    for offset_ms in (0, -60_000, 60_000):
        payload = _build_signed_payload(
            image_bytes, client_id, client_secret, function_option,
            return_image_info, timestamp_ms=_quark_timestamp_ms(offset_ms),
        )
        try:
            resp = requests.post(QUARK_API_URL, json=payload, timeout=TIMEOUT)
            if not resp.ok:
                return None, f'HTTP {resp.status_code}: {resp.text[:200]}'

            body = resp.json()
            if body.get('code') == SUCCESS_CODE:
                return body.get('data') or {}, None

            code = body.get('code', '')
            last_err = _format_quark_error(code, body.get('message'))
            if code != 'A0202':
                return None, last_err
        except requests.Timeout:
            return None, '夸克 API 請求逾時'
        except requests.RequestException as e:
            return None, f'夸克 API 網絡錯誤: {e}'
        except Exception as e:
            return None, f'夸克 OCR 錯誤: {e}'

    return None, last_err or '夸克 API 錯誤'


def _extract_structured_from_quark_data(data):
    """從夸克 API data 提取結構化發票 JSON"""
    if not data:
        return None

    nested_keys = (
        'CommercialInvoiceInfo', 'InvoiceInfo', 'invoice', 'result',
        'ocrResult', 'structured_result', 'StructuredResult',
    )
    for key in nested_keys:
        val = data.get(key)
        if isinstance(val, dict):
            return val

    ocr_info = data.get('OcrInfo') or []
    if ocr_info and isinstance(ocr_info[0], dict):
        block = ocr_info[0]
        for key in nested_keys + ('Result', 'Data', 'data'):
            val = block.get(key)
            if isinstance(val, dict):
                return val
        text = (block.get('Text') or '').strip()
        if text.startswith('{') or text.startswith('['):
            try:
                parsed = json.loads(text)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass

    if isinstance(data, dict) and any(
        k in data for k in (
            'invoice_no', 'invoiceNo', 'line_items', 'lineItems', 'items',
            'seller_name', 'sellerName', 'total_amount', 'totalAmount',
            '發票號碼', '銷售方', '合計', '明細',
        )
    ):
        return data

    return None


def quark_recognize_image(image_bytes, client_id, client_secret,
                          function_option=QUARK_GENERAL, return_image_info=False):
    """
    識別單張圖片
    返回: (text, error_msg)
    """
    data, err = quark_recognize_raw(
        image_bytes, client_id, client_secret, function_option, return_image_info
    )
    if err and not data:
        return None, err

    ocr_info = (data or {}).get('OcrInfo') or []
    if not ocr_info:
        return '', None

    text = ocr_info[0].get('Text') or ''
    return text.strip(), None


def quark_recognize_commercial_invoice(image_bytes, client_id, client_secret):
    """商業發票結構化識別（RecognizeCommercialInvoice）"""
    data, err = quark_recognize_raw(
        image_bytes, client_id, client_secret, QUARK_COMMERCIAL_INVOICE
    )
    if err and not data:
        return None, err
    structured = _extract_structured_from_quark_data(data)
    if structured:
        return structured, None
    return data, None


def quark_recognize_commercial_invoice_images(image_bytes_list, client_id, client_secret):
    """多頁商業發票識別"""
    if not image_bytes_list:
        return None, '無圖像'

    merged = {}
    last_err = None
    for i, img in enumerate(image_bytes_list):
        data, err = quark_recognize_commercial_invoice(img, client_id, client_secret)
        if err and not data:
            if i == 0:
                return None, err
            last_err = err
            continue
        if data:
            if len(image_bytes_list) > 1:
                merged[f'page_{i + 1}'] = data
            else:
                merged = data

    if merged:
        return merged, None
    return None, last_err or '未識別到商業發票資料'


def quark_recognize_images(image_bytes_list, client_id, client_secret, function_option=QUARK_GENERAL,
                           max_pages=2):
    """識別多頁圖片，合併文字"""
    if not image_bytes_list:
        return None, '無圖像'

    parts = []
    last_err = None
    for i, img in enumerate(image_bytes_list[:max_pages]):
        text, err = quark_recognize_image(img, client_id, client_secret, function_option)
        last_err = err
        if err and not text:
            if i == 0:
                return None, err
            if is_quark_fatal_error(err):
                return None, err
            continue
        if text:
            if len(image_bytes_list) > 1:
                parts.append(f'--- 第 {i + 1} 頁 ---\n{text}')
            else:
                parts.append(text)

    combined = '\n\n'.join(parts).strip()
    return (combined, None) if combined else (None, err or '未識別到文字')


def is_quark_configured(client_id, client_secret):
    return bool(client_id and client_secret)


def is_quark_scene_configured(api_key):
    return bool(api_key and str(api_key).strip())


def quark_recognize_scene(image_bytes, api_key, scene=SCENE_COMMERCIAL_INVOICE, data_type='image'):
    """
    夸克場景化結構化識別（海外票據 / 商業發票等）
    使用 aiApiKey 認證，回傳原始 data 字典
    返回: (data_dict, error_msg)
    """
    if not is_quark_scene_configured(api_key):
        return None, '未設定夸克 API Key（海外票據識別需 aiApiKey）'

    import base64
    payload = {
        'aiApiKey': api_key.strip(),
        'dataType': data_type,
        'scene': scene,
        'dataBase64': base64.b64encode(image_bytes).decode('ascii'),
    }
    headers = {'Content-Type': 'application/json', 'X-Appbuilder-From': 'app'}

    try:
        resp = requests.post(QUARK_API_URL, json=payload, headers=headers, timeout=TIMEOUT)
        if not resp.ok:
            return None, f'HTTP {resp.status_code}: {resp.text[:200]}'

        body = resp.json()
        if body.get('code') != SUCCESS_CODE:
            msg = body.get('message', '未知錯誤')
            if body.get('code') == 'A0211':
                msg = '額度不足，請到夸克開發者後台充值 API 套餐'
            return None, f'夸克 API: {msg} (code={body.get("code")})'

        return body.get('data') or {}, None

    except requests.Timeout:
        return None, '夸克 API 請求逾時'
    except requests.RequestException as e:
        return None, f'夸克 API 網絡錯誤: {e}'
    except Exception as e:
        return None, f'夸克場景識別錯誤: {e}'


def quark_recognize_scene_images(image_bytes_list, api_key, scene=SCENE_COMMERCIAL_INVOICE):
    """多頁圖片場景識別，合併結構化結果"""
    if not image_bytes_list:
        return None, '無圖像'

    merged = {}
    last_err = None
    for i, img in enumerate(image_bytes_list):
        data, err = quark_recognize_scene(img, api_key, scene)
        if err and not data:
            if i == 0:
                return None, err
            last_err = err
            continue
        if data:
            if len(image_bytes_list) > 1:
                merged[f'page_{i + 1}'] = data
            else:
                merged = data

    if merged:
        return merged, None
    return None, last_err or '未識別到票據資料'


def _first_value(obj, keys):
    """從 dict 或巢狀結構中依序查找第一個非空值"""
    if not isinstance(obj, dict):
        return None
    for key in keys:
        val = obj.get(key)
        if val is not None and str(val).strip() not in ('', 'null', 'None'):
            return val
    for val in obj.values():
        if isinstance(val, dict):
            found = _first_value(val, keys)
            if found is not None:
                return found
    return None


def _parse_amount(val):
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    s = re.sub(r'[^\d.\-]', '', s.replace(',', ''))
    try:
        return float(s) if s else None
    except ValueError:
        return None


def _normalize_date_str(val):
    if not val:
        return None
    s = str(val).strip()
    m = re.search(r'(\d{4})[年/\-\.](\d{1,2})[月/\-\.](\d{1,2})', s)
    if m:
        return f'{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}'
    m = re.search(r'(\d{1,2})[\/\-\.](\d{1,2})[\/\-\.](\d{2,4})', s)
    if m:
        d, mo, y = m.group(1), m.group(2), m.group(3)
        if len(y) == 2:
            y = f'20{y}'
        return f'{y}-{int(mo):02d}-{int(d):02d}'
    m = re.search(r'(\d{4})[\/\-\.](\d{1,2})[\/\-\.](\d{1,2})', s)
    if m:
        return f'{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}'
    return s[:10] if len(s) >= 8 else s


def _parse_line_items(data):
    """從結構化 JSON 提取 line_items"""
    list_keys = ('line_items', 'lineItems', 'items', 'details', 'entry',
                 'item_list', 'itemList', 'products', 'productList', 'invoiceLists',
                 '明細', '明细', '商品明細', '商品明细', '貨品明細', '货品明细')
    items_raw = None
    for key in list_keys:
        if isinstance(data.get(key), list) and data[key]:
            items_raw = data[key]
            break
    if not items_raw:
        for val in data.values():
            if isinstance(val, dict):
                items_raw = _parse_line_items(val)
                if items_raw:
                    return items_raw
        return []

    items = []
    for i, row in enumerate(items_raw):
        if not isinstance(row, dict):
            if isinstance(row, str) and row.strip():
                items.append({'no': str(i + 1), 'description': row.strip(),
                              'qty': '', 'unit': '', 'unit_price': '', 'amount': ''})
            continue
        desc = _first_value(row, (
            'description', 'name', 'item_name', 'itemName', 'entry_name',
            'product_name', 'productName', 'commodityName', 'goods_name', 'title',
            '貨品名稱', '货品名称', '品名', '項目描述', '项目描述', '商品名稱', '商品名称',
        ))
        qty = _first_value(row, ('qty', 'quantity', 'qnty', 'num', '數量', '数量'))
        unit = _first_value(row, ('unit', 'uom', 'measure', '單位', '单位'))
        unit_price = _parse_amount(_first_value(row, (
            'unit_price', 'unitPrice', 'price', 'unit_prict', 'unit_amount',
        )))
        amount = _parse_amount(_first_value(row, (
            'amount', 'total', 'total_price', 'price_amount', 'line_total', 'sum',
        )))
        items.append({
            'no': str(_first_value(row, ('no', 'index', 'seq', 'line_no')) or (i + 1)),
            'description': str(desc or '').strip(),
            'qty': str(qty or '').strip(),
            'unit': str(unit or '').strip(),
            'unit_price': unit_price if unit_price is not None else '',
            'amount': amount if amount is not None else '',
        })
    return [it for it in items if it.get('description')]


def parse_overseas_invoice_data(api_data, scene=SCENE_COMMERCIAL_INVOICE):
    """
    將夸克海外票據 / 商業發票結構化 JSON 映射為系統欄位
    """
    if not api_data:
        return {
            'invoice_no': None, 'invoice_date': None, 'quotation_no': None,
            'company_name_en': None, 'company_name_zh': None,
            'description': None, 'amount': None, 'total_amount': None,
            'line_items': [], 'raw_text': '',
        }

    root = api_data
    if len(api_data) == 1 and isinstance(next(iter(api_data.values())), dict):
        root = next(iter(api_data.values()))

    invoice_no = _first_value(root, (
        'invoice_no', 'invoiceNo', 'invoice_number', 'invoiceNumber',
        'InvoiceNumber', 'number', 'no', 'invoice_id',
        '發票號碼', '发票号码', '單據編號', '单据编号',
    ))
    invoice_date = _normalize_date_str(_first_value(root, (
        'invoice_date', 'invoiceDate', 'date', 'issue_date', 'IssueDate',
        'billing_date', 'transaction_date', '開票日期', '开票日期', '日期',
    )))
    company = _first_value(root, (
        'seller_name', 'sellerName', 'vendor', 'vendor_name', 'supplier',
        'supplier_name', 'company_name', 'companyName', 'merchant_name',
        'issuer', 'from', 'seller', '銷售方', '销售方', '供應商', '供应商',
    ))
    buyer = _first_value(root, (
        'buyer_name', 'buyerName', 'customer', 'customer_name', 'bill_to',
    ))
    currency = _first_value(root, (
        'currency', 'currency_code', 'currencyCode', 'total_currency',
    ))
    total = _parse_amount(_first_value(root, (
        'total_amount', 'totalAmount', 'total', 'total_price', 'total_price_and_tax',
        'amount', 'grand_total', 'sum', 'invoice_total', 'total_including_tax',
        '合計', '合计', '總金額', '总金额', '價稅合計', '价税合计',
    )))
    description = _first_value(root, (
        'description', 'summary', 'subject', 'remarks', 'note', 'title',
    ))
    line_items = _parse_line_items(root)

    company_str = str(company or '').strip()
    company_en = company_str if re.search(r'[A-Za-z]', company_str) else None
    company_zh = company_str if re.search(r'[\u4e00-\u9fff]', company_str) else None
    if not company_en and not company_zh and buyer:
        buyer_str = str(buyer).strip()
        company_en = buyer_str if re.search(r'[A-Za-z]', buyer_str) else None
        company_zh = buyer_str if re.search(r'[\u4e00-\u9fff]', buyer_str) else None

    if not description and line_items:
        description = '；'.join(
            it['description'] for it in line_items[:3] if it.get('description')
        )

    raw_text = json.dumps(api_data, ensure_ascii=False, indent=2)

    return {
        'invoice_no': str(invoice_no).strip() if invoice_no else None,
        'invoice_date': invoice_date,
        'quotation_no': None,
        'company_name_en': company_en,
        'company_name_zh': company_zh,
        'description': str(description).strip() if description else None,
        'amount': total,
        'total_amount': total,
        'currency': str(currency).strip() if currency else None,
        'line_items': line_items,
        'raw_text': raw_text,
        'quark_scene': scene,
    }
