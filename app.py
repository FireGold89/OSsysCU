"""
app.py — QS付款管理系統 Flask API主程式
啟動: python app.py
訪問: http://localhost:5000
"""
import os
import json
import uuid
from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename

import database as db
from config import BASE_DIR, FRONTEND_DIR, UPLOAD_DIR
from ocr_processor import process_pdf

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path='')
CORS(app)

ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def resp(data=None, error=None, status=200):
    if error:
        return jsonify({'success': False, 'error': error}), status
    return jsonify({'success': True, 'data': data}), status


# ─── 前端路由 ───────────────────────────────────────────────────────────
@app.route('/')
def index():
    return send_from_directory(FRONTEND_DIR, 'index.html')


@app.route('/css/<path:filename>')
def static_css(filename):
    return send_from_directory(os.path.join(FRONTEND_DIR, 'css'), filename)


@app.route('/js/<path:filename>')
def static_js(filename):
    return send_from_directory(os.path.join(FRONTEND_DIR, 'js'), filename)


@app.route('/assets/<path:filename>')
def static_assets(filename):
    return send_from_directory(os.path.join(FRONTEND_DIR, 'assets'), filename)


# ─── Settings API ───────────────────────────────────────────────────────
@app.route('/api/settings', methods=['GET'])
def get_settings():
    return resp({
        'gemini_api_key': db.get_setting('gemini_api_key', ''),
        'quark_client_id': db.get_setting('quark_client_id', ''),
        'quark_client_key': db.get_setting('quark_client_key', ''),
        'quark_api_key': db.get_setting('quark_api_key', ''),
        'ocr_mode': db.get_setting('ocr_mode', 'auto'),
        'company_name': db.get_setting('company_name', 'Mepork Engineering Services Limited'),
    })


@app.route('/api/settings', methods=['POST'])
def save_settings():
    data = request.json or {}
    for key, value in data.items():
        db.set_setting(key, str(value))
    return resp({'message': '設定已儲存'})


# ─── Projects API ───────────────────────────────────────────────────────
@app.route('/api/projects', methods=['GET'])
def get_projects():
    return resp(db.get_all_projects())


@app.route('/api/projects/<int:project_id>', methods=['GET'])
def get_project(project_id):
    project = db.get_project(project_id)
    if not project:
        return resp(error='項目不存在', status=404)
    return resp(project)


@app.route('/api/projects', methods=['POST'])
def create_project():
    data = request.json or {}
    required = ['project_code']
    for field in required:
        if not data.get(field):
            return resp(error=f'缺少必填欄位: {field}', status=400)
    data.setdefault('project_name', data['project_code'])
    data.setdefault('client', '')
    data.setdefault('main_contractor', '')
    data.setdefault('contract_amount', 0)
    data.setdefault('start_date', None)
    data.setdefault('status', 'Active')
    data.setdefault('notes', '')
    data.setdefault('labour_allocation', 0)
    new_id = db.create_project(data)
    return resp({'id': new_id}, status=201)


@app.route('/api/projects/<int:project_id>', methods=['PUT'])
def update_project(project_id):
    data = request.json or {}
    data.setdefault('project_code', '')
    data.setdefault('project_name', '')
    data.setdefault('client', '')
    data.setdefault('main_contractor', '')
    data.setdefault('contract_amount', 0)
    data.setdefault('start_date', None)
    data.setdefault('status', 'Active')
    data.setdefault('notes', '')
    data.setdefault('labour_allocation', 0)
    db.update_project(project_id, data)
    return resp({'message': '已更新'})


@app.route('/api/projects/<int:project_id>', methods=['DELETE'])
def delete_project(project_id):
    db.delete_project(project_id)
    return resp({'message': '已刪除'})


# ─── Subcontractors API ─────────────────────────────────────────────────
@app.route('/api/projects/<int:project_id>/subcontractors', methods=['GET'])
def get_subcontractors(project_id):
    return resp(db.get_subcontractors(project_id))


@app.route('/api/subcontractors', methods=['POST'])
def create_subcontractor():
    data = request.json or {}
    if not data.get('project_id') or not data.get('sc_no'):
        return resp(error='缺少必填欄位', status=400)
    data.setdefault('quotation_no', None)
    data.setdefault('company_name_en', None)
    data.setdefault('company_name_zh', None)
    data.setdefault('description', None)
    data.setdefault('contract_amount', 0)
    data.setdefault('payment_note', None)
    data.setdefault('oa_status', None)
    data.setdefault('oa_ref', None)
    data.setdefault('oa_no', None)
    data.setdefault('quotation_saved', None)
    data.setdefault('quotation_date', None)
    data.setdefault('oa_date', None)
    data.setdefault('is_excluded', 0)
    data.setdefault('contract_sum', data.get('contract_amount') or 0)
    data.setdefault('vo_amount', 0)
    if data.get('contract_sum') is not None or data.get('vo_amount') is not None:
        data['contract_amount'] = float(data.get('contract_sum') or 0) + float(data.get('vo_amount') or 0)
    from sc_ref import derive_parent_sc_no
    data.setdefault('parent_sc_no', derive_parent_sc_no(data.get('sc_no')))
    ocr_id = data.pop('ocr_id', None)
    data['ocr_id'] = ocr_id
    sc_id = db.upsert_subcontractor(data)
    if ocr_id:
        db.link_ocr_extraction(ocr_id, project_id=data['project_id'], sc_id=sc_id, doc_type='quotation')
    return resp({'id': sc_id}, status=201)


@app.route('/api/subcontractors/<int:sc_id>', methods=['GET'])
def get_subcontractor(sc_id):
    sc = db.get_subcontractor(sc_id)
    if not sc:
        return resp(error='合同項目不存在', status=404)
    sc['documents'] = db.get_sc_documents(sc_id)
    return resp(sc)


@app.route('/api/files/upload', methods=['POST'])
def upload_file():
    """上傳 PDF/圖片至伺服器（不跑 OCR）"""
    if 'file' not in request.files:
        return resp(error='沒有文件', status=400)
    file = request.files['file']
    if not file.filename or not allowed_file(file.filename):
        return resp(error='不支援的文件格式（請上傳 PDF/PNG/JPG）', status=400)

    ext = file.filename.rsplit('.', 1)[1].lower()
    unique_name = f"{uuid.uuid4().hex}.{ext}"
    save_path = os.path.join(UPLOAD_DIR, unique_name)
    file.save(save_path)
    return resp({'pdf_path': unique_name, 'filename': file.filename})


@app.route('/api/subcontractors/<int:sc_id>/quotation-pdf', methods=['POST'])
def upload_sc_quotation_pdf(sc_id):
    """編輯合同時直接上傳報價 PDF（不跑 OCR）"""
    sc = db.get_subcontractor(sc_id)
    if not sc:
        return resp(error='合同項目不存在', status=404)
    if 'file' not in request.files:
        return resp(error='沒有文件', status=400)
    file = request.files['file']
    if not file.filename or not allowed_file(file.filename):
        return resp(error='不支援的文件格式（請上傳 PDF/PNG/JPG）', status=400)

    ext = file.filename.rsplit('.', 1)[1].lower()
    unique_name = f"{uuid.uuid4().hex}.{ext}"
    save_path = os.path.join(UPLOAD_DIR, unique_name)
    file.save(save_path)

    db.attach_quotation_pdf(sc_id, unique_name, original_filename=file.filename)
    return resp({
        'pdf_path': unique_name,
        'filename': file.filename,
        'message': '報價 PDF 已上傳',
    })


@app.route('/api/subcontractors/<int:sc_id>', methods=['DELETE'])
def delete_subcontractor(sc_id):
    db.delete_subcontractor(sc_id)
    return resp({'message': '已刪除'})


# ─── Payment Records API ────────────────────────────────────────────────
@app.route('/api/projects/<int:project_id>/payments', methods=['GET'])
def get_payments(project_id):
    filters = {
        'sc_no': request.args.get('sc_no'),
        'sc_group': request.args.get('sc_group'),
        'search': request.args.get('search'),
    }
    return resp(db.get_payments(project_id, filters))


@app.route('/api/payments', methods=['POST'])
def create_payment():
    data = request.json or {}
    if not data.get('project_id'):
        return resp(error='缺少project_id', status=400)
    # 填充預設值
    for f in ['sc_id', 'seq_no', 'invoice_date', 'invoice_no', 'quotation_no',
              'sc_no', 'company_name_en', 'company_name_zh', 'description',
              'oa_ref', 'oa_no', 'mc_ip_no', 'bc_to_sub', 'sub_ip_no',
              'remark', 'pdf_path', 'ocr_status']:
        data.setdefault(f, None)
    for f in ['contract_amount', 'paid_amount', 'remainder_amount']:
        data.setdefault(f, 0)
    ocr_id = data.pop('ocr_id', None)
    data['ocr_id'] = ocr_id
    new_id = db.create_payment(data)
    if ocr_id:
        db.link_ocr_extraction(
            ocr_id, project_id=data['project_id'], sc_id=data.get('sc_id'),
            payment_id=new_id, doc_type='invoice',
        )
    return resp({'id': new_id}, status=201)


@app.route('/api/payments/<int:payment_id>', methods=['GET'])
def get_payment(payment_id):
    payment = db.get_payment(payment_id)
    if not payment:
        return resp(error='記錄不存在', status=404)
    return resp(payment)


@app.route('/api/payments/<int:payment_id>', methods=['PUT'])
def update_payment(payment_id):
    data = request.json or {}
    for f in ['invoice_date', 'invoice_no', 'quotation_no', 'sc_no',
              'company_name_en', 'company_name_zh', 'description',
              'oa_ref', 'oa_no', 'mc_ip_no', 'bc_to_sub', 'sub_ip_no', 'remark']:
        data.setdefault(f, None)
    for f in ['contract_amount', 'paid_amount', 'remainder_amount']:
        data.setdefault(f, 0)
    db.update_payment(payment_id, data)
    return resp({'message': '已更新'})


@app.route('/api/payments/<int:payment_id>', methods=['DELETE'])
def delete_payment(payment_id):
    db.delete_payment(payment_id)
    return resp({'message': '已刪除'})


# ─── OCR API ────────────────────────────────────────────────
@app.route('/api/ocr/engines', methods=['GET'])
def ocr_engines():
    """返回可用OCR引擎列表"""
    from ocr_processor import get_available_engines
    return resp({'engines': get_available_engines(
        quark_client_id=db.get_setting('quark_client_id'),
        quark_client_key=db.get_setting('quark_client_key'),
        quark_api_key=db.get_setting('quark_api_key'),
        gemini_api_key=db.get_setting('gemini_api_key'),
    )})


@app.route('/api/ocr/upload', methods=['POST'])
def ocr_upload():
    if 'file' not in request.files:
        return resp(error='沒有文件', status=400)

    file = request.files['file']
    if not file.filename or not allowed_file(file.filename):
        return resp(error='不支援的文件格式（請上傳PDF/PNG/JPG）', status=400)

    # 儲存文件
    ext = file.filename.rsplit('.', 1)[1].lower()
    unique_name = f"{uuid.uuid4().hex}.{ext}"
    save_path = os.path.join(UPLOAD_DIR, unique_name)
    file.save(save_path)

    api_key = db.get_setting('gemini_api_key') or None
    quark_id = db.get_setting('quark_client_id') or None
    quark_key = db.get_setting('quark_client_key') or None
    quark_scene_key = db.get_setting('quark_api_key') or None
    ocr_mode = db.get_setting('ocr_mode', 'auto') or 'auto'

    # 執行OCR
    try:
        extracted, raw_text, method, error = process_pdf(
            save_path, api_key,
            quark_client_id=quark_id,
            quark_client_key=quark_key,
            quark_api_key=quark_scene_key,
            ocr_mode=ocr_mode,
        )
    except Exception as e:
        return resp(error=f'OCR處理錯誤: {str(e)}', status=500)

    project_id = request.form.get('project_id', type=int)

    # 儲存OCR記錄（每次上傳均保留 PDF 路徑）
    ocr_id = db.save_ocr_extraction(
        payment_id=None,
        filename=unique_name,
        raw_text=raw_text or '',
        extracted_json=extracted or {},
        confidence='high' if method in (
            'gemini', 'quark_handwritten', 'quark_general', 'quark_invoice') else 'medium',
        status='success' if extracted else 'failed',
        project_id=project_id,
        doc_type='scan',
    )

    from ocr_processor import enrich_extracted_result
    extracted = enrich_extracted_result(extracted or {}, raw_text or '')

    return resp({
        'ocr_id': ocr_id,
        'method': method,
        'filename': file.filename,
        'pdf_path': unique_name,
        'extracted': extracted,
        'raw_text': (raw_text or '')[:2000],  # 限制回傳長度
        'error': error,
    })


@app.route('/api/projects/<int:project_id>/ocr/suggest-sc', methods=['POST'])
def ocr_suggest_sc(project_id):
    if not db.get_project(project_id):
        return resp(error='項目不存在', status=404)
    hints = request.json or {}
    return resp(db.suggest_sc_matches(project_id, hints))


@app.route('/api/projects/<int:project_id>/ocr/next-sc', methods=['POST'])
def ocr_next_sc(project_id):
    if not db.get_project(project_id):
        return resp(error='項目不存在', status=404)
    body = request.json or {}
    prefix = (body.get('prefix') or 'SC').strip().upper()
    company = (body.get('company') or '').strip()
    return resp(db.suggest_next_sc_number(project_id, prefix, company))


@app.route('/api/projects/<int:project_id>/payments/check-invoice', methods=['GET'])
def check_invoice_duplicate(project_id):
    invoice_no = request.args.get('invoice_no', '').strip()
    if not invoice_no:
        return resp({'exists': False})
    existing = db.payment_invoice_exists(project_id, invoice_no)
    return resp({'exists': bool(existing), 'payment': existing})


@app.route('/api/uploads/<filename>')
def serve_upload(filename):
    """提供上傳文件（PDF/圖片），供瀏覽器內嵌預覽"""
    safe = os.path.basename(filename)
    if safe != filename or '..' in filename:
        return jsonify({'success': False, 'error': '無效文件名'}), 400
    path = os.path.join(UPLOAD_DIR, safe)
    if not os.path.isfile(path):
        return jsonify({'success': False, 'error': '文件不存在'}), 404
    ext = safe.rsplit('.', 1)[-1].lower() if '.' in safe else ''
    mime = {
        'pdf': 'application/pdf',
        'png': 'image/png',
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
    }.get(ext, 'application/octet-stream')
    return send_file(path, mimetype=mime, as_attachment=False, download_name=safe)


@app.route('/api/projects/<int:project_id>/interim-payments', methods=['GET'])
def get_interim_payments_api(project_id):
    summary = db.get_ip_period_summary(project_id)
    if summary is None:
        return resp(error='項目不存在', status=404)
    return resp(summary)


@app.route('/api/projects/<int:project_id>/interim-payments/meta', methods=['PUT'])
def update_ip_meta(project_id):
    data = request.json or {}
    if not db.get_project(project_id):
        return resp(error='項目不存在', status=404)
    db.update_ip_period_meta(project_id, data)
    return resp(db.get_ip_period_summary(project_id))


@app.route('/api/interim-payments', methods=['POST'])
def create_interim_payment():
    data = request.json or {}
    if not data.get('project_id') or not data.get('ip_no'):
        return resp(error='缺少 project_id 或 ip_no', status=400)
    for f in ['applied_date', 'certificate_date', 'subcon_cert_date']:
        data.setdefault(f, None)
    for f in ['application_amount', 'certified_income', 'subcon_paid']:
        data.setdefault(f, 0)
    data.setdefault('seq_no', 0)
    ip_id = db.upsert_interim_payment(data)
    return resp({'id': ip_id, 'summary': db.get_ip_period_summary(data['project_id'])}, status=201)


@app.route('/api/interim-payments/<int:ip_id>', methods=['GET'])
def get_interim_payment_api(ip_id):
    row = db.get_interim_payment(ip_id)
    if not row:
        return resp(error='糧期記錄不存在', status=404)
    return resp(row)


@app.route('/api/interim-payments/<int:ip_id>', methods=['PUT'])
def update_interim_payment(ip_id):
    data = request.json or {}
    existing = db.get_interim_payment(ip_id)
    if not existing:
        return resp(error='糧期記錄不存在', status=404)
    data['id'] = ip_id
    data['project_id'] = existing['project_id']
    if not data.get('ip_no'):
        data['ip_no'] = existing['ip_no']
    for f in ['applied_date', 'certificate_date', 'subcon_cert_date']:
        data.setdefault(f, None)
    for f in ['application_amount', 'certified_income', 'subcon_paid', 'seq_no']:
        data.setdefault(f, existing.get(f) or 0)
    db.upsert_interim_payment(data)
    return resp({'summary': db.get_ip_period_summary(existing['project_id'])})


@app.route('/api/interim-payments/<int:ip_id>', methods=['DELETE'])
def delete_interim_payment_api(ip_id):
    project_id = db.delete_interim_payment(ip_id)
    if not project_id:
        return resp(error='糧期記錄不存在', status=404)
    return resp({'summary': db.get_ip_period_summary(project_id)})


# ─── Reports API ────────────────────────────────────────────────────────
@app.route('/api/reports/summary/<int:project_id>', methods=['GET'])
def project_summary(project_id):
    summary = db.get_project_summary(project_id)
    if not summary:
        return resp(error='項目不存在', status=404)
    return resp(summary)


# ─── System API ───────────────────────────────────────────────────────────
@app.route('/api/system/status', methods=['GET'])
def system_status():
    from config import DATA_DIR, DB_PATH, UPLOAD_DIR
    projects = db.get_all_projects()
    upload_count = 0
    if os.path.isdir(UPLOAD_DIR):
        upload_count = len([f for f in os.listdir(UPLOAD_DIR) if os.path.isfile(os.path.join(UPLOAD_DIR, f))])
    conn = db.get_conn()
    payment_count = conn.execute('SELECT COUNT(*) FROM payment_records').fetchone()[0]
    conn.close()
    return resp({
        'data_dir': DATA_DIR,
        'db_path': DB_PATH,
        'db_exists': os.path.exists(DB_PATH),
        'db_size_bytes': os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0,
        'project_count': len(projects),
        'payment_count': payment_count,
        'upload_count': upload_count,
        'volume_mounted': DATA_DIR == '/data',
        'restore_token_configured': bool(os.environ.get('RESTORE_TOKEN', '').strip()),
    })


@app.route('/api/system/restore-db', methods=['POST'])
def restore_database():
    """上傳本機 qs_system.db 還原（空庫可免 token；有資料時需 RESTORE_TOKEN）"""
    expected = os.environ.get('RESTORE_TOKEN', '').strip()
    token = (request.headers.get('X-Restore-Token') or request.form.get('token') or '').strip()
    conn = db.get_conn()
    empty_db = conn.execute('SELECT COUNT(*) FROM payment_records').fetchone()[0] == 0
    empty_db = empty_db and conn.execute('SELECT COUNT(*) FROM projects').fetchone()[0] == 0
    conn.close()

    if expected:
        if token != expected:
            return resp(error='未授權', status=403)
    elif not empty_db:
        return resp(error='請在 Zeabur Variables 設定 RESTORE_TOKEN', status=403)

    if 'file' not in request.files:
        return resp(error='請上傳 qs_system.db 文件', status=400)
    file = request.files['file']
    if not file.filename:
        return resp(error='沒有文件', status=400)

    from config import DB_PATH
    tmp_path = DB_PATH + '.restore_tmp'
    file.save(tmp_path)
    try:
        import sqlite3
        conn = sqlite3.connect(tmp_path)
        conn.execute('SELECT 1 FROM projects LIMIT 1')
        conn.close()
        if os.path.exists(DB_PATH):
            os.replace(DB_PATH, DB_PATH + '.bak')
        os.replace(tmp_path, DB_PATH)
    except Exception as e:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        return resp(error=f'無效的資料庫文件: {e}', status=400)

    projects = db.get_all_projects()
    return resp({
        'message': '資料庫已還原',
        'project_count': len(projects),
    })


@app.route('/api/system/sync-excel', methods=['POST'])
def sync_excel_api():
    """從內建 Excel 同步合同、付款、糧期（需 SYNC_TOKEN 或空庫）"""
    expected = os.environ.get('SYNC_TOKEN', os.environ.get('RESTORE_TOKEN', '')).strip()
    token = (request.headers.get('X-Sync-Token') or request.form.get('token') or '').strip()
    if expected:
        if token != expected:
            return resp(error='未授權', status=403)

    excel_name = 'MS_Q1241_24 - Main contract Works Payment Status Table - R4.xlsx'
    excel_path = os.path.join(BASE_DIR, excel_name)
    if not os.path.exists(excel_path):
        return resp(error=f'找不到 Excel: {excel_name}', status=404)

    project_id = request.json.get('project_id') if request.is_json else None
    if project_id is None:
        project_id = request.form.get('project_id', type=int)

    try:
        from excel_importer import sync_excel_data
        pid = sync_excel_data(excel_path, project_id)
        ip = db.get_ip_period_summary(pid)
        return resp({
            'project_id': pid,
            'message': 'Excel 同步完成',
            'ip_periods': len((ip or {}).get('items') or []),
        })
    except Exception as e:
        return resp(error=f'同步失敗: {str(e)}', status=500)


# ─── Excel Import API ───────────────────────────────────────────────────
@app.route('/api/import/excel', methods=['POST'])
def import_excel_api():
    if 'file' not in request.files:
        return resp(error='沒有文件', status=400)
    file = request.files['file']
    if not file.filename.endswith(('.xlsx', '.xls')):
        return resp(error='請上傳Excel文件', status=400)

    save_path = os.path.join(UPLOAD_DIR, secure_filename(file.filename))
    file.save(save_path)

    try:
        from excel_importer import import_excel
        project_id = import_excel(save_path)
        return resp({'project_id': project_id, 'message': 'Excel匯入成功'})
    except Exception as e:
        return resp(error=f'匯入失敗: {str(e)}', status=500)


# ─── 啟動 ────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    import startup

    port = int(os.environ.get('PORT', 5000))
    print('=' * 60)
    print('  QS付款管理系統 v1.0')
    print(f'  訪問地址: http://localhost:{port}')
    print('=' * 60)

    startup.run()
    app.run(host='0.0.0.0', port=port, debug=False)
