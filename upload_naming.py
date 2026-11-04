"""uploads/ 實體檔：功能子目錄 + 項目子目錄 + 可讀檔名（原檔名 + 日期）。"""
import os
import re
import uuid
from datetime import datetime

_FORBIDDEN = re.compile(r'[\\/:*?"<>|\x00-\x1f]')
_LEGACY_HEX_PDF = re.compile(r'^[a-f0-9]{32}\.pdf$', re.I)
_GENERAL_BUCKET = '_general'

# 會寫入 uploads 的功能（路徑第一層目錄 id → 說明）
UPLOAD_CATEGORIES = {
    'iso': {
        'label': 'ISO 文件',
        'feature': 'ISO 文件登記 · 上傳附件',
        'path': 'iso/{項目}/',
    },
    'ocr': {
        'label': 'OCR／掃描',
        'feature': 'OCR 頁、付款登記掃描發票／報價',
        'path': 'ocr/{項目}/',
    },
    'quotations': {
        'label': '分判報價 PDF',
        'feature': '合同項目 · 上傳報價 PDF',
        'path': 'quotations/{項目}/',
    },
    'main-fac': {
        'label': '主包 FAC 附件',
        'feature': '主包 FAC · 結算表／證書上傳',
        'path': 'main-fac/{項目}/',
    },
    'sc-vo': {
        'label': '分判 VO 附件',
        'feature': '批核／報價／扣款／工程指令附件',
        'path': 'sc-vo/{項目}/',
    },
    'ip': {
        'label': '糧期附件',
        'feature': '糧期狀況 · 支票／IP Application／Cert',
        'path': 'ip/{項目}/',
    },
    'imports': {
        'label': 'Excel 匯入暫存',
        'feature': 'Master List、地盤付款表、NN1、Portfolio 等匯入',
        'path': 'imports/_general/',
    },
    'misc': {
        'label': '其他上傳',
        'feature': '通用 /api/files/upload',
        'path': 'misc/_general/',
    },
    'legacy-root': {
        'label': '舊版根目錄',
        'feature': '20261104 前 uuid 檔（OCR 等），DB 仍可能引用',
        'path': 'uploads/*.pdf（根目錄）',
    },
}

# 僅記憶體生成、不寫 uploads（供維運對照）
GENERATED_EXPORTS = [
    {'id': 'boss-pdf', 'label': 'QS 匯報表 PDF', 'feature': '報告 · 預覽／下載'},
    {'id': 'boss-docx', 'label': 'QS 匯報 Word', 'feature': '報告 · 下載'},
    {'id': 'signoff', 'label': '會簽表 PDF/DOCX', 'feature': '工程部 · 會簽出表'},
    {'id': 'main-fac-pdf', 'label': '主包 FAC PDF', 'feature': '主包 FAC · 預覽／下載（非上傳附件）'},
    {'id': 'sc-fac-pdf', 'label': '分判 FAC PDF/DOCX', 'feature': '分判 FAC · 預覽／下載'},
    {'id': 'interim-cert', 'label': '中期糧款計算書', 'feature': '付款 · 打印／匯出 PDF/Excel/Word'},
    {'id': 'portfolio-xlsx', 'label': 'N 項目／進行中匯出', 'feature': 'Portfolio · 直接下載 xlsx'},
    {'id': 'master-xlsx', 'label': 'Master List 匯出', 'feature': 'Master List · 直接下載'},
]


def sanitize_original_basename(original_filename):
    """只取檔名、去掉路徑與 Windows 非法字元；保留中文與空格。"""
    name = (original_filename or 'file').strip().replace('\\', '/')
    name = name.split('/')[-1].strip()
    name = _FORBIDDEN.sub('_', name)
    return name or 'file'


def upload_slug(*parts, max_len=72):
    """路徑用短標籤（項目編號、IP 期次等）。"""
    bits = []
    for part in parts:
        if part is None:
            continue
        s = str(part).strip()
        if not s:
            continue
        s = s.replace('/', '_').replace('\\', '_')
        s = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', '_', s)
        s = re.sub(r'_+', '_', s).strip('_')
        if s:
            bits.append(s[:36])
    joined = '_'.join(bits)
    return (joined[:max_len] or None)


def _normalize_category(category):
    category = (category or 'misc').strip().lower().replace(' ', '-')
    return re.sub(r'[^a-z0-9_-]+', '', category) or 'misc'


def _stem_ext(safe_name):
    if '.' in safe_name:
        stem, ext = safe_name.rsplit('.', 1)
        ext = re.sub(r'[^\w.+-]', '', ext.lower())[:16] or 'pdf'
    else:
        stem, ext = safe_name, 'pdf'
    stem = stem.strip()[:120] or 'file'
    return stem, ext


def allocate_dated_basename(original_filename, dest_dir=None, slug=None, when=None):
    """
    {slug_}{原檔主檔名}_{YYYYMMDD}.{ext}；同目錄碰撞加 _8位hex。
    回傳檔名（不含路徑）。
    """
    when = when or datetime.now()
    date_tag = when.strftime('%Y%m%d')
    stem, ext = _stem_ext(sanitize_original_basename(original_filename))
    slug_s = upload_slug(slug) if slug else None
    prefix = f'{slug_s}_' if slug_s else ''
    name = f'{prefix}{stem}_{date_tag}.{ext}'
    if not dest_dir:
        return name
    full = os.path.join(dest_dir, name)
    if not os.path.isfile(full):
        return name
    uid = uuid.uuid4().hex[:8]
    return f'{prefix}{stem}_{date_tag}_{uid}.{ext}'


def upload_rel_path(
    category,
    original_filename,
    base_dir,
    project_code=None,
    detail_slug=None,
    when=None,
):
    """
    路徑：{category}/{項目或_general}/{檔名}。
    project_code：MS_Q1161_25_jc 等；無項目時用 _general。
    detail_slug：寫入檔名前綴（如 statement、IP3_receipt）。
    """
    category = _normalize_category(category)
    bucket = upload_slug(project_code) if project_code else _GENERAL_BUCKET
    dir_path = os.path.join(base_dir, category, bucket)
    os.makedirs(dir_path, exist_ok=True)
    basename = allocate_dated_basename(
        original_filename,
        dest_dir=dir_path,
        slug=detail_slug,
        when=when,
    )
    return f'{category}/{bucket}/{basename}'


def classify_upload_relpath(rel_path):
    """依相對路徑推斷功能分類 id（含 legacy-root）。"""
    rel = (rel_path or '').replace('\\', '/').strip().lstrip('/')
    if not rel:
        return 'misc'
    if '..' in rel.split('/'):
        return 'misc'
    parts = [p for p in rel.split('/') if p]
    if len(parts) == 1 and _LEGACY_HEX_PDF.match(parts[0]):
        return 'legacy-root'
    if parts[0] in UPLOAD_CATEGORIES and parts[0] != 'legacy-root':
        return parts[0]
    if parts[0] == 'iso':
        return 'iso'
    return 'misc'


def upload_storage_summary(base_dir):
    """各分類檔案數與容量（遞迴 uploads）。"""
    totals = {k: {'files': 0, 'bytes': 0} for k in UPLOAD_CATEGORIES}
    if not os.path.isdir(base_dir):
        return _summary_rows(totals)
    for root, _dirs, files in os.walk(base_dir):
        for name in files:
            if name.startswith('_restore') and name.endswith('.zip'):
                continue
            full = os.path.join(root, name)
            if not os.path.isfile(full):
                continue
            try:
                size = os.path.getsize(full)
            except OSError:
                size = 0
            rel = os.path.relpath(full, base_dir).replace('\\', '/')
            cat = classify_upload_relpath(rel)
            if cat not in totals:
                cat = 'misc'
            totals[cat]['files'] += 1
            totals[cat]['bytes'] += size
    return _summary_rows(totals)


def _summary_rows(totals):
    rows = []
    for cat_id, meta in UPLOAD_CATEGORIES.items():
        t = totals.get(cat_id) or {'files': 0, 'bytes': 0}
        rows.append({
            'id': cat_id,
            'label': meta['label'],
            'feature': meta['feature'],
            'path_hint': meta['path'],
            'files': t['files'],
            'bytes': t['bytes'],
        })
    return rows
