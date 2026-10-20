"""登入權限：範圍 × 不可見／只看／可編輯。管理員帳號不受個別範圍限制。"""

AREAS = (
    {'id': 'projects', 'label': '工程項目／概覽', 'hint': '項目資料、概覽、工程分類'},
    {'id': 'iso', 'label': 'ISO 文件', 'hint': '主合約及分判附件'},
    {'id': 'payments', 'label': '分判付款', 'hint': '付款登記、OCR、發票'},
    {'id': 'vo', 'label': '變更以及扣款', 'hint': 'VO／扣款登記'},
    {'id': 'ip', 'label': '糧期狀況', 'hint': '中期糧款、糧期核對'},
    {'id': 'fac', 'label': '最終結算', 'hint': '主合約及分判 FAC'},
    {'id': 'sc', 'label': '分判商', 'hint': '判項主檔'},
    {'id': 'docs', 'label': '項目文件', 'hint': '項目文件庫'},
    {'id': 'master', 'label': 'Master List', 'hint': '報價／標書／行政開票欄'},
    {'id': 'sc_contract', 'label': '分判合約編號', 'hint': 'MS/C 合約編號'},
    {'id': 'portfolio', 'label': '全公司總表', 'hint': '進行中項目、結算總表'},
    {'id': 'eng', 'label': '工程部會簽', 'hint': '項目登記、會簽出表'},
    {'id': 'reports', 'label': '財務報表', 'hint': '統計與項目視角'},
    {'id': 'staff', 'label': '項目負責人名單', 'hint': '負責人主檔（非登入帳號）'},
)

LEVELS = ('none', 'view', 'edit')
PRESET_ROLES = ('admin', 'qs', 'finance', 'viewer', 'custom')

_QS = {
    'projects': 'edit', 'iso': 'edit', 'payments': 'edit', 'vo': 'edit', 'ip': 'edit',
    'fac': 'edit', 'sc': 'edit', 'docs': 'edit', 'master': 'view', 'sc_contract': 'edit',
    'portfolio': 'view', 'eng': 'view', 'reports': 'view', 'staff': 'view',
}
_FINANCE = {
    'projects': 'view', 'iso': 'view', 'payments': 'view', 'vo': 'view', 'ip': 'view',
    'fac': 'view', 'sc': 'view', 'docs': 'view', 'master': 'edit', 'sc_contract': 'view',
    'portfolio': 'view', 'eng': 'none', 'reports': 'view', 'staff': 'view',
}
_VIEW = {a['id']: 'view' for a in AREAS}
_ADMIN = {a['id']: 'edit' for a in AREAS}
_NONE = {a['id']: 'none' for a in AREAS}

PRESETS = {
    'admin': _ADMIN,
    'qs': _QS,
    'user': _QS,
    'finance': _FINANCE,
    'viewer': _VIEW,
    'custom': _NONE,
}

# 較長的路徑片段優先
_PATH_RULES = (
    ('iso', ('/iso-documents', '/iso-meta')),
    ('payments', ('/payments', '/ocr', '/api/import')),
    ('vo', ('/sc-vo',)),
    ('ip', ('/interim-payments', '/ip-reconciliation', '/ip-sc-drilldown')),
    ('fac', ('/main-con-fac', '/sc-fac')),
    ('docs', ('/documents', '/project-documents')),
    ('sc', ('/subcontractors',)),
    ('master', ('/api/master',)),
    ('sc_contract', ('/api/sc-contract-registry',)),
    ('portfolio', ('/api/portfolio', '/api/company-summary')),
    ('eng', ('/api/eng',)),
    ('reports', ('/api/reports', '/dashboard-overview', '/cover-page')),
    ('staff', ('/api/staff',)),
    ('projects', ('/api/projects', '/api/engineering-categories')),
)

_SYSTEM_PREFIXES = (
    '/api/admin',
    '/api/settings',
    '/api/system/restore-db',
    '/api/system/restore-uploads',
    '/api/system/sync-excel',
)


def preset_matrix(role):
    base = PRESETS.get((role or '').strip().lower()) or _QS
    return {a['id']: base.get(a['id'], 'none') for a in AREAS}


def normalize_matrix(raw, role):
    """缺欄用角色預設補上；非法值當成 none。"""
    base = preset_matrix(role if role in PRESETS else 'custom')
    if not isinstance(raw, dict):
        return base
    out = {}
    for area in AREAS:
        val = raw.get(area['id'], base[area['id']])
        out[area['id']] = val if val in LEVELS else 'none'
    return out


def matrix_matches(role, matrix):
    return matrix == preset_matrix(role)


def catalog_payload():
    return {
        'areas': list(AREAS),
        'levels': [
            {'id': 'none', 'label': '不可見'},
            {'id': 'view', 'label': '只看'},
            {'id': 'edit', 'label': '可編輯'},
        ],
        'presets': [
            {'id': 'admin', 'label': '管理員', 'hint': '全部可編輯，含帳號與系統設定'},
            {'id': 'qs', 'label': 'QS', 'hint': '地盤付款、糧期、ISO、結算可編輯；Master List 只看'},
            {'id': 'finance', 'label': '財務／行政', 'hint': 'Master List 可編輯；地盤資料只看'},
            {'id': 'viewer', 'label': '唯讀', 'hint': '全部只看'},
            {'id': 'custom', 'label': '自訂', 'hint': '按下方範圍逐項設定'},
        ],
        'matrices': {key: preset_matrix(key) for key in ('admin', 'qs', 'finance', 'viewer', 'custom')},
    }


def area_for_path(path):
    path = path or ''
    for area, needles in _PATH_RULES:
        for needle in needles:
            if needle in path:
                return area
    return None


def is_system_path(path):
    path = path or ''
    return any(path == p or path.startswith(p + '/') or path.startswith(p) for p in _SYSTEM_PREFIXES)


def decide(actor, method, path):
    """回傳錯誤訊息；允許則 None。actor 含 is_admin、perms。"""
    if not actor:
        return '請先登入'
    if (method or '').upper() == 'OPTIONS':
        return None
    if is_system_path(path):
        if not actor.get('is_admin'):
            return '需要管理員權限'
        return None
    perms = actor.get('perms') or {}
    writing = (method or '').upper() in ('POST', 'PUT', 'PATCH', 'DELETE')
    if path.startswith(('/api/uploads', '/api/files', '/api/sc-vo-templates', '/api/app-config')):
        levels = set(perms.values())
        if writing and 'edit' not in levels:
            return '此帳號沒有編輯權限'
        if not writing and not levels.intersection({'view', 'edit'}):
            return '此帳號不可查看該範圍'
        return None
    area = area_for_path(path)
    if not area:
        return None
    level = perms.get(area, 'none')
    if writing:
        if level != 'edit':
            return '此帳號對該範圍沒有編輯權限'
        return None
    if level == 'none':
        return '此帳號不可查看該範圍'
    return None
