"""uploads/ 實體檔命名：保留原檔名 + 日期 + 分類子目錄（避免根目錄一堆 uuid）。"""
import os
import re
import uuid
from datetime import datetime

_FORBIDDEN = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


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


def upload_rel_path(category, original_filename, base_dir, slug=None, when=None):
    """
    寫入 base_dir/{category}/… 並回傳相對 base_dir 之路徑（正斜線）。
    category 例：ocr、quotations、payments、main-fac、sc-vo、ip、imports、misc
    """
    category = (category or 'misc').strip().lower().replace(' ', '-')
    category = re.sub(r'[^a-z0-9_-]+', '', category) or 'misc'
    dir_path = os.path.join(base_dir, category)
    os.makedirs(dir_path, exist_ok=True)
    basename = allocate_dated_basename(
        original_filename, dest_dir=dir_path, slug=slug, when=when,
    )
    return f'{category}/{basename}'
