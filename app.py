"""
app.py — QS付款管理系統 Flask API主程式
啟動: python app.py
訪問: http://localhost:5000
"""
import os
import json
import uuid
import re
from io import BytesIO
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, send_from_directory, send_file, session
from flask_cors import CORS
from werkzeug.utils import secure_filename

import auth
import database as db
from config import BASE_DIR, FRONTEND_DIR, UPLOAD_DIR
from ocr_processor import process_pdf

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path='')
app.config['SECRET_KEY'] = auth.secret_key()
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=auth.session_lifetime_days())
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
_secure = os.environ.get('SESSION_COOKIE_SECURE', '').strip().lower()
if _secure in ('1', 'true', 'yes'):
    app.config['SESSION_COOKIE_SECURE'] = True
elif os.path.exists('/.dockerenv'):
    app.config['SESSION_COOKIE_SECURE'] = True
else:
    app.config['SESSION_COOKIE_SECURE'] = False
CORS(app, supports_credentials=True)

ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def resp(data=None, error=None, status=200):
    if error:
        return jsonify({'success': False, 'error': error}), status
    return jsonify({'success': True, 'data': data}), status


@app.before_request
def _require_login():
    return auth.check_request()


# ─── 登入 ────────────────────────────────────────────────────────────────
@app.route('/login.html')
def login_page():
    return send_from_directory(FRONTEND_DIR, 'login.html')


@app.route('/api/auth/login', methods=['POST'])
def auth_login():
    if not auth.is_enabled():
        return resp({'message': '登入未啟用', 'auth_required': False})
    data = request.json or {}
    user = auth.authenticate(data.get('username'), data.get('password'))
    if not user:
        return resp(error='帳號或密碼錯誤', status=401)
    auth.login_user(user)
    return resp({
        'username': user['username'],
        'role': user['role'],
        'auth_required': True,
    })


@app.route('/api/auth/logout', methods=['POST'])
def auth_logout():
    auth.logout_user()
    return resp({'message': '已登出'})


@app.route('/api/auth/me', methods=['GET'])
def auth_me():
    if not auth.is_enabled():
        return resp({'auth_required': False, 'user': None})
    user = auth.current_user()
    if not user:
        return resp({'auth_required': True, 'user': None})
    return resp({'auth_required': True, 'user': user})


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
    fe = os.path.join(FRONTEND_DIR, 'assets')
    if os.path.isfile(os.path.join(fe, filename)):
        return send_from_directory(fe, filename)
    return send_from_directory(os.path.join(BASE_DIR, 'assets'), filename)


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
        'doc_library_url': db.get_setting('doc_library_url', ''),
    })


@app.route('/api/settings', methods=['POST'])
def save_settings():
    data = request.json or {}
    for key, value in data.items():
        db.set_setting(key, str(value))
    return resp({'message': '設定已儲存'})


@app.route('/api/settings/doc-library', methods=['GET'])
def get_doc_library_settings():
    """文件管理設定 — 全局 + 各項目文件庫連結"""
    projects = db.get_all_projects()
    return resp({
        'global_url': db.get_setting('doc_library_url', ''),
        'projects': [
            {
                'id': p['id'],
                'project_code': p.get('project_code'),
                'project_name_zh': p.get('project_name_zh') or p.get('project_name_en') or '',
                'status': p.get('status'),
                'doc_library_url': p.get('doc_library_url') or '',
            }
            for p in projects
        ],
    })


@app.route('/api/settings/doc-library', methods=['POST'])
def save_doc_library_settings():
    """儲存文件管理設定（全局 URL + 各項目 URL）"""
    data = request.json or {}
    if 'global_url' in data:
        db.set_setting('doc_library_url', (data.get('global_url') or '').strip())
    for row in data.get('projects') or []:
        pid = row.get('id')
        if not pid:
            continue
        db.update_project_doc_library_url(pid, row.get('doc_library_url'))
    return resp({'message': '文件管理設定已儲存'})


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
    data.setdefault('project_name_en', '')
    data.setdefault('project_name_zh', '')
    data.setdefault('client', '')
    data.setdefault('main_contractor', '')
    data.setdefault('contract_amount', 0)
    data.setdefault('start_date', None)
    data.setdefault('status', 'Active')
    data.setdefault('notes', '')
    data.setdefault('labour_allocation', 0)
    data.setdefault('quotation_no', None)
    data.setdefault('person_code', None)
    data.setdefault('person_in_charge', None)
    try:
        new_id = db.create_project(data)
    except ValueError as e:
        return resp(error=str(e), status=400)
    return resp({'id': new_id}, status=201)


@app.route('/api/projects/<int:project_id>', methods=['PUT'])
def update_project(project_id):
    data = request.json or {}
    data.setdefault('project_code', '')
    data.setdefault('project_name', '')
    data.setdefault('project_name_en', '')
    data.setdefault('project_name_zh', '')
    data.setdefault('client', '')
    data.setdefault('main_contractor', '')
    data.setdefault('contract_amount', 0)
    data.setdefault('start_date', None)
    data.setdefault('status', 'Active')
    data.setdefault('notes', '')
    data.setdefault('labour_allocation', 0)
    data.setdefault('quotation_no', None)
    data.setdefault('person_code', None)
    data.setdefault('person_in_charge', None)
    try:
        db.update_project(project_id, data)
    except ValueError as e:
        return resp(error=str(e), status=400)
    return resp({'message': '已更新'})


@app.route('/api/projects/<int:project_id>', methods=['DELETE'])
def delete_project(project_id):
    db.delete_project(project_id)
    return resp({'message': '已刪除'})


@app.route('/api/company-summary', methods=['GET'])
def company_summary():
    """第2頁 Summary — 全公司項目總表"""
    return resp(db.get_company_summary())


@app.route('/api/projects/<int:project_id>/cover-page', methods=['GET'])
def project_cover_page(project_id):
    """Cover Page 主檔（第4–6頁）"""
    cover = db.get_cover_page(project_id)
    if not cover:
        return resp(error='項目不存在', status=404)
    return resp(cover)


@app.route('/api/projects/<int:project_id>/main-con-fac', methods=['GET'])
def get_main_con_fac_api(project_id):
    fac = db.get_main_con_fac(project_id)
    if not fac:
        return resp(error='項目不存在', status=404)
    return resp(fac)


@app.route('/api/projects/<int:project_id>/main-con-fac', methods=['POST'])
def update_main_con_fac_api(project_id):
    data = request.json or {}
    if not db.get_project(project_id):
        return resp(error='項目不存在', status=404)
    ok = db.update_main_con_fac(project_id, data)
    if not ok:
        return resp(error='更新失敗', status=400)
    return resp(db.get_main_con_fac(project_id))


@app.route('/api/projects/<int:project_id>/main-con-fac/upload', methods=['POST'])
def upload_main_con_fac_attachment(project_id):
    if not db.get_project(project_id):
        return resp(error='項目不存在', status=404)
    att_type = (request.form.get('type') or '').strip().lower()
    if att_type not in ('statement', 'pc_cert', 'mg_cert'):
        return resp(error='type 須為 statement、pc_cert 或 mg_cert', status=400)
    if 'file' not in request.files:
        return resp(error='沒有文件', status=400)
    file = request.files['file']
    if not file.filename or not allowed_file(file.filename):
        return resp(error='不支援的文件格式（請上傳 PDF/PNG/JPG）', status=400)
    ext = file.filename.rsplit('.', 1)[1].lower()
    unique_name = f"{uuid.uuid4().hex}.{ext}"
    save_path = os.path.join(UPLOAD_DIR, unique_name)
    file.save(save_path)
    db.update_main_fac_attachment(project_id, att_type, unique_name, file.filename)
    return resp({
        'path': unique_name,
        'filename': file.filename,
        'type': att_type,
        'message': '已上傳',
    })


@app.route('/api/sc-contract-registry/status', methods=['GET'])
def sc_contract_registry_status_api():
    from sc_contract_ref import ref_status
    return resp(ref_status())


@app.route('/api/sc-contract-registry', methods=['GET'])
def list_sc_contract_registry_api():
    q = request.args.get('q')
    project_core = request.args.get('project_core')
    sheet = request.args.get('year') or request.args.get('sheet')
    person = request.args.get('person')
    company = request.args.get('company')
    rows = db.search_sc_contract_registry(
        q=q, project_core=project_core, sheet=sheet, person=person, company=company,
    )
    status = db.get_sc_contract_registry_status()
    filters = db.get_sc_contract_registry_filters()
    return resp({'rows': rows, 'status': status, 'filters': filters})


@app.route('/api/sc-contract-registry', methods=['POST'])
def create_sc_contract_registry_api():
    from sc_contract_ref import invalidate_cache
    data = request.json or {}
    try:
        row = db.save_sc_contract_registry_row(data)
    except ValueError as e:
        return resp(error=str(e), status=400)
    except Exception as e:
        return resp(error=f'儲存失敗: {e}', status=500)
    invalidate_cache()
    return resp(row, status=201)


@app.route('/api/sc-contract-registry/<path:sub_contract_no>', methods=['PUT'])
def update_sc_contract_registry_api(sub_contract_no):
    data = request.json or {}
    data['sub_contract_no'] = sub_contract_no
    try:
        row = db.save_sc_contract_registry_row(data)
    except ValueError as e:
        return resp(error=str(e), status=400)
    except Exception as e:
        return resp(error=f'更新失敗: {e}', status=500)
    return resp(row)


@app.route('/api/sc-contract-registry/<path:sub_contract_no>', methods=['DELETE'])
def delete_sc_contract_registry_api(sub_contract_no):
    if not db.delete_sc_contract_registry_row(sub_contract_no):
        return resp(error='記錄不存在', status=404)
    return resp({'deleted': sub_contract_no})


@app.route('/api/projects/<int:project_id>/subcontractors/ms-c-resolve', methods=['POST'])
def resolve_ms_c_preview_api(project_id):
    from sc_contract_ref import display_p1_sub_contract_no, resolve_sub_contract_no

    project = db.get_project(project_id)
    if not project:
        return resp(error='項目不存在', status=404)
    data = request.json or {}
    sc = {
        'sc_no': data.get('sc_no'),
        'company_name_en': data.get('company_name_en'),
        'company_name_zh': data.get('company_name_zh'),
        'description': data.get('description'),
        'contract_amount': data.get('contract_amount'),
        'contract_sum': data.get('contract_sum'),
        'quotation_no': data.get('quotation_no'),
        'sub_contract_no': data.get('sub_contract_no'),
    }
    all_scs = db.get_subcontractors(project_id)
    resolved = display_p1_sub_contract_no(
        resolve_sub_contract_no(project, sc, all_scs),
    )
    manual = (sc.get('sub_contract_no') or '').strip()
    if manual and display_p1_sub_contract_no(manual) != '—':
        source = 'manual'
    elif (sc.get('quotation_no') or '').strip().upper().startswith('MS/C'):
        source = 'quotation'
    elif resolved != '—':
        source = 'registry'
    else:
        source = 'none'
    return resp({'resolved': resolved, 'source': source})


@app.route('/api/sc-contract-registry/sync', methods=['POST'])
def sc_contract_registry_sync_api():
    from sc_contract_importer import sync_from_ref
    try:
        result = sync_from_ref()
    except Exception as e:
        return resp(error=f'同步失敗: {e}', status=500)
    if not result.get('ok'):
        return resp(error=result.get('error', '同步失敗'), status=400)
    return resp(result)


@app.route('/api/engineering-categories/status', methods=['GET'])
def engineering_categories_status_api():
    from engineering_category_ref import ref_status
    status = ref_status()
    status['db_count'] = db.engineering_category_count()
    return resp(status)


@app.route('/api/engineering-categories', methods=['GET'])
def list_engineering_categories_api():
    return resp({
        'tree': db.list_engineering_categories_tree(),
        'rows': db.list_engineering_categories(),
    })


@app.route('/api/engineering-categories/sync', methods=['POST'])
def engineering_categories_sync_api():
    try:
        result = db.sync_engineering_categories()
    except FileNotFoundError as e:
        return resp(error=str(e), status=404)
    except Exception as e:
        return resp(error=f'同步失敗: {e}', status=500)
    return resp(result)


@app.route('/api/engineering-categories/auto-classify', methods=['POST'])
def engineering_categories_auto_classify_api():
    body = request.json or {}
    only_empty = body.get('only_empty', True)
    dry_run = body.get('dry_run', False)
    try:
        result = db.auto_classify_projects(only_empty=only_empty, dry_run=dry_run)
    except Exception as e:
        return resp(error=f'分類失敗: {e}', status=500)
    return resp(result)


@app.route('/api/projects/<int:project_id>/category-suggest', methods=['GET'])
def project_category_suggest_api(project_id):
    if not db.get_project(project_id):
        return resp(error='項目不存在', status=404)
    return resp(db.suggest_project_category(project_id) or {'l2_code': None})


@app.route('/api/projects/<int:project_id>/sc-fac', methods=['GET'])
def list_sc_fac_api(project_id):
    if not db.get_project(project_id):
        return resp(error='項目不存在', status=404)
    return resp(db.list_sc_fac_items(project_id))


@app.route('/api/projects/<int:project_id>/subcontractors/<int:sc_id>/sc-fac', methods=['GET'])
def get_sc_fac_api(project_id, sc_id):
    fac = db.get_sc_fac(project_id, sc_id)
    if not fac:
        return resp(error='判項不存在或不可結算', status=404)
    return resp(fac)


@app.route('/api/projects/<int:project_id>/subcontractors/<int:sc_id>/sc-fac/pdf', methods=['GET'])
def sc_fac_pdf_api(project_id, sc_id):
    fac = db.get_sc_fac(project_id, sc_id)
    if not fac:
        return resp(error='判項不存在或不可結算', status=404)
    try:
        from sc_fac_pdf import (
            generate_sc_fac_pdf,
            normalize_sc_fac_theme,
            resolve_appendix_pages,
        )
        from flask import Response, request
        import startup
        theme = normalize_sc_fac_theme(request.args.get('theme'))
        print_vo_empty = request.args.get('appendix_vo') == '1'
        print_contra_empty = request.args.get('appendix_contra') == '1'
        include_vo, include_contra = resolve_appendix_pages(
            fac,
            print_vo_empty=print_vo_empty,
            print_contra_empty=print_contra_empty,
        )
        pdf_bytes = generate_sc_fac_pdf(
            fac,
            theme=theme,
            print_appendix_vo_empty=print_vo_empty,
            print_appendix_contra_empty=print_contra_empty,
        )
    except Exception as e:
        return resp(error=f'PDF 生成失敗: {e}', status=500)
    sc_no = (fac.get('header') or {}).get('sc_no') or str(sc_id)
    import re
    safe = re.sub(r'[^\w\-]+', '_', sc_no)
    inline = request.args.get('inline') == '1' or request.args.get('preview') == '1'
    disp = 'inline' if inline else 'attachment'
    return Response(
        pdf_bytes,
        mimetype='application/pdf',
        headers={
            'Content-Disposition': f'{disp}; filename="SC_FAC_{safe}.pdf"',
            'Cache-Control': 'no-store, no-cache, must-revalidate',
            'Pragma': 'no-cache',
            'X-App-Version': startup.APP_VERSION,
            'X-SC-FAC-Theme': theme,
            'X-SC-FAC-Appendix-Vo': '1' if include_vo else '0',
            'X-SC-FAC-Appendix-Contra': '1' if include_contra else '0',
        },
    )


@app.route('/api/projects/<int:project_id>/subcontractors/<int:sc_id>/sc-fac/docx', methods=['GET'])
def sc_fac_docx_api(project_id, sc_id):
    fac = db.get_sc_fac(project_id, sc_id)
    if not fac:
        return resp(error='判項不存在或不可結算', status=404)
    try:
        from sc_fac_docx import generate_sc_fac_docx
        from sc_fac_pdf import normalize_sc_fac_theme
        from flask import Response, request
        theme = normalize_sc_fac_theme(request.args.get('theme'))
        docx_bytes = generate_sc_fac_docx(fac, theme=theme)
    except Exception as e:
        return resp(error=f'Word 生成失敗: {e}', status=500)
    sc_no = (fac.get('header') or {}).get('sc_no') or str(sc_id)
    import re
    safe = re.sub(r'[^\w\-]+', '_', sc_no)
    suffix = '_classic' if theme == 'classic' else ''
    return Response(
        docx_bytes,
        mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        headers={
            'Content-Disposition': f'attachment; filename="SC_FAC_{safe}{suffix}.docx"',
            'Cache-Control': 'no-store, no-cache, must-revalidate',
            'Pragma': 'no-cache',
        },
    )


@app.route('/api/projects/<int:project_id>/documents', methods=['GET'])
def get_project_documents(project_id):
    return resp(db.get_project_documents(project_id))


@app.route('/api/projects/<int:project_id>/documents', methods=['POST'])
def add_project_document(project_id):
    data = request.json or {}
    category = (data.get('doc_category') or '').strip()
    file_path = (data.get('file_path') or '').strip()
    if not category or not file_path:
        return resp(error='缺少 doc_category 或 file_path', status=400)
    from project_cover import PROJECT_DOC_CATEGORIES
    if category not in PROJECT_DOC_CATEGORIES:
        return resp(error='無效的 doc_category', status=400)
    if not db.get_project(project_id):
        return resp(error='項目不存在', status=404)
    doc_id = db.add_project_document(
        project_id,
        category,
        file_path,
        data.get('original_filename'),
        data.get('notes'),
    )
    return resp({'id': doc_id}, status=201)


@app.route('/api/project-documents/<int:doc_id>', methods=['DELETE'])
def delete_project_document(doc_id):
    db.delete_project_document(doc_id)
    return resp({'message': '已刪除'})


# ─── ISO Documents API ──────────────────────────────────────────────────

def _iso_project_upload_dir(project_id):
    """ISO 附件目錄：uploads/iso/{project_code}/"""
    p = db.get_project(project_id)
    code = db.iso_safe_project_code(p.get('project_code') if p else None)
    subdir = os.path.join(UPLOAD_DIR, 'iso', code)
    os.makedirs(subdir, exist_ok=True)
    return subdir, f'iso/{code}'


def _iso_disk_filename(doc_slot, original_filename):
    """實體檔名：{槽位中文名}_{YYYYMMDD}_{短ID}.ext"""
    label = db.iso_slot_disk_label(doc_slot)
    label = re.sub(r'[\\/:*?"<>|\x00-\x1f\s]+', '_', label.strip())[:40] or 'ISO文件'
    date = datetime.now().strftime('%Y%m%d')
    name = (original_filename or 'file.pdf').strip()
    ext = name.rsplit('.', 1)[-1].lower() if '.' in name else 'pdf'
    uid = uuid.uuid4().hex[:8]
    return f"{label}_{date}_{uid}.{ext}"


@app.route('/api/projects/<int:project_id>/iso-documents', methods=['GET'])
def get_iso_documents(project_id):
    board = db.get_iso_documents_board(project_id)
    if not board:
        return resp(error='項目不存在', status=404)
    return resp(board)


@app.route('/api/projects/<int:project_id>/iso-documents', methods=['POST'])
def upsert_iso_document(project_id):
    if not db.get_project(project_id):
        return resp(error='項目不存在', status=404)
    data = request.json or {}
    scope = (data.get('scope') or '').strip()
    doc_slot = (data.get('doc_slot') or '').strip()
    file_path = (data.get('file_path') or '').strip()
    if not scope or not doc_slot or not file_path:
        return resp(error='缺少 scope、doc_slot 或 file_path', status=400)
    try:
        row = db.upsert_iso_document(
            project_id,
            scope,
            doc_slot,
            file_path,
            data.get('original_filename'),
            data.get('subcontractor_id'),
        )
    except ValueError as e:
        return resp(error=str(e), status=400)
    return resp(row, status=201)


@app.route('/api/projects/<int:project_id>/iso-documents/upload', methods=['POST'])
def upload_iso_document(project_id):
    """上傳 ISO 附件（PDF/圖片）並寫入槽位"""
    if not db.get_project(project_id):
        return resp(error='項目不存在', status=404)
    if 'file' not in request.files:
        return resp(error='沒有文件', status=400)
    file = request.files['file']
    if not file.filename or not allowed_file(file.filename):
        return resp(error='不支援的文件格式（請上傳 PDF/PNG/JPG）', status=400)

    scope = (request.form.get('scope') or '').strip()
    doc_slot = (request.form.get('doc_slot') or '').strip()
    sc_id_raw = request.form.get('subcontractor_id')
    subcontractor_id = int(sc_id_raw) if sc_id_raw else None

    unique_name = _iso_disk_filename(doc_slot, file.filename)
    subdir, rel_prefix = _iso_project_upload_dir(project_id)
    rel_path = f"{rel_prefix}/{unique_name}"
    save_path = os.path.join(UPLOAD_DIR, rel_path.replace('/', os.sep))
    file.save(save_path)

    try:
        row = db.upsert_iso_document(
            project_id, scope, doc_slot, rel_path, file.filename, subcontractor_id,
            storage_type='file',
        )
    except ValueError as e:
        try:
            os.remove(save_path)
        except OSError:
            pass
        return resp(error=str(e), status=400)

    return resp(row)


@app.route('/api/projects/<int:project_id>/iso-documents/link', methods=['POST'])
def iso_document_link(project_id):
    """只填 SharePoint / 內網連結（不上傳本地副本）"""
    if not db.get_project(project_id):
        return resp(error='項目不存在', status=404)
    data = request.json or {}
    scope = (data.get('scope') or '').strip()
    doc_slot = (data.get('doc_slot') or '').strip()
    external_url = (data.get('external_url') or '').strip()
    sc_id_raw = data.get('subcontractor_id')
    subcontractor_id = int(sc_id_raw) if sc_id_raw else None
    if not scope or not doc_slot or not external_url:
        return resp(error='缺少 scope、doc_slot 或 external_url', status=400)
    try:
        row = db.upsert_iso_document(
            project_id, scope, doc_slot, '',
            data.get('link_label') or data.get('original_filename'),
            subcontractor_id,
            external_url=external_url,
            storage_type='link',
            link_label=data.get('link_label'),
        )
    except ValueError as e:
        return resp(error=str(e), status=400)
    return resp(row, status=201)


@app.route('/api/projects/<int:project_id>/iso-documents/versions', methods=['GET'])
def iso_document_versions(project_id):
    if not db.get_project(project_id):
        return resp(error='項目不存在', status=404)
    scope = (request.args.get('scope') or '').strip()
    doc_slot = (request.args.get('doc_slot') or '').strip()
    sc_id_raw = request.args.get('subcontractor_id')
    subcontractor_id = int(sc_id_raw) if sc_id_raw else None
    if not scope or not doc_slot:
        return resp(error='缺少 scope 或 doc_slot', status=400)
    versions = db.list_iso_document_versions(project_id, scope, doc_slot, subcontractor_id)
    return resp({'versions': versions})


@app.route('/api/iso-documents/<int:doc_id>', methods=['DELETE'])
def delete_iso_document(doc_id):
    existing = db.get_iso_document(doc_id)
    if not existing:
        return resp(error='附件不存在', status=404)
    db.delete_iso_document(doc_id)
    return resp({'message': '已刪除'})


@app.route('/api/projects/<int:project_id>/iso-meta', methods=['PATCH'])
def patch_iso_meta(project_id):
    if not db.get_project(project_id):
        return resp(error='項目不存在', status=404)
    data = request.json or {}
    if 'supplemental_contract_amount' in data:
        db.update_iso_supplemental_amount(project_id, data.get('supplemental_contract_amount'))
    board = db.get_iso_documents_board(project_id)
    return resp(board)


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
    data.setdefault('sc_entry_type', 'quotation')
    data.setdefault('retention_sum', None)
    data.setdefault('sub_contract_no', None)
    from sc_contract_ref import normalize_ms_c_input, validate_ms_c_input
    ok, msg = validate_ms_c_input(data.get('sub_contract_no'))
    if not ok:
        return resp(error=msg, status=400)
    data['sub_contract_no'] = normalize_ms_c_input(data.get('sub_contract_no'))
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
              'remark', 'pdf_path', 'ocr_status', 'payment_type',
              'deduction_ids_json', 'vo_ids_json', 'interim_cert_json']:
        data.setdefault(f, None)
    for f in ['contract_amount', 'paid_amount', 'remainder_amount', 'backcharge_amount', 'deduction_total']:
        data.setdefault(f, 0)
    if not data.get('payment_type'):
        data['payment_type'] = 'normal'
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
              'oa_ref', 'oa_no', 'mc_ip_no', 'bc_to_sub', 'sub_ip_no', 'remark', 'payment_type',
              'deduction_ids_json', 'vo_ids_json', 'interim_cert_json']:
        data.setdefault(f, None)
    for f in ['contract_amount', 'paid_amount', 'remainder_amount', 'backcharge_amount', 'deduction_total']:
        data.setdefault(f, 0)
    if not data.get('payment_type'):
        data['payment_type'] = 'normal'
    try:
        db.update_payment(payment_id, data)
    except ValueError as e:
        return resp(error=str(e), status=400)
    return resp({'message': '已更新'})


@app.route('/api/payments/<int:payment_id>/withdraw', methods=['POST'])
def withdraw_interim_cert(payment_id):
    try:
        db.revoke_interim_cert(payment_id)
    except ValueError as e:
        return resp(error=str(e), status=400)
    return resp({'message': '已還原至提交前'})


@app.route('/api/payments/<int:payment_id>/restore', methods=['POST'])
def restore_interim_cert(payment_id):
    try:
        db.restore_interim_cert(payment_id)
    except ValueError as e:
        return resp(error=str(e), status=400)
    return resp({'message': '已還原計算書'})


@app.route('/api/payments/<int:payment_id>', methods=['DELETE'])
def delete_payment(payment_id):
    try:
        db.delete_payment(payment_id)
    except ValueError as e:
        return resp(error=str(e), status=400)
    return resp({'message': '已刪除'})


@app.route('/api/sc-vo-templates', methods=['GET'])
def sc_vo_templates_api():
    from sc_vo_templates import all_templates, list_all_templates
    if request.args.get('manage') in ('1', 'true', 'yes'):
        return resp(list_all_templates(include_inactive=True))
    return resp(all_templates())


@app.route('/api/sc-vo-templates', methods=['POST'])
def create_sc_vo_template_api():
    data = request.get_json(silent=True) or {}
    try:
        row = db.upsert_sc_vo_template_catalog(data)
        from sc_vo_templates import invalidate_template_cache
        invalidate_template_cache()
        return resp(row, status=201)
    except ValueError as e:
        return resp(error=str(e), status=400)


@app.route('/api/sc-vo-templates/<code>', methods=['PUT'])
def update_sc_vo_template_api(code):
    data = request.get_json(silent=True) or {}
    data['code'] = code
    try:
        row = db.upsert_sc_vo_template_catalog(data)
        return resp(row)
    except ValueError as e:
        return resp(error=str(e), status=400)


@app.route('/api/sc-vo-templates/<code>', methods=['DELETE'])
def delete_sc_vo_template_api(code):
    try:
        db.delete_sc_vo_template_catalog(code)
        return resp({'message': '已刪除'})
    except ValueError as e:
        return resp(error=str(e), status=400)


@app.route('/api/projects/<int:project_id>/sc-vo-records', methods=['GET'])
def get_sc_vo_records_api(project_id):
    sc_no = request.args.get('sc_no')
    unapplied = request.args.get('unapplied') in ('1', 'true', 'yes')
    record_type = request.args.get('record_type')
    rows = db.get_sc_vo_records(project_id, sc_no=sc_no, unapplied_only=unapplied)
    if record_type:
        rows = [r for r in rows if r.get('record_type') == record_type]
    return resp(rows)


@app.route('/api/projects/<int:project_id>/sc-vo-records/next-ref', methods=['GET'])
def suggest_sc_vo_ref_api(project_id):
    sc_no = (request.args.get('sc_no') or '').strip()
    record_type = request.args.get('record_type') or 'vo'
    if not sc_no:
        return resp(error='缺少判項編號', status=400)
    if record_type not in ('vo', 'deduction'):
        return resp(error='record_type 須為 vo 或 deduction', status=400)
    exclude_id = request.args.get('exclude_id', type=int)
    ref_no = db.suggest_next_svr_ref_no(project_id, sc_no, record_type, exclude_id=exclude_id)
    return resp({'ref_no': ref_no, 'sc_no': sc_no, 'record_type': record_type})


@app.route('/api/projects/<int:project_id>/sc-vo-records', methods=['POST'])
def create_sc_vo_record_api(project_id):
    data = request.json or {}
    if not data.get('sc_no'):
        return resp(error='缺少判項編號', status=400)
    data['project_id'] = project_id
    sc = db.get_subcontractor_by_sc_no(project_id, data['sc_no'])
    if sc:
        data['sc_id'] = sc['id']
    try:
        new_id = db.create_sc_vo_record(data)
    except Exception as e:
        return resp(error=str(e), status=400)
    return resp({'id': new_id}, status=201)


@app.route('/api/sc-vo-records/<int:record_id>', methods=['GET'])
def get_sc_vo_record_api(record_id):
    row = db.get_sc_vo_record(record_id)
    if not row:
        return resp(error='記錄不存在', status=404)
    return resp(row)


@app.route('/api/sc-vo-records/<int:record_id>', methods=['PUT'])
def update_sc_vo_record_api(record_id):
    data = request.json or {}
    ok = db.update_sc_vo_record(record_id, data)
    if not ok:
        return resp(error='記錄不存在', status=404)
    return resp({'message': '已更新'})


@app.route('/api/sc-vo-records/<int:record_id>', methods=['DELETE'])
def delete_sc_vo_record_api(record_id):
    try:
        ok = db.delete_sc_vo_record(record_id)
    except ValueError as e:
        return resp(error=str(e), status=400)
    if not ok:
        return resp(error='記錄不存在', status=404)
    return resp({'message': '已刪除'})


@app.route('/api/sc-vo-records/<int:record_id>/upload', methods=['POST'])
def upload_sc_vo_attachment(record_id):
    row = db.get_sc_vo_record(record_id)
    if not row:
        return resp(error='記錄不存在', status=404)
    att_type = (request.form.get('type') or '').strip().lower()
    if att_type not in ('approval', 'quotation'):
        return resp(error='type 須為 approval 或 quotation', status=400)
    if 'file' not in request.files:
        return resp(error='沒有文件', status=400)
    file = request.files['file']
    if not file.filename or not allowed_file(file.filename):
        return resp(error='不支援的文件格式（請上傳 PDF/PNG/JPG）', status=400)
    ext = file.filename.rsplit('.', 1)[1].lower()
    unique_name = f"{uuid.uuid4().hex}.{ext}"
    save_path = os.path.join(UPLOAD_DIR, unique_name)
    file.save(save_path)
    old_path = row.get('approval_attachment') if att_type == 'approval' else row.get('quotation_attachment')
    if old_path:
        old_full = os.path.join(UPLOAD_DIR, old_path)
        if os.path.isfile(old_full):
            try:
                os.remove(old_full)
            except OSError:
                pass
    db.update_sc_vo_attachment(record_id, att_type, unique_name, file.filename)
    return resp({
        'path': unique_name,
        'filename': file.filename,
        'type': att_type,
        'message': '已上傳',
    })


@app.route('/api/payments/interim-cert/model', methods=['POST'])
def interim_cert_model_api():
    from interim_cert_report import enrich_interim_cert_payload, build_interim_cert_model
    enriched = enrich_interim_cert_payload(request.json or {})
    return resp(enriched.get('model') or build_interim_cert_model(enriched))


@app.route('/api/payments/interim-cert/pdf', methods=['POST'])
def interim_cert_pdf_preview():
    """計算書 PDF（預覽／下載，可不帶 payment id）"""
    data = request.json or {}
    try:
        from interim_cert_report import generate_interim_cert_pdf
        pdf_bytes = generate_interim_cert_pdf(data)
    except Exception as e:
        return resp(error=f'PDF 生成失敗: {e}', status=500)
    buf = BytesIO(pdf_bytes)
    buf.seek(0)
    code = (data.get('project') or {}).get('project_code') or 'cert'
    fname = f'InterimCert_{code}_{datetime.now().strftime("%Y%m%d")}.pdf'
    return send_file(buf, mimetype='application/pdf', as_attachment=True, download_name=fname)


@app.route('/api/payments/interim-cert/xlsx', methods=['POST'])
def interim_cert_xlsx_preview():
    """計算書 Excel（對齊 QS 範本）"""
    data = request.json or {}
    try:
        from interim_cert_report import generate_interim_cert_xlsx
        xlsx_bytes = generate_interim_cert_xlsx(data)
    except Exception as e:
        return resp(error=f'Excel 生成失敗: {e}', status=500)
    buf = BytesIO(xlsx_bytes)
    buf.seek(0)
    code = (data.get('project') or {}).get('project_code') or 'cert'
    fname = f'InterimCert_{code}_{datetime.now().strftime("%Y%m%d")}.xlsx'
    return send_file(
        buf,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=fname,
    )


@app.route('/api/payments/interim-cert/docx', methods=['POST'])
def interim_cert_docx_preview():
    """計算書 Word（對齊 PDF 版面，供改完交回調格式）"""
    data = request.json or {}
    try:
        from interim_cert_report import generate_interim_cert_docx
        docx_bytes = generate_interim_cert_docx(data)
    except Exception as e:
        return resp(error=f'Word 生成失敗: {e}', status=500)
    buf = BytesIO(docx_bytes)
    buf.seek(0)
    code = (data.get('project') or {}).get('project_code') or 'cert'
    fname = f'InterimCert_{code}_{datetime.now().strftime("%Y%m%d")}.docx'
    return send_file(
        buf,
        mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        as_attachment=True,
        download_name=fname,
    )


@app.route('/api/payments/<int:payment_id>/interim-cert/pdf', methods=['GET'])
def interim_cert_pdf_saved(payment_id):
    payment = db.get_payment(payment_id)
    if not payment:
        return resp(error='記錄不存在', status=404)
    cert = payment.get('interim_cert')
    if not cert and payment.get('interim_cert_json'):
        import json
        try:
            cert = json.loads(payment['interim_cert_json'])
        except json.JSONDecodeError:
            cert = None
    if not cert:
        project = db.get_project(payment['project_id'])
        cert = {
            'project': dict(project) if project else {},
            'sc_no': payment.get('sc_no'),
            'company_en': payment.get('company_name_en'),
            'company_zh': payment.get('company_name_zh'),
            'invoice_no': payment.get('invoice_no'),
            'invoice_date': payment.get('invoice_date'),
            'description': payment.get('description'),
            'contract_amount': payment.get('contract_amount'),
            'paid_amount': payment.get('paid_amount'),
            'remainder_amount': payment.get('remainder_amount'),
            'deduction_total': payment.get('deduction_total'),
            'deductions': [],
        }
    try:
        from interim_cert_report import generate_interim_cert_pdf
        pdf_bytes = generate_interim_cert_pdf(cert)
    except Exception as e:
        return resp(error=f'PDF 生成失敗: {e}', status=500)
    buf = BytesIO(pdf_bytes)
    buf.seek(0)
    code = (cert.get('project') or {}).get('project_code') or 'cert'
    fname = f'InterimCert_{code}_{payment_id}.pdf'
    return send_file(buf, mimetype='application/pdf', as_attachment=True, download_name=fname)


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
            original_filename=file.filename,
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


@app.route('/api/uploads/<path:filepath>')
def serve_upload(filepath):
    """提供上傳文件（PDF/圖片），供瀏覽器內嵌預覽；支援子目錄如 iso/{project_code}/"""
    filepath = filepath.replace('\\', '/')
    if '..' in filepath or filepath.startswith('/'):
        return jsonify({'success': False, 'error': '無效文件名'}), 400
    safe_parts = [os.path.basename(p) for p in filepath.split('/') if p]
    if not safe_parts:
        return jsonify({'success': False, 'error': '無效文件名'}), 400
    path = os.path.join(UPLOAD_DIR, *safe_parts)
    if not os.path.isfile(path):
        return jsonify({'success': False, 'error': '文件不存在'}), 404
    safe = safe_parts[-1]
    ext = safe.rsplit('.', 1)[-1].lower() if '.' in safe else ''
    mime = {
        'pdf': 'application/pdf',
        'png': 'image/png',
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'gif': 'image/gif',
        'webp': 'image/webp',
    }.get(ext, 'application/octet-stream')
    return send_file(path, mimetype=mime, as_attachment=False, download_name=safe)


@app.route('/api/projects/<int:project_id>/interim-payments', methods=['GET'])
def get_interim_payments_api(project_id):
    summary = db.get_ip_period_summary(project_id)
    if summary is None:
        return resp(error='項目不存在', status=404)
    return resp(summary)


@app.route('/api/projects/<int:project_id>/ip-reconciliation', methods=['GET'])
def project_ip_reconciliation(project_id):
    if not db.get_project(project_id):
        return resp(error='項目不存在', status=404)
    return resp(db.get_ip_reconciliation(project_id=project_id))


@app.route('/api/projects/<int:project_id>/ip-sc-drilldown', methods=['GET'])
def ip_sc_drilldown(project_id):
    if not db.get_project(project_id):
        return resp(error='項目不存在', status=404)
    ip_no = request.args.get('ip_no', '').strip()
    sc_no = request.args.get('sc_no', '').strip()
    if not ip_no or not sc_no:
        return resp(error='缺少 ip_no 或 sc_no', status=400)
    return resp(db.get_ip_sc_drilldown(project_id, ip_no, sc_no))


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
    for f in ['applied_date', 'certificate_date', 'subcon_cert_date', 'receipt_date']:
        data.setdefault(f, None)
    for f in ['application_amount', 'certified_income', 'subcon_paid']:
        data.setdefault(f, 0)
    for f in ['receipt_method', 'receipt_cheque_no', 'receipt_bank', 'receipt_note']:
        data.setdefault(f, None)
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
    for f in ['applied_date', 'certificate_date', 'subcon_cert_date', 'receipt_date']:
        data.setdefault(f, None)
    for f in ['application_amount', 'certified_income', 'subcon_paid', 'seq_no']:
        data.setdefault(f, existing.get(f) or 0)
    for f in ['receipt_method', 'receipt_cheque_no', 'receipt_bank', 'receipt_note']:
        if f not in data:
            data[f] = existing.get(f)
    db.upsert_interim_payment(data)
    return resp({'summary': db.get_ip_period_summary(existing['project_id'])})


@app.route('/api/interim-payments/<int:ip_id>/receipt-attachment', methods=['POST'])
def upload_ip_receipt_attachment(ip_id):
    """上傳糧期收款支票／過數附件（PDF/圖片）"""
    existing = db.get_interim_payment(ip_id)
    if not existing:
        return resp(error='糧期記錄不存在', status=404)
    if 'file' not in request.files:
        return resp(error='沒有文件', status=400)
    file = request.files['file']
    if not file.filename or not allowed_file(file.filename):
        return resp(error='不支援的文件格式（請上傳 PDF/PNG/JPG）', status=400)

    ext = file.filename.rsplit('.', 1)[1].lower()
    unique_name = f"{uuid.uuid4().hex}.{ext}"
    save_path = os.path.join(UPLOAD_DIR, unique_name)
    file.save(save_path)
    db.set_ip_receipt_attachment(ip_id, unique_name, file.filename)
    return resp({
        'receipt_attachment': unique_name,
        'receipt_attachment_name': file.filename,
        'summary': db.get_ip_period_summary(existing['project_id']),
    })


@app.route('/api/interim-payments/<int:ip_id>/receipt-attachment', methods=['DELETE'])
def delete_ip_receipt_attachment(ip_id):
    existing = db.get_interim_payment(ip_id)
    if not existing:
        return resp(error='糧期記錄不存在', status=404)
    old_path = db.clear_ip_receipt_attachment(ip_id)
    if old_path:
        full = os.path.join(UPLOAD_DIR, old_path)
        if os.path.isfile(full):
            try:
                os.remove(full)
            except OSError:
                pass
    return resp({'summary': db.get_ip_period_summary(existing['project_id'])})


@app.route('/api/interim-payments/<int:ip_id>/ip-cert-attachment', methods=['POST'])
def upload_ip_cert_attachment(ip_id):
    """上傳糧期 IP Cert. 附件（PDF/圖片）"""
    existing = db.get_interim_payment(ip_id)
    if not existing:
        return resp(error='糧期記錄不存在', status=404)
    if 'file' not in request.files:
        return resp(error='沒有文件', status=400)
    file = request.files['file']
    if not file.filename or not allowed_file(file.filename):
        return resp(error='不支援的文件格式（請上傳 PDF/PNG/JPG）', status=400)

    ext = file.filename.rsplit('.', 1)[1].lower()
    unique_name = f"{uuid.uuid4().hex}.{ext}"
    save_path = os.path.join(UPLOAD_DIR, unique_name)
    file.save(save_path)
    db.set_ip_cert_attachment(ip_id, unique_name, file.filename)
    return resp({
        'ip_cert_attachment': unique_name,
        'ip_cert_attachment_name': file.filename,
        'summary': db.get_ip_period_summary(existing['project_id']),
    })


@app.route('/api/interim-payments/<int:ip_id>/ip-cert-attachment', methods=['DELETE'])
def delete_ip_cert_attachment(ip_id):
    existing = db.get_interim_payment(ip_id)
    if not existing:
        return resp(error='糧期記錄不存在', status=404)
    old_path = db.clear_ip_cert_attachment(ip_id)
    if old_path:
        full = os.path.join(UPLOAD_DIR, old_path)
        if os.path.isfile(full):
            try:
                os.remove(full)
            except OSError:
                pass
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


@app.route('/api/reports/boss-pdf/<int:project_id>', methods=['GET'])
def boss_report_pdf(project_id):
    """一鍵生成老細 QS 匯報 PDF（A4）"""
    summary = db.get_project_summary(project_id)
    if not summary:
        return resp(error='項目不存在', status=404)
    sc_list = db.get_subcontractors(project_id)
    company = db.get_setting('company_name') or 'Mepork Engineering Services Limited'
    conn = db.get_conn()
    payment_count = conn.execute(
        'SELECT COUNT(*) FROM payment_records WHERE project_id=?', (project_id,)
    ).fetchone()[0]
    conn.close()
    try:
        from qs_report_pdf import generate_boss_qs_report
        pdf_bytes = generate_boss_qs_report(
            summary, sc_list, company_name=company, payment_count=payment_count,
        )
    except Exception as e:
        return resp(error=f'PDF 生成失敗: {e}', status=500)
    code = summary['project'].get('project_code') or str(project_id)
    date_str = datetime.now().strftime('%Y%m%d')
    filename = f'QS匯報_{code}_{date_str}.pdf'
    response = send_file(
        BytesIO(pdf_bytes),
        mimetype='application/pdf',
        as_attachment=True,
        download_name=filename,
    )
    try:
        from startup import APP_VERSION
        response.headers['X-App-Version'] = APP_VERSION
    except Exception:
        pass
    return response


@app.route('/api/reports/boss-docx/<int:project_id>', methods=['GET'])
def boss_report_docx(project_id):
    """QS 地盤財務匯報 Word（供版面微調後交回對照 PDF）"""
    summary = db.get_project_summary(project_id)
    if not summary:
        return resp(error='項目不存在', status=404)
    sc_list = db.get_subcontractors(project_id)
    company = db.get_setting('company_name') or 'Mepork Engineering Services Limited'
    conn = db.get_conn()
    payment_count = conn.execute(
        'SELECT COUNT(*) FROM payment_records WHERE project_id=?', (project_id,)
    ).fetchone()[0]
    conn.close()
    try:
        from qs_report_docx import generate_boss_qs_report_docx
        docx_bytes = generate_boss_qs_report_docx(
            summary, sc_list, company_name=company, payment_count=payment_count,
        )
    except Exception as e:
        return resp(error=f'Word 生成失敗: {e}', status=500)
    code = summary['project'].get('project_code') or str(project_id)
    date_str = datetime.now().strftime('%Y%m%d')
    filename = f'QS匯報_{code}_{date_str}.docx'
    return send_file(
        BytesIO(docx_bytes),
        mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        as_attachment=True,
        download_name=filename,
    )


# ─── Staff roster API（負責人名單 → 未來權限）────────────────────────────
@app.route('/api/staff', methods=['GET'])
def list_staff():
    active_only = request.args.get('active') == '1'
    role = (request.args.get('role') or '').strip().lower() or None
    if role:
        try:
            return resp(db.list_staff_by_access_role(active_only=active_only, access_role=role))
        except ValueError as e:
            return resp(error=str(e), status=400)
    return resp(db.list_staff_members(active_only=active_only))


@app.route('/api/staff/quotations', methods=['GET'])
def staff_person_quotations():
    person = request.args.get('person', '').strip()
    person_id = request.args.get('person_id', type=int)
    if person_id and not person:
        staff = db.get_staff_member(person_id)
        if staff:
            person = (staff.get('name_en') or staff.get('name_zh') or '').strip()
    if not person:
        return resp(error='缺少 person 或 person_id', status=400)
    limit = min(request.args.get('limit', 100, type=int), 500)
    offset = max(request.args.get('offset', 0, type=int), 0)
    return resp(db.list_quotations_for_roster_person(person, limit=limit, offset=offset))


@app.route('/api/staff/roles', methods=['GET'])
def staff_roles():
    return resp({
        'roles': [
            {'id': 'qs', 'label': 'QS', 'hint': '報價／判項／付款（預設）'},
            {'id': 'finance', 'label': '財務', 'hint': '發票／支票欄位（預留）'},
            {'id': 'admin', 'label': '管理員', 'hint': '全系統設定（預留）'},
            {'id': 'viewer', 'label': '唯讀', 'hint': '僅查閱（預留）'},
        ],
    })


@app.route('/api/staff/<int:staff_id>', methods=['GET'])
def get_staff(staff_id):
    row = db.get_staff_member(staff_id)
    if not row:
        return resp(error='找不到人員', status=404)
    return resp(row)


@app.route('/api/staff', methods=['POST'])
def create_staff():
    data = request.json or {}
    if not data.get('code'):
        return resp(error='請填寫縮寫', status=400)
    try:
        new_id = db.create_staff_member(data)
        return resp({'id': new_id}, status=201)
    except ValueError as e:
        return resp(error=str(e), status=400)


@app.route('/api/staff/<int:staff_id>', methods=['PUT'])
def update_staff(staff_id):
    data = request.json or {}
    if not db.get_staff_member(staff_id):
        return resp(error='找不到人員', status=404)
    try:
        db.update_staff_member(staff_id, data)
        return resp(db.get_staff_member(staff_id))
    except ValueError as e:
        return resp(error=str(e), status=400)


@app.route('/api/staff/<int:staff_id>', methods=['DELETE'])
def deactivate_staff(staff_id):
    if not db.get_staff_member(staff_id):
        return resp(error='找不到人員', status=404)
    db.deactivate_staff_member(staff_id)
    return resp({'message': '已停用'})


# ─── Master List API ─────────────────────────────────────────────────────
@app.route('/api/master/trade-categories/status', methods=['GET'])
def master_trade_categories_status_api():
    from master_trade_ref import ref_status
    status = ref_status()
    status['db_count'] = db.master_trade_category_count()
    grouped = db.list_master_trade_options_grouped()
    status['eng_category_count'] = len(grouped.get('override_options') or [])
    return resp(status)


@app.route('/api/master/trade-categories', methods=['GET'])
def list_master_trade_categories_api():
    return resp(db.list_master_trade_options_grouped())


@app.route('/api/master/trade-categories/sync', methods=['POST'])
def master_trade_categories_sync_api():
    try:
        result = db.sync_master_trade_categories()
    except FileNotFoundError as e:
        return resp(error=str(e), status=404)
    except ValueError as e:
        return resp(error=str(e), status=400)
    except Exception as e:
        return resp(error=f'同步失敗: {e}', status=500)
    return resp(result)


@app.route('/api/master/trade-categories', methods=['POST'])
def create_master_trade_category_api():
    data = request.get_json(silent=True) or {}
    try:
        row = db.create_master_trade_category(data)
    except ValueError as e:
        return resp(error=str(e), status=400)
    return resp(row, status=201)


@app.route('/api/master/trade-categories/<int:row_id>', methods=['PUT'])
def update_master_trade_category_api(row_id):
    data = request.get_json(silent=True) or {}
    try:
        row = db.update_master_trade_category(row_id, data)
    except ValueError as e:
        return resp(error=str(e), status=400)
    if not row:
        return resp(error='找不到分類', status=404)
    return resp(row)


@app.route('/api/master/trade-categories/<int:row_id>', methods=['DELETE'])
def delete_master_trade_category_api(row_id):
    if not db.deactivate_master_trade_category(row_id):
        return resp(error='找不到分類', status=404)
    return resp({'message': '已停用'})


@app.route('/api/master/years', methods=['GET'])
def master_list_years():
    return resp(db.list_master_registry_years())


@app.route('/api/master/stats', methods=['GET'])
def master_list_stats():
    q = request.args.get('q', '').strip()
    awarded_only = request.args.get('awarded') == '1'
    unlinked_only = request.args.get('unlinked') == '1'
    source_year = request.args.get('year', type=int)
    person_in_charge = request.args.get('person', '').strip() or None
    doc_type = request.args.get('doc_type', '').strip() or None
    if doc_type not in (None, '報價', '標書'):
        doc_type = None
    return resp(db.get_quotation_registry_stats(
        q=q or None, awarded_only=awarded_only, unlinked_only=unlinked_only,
        source_year=source_year, person_in_charge=person_in_charge, doc_type=doc_type,
    ))


@app.route('/api/master/field-suggestions', methods=['GET'])
def master_field_suggestions():
    limit = request.args.get('limit', 300, type=int)
    return resp(db.list_master_field_suggestions(limit=limit))


@app.route('/api/master/imports', methods=['GET'])
def master_list_import_history():
    return resp(db.list_master_import_history())


@app.route('/api/master/auto-link/preview', methods=['GET'])
def master_auto_link_preview():
    source_year = request.args.get('year', type=int)
    return resp(db.preview_auto_link_quotations(source_year=source_year))


@app.route('/api/master/auto-link', methods=['POST'])
def master_auto_link_run():
    data = request.get_json(silent=True) or {}
    year = data.get('year')
    if year is not None and year != '':
        try:
            year = int(year)
        except (TypeError, ValueError):
            return resp(error='year 格式不正確', status=400)
    else:
        year = None
    return resp(db.run_auto_link_quotations(source_year=year))


@app.route('/api/master/item/suggest', methods=['GET'])
def master_item_suggest():
    qno = request.args.get('quotation_no', '').strip()
    if not qno:
        return resp(error='缺少 quotation_no', status=400)
    result = db.suggest_project_for_quotation(qno)
    return resp(result or {})


@app.route('/api/master/quotations', methods=['GET'])
def master_list_quotations():
    q = request.args.get('q', '').strip()
    awarded_only = request.args.get('awarded') == '1'
    unlinked_only = request.args.get('unlinked') == '1'
    source_year = request.args.get('year', type=int)
    person_id = request.args.get('person_id', type=int)
    person_in_charge = request.args.get('person', '').strip() or None
    if person_id:
        staff = db.get_staff_member(person_id)
        if staff:
            person_in_charge = (staff.get('name_en') or staff.get('name_zh') or '').strip() or person_in_charge
    limit = min(request.args.get('limit', 100, type=int), 500)
    offset = max(request.args.get('offset', 0, type=int), 0)
    sort_by = request.args.get('sort', '').strip() or None
    sort_dir = request.args.get('dir', 'desc').strip().lower()
    if sort_dir not in ('asc', 'desc'):
        sort_dir = 'desc'
    doc_type = request.args.get('doc_type', '').strip() or None
    if doc_type not in (None, '報價', '標書'):
        doc_type = None
    return resp(db.list_quotation_registry(
        q=q or None, awarded_only=awarded_only, unlinked_only=unlinked_only,
        source_year=source_year, person_in_charge=person_in_charge, doc_type=doc_type,
        limit=limit, offset=offset,
        sort_by=sort_by, sort_dir=sort_dir,
    ))


@app.route('/api/master/quotations/next-no', methods=['GET'])
def master_quotation_next_no():
    doc_type = request.args.get('doc_type', '').strip() or '報價'
    if doc_type not in ('報價', '標書'):
        return resp(error='僅支援報價或標書自動編號', status=400)
    year = request.args.get('year', type=int)
    person_code = request.args.get('person_code', '').strip() or None
    result = db.suggest_next_quotation_no(doc_type, source_year=year, person_code=person_code)
    if not result:
        return resp(error='無法產生編號', status=400)
    return resp(result)


def _master_item_by_id(row_id):
    if not row_id:
        return None, resp(error='缺少 id', status=400)
    row = db.get_quotation_by_id(row_id)
    if not row:
        return None, resp(error='找不到報價記錄', status=404)
    return row, None


@app.route('/api/master/item', methods=['GET'])
def master_item_get():
    row_id = request.args.get('id', type=int)
    row, err = _master_item_by_id(row_id)
    if err:
        return err
    return resp(_master_quotation_row(row))


@app.route('/api/master/item', methods=['POST'])
def master_item_create():
    data = request.json or {}
    qno = (data.get('quotation_no') or '').strip()
    if not qno:
        return resp(error='請填寫報價編號', status=400)
    try:
        row = db.create_quotation_registry(qno, data)
        return resp(_master_quotation_row(row))
    except ValueError as e:
        return resp(error=str(e), status=400)
    except Exception as e:
        return resp(error=str(e), status=400)


@app.route('/api/master/item/finance', methods=['GET'])
def master_item_finance():
    row_id = request.args.get('id', type=int)
    row, err = _master_item_by_id(row_id)
    if err:
        return err
    return resp(db.get_quotation_finance(row['quotation_no']))


@app.route('/api/master/item/ip-reconcile', methods=['GET'])
def master_item_ip_reconcile():
    row_id = request.args.get('id', type=int)
    row, err = _master_item_by_id(row_id)
    if err:
        return err
    return resp(db.get_ip_reconciliation(
        project_id=row.get('project_id'),
        quotation_no=row['quotation_no'],
    ))


@app.route('/api/master/item/link', methods=['POST'])
def master_item_link():
    row_id = request.args.get('id', type=int)
    data = request.json or {}
    project_id = data.get('project_id')
    if not project_id:
        return resp(error='缺少 project_id', status=400)
    row, err = _master_item_by_id(row_id)
    if err:
        return err
    if not db.get_project(project_id):
        return resp(error='項目不存在', status=404)
    qno = row['quotation_no']
    db.link_quotation_to_project(qno, project_id, sync_project_code=True)
    return resp({'message': '已配對項目', 'quotation_no': qno, 'project_id': project_id})


@app.route('/api/master/item/unlink', methods=['POST'])
def master_item_unlink():
    row_id = request.args.get('id', type=int)
    row, err = _master_item_by_id(row_id)
    if err:
        return err
    db.unlink_quotation_from_project(row['quotation_no'])
    return resp({'message': '已解除項目配對'})


@app.route('/api/master/item', methods=['PUT'])
def master_item_update():
    row_id = request.args.get('id', type=int)
    data = request.json or {}
    row, err = _master_item_by_id(row_id)
    if err:
        return err
    qno = row['quotation_no']
    try:
        db.update_quotation_registry(qno, data)
        return resp(db.get_quotation_by_no(qno))
    except Exception as e:
        return resp(error=str(e), status=400)


def _master_quotation_row(row):
    if row.get('project_id'):
        row['project'] = db.get_project(row['project_id'])
    return row


@app.route('/api/master/quotations/id/<int:row_id>', methods=['GET'])
def master_list_quotation_by_id(row_id):
    row = db.get_quotation_by_id(row_id)
    if not row:
        return resp(error='找不到報價記錄', status=404)
    return resp(_master_quotation_row(row))


@app.route('/api/master/quotations/id/<int:row_id>/finance', methods=['GET'])
def master_list_quotation_finance_by_id(row_id):
    row = db.get_quotation_by_id(row_id)
    if not row:
        return resp(error='找不到報價記錄', status=404)
    return resp(db.get_quotation_finance(row['quotation_no']))


@app.route('/api/master/quotations/id/<int:row_id>/link', methods=['POST'])
def master_list_link_project_by_id(row_id):
    data = request.json or {}
    project_id = data.get('project_id')
    if not project_id:
        return resp(error='缺少 project_id', status=400)
    row = db.get_quotation_by_id(row_id)
    if not row:
        return resp(error='找不到報價記錄', status=404)
    if not db.get_project(project_id):
        return resp(error='項目不存在', status=404)
    qno = row['quotation_no']
    db.link_quotation_to_project(qno, project_id, sync_project_code=True)
    return resp({'message': '已配對項目', 'quotation_no': qno, 'project_id': project_id})


@app.route('/api/master/quotations/id/<int:row_id>/unlink', methods=['POST'])
def master_list_unlink_project_by_id(row_id):
    row = db.get_quotation_by_id(row_id)
    if not row:
        return resp(error='找不到報價記錄', status=404)
    db.unlink_quotation_from_project(row['quotation_no'])
    return resp({'message': '已解除項目配對'})


@app.route('/api/master/quotations/id/<int:row_id>', methods=['PUT'])
def master_list_update_quotation_by_id(row_id):
    data = request.json or {}
    row = db.get_quotation_by_id(row_id)
    if not row:
        return resp(error='找不到報價記錄', status=404)
    qno = row['quotation_no']
    try:
        db.update_quotation_registry(qno, data)
        return resp(db.get_quotation_by_no(qno))
    except Exception as e:
        return resp(error=str(e), status=400)


@app.route('/api/master/quotations/<path:quotation_no>', methods=['GET'])
def master_list_quotation_detail(quotation_no):
    row = db.get_quotation_by_no(quotation_no)
    if not row:
        return resp(error='找不到報價記錄', status=404)
    return resp(_master_quotation_row(row))


@app.route('/api/master/quotations/<path:quotation_no>/finance', methods=['GET'])
def master_list_quotation_finance(quotation_no):
    if not db.get_quotation_by_no(quotation_no):
        return resp(error='找不到報價記錄', status=404)
    return resp(db.get_quotation_finance(quotation_no))


@app.route('/api/master/quotations/<path:quotation_no>/link', methods=['POST'])
def master_list_link_project(quotation_no):
    data = request.json or {}
    project_id = data.get('project_id')
    if not project_id:
        return resp(error='缺少 project_id', status=400)
    if not db.get_quotation_by_no(quotation_no):
        return resp(error='找不到報價記錄', status=404)
    if not db.get_project(project_id):
        return resp(error='項目不存在', status=404)
    db.link_quotation_to_project(quotation_no, project_id, sync_project_code=True)
    return resp({'message': '已配對項目', 'quotation_no': quotation_no, 'project_id': project_id})


@app.route('/api/master/quotations/<path:quotation_no>/unlink', methods=['POST'])
def master_list_unlink_project(quotation_no):
    if not db.get_quotation_by_no(quotation_no):
        return resp(error='找不到報價記錄', status=404)
    db.unlink_quotation_from_project(quotation_no)
    return resp({'message': '已解除項目配對'})


@app.route('/api/master/quotations/<path:quotation_no>', methods=['PUT'])
def master_list_update_quotation(quotation_no):
    data = request.json or {}
    if not db.get_quotation_by_no(quotation_no):
        return resp(error='找不到報價記錄', status=404)
    try:
        db.update_quotation_registry(quotation_no, data)
        return resp(db.get_quotation_by_no(quotation_no))
    except Exception as e:
        return resp(error=str(e), status=400)


@app.route('/api/master/preview', methods=['POST'])
def master_list_preview():
    if 'file' not in request.files:
        return resp(error='沒有文件', status=400)
    file = request.files['file']
    if not file.filename.lower().endswith(('.xlsx', '.xls')):
        return resp(error='請上傳 Master List Excel', status=400)
    save_path = os.path.join(UPLOAD_DIR, secure_filename(file.filename))
    file.save(save_path)
    try:
        from master_list_importer import preview_master_import
        return resp(preview_master_import(save_path))
    except Exception as e:
        return resp(error=f'預覽失敗: {str(e)}', status=500)


@app.route('/api/master/sync', methods=['POST'])
def master_list_sync():
    if 'file' not in request.files:
        return resp(error='沒有文件', status=400)
    file = request.files['file']
    if not file.filename.lower().endswith(('.xlsx', '.xls')):
        return resp(error='請上傳 Master List Excel', status=400)
    save_path = os.path.join(UPLOAD_DIR, secure_filename(file.filename))
    file.save(save_path)
    try:
        from master_list_importer import sync_master_import
        stats = sync_master_import(save_path)
        stats['stats'] = db.get_quotation_registry_stats()
        return resp(stats)
    except Exception as e:
        return resp(error=f'同步失敗: {str(e)}', status=500)


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
        'auth_enabled': auth.is_enabled(),
        'auth_usernames': auth.configured_usernames(),
        'app_version': _app_version(),
    })


def _app_version():
    try:
        import startup
        return startup.APP_VERSION
    except Exception:
        return os.environ.get('APP_VERSION', 'unknown')


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


@app.route('/api/system/restore-uploads', methods=['POST'])
def restore_uploads():
    """上傳 uploads.zip 還原附件（保留檔名；需 RESTORE_TOKEN）"""
    import shutil
    import zipfile

    expected = os.environ.get('RESTORE_TOKEN', '').strip()
    token = (request.headers.get('X-Restore-Token') or request.form.get('token') or '').strip()
    if not expected or token != expected:
        return resp(error='未授權', status=403)

    if 'file' not in request.files:
        return resp(error='請上傳 uploads.zip', status=400)
    file = request.files['file']
    if not file.filename:
        return resp(error='沒有文件', status=400)

    from config import UPLOAD_DIR
    tmp_zip = os.path.join(UPLOAD_DIR, '_restore_uploads.zip')
    file.save(tmp_zip)
    synced = skipped = 0
    try:
        with zipfile.ZipFile(tmp_zip, 'r') as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                base = os.path.basename(info.filename)
                if not base or base.startswith('.') or '..' in base:
                    continue
                dest = os.path.join(UPLOAD_DIR, base)
                if os.path.exists(dest):
                    skipped += 1
                    continue
                with zf.open(info) as src, open(dest, 'wb') as dst:
                    shutil.copyfileobj(src, dst)
                synced += 1
    except zipfile.BadZipFile as e:
        return resp(error=f'無效的 zip: {e}', status=400)
    finally:
        if os.path.exists(tmp_zip):
            os.remove(tmp_zip)

    upload_count = len([
        f for f in os.listdir(UPLOAD_DIR)
        if os.path.isfile(os.path.join(UPLOAD_DIR, f))
    ])
    return resp({
        'message': 'uploads 已同步',
        'synced': synced,
        'skipped': skipped,
        'upload_count': upload_count,
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


# ─── Summary Import API ───────────────────────────────────────────────
@app.route('/api/import/summary', methods=['POST'])
def import_summary_api():
    """上傳 Summary.xlsx 匯入工程項目"""
    if 'file' not in request.files:
        return resp(error='沒有文件', status=400)
    file = request.files['file']
    if not file.filename.lower().endswith(('.xlsx', '.xls')):
        return resp(error='請上傳 Excel 文件', status=400)

    save_path = os.path.join(UPLOAD_DIR, secure_filename(file.filename))
    file.save(save_path)
    try:
        from summary_importer import sync_summary_import
        stats = sync_summary_import(save_path, update_existing=True)
        return resp(stats)
    except Exception as e:
        return resp(error=f'匯入失敗: {str(e)}', status=500)


@app.route('/api/import/summary/sync', methods=['POST'])
def sync_summary_ref():
    """從 Ref/Summary.xlsx 同步工程項目"""
    from summary_importer import DEFAULT_SUMMARY_PATH, sync_summary_import
    if not os.path.exists(DEFAULT_SUMMARY_PATH):
        return resp(error=f'找不到 {DEFAULT_SUMMARY_PATH}', status=404)
    try:
        stats = sync_summary_import(DEFAULT_SUMMARY_PATH, update_existing=True)
        return resp(stats)
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
