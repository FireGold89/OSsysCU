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
    sc_id = db.upsert_subcontractor(data)
    return resp({'id': sc_id}, status=201)


@app.route('/api/subcontractors/<int:sc_id>', methods=['GET'])
def get_subcontractor(sc_id):
    sc = db.get_subcontractor(sc_id)
    if not sc:
        return resp(error='合同項目不存在', status=404)
    return resp(sc)


@app.route('/api/subcontractors/<int:sc_id>', methods=['DELETE'])
def delete_subcontractor(sc_id):
    db.delete_subcontractor(sc_id)
    return resp({'message': '已刪除'})


# ─── Payment Records API ────────────────────────────────────────────────
@app.route('/api/projects/<int:project_id>/payments', methods=['GET'])
def get_payments(project_id):
    filters = {
        'sc_no': request.args.get('sc_no'),
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
    new_id = db.create_payment(data)
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

    # 儲存OCR記錄
    ocr_id = db.save_ocr_extraction(
        payment_id=None,
        filename=file.filename,
        raw_text=raw_text or '',
        extracted_json=extracted or {},
        confidence='high' if method in (
            'gemini', 'quark_handwritten', 'quark_general', 'quark_invoice') else 'medium',
        status='success' if extracted else 'failed'
    )

    return resp({
        'ocr_id': ocr_id,
        'method': method,
        'filename': file.filename,
        'pdf_path': unique_name,
        'extracted': extracted or {},
        'raw_text': (raw_text or '')[:2000],  # 限制回傳長度
        'error': error,
    })


@app.route('/api/uploads/<filename>')
def serve_upload(filename):
    return send_from_directory(UPLOAD_DIR, filename)


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
