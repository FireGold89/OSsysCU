"""業務操作稽核（模組摘要 + 欄位級 diff）。"""
import json

import auth
import database as db

MODULE_LABELS = {
    'staff': '項目負責人',
    'payment': '地盤付款',
    'master': 'Master List',
    'portfolio': '項目登記',
}

ACTION_LABELS = {
    'create': '新增',
    'update': '修改',
    'delete': '刪除',
    'deactivate': '停用',
    'link': '配對項目',
    'unlink': '解除配對',
    'withdraw': '撤回計算書',
    'restore': '還原計算書',
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
                 'quoted_amount', 'awarded_amount', 'subcon_amount', 'profit_amount'):
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
