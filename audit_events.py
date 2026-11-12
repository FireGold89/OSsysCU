"""業務操作稽核（模組摘要 + 欄位級 diff）。"""
import json

import access_control
import auth
import database as db

MODULE_LABELS = {
    'staff': '項目負責人',
    'payment': '地盤付款',
    'master': 'Master List',
    'portfolio': '項目登記',
    'ip': '糧期',
    'access': '帳號與權限',
    'iso': 'ISO 文件',
    'sc_contract': 'MS/C 合約',
    'sc': '判項／分判商',
}

ACTION_LABELS = {
    'create': '新增',
    'update': '修改',
    'delete': '刪除',
    'deactivate': '停用',
    'link': '配對項目',
    'unlink': '解除配對',
    'withdraw': '撤回計算書',
    'restore': '還原',
    'upload': '上傳',
}

STAFF_FIELDS = (
    'code', 'name_en', 'name_zh', 'email', 'phone',
    'department', 'access_role', 'is_active', 'notes',
)
STAFF_LABELS = {
    'code': '編號縮寫',
    'name_en': '英文姓名',
    'name_zh': '中文姓名',
    'email': '電郵',
    'phone': '電話',
    'department': '部門',
    'access_role': '權限角色',
    'is_active': '啟用',
    'notes': '備註',
}

PAYMENT_FIELDS = (
    'invoice_no', 'invoice_date', 'sc_no', 'quotation_no',
    'company_name_en', 'company_name_zh', 'description',
    'contract_amount', 'paid_amount', 'remainder_amount',
    'oa_ref', 'oa_no', 'mc_ip_no', 'sub_ip_no', 'remark', 'payment_type',
)
PAYMENT_LABELS = {
    'invoice_no': '發票號',
    'invoice_date': '發票日期',
    'sc_no': '判項',
    'quotation_no': '報價編號',
    'company_name_en': '分判商（英）',
    'company_name_zh': '分判商（中）',
    'description': '描述',
    'contract_amount': '合約金額',
    'paid_amount': '已付金額',
    'remainder_amount': '餘額',
    'oa_ref': 'OA Ref',
    'oa_no': 'OA No',
    'mc_ip_no': 'MC IP',
    'sub_ip_no': 'Sub IP',
    'remark': '備註',
    'payment_type': '類型',
}

MASTER_LABELS = {
    'quote_date': '報價日期',
    'doc_type': '文件類型',
    'awarded': '中標',
    'site_name': '地盤名稱',
    'trade_scope': '工種範圍',
    'trade_override': '工種覆寫',
    'trade_category': '工種分類',
    'description': '描述',
    'person_code': '負責人代碼',
    'person_in_charge': '負責人',
    'client_name': '客戶',
    'quoted_amount': '報價金額',
    'margin_pct': '毛利率',
    'awarded_amount': '中標金額',
    'contract_days': '合約天數',
    'start_date': '開工日',
    'completion_date': '完工日',
    'subcon_type': '分判類型',
    'subcon_company': '分判商',
    'subcon_amount': '分判金額',
    'profit_amount': '利潤',
    'profit_pct': '利潤率',
    'checklist_json': '開票欄位',
}

PORTFOLIO_LABELS = {
    'n_code': 'N 碼',
    'expected_completion_date': '預計完工',
    'project_progress_status': '項目狀態',
    'client_fac_status': 'Client FA',
    'portfolio_remark': '備註',
    'pc_cert_done': 'PC 證書',
    'defect_cert_done': '缺陷證書',
    'dlp_commencement_date': 'DLP 開始',
    'dlp_days': 'DLP（日）',
    'dlp_expiry_date': 'DLP 到期',
}


def _norm(value):
    if value is None:
        return ''
    if isinstance(value, bool):
        return '1' if value else '0'
    if isinstance(value, (int, float)):
        if isinstance(value, float) and value == int(value):
            return str(int(value))
        return str(value)
    s = str(value).strip()
    if s in ('null', 'None'):
        return ''
    return s


def _display(field, value, labels):
    if field == 'is_active':
        return '啟用' if str(value) in ('1', 'True', 'true') else '停用'
    if field == 'awarded':
        if value in (True, 1, '1', 'true', 'True'):
            return '是'
        if value in (False, 0, '0', 'false', 'False'):
            return '否'
    if field in ('contract_amount', 'paid_amount', 'remainder_amount',
                 'quoted_amount', 'awarded_amount', 'subcon_amount', 'profit_amount',
                 'application_amount', 'certified_income', 'subcon_paid', 'amount',
                 'ip_total_income', 'ip_total_expenditure', 'ip_advance',
                 'supplemental_contract_amount'):
        try:
            num = float(value or 0)
            return f'HK${num:,.2f}'
        except (TypeError, ValueError):
            pass
    if field in ('pc_cert_done', 'defect_cert_done'):
        return '✔' if str(value) in ('1', 'True', 'true') else '—'
    if field == 'checklist_json' and value:
        raw = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
        return raw[:120] + ('…' if len(raw) > 120 else '')
    return _norm(value) or '—'


def diff_dict(old, new, fields, labels):
    """比對欄位，回傳 changes 列表。"""
    changes = []
    old = old or {}
    new = new or {}
    for key in fields:
        if key not in new and old:
            continue
        ov = old.get(key)
        nv = new.get(key)
        if _norm(ov) == _norm(nv):
            continue
        changes.append({
            'field': key,
            'label': labels.get(key, key),
            'old': _display(key, ov, labels),
            'new': _display(key, nv, labels),
        })
    return changes


def summary_from_changes(action, object_label, changes, extra=None):
    verb = ACTION_LABELS.get(action, action)
    if not changes:
        tail = extra or ''
        return f'{verb} {object_label}{tail}'
    parts = []
    for ch in changes[:4]:
        parts.append(f'{ch["label"]}：{ch["old"]} → {ch["new"]}')
    more = f' 等 {len(changes)} 項' if len(changes) > 4 else ''
    extra_suffix = f'；{extra}' if extra else ''
    return f'{verb} {object_label} — ' + '；'.join(parts) + more + extra_suffix


def staff_object_label(row):
    if not row:
        return '項目負責人'
    name = (row.get('name_zh') or row.get('name_en') or '').strip()
    code = (row.get('code') or '').strip()
    if name and code:
        return f'{name}（{code}）'
    return name or (f'#{row.get("id")}' if row.get('id') else '項目負責人')


def payment_object_label(row):
    if not row:
        return '付款記錄'
    inv = (row.get('invoice_no') or '').strip()
    sc = (row.get('sc_no') or '').strip()
    parts = []
    if inv:
        parts.append(f'發票 {inv}')
    if sc:
        parts.append(f'判項 {sc}')
    pid = row.get('id')
    if parts:
        return ' · '.join(parts)
    return f'付款 #{pid}' if pid else '付款記錄'


def master_object_label(row):
    qno = (row or {}).get('quotation_no') or ''
    site = ((row or {}).get('site_name') or '').strip()
    if qno and site:
        return f'{qno} · {site}'
    return qno or 'Master 報價'


def portfolio_object_label(row):
    code = (row or {}).get('project_code') or ''
    name = (row or {}).get('project_name_zh') or (row or {}).get('project_name') or ''
    if code and name:
        return f'{code} · {name[:40]}'
    return code or name or '項目登記'


def project_code_for_id(project_id):
    if not project_id:
        return None
    proj = db.get_project(project_id)
    if not proj:
        return None
    return (proj.get('project_code') or '').strip() or None


def record(module, action, object_label, *, project_code=None, summary=None,
           changes=None, snapshot=None):
    user = auth.current_user()
    if not user:
        return
    detail = {}
    if changes:
        detail['changes'] = changes
    if snapshot:
        detail['snapshot'] = snapshot
    if not summary:
        summary = summary_from_changes(action, object_label, changes or [])
    db.insert_audit_event(
        username=user.get('username'),
        display_name=auth.actor_display_name(),
        role=user.get('role'),
        module=module,
        action=action,
        object_label=object_label,
        project_code=project_code,
        summary=summary[:500],
        detail_json=json.dumps(detail, ensure_ascii=False) if detail else None,
    )


def audit_staff_create(staff_id):
    row = db.get_staff_member(staff_id)
    if not row:
        return
    snap = {k: _display(k, row.get(k), STAFF_LABELS) for k in STAFF_FIELDS}
    record(
        'staff', 'create', staff_object_label(row),
        summary=f'新增項目負責人 {staff_object_label(row)}',
        snapshot=snap,
    )


def audit_staff_update(staff_id, before, after):
    changes = diff_dict(before, after, STAFF_FIELDS, STAFF_LABELS)
    if not changes:
        return
    record(
        'staff', 'update', staff_object_label(after),
        summary=summary_from_changes('update', staff_object_label(after), changes),
        changes=changes,
    )


def audit_staff_deactivate(before):
    if not before:
        return
    record(
        'staff', 'deactivate', staff_object_label(before),
        summary=f'停用項目負責人 {staff_object_label(before)}',
        snapshot={k: _display(k, before.get(k), STAFF_LABELS) for k in STAFF_FIELDS},
    )


def audit_payment_create(payment_id):
    row = db.get_payment(payment_id)
    if not row:
        return
    pcode = project_code_for_id(row.get('project_id'))
    snap = {k: _display(k, row.get(k), PAYMENT_LABELS) for k in PAYMENT_FIELDS if row.get(k) not in (None, '', 0)}
    record(
        'payment', 'create', payment_object_label(row),
        project_code=pcode,
        summary=f'新增付款 {payment_object_label(row)}' + (f'（{pcode}）' if pcode else ''),
        snapshot=snap,
    )


def audit_payment_update(payment_id, before, patch):
    after = db.get_payment(payment_id) or {**before, **patch}
    changes = diff_dict(before, after, PAYMENT_FIELDS, PAYMENT_LABELS)
    if not changes:
        return
    pcode = project_code_for_id(after.get('project_id') or before.get('project_id'))
    record(
        'payment', 'update', payment_object_label(after),
        project_code=pcode,
        summary=summary_from_changes('update', payment_object_label(after), changes),
        changes=changes,
    )


def audit_payment_delete(before):
    if not before:
        return
    pcode = project_code_for_id(before.get('project_id'))
    record(
        'payment', 'delete', payment_object_label(before),
        project_code=pcode,
        summary=f'刪除付款 {payment_object_label(before)}' + (f'（{pcode}）' if pcode else ''),
        snapshot={k: _display(k, before.get(k), PAYMENT_LABELS) for k in PAYMENT_FIELDS
                  if before.get(k) not in (None, '', 0)},
    )


def audit_payment_message(payment_id, action):
    row = db.get_payment(payment_id)
    if not row:
        return
    pcode = project_code_for_id(row.get('project_id'))
    record(
        'payment', action, payment_object_label(row),
        project_code=pcode,
        summary=f'{ACTION_LABELS.get(action, action)} {payment_object_label(row)}',
    )


def audit_master_create(row):
    if not row:
        return
    snap = {k: _display(k, row.get(k), MASTER_LABELS) for k in db.MASTER_EDITABLE_FIELDS
            if row.get(k) not in (None, '', [])}
    record(
        'master', 'create', master_object_label(row),
        summary=f'新增 Master {master_object_label(row)}',
        snapshot=snap,
    )


def audit_master_update(quotation_no, before, patch):
    after = db.get_quotation_by_no(quotation_no) or {**before, **patch}
    fields = [k for k in db.MASTER_EDITABLE_FIELDS if k in patch]
    changes = diff_dict(before, after, fields, MASTER_LABELS)
    if not changes:
        return
    pcode = None
    if after.get('project_id'):
        pcode = project_code_for_id(after['project_id'])
    record(
        'master', 'update', master_object_label(after),
        project_code=pcode,
        summary=summary_from_changes('update', master_object_label(after), changes),
        changes=changes,
    )


def audit_master_link(row, project_id):
    pcode = project_code_for_id(project_id)
    record(
        'master', 'link', master_object_label(row),
        project_code=pcode,
        summary=f'Master {master_object_label(row)} 配對項目 {pcode or project_id}',
    )


def audit_master_unlink(row):
    pcode = project_code_for_id(row.get('project_id')) if row else None
    record(
        'master', 'unlink', master_object_label(row),
        project_code=pcode,
        summary=f'Master {master_object_label(row)} 解除項目配對',
    )


def audit_portfolio_update(portfolio_id, before, payload, after):
    fields = [k for k in payload if k in PORTFOLIO_LABELS]
    changes = diff_dict(before, after, fields, PORTFOLIO_LABELS)
    if not changes:
        return
    record(
        'portfolio', 'update', portfolio_object_label(after),
        project_code=(after or {}).get('project_code'),
        summary=summary_from_changes('update', portfolio_object_label(after), changes),
        changes=changes,
    )


def audit_portfolio_sc_status(portfolio_id, slot_count):
    from portfolio import get_portfolio_item
    item = get_portfolio_item(portfolio_id)
    label = portfolio_object_label(item) if item else f'項目登記 #{portfolio_id}'
    record(
        'portfolio', 'update', label,
        project_code=(item or {}).get('project_code'),
        summary=f'修改 {label} 的分判 FAC 狀態（{slot_count} 槽）',
    )


LEVEL_LABELS = {'none': '不可見', 'view': '只看', 'edit': '可編輯'}

IP_FIELDS = (
    'ip_no', 'applied_date', 'certificate_date', 'subcon_cert_date', 'receipt_date',
    'application_amount', 'certified_income', 'subcon_paid',
    'receipt_method', 'receipt_cheque_no', 'receipt_bank', 'receipt_note',
)
IP_LABELS = {
    'ip_no': '糧期號',
    'applied_date': '申請日期',
    'certificate_date': '證書日期',
    'subcon_cert_date': '分包證書日期',
    'receipt_date': '收款日期',
    'application_amount': '申請金額',
    'certified_income': '核定收入',
    'subcon_paid': '分包支出',
    'receipt_method': '收款方式',
    'receipt_cheque_no': '支票號',
    'receipt_bank': '銀行',
    'receipt_note': '收款備註',
}

IP_META_FIELDS = (
    'site_period_text', 'ip_total_income', 'ip_total_expenditure', 'ip_advance',
)
IP_META_LABELS = {
    'site_period_text': '糧期涵蓋',
    'ip_total_income': '糧期總收入',
    'ip_total_expenditure': '糧期總支出',
    'ip_advance': '墊支',
}

SC_FIELDS = (
    'sc_no', 'quotation_no', 'company_name_en', 'company_name_zh', 'description',
    'contract_sum', 'vo_amount', 'contract_amount', 'sub_contract_no', 'parent_sc_no',
    'is_excluded', 'oa_ref', 'oa_no', 'payment_note',
)
SC_LABELS = {
    'sc_no': '判項',
    'quotation_no': '報價編號',
    'company_name_en': '分判商（英）',
    'company_name_zh': '分判商（中）',
    'description': '描述',
    'contract_sum': '合約金額',
    'vo_amount': 'VO 金額',
    'contract_amount': '合計金額',
    'sub_contract_no': 'MS/C',
    'parent_sc_no': '父判項',
    'is_excluded': '排除統計',
    'oa_ref': 'OA Ref',
    'oa_no': 'OA No',
    'payment_note': '付款備註',
}

SCR_FIELDS = (
    'sub_contract_no', 'company', 'works', 'project_code', 'person_in_charge',
    'amount', 'countersign', 'partner', 'tender_minutes', 'final_account',
    'final_account_statement', 'iso_flag', 'remark',
)
SCR_LABELS = {
    'sub_contract_no': 'MS/C',
    'company': '分判商',
    'works': '工程內容',
    'project_code': '項目編號',
    'person_in_charge': '負責人',
    'amount': '金額',
    'countersign': '會簽',
    'partner': 'Partner',
    'tender_minutes': '標書會議',
    'final_account': '最終帳',
    'final_account_statement': '結算表',
    'iso_flag': 'ISO',
    'remark': '備註',
}

APP_USER_FIELDS = ('display_name', 'role', 'is_active')
APP_USER_LABELS = {
    'display_name': '顯示名稱',
    'role': '角色範本',
    'is_active': '啟用',
}


def diff_permissions(old_perm, new_perm):
    old_perm = old_perm or {}
    new_perm = new_perm or {}
    changes = []
    for area in access_control.AREAS:
        aid = area['id']
        ov = old_perm.get(aid, 'none')
        nv = new_perm.get(aid, 'none')
        if _norm(ov) == _norm(nv):
            continue
        changes.append({
            'field': aid,
            'label': area['label'],
            'old': LEVEL_LABELS.get(ov, ov),
            'new': LEVEL_LABELS.get(nv, nv),
        })
    return changes


def ip_object_label(row):
    ip = (row or {}).get('ip_no') or ''
    return f'糧期 {ip}' if ip else '糧期記錄'


def sc_object_label(row):
    sc = (row or {}).get('sc_no') or ''
    name = (row or {}).get('company_name_zh') or (row or {}).get('company_name_en') or ''
    if sc and name:
        return f'判項 {sc} · {name[:30]}'
    return f'判項 {sc}' if sc else '判項'


def scr_object_label(row):
    return (row or {}).get('sub_contract_no') or 'MS/C'


def iso_object_label(row, project_id=None):
    scope = (row or {}).get('scope') or ''
    slot = (row or {}).get('doc_slot') or ''
    name = (row or {}).get('original_filename') or (row or {}).get('link_label') or ''
    parts = [p for p in (scope, slot, name) if p]
    label = ' · '.join(parts) if parts else 'ISO 附件'
    if project_id:
        pcode = project_code_for_id(project_id)
        if pcode:
            return f'{label}（{pcode}）'
    return label


def access_user_label(row):
    un = (row or {}).get('username') or ''
    dn = (row or {}).get('display_name') or ''
    if un and dn and dn != un:
        return f'{dn}（{un}）'
    return un or '系統帳號'


def template_object_label(row):
    return (row or {}).get('label') or (row or {}).get('id') or '角色範本'


def audit_ip_create(ip_id):
    row = db.get_interim_payment(ip_id)
    if not row:
        return
    pcode = project_code_for_id(row.get('project_id'))
    snap = {IP_LABELS[k]: _display(k, row.get(k), IP_LABELS) for k in IP_FIELDS
            if row.get(k) not in (None, '', 0)}
    record(
        'ip', 'create', ip_object_label(row),
        project_code=pcode,
        summary=f'新增 {ip_object_label(row)}' + (f'（{pcode}）' if pcode else ''),
        snapshot=snap,
    )


def audit_ip_update(ip_id, before, patch=None):
    after = db.get_interim_payment(ip_id)
    if not after:
        return
    fields = list(IP_FIELDS)
    changes = diff_dict(before, after, fields, IP_LABELS)
    if not changes:
        return
    pcode = project_code_for_id(after.get('project_id'))
    record(
        'ip', 'update', ip_object_label(after),
        project_code=pcode,
        summary=summary_from_changes('update', ip_object_label(after), changes),
        changes=changes,
    )


def audit_ip_delete(before):
    if not before:
        return
    pcode = project_code_for_id(before.get('project_id'))
    record(
        'ip', 'delete', ip_object_label(before),
        project_code=pcode,
        summary=f'刪除 {ip_object_label(before)}' + (f'（{pcode}）' if pcode else ''),
        snapshot={IP_LABELS[k]: _display(k, before.get(k), IP_LABELS) for k in IP_FIELDS
                  if before.get(k) not in (None, '', 0)},
    )


def audit_ip_meta_update(project_id, before_proj, meta):
    after = db.get_project(project_id) or {}
    patch = {k: meta[k] for k in IP_META_FIELDS if k in meta}
    changes = diff_dict(before_proj, after, list(patch.keys()), IP_META_LABELS)
    if not changes:
        return
    pcode = (after.get('project_code') or '').strip() or None
    record(
        'ip', 'update', f'糧期彙總 · {pcode or project_id}',
        project_code=pcode,
        summary=summary_from_changes('update', f'項目糧期彙總', changes),
        changes=changes,
    )


def audit_ip_attachment(ip_id, kind, filename):
    row = db.get_interim_payment(ip_id)
    if not row:
        return
    pcode = project_code_for_id(row.get('project_id'))
    kinds = {
        'receipt': '收款附件',
        'application': 'IP Application',
        'cert': 'IP Cert.',
    }
    label = kinds.get(kind, '附件')
    record(
        'ip', 'upload', ip_object_label(row),
        project_code=pcode,
        summary=f'上傳 {ip_object_label(row)} 的{label}：{filename or "—"}',
        snapshot={label: filename or '—'},
    )


def audit_ip_attachment_removed(ip_id, kind):
    row = db.get_interim_payment(ip_id)
    if not row:
        return
    pcode = project_code_for_id(row.get('project_id'))
    record(
        'ip', 'delete', ip_object_label(row),
        project_code=pcode,
        summary=f'移除 {ip_object_label(row)} 的{kind}附件',
    )


def audit_sc_upsert(sc_id, before, after, created):
    if created:
        snap = {SC_LABELS[k]: _display(k, after.get(k), SC_LABELS) for k in SC_FIELDS
                if after.get(k) not in (None, '', 0)}
        pcode = project_code_for_id(after.get('project_id'))
        record(
            'sc', 'create', sc_object_label(after),
            project_code=pcode,
            summary=f'新增 {sc_object_label(after)}' + (f'（{pcode}）' if pcode else ''),
            snapshot=snap,
        )
        return
    changes = diff_dict(before, after, SC_FIELDS, SC_LABELS)
    if not changes:
        return
    pcode = project_code_for_id(after.get('project_id'))
    record(
        'sc', 'update', sc_object_label(after),
        project_code=pcode,
        summary=summary_from_changes('update', sc_object_label(after), changes),
        changes=changes,
    )


def audit_sc_delete(before):
    if not before:
        return
    pcode = project_code_for_id(before.get('project_id'))
    record(
        'sc', 'delete', sc_object_label(before),
        project_code=pcode,
        summary=f'刪除 {sc_object_label(before)}' + (f'（{pcode}）' if pcode else ''),
        snapshot={SC_LABELS[k]: _display(k, before.get(k), SC_LABELS) for k in SC_FIELDS
                  if before.get(k) not in (None, '', 0)},
    )


def audit_scr_save(before, after, created):
    if created:
        snap = {SCR_LABELS[k]: _display(k, after.get(k), SCR_LABELS) for k in SCR_FIELDS
                if after.get(k) not in (None, '', 0)}
        record(
            'sc_contract', 'create', scr_object_label(after),
            project_code=(after.get('project_code') or '').strip() or None,
            summary=f'新增 MS/C {scr_object_label(after)}',
            snapshot=snap,
        )
        return
    changes = diff_dict(before, after, SCR_FIELDS, SCR_LABELS)
    if not changes:
        return
    record(
        'sc_contract', 'update', scr_object_label(after),
        project_code=(after.get('project_code') or '').strip() or None,
        summary=summary_from_changes('update', scr_object_label(after), changes),
        changes=changes,
    )


def audit_scr_delete(before):
    if not before:
        return
    record(
        'sc_contract', 'delete', scr_object_label(before),
        project_code=(before.get('project_code') or '').strip() or None,
        summary=f'刪除 MS/C {scr_object_label(before)}',
        snapshot={SCR_LABELS[k]: _display(k, before.get(k), SCR_LABELS) for k in SCR_FIELDS
                  if before.get(k) not in (None, '', 0)},
    )


def audit_iso_upload(row, project_id, filename):
    pcode = project_code_for_id(project_id)
    record(
        'iso', 'upload', iso_object_label(row, project_id),
        project_code=pcode,
        summary=f'上傳 ISO：{iso_object_label(row, project_id)}',
        snapshot={'檔名': filename or row.get('original_filename') or '—'},
    )


def audit_iso_link(row, project_id, url):
    pcode = project_code_for_id(project_id)
    short = (url or '')[:80] + ('…' if len(url or '') > 80 else '')
    record(
        'iso', 'link', iso_object_label(row, project_id),
        project_code=pcode,
        summary=f'ISO 連結：{iso_object_label(row, project_id)}',
        snapshot={'連結': short or '—'},
    )


def audit_iso_delete(before, project_id):
    pcode = project_code_for_id(project_id or before.get('project_id'))
    record(
        'iso', 'delete', iso_object_label(before, project_id),
        project_code=pcode,
        summary=f'刪除 ISO：{iso_object_label(before, project_id)}',
    )


def audit_iso_meta_amount(project_id, before_amount, new_amount):
    pcode = project_code_for_id(project_id)
    record(
        'iso', 'update', f'補充合約金額 · {pcode or project_id}',
        project_code=pcode,
        summary=f'補充合約金額：{_display("amount", before_amount, {})} → {_display("amount", new_amount, {})}',
        changes=[{
            'field': 'supplemental_contract_amount',
            'label': '補充合約金額',
            'old': _display('supplemental_contract_amount', before_amount, {}),
            'new': _display('supplemental_contract_amount', new_amount, {}),
        }],
    )


def audit_access_user_create(row, password_set):
    snap = {APP_USER_LABELS[k]: _display(k, row.get(k), APP_USER_LABELS) for k in APP_USER_FIELDS}
    extra = '（已設密碼）' if password_set else ''
    record(
        'access', 'create', access_user_label(row),
        summary=f'新增帳號 {access_user_label(row)}{extra}',
        snapshot=snap,
    )


def audit_access_user_update(before, after, password_changed):
    changes = diff_dict(before, after, APP_USER_FIELDS, APP_USER_LABELS)
    changes.extend(diff_permissions(before.get('permissions'), after.get('permissions')))
    if not changes and not password_changed:
        return
    extra = '；已重設密碼' if password_changed else ''
    record(
        'access', 'update', access_user_label(after),
        summary=summary_from_changes('update', access_user_label(after), changes, extra=extra.strip('；') or None),
        changes=changes or None,
        snapshot={'密碼': '已變更'} if password_changed and not changes else None,
    )


def audit_access_user_delete(before):
    if not before:
        return
    record(
        'access', 'delete', access_user_label(before),
        summary=f'刪除帳號 {access_user_label(before)}',
        snapshot={APP_USER_LABELS[k]: _display(k, before.get(k), APP_USER_LABELS) for k in APP_USER_FIELDS},
    )


def audit_access_template_create(row):
    record(
        'access', 'create', template_object_label(row),
        summary=f'新增角色範本 {template_object_label(row)}',
        snapshot={'說明': (row.get('hint') or '—')[:120]},
    )


def audit_access_template_update(before, after, followers=0):
    changes = []
    if before:
        for key, label in (('label', '名稱'), ('hint', '說明')):
            if _norm(before.get(key)) != _norm(after.get(key)):
                changes.append({
                    'field': key,
                    'label': label,
                    'old': _display(key, before.get(key), {}),
                    'new': _display(key, after.get(key), {}),
                })
        changes.extend(diff_permissions(before.get('matrix'), after.get('matrix')))
    if not changes:
        extra = f'已更新 {followers} 個跟隨帳號' if followers else None
        record(
            'access', 'update', template_object_label(after),
            summary=f'儲存角色範本 {template_object_label(after)}' + (f'（{extra}）' if extra else ''),
        )
        return
    extra = f'已更新 {followers} 個跟隨帳號' if followers else None
    record(
        'access', 'update', template_object_label(after),
        summary=summary_from_changes('update', template_object_label(after), changes, extra=extra),
        changes=changes,
    )


def audit_access_template_restore(after, followers=0):
    record(
        'access', 'restore', template_object_label(after),
        summary=f'還原角色範本 {template_object_label(after)}'
        + (f'（已更新 {followers} 個跟隨帳號）' if followers else ''),
    )


def audit_access_template_delete(before, detach=False):
    if not before:
        return
    record(
        'access', 'delete', template_object_label(before),
        summary=f'刪除角色範本 {template_object_label(before)}'
        + ('（跟隨帳號改為自訂）' if detach else ''),
    )
