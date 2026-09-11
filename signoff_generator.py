"""
signoff_generator.py — 投標合約會簽表 Word / PDF 輸出

以 Ref/投標合約會簽表Template.docx 為準：保留底線 run、審批 tick、頁首 LOGO。
"""
from __future__ import annotations

import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from copy import deepcopy
from datetime import datetime
from io import BytesIO

from docx import Document
from docx.enum.text import WD_UNDERLINE
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.text.run import Run

from qs_report_pdf import FONT, _esc, ensure_pdf_font, ensure_pdf_font_bold

REF_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Ref')
ASSETS_SIGNOFF_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets', 'signoff')
# 部署用 ASCII 檔名；本機 Ref 仍可用中文 Template 檔
DEPLOY_TEMPLATE_FILENAME = 'signoff_template.docx'
LEGACY_TEMPLATE_FILENAME = '投標合約會簽表Template.docx'
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Linux LibreOffice：Template 內 MS 字型名 → 容器已裝 metric-compatible 字型
_LINUX_FONT_MAP = {
    '新細明體': 'AR PL UMing TW',
    '新宋体': 'AR PL UMing CN',
    'SimSun': 'AR PL UMing CN',
    '宋体': 'AR PL UMing CN',
    '標楷體': 'AR PL UKai TW',
    '标楷体': 'AR PL UKai TW',
    'DFKai-SB': 'AR PL UKai TW',
    'Arial': 'Carlito',
    'Calibri': 'Carlito',
    'Times New Roman': 'Caladea',
}
_LO_PDF_FILTER = (
    'pdf:writer_pdf_Export:'
    '{"SelectPdfVersion":{"type":"long","value":"1"},'
    '"UseLosslessCompression":{"type":"boolean","value":"true"},'
    '"ExportFormFields":{"type":"boolean","value":"false"}}'
)

# Template 頁首 LOGO 尺寸（EMU，取自 Template.docx header）
TEMPLATE_LOGO_CX = 8194261
TEMPLATE_LOGO_CY = 850197

COMPANY_NAME = '美博工程服務有限公司'
DEPT_NAME = '美博'
# Wingdings sym 經 Word→PDF 在本機常顯示反了；改 Unicode 方格，Word/PDF 一致
CHECKBOX_CHECKED = '\u2611'
CHECKBOX_UNCHECKED = '\u2610'
CONTRACT_DATE_WIDTHS = (6, 5, 5)
_DATE_SLOT_RE = re.compile(r'(_+)年(_+)月(_+)')
OTHER_SPACER = '  '
BODY_FONT_HALF_PT = '24'  # 12pt（Word w:sz 半點值；Template 大部份為 24，日期欄曾混 22=11pt）
BID_FONT_HALF_PT = '22'  # 11pt — 截標日期及時間欄（Template 原字級）
CONTRACT_PERIOD_FONT_HALF_PT = '22'  # 11pt — 合約年期／上次合約年期日期區
FORM_FONT_MAX_ROW = 15
_FORM_FONT_SKIP = {(6, 2)}  # 截標日期及時間：保留 11pt
_CONTRACT_PERIOD_ROWS = (9, 10)


def _ensure_body_font(run, *, half_pt: str = BODY_FONT_HALF_PT) -> None:
    """統一表單字級 12pt，避免 11pt 底線看起來較幼。"""
    rpr = run._element.find(qn('w:rPr'))
    if rpr is None:
        rpr = OxmlElement('w:rPr')
        run._element.insert(0, rpr)
    for tag in ('w:sz', 'w:szCs'):
        el = rpr.find(qn(tag))
        if el is None:
            el = OxmlElement(tag)
            rpr.append(el)
        el.set(qn('w:val'), half_pt)


def _normalize_form_font_size(table, *, max_row: int = FORM_FONT_MAX_ROW) -> None:
    """部份一＋簽署列：全部 run 改 12pt（保留頁尾註解原字級）。"""
    for ri in range(min(max_row + 1, len(table.rows))):
        for ci, cell in enumerate(table.rows[ri].cells):
            if (ri, ci) in _FORM_FONT_SKIP:
                continue
            for p in cell.paragraphs:
                for r in p.runs:
                    _ensure_body_font(r)


def _ensure_cell_font_size(cell, *, half_pt: str) -> None:
    for p in cell.paragraphs:
        for r in p.runs:
            _ensure_body_font(r, half_pt=half_pt)


def _apply_contract_period_paragraph_fonts(paragraph) -> None:
    """合約年期：日期區 11pt；「至」及 (共 X 月) 維持 12pt。"""
    runs = list(paragraph.runs)
    gong_idx = next((i for i, r in enumerate(runs) if '共' in r.text), None)
    if gong_idx is None:
        for r in runs:
            half_pt = BODY_FONT_HALF_PT if '至' in r.text else CONTRACT_PERIOD_FONT_HALF_PT
            _ensure_body_font(r, half_pt=half_pt)
        return
    for r in runs[:gong_idx]:
        _ensure_body_font(r, half_pt=CONTRACT_PERIOD_FONT_HALF_PT)
    for r in runs[gong_idx:]:
        _ensure_body_font(r, half_pt=BODY_FONT_HALF_PT)


def _apply_contract_period_row_fonts(table) -> None:
    for ri in _CONTRACT_PERIOD_ROWS:
        if ri >= len(table.rows):
            continue
        for ci in (2, 3):
            if ci >= len(table.rows[ri].cells):
                continue
            for p in table.rows[ri].cells[ci].paragraphs:
                _apply_contract_period_paragraph_fonts(p)


def _insert_run_after(ref_run, text: str):
    new_r = OxmlElement('w:r')
    rpr = OxmlElement('w:rPr')
    rfonts = OxmlElement('w:rFonts')
    rfonts.set(qn('w:ascii'), '標楷體')
    rfonts.set(qn('w:eastAsia'), '標楷體')
    rfonts.set(qn('w:hAnsi'), '標楷體')
    rpr.append(rfonts)
    sz = OxmlElement('w:sz')
    sz.set(qn('w:val'), BODY_FONT_HALF_PT)
    rpr.append(sz)
    sz_cs = OxmlElement('w:szCs')
    sz_cs.set(qn('w:val'), BODY_FONT_HALF_PT)
    rpr.append(sz_cs)
    new_r.append(rpr)
    t = OxmlElement('w:t')
    t.set(qn('xml:space'), 'preserve')
    t.text = text
    new_r.append(t)
    ref_run._element.addnext(new_r)
    return Run(new_r, ref_run._parent)


def _other_field_runs(paragraph):
    """「其他」後的底線欄 runs（Template 現用 font underline 空格，非 literal _）。"""
    runs = list(paragraph.runs)
    other_idx = next((i for i, r in enumerate(runs) if r.text.strip() == '其他'), None)
    if other_idx is None:
        return None, [], None
    other_run = runs[other_idx]
    spacer_run = None
    field_runs = []
    for r in runs[other_idx + 1:]:
        if r.text == OTHER_SPACER:
            spacer_run = r
            continue
        if r.font.underline:
            field_runs.append(r)
        elif field_runs:
            break
        elif r.text.strip() and not r.text.isspace():
            break
    return other_run, field_runs, spacer_run


def _fill_other_underscores(paragraph, text: str) -> None:
    """「其他」後：兩空格 + 底線欄（font underline，與 Template 一致）。"""
    other_run, field_runs, spacer_run = _other_field_runs(paragraph)
    if other_run is None or not field_runs:
        return

    content = (text or '').strip()
    if not content:
        if spacer_run is not None:
            spacer_run._element.getparent().remove(spacer_run._element)
        for r in field_runs:
            r.text = ' ' * len(r.text) if r.text else r.text
            _ensure_underline_single(r)
        return

    if spacer_run is None:
        _insert_run_after(other_run, OTHER_SPACER)

    widths = [len(r.text) for r in field_runs]
    total = sum(widths)
    padded = content.ljust(total)[:total]
    pos = 0
    for i, r in enumerate(field_runs):
        width = widths[i]
        r.text = padded[pos:pos + width]
        _ensure_underline_single(r)
        pos += width


def get_signoff_template_path():
    """優先 assets/signoff（隨 Git 部署）；其次 Ref/ 本機參考。"""
    deploy = os.path.join(ASSETS_SIGNOFF_DIR, DEPLOY_TEMPLATE_FILENAME)
    if os.path.isfile(deploy):
        return deploy
    legacy = os.path.join(REF_DIR, LEGACY_TEMPLATE_FILENAME)
    if os.path.isfile(legacy):
        return legacy
    if os.path.isdir(REF_DIR):
        for name in os.listdir(REF_DIR):
            if name.endswith('Template.docx'):
                return os.path.join(REF_DIR, name)
    if os.path.isdir(ASSETS_SIGNOFF_DIR):
        for name in os.listdir(ASSETS_SIGNOFF_DIR):
            if name.endswith('.docx'):
                return os.path.join(ASSETS_SIGNOFF_DIR, name)
    return None


def _logo_path():
    for name in ('mepork_logo.png', 'mepork_logo_w.jpeg', 'MeporkLogo.png'):
        p = os.path.join(BASE_DIR, 'assets', name)
        if os.path.isfile(p):
            return p
    return None


def _money_digits(val) -> str:
    if val in (None, ''):
        return ''
    try:
        n = float(val)
    except (TypeError, ValueError):
        return ''
    return f'{n:,.2f}'


def _parse_date(iso):
    if not iso:
        return None
    try:
        return datetime.strptime(str(iso)[:10], '%Y-%m-%d')
    except ValueError:
        return None


def _runs(cell):
    for p in cell.paragraphs:
        for r in p.runs:
            yield r


def _underlined_runs(cell):
    return [r for r in _runs(cell) if r.font.underline]


def _center_in(width: int, value, char: str = '_') -> str:
    s = str(value) if value not in (None, '') else ''
    if len(s) > width:
        return s[:width]
    pad = width - len(s)
    left = pad // 2
    right = pad - left
    return char * left + s + char * right


def _ensure_underline_single(run) -> None:
    """底線粗度與 Template 一致（w:u val=single）。"""
    run.font.underline = WD_UNDERLINE.SINGLE
    rpr = run._element.find(qn('w:rPr'))
    if rpr is None:
        rpr = OxmlElement('w:rPr')
        run._element.insert(0, rpr)
    u = rpr.find(qn('w:u'))
    if u is None:
        u = OxmlElement('w:u')
        rpr.append(u)
    u.set(qn('w:val'), 'single')
    _ensure_body_font(run)


def _distribute_to_runs(runs, text: str, *, align: str = 'center') -> None:
    """把 text 填入底線 run，保留各 run 長度與底線格式（預設置中）。"""
    if not runs:
        return
    total = sum(len(r.text) for r in runs)
    text = text or ''
    if len(text) >= total:
        padded = text[:total]
    elif align == 'center':
        pad = total - len(text)
        left = pad // 2
        right = pad - left
        padded = (' ' * left) + text + (' ' * right)
    else:
        padded = text.ljust(total)[:total]
    pos = 0
    for r in runs:
        n = len(r.text)
        r.text = padded[pos:pos + n]
        pos += n
        _ensure_underline_single(r)


def _fill_underlined_left_full(cell, value: str) -> None:
    """底線填滿整格（文字靠左，右側空白保留底線）— 項目名稱等。"""
    runs = _underlined_runs(cell)
    if not runs:
        return
    _distribute_to_runs(runs, value or '', align='left')


def _fill_underlined_truncated(runs, text: str) -> None:
    """底線只覆蓋文字長度（項目名稱等），其餘不畫底線。"""
    text = text or ''
    pos = 0
    for r in runs:
        if pos >= len(text):
            r.text = ''
            r.font.underline = False
            continue
        n = len(r.text)
        take = min(n, len(text) - pos)
        r.text = text[pos:pos + take]
        pos += take


def _fill_underlined_cell(cell, value: str, *, truncate: bool = False, align: str = 'center') -> None:
    runs = _underlined_runs(cell)
    if runs:
        if truncate:
            _fill_underlined_truncated(runs, value or '')
        else:
            _distribute_to_runs(runs, value or '', align=align)
        return
    if not (value or '').strip():
        return


def _fill_text_cell(cell, value: str, *, align: str = 'left') -> None:
    """有底線 run 則沿用；否則直接填文字（新版 Template 附件欄可能為空 cell）。"""
    if not (value or '').strip():
        return
    runs = _underlined_runs(cell)
    if runs:
        _distribute_to_runs(runs, value, align=align)
        return
    if not cell.paragraphs:
        cell.add_paragraph()
    p = cell.paragraphs[0]
    if p.runs:
        p.runs[0].text = value
        for r in p.runs[1:]:
            r.text = ''
        _ensure_body_font(p.runs[0])
    else:
        _ensure_body_font(p.add_run(value))


def _fill_date_cell(cell, iso_date) -> None:
    """依 年/月/日 標籤，把日期填到底線空格（無日期則保留 template）。"""
    d = _parse_date(iso_date)
    if not d:
        return
    parts = {'年': str(d.year), '月': f'{d.month:02d}', '日': f'{d.day:02d}'}
    for p in cell.paragraphs:
        runs = list(p.runs)
        for i, r in enumerate(runs):
            prefix = ''.join(runs[k].text for k in range(i))
            for label, val in parts.items():
                if label not in r.text:
                    continue
                if label == '月' and '(共' in prefix:
                    continue
                ul = []
                j = i - 1
                while j >= 0 and runs[j].font.underline:
                    ul.insert(0, runs[j])
                    j -= 1
                _distribute_to_runs(ul, val)
                break


def _ensure_strike_single(run) -> None:
    """刪除線（w:strike）— 上/下午選項標示。"""
    rpr = run._element.find(qn('w:rPr'))
    if rpr is None:
        rpr = OxmlElement('w:rPr')
        run._element.insert(0, rpr)
    strike = rpr.find(qn('w:strike'))
    if strike is None:
        strike = OxmlElement('w:strike')
        rpr.append(strike)
    strike.set(qn('w:val'), 'true')
    u = rpr.find(qn('w:u'))
    if u is not None:
        rpr.remove(u)
    run.font.underline = False


def _apply_strike_ranges(paragraph, ranges: list[tuple[int, int]]) -> None:
    """對字元區間加刪除線（必要時 split run）。"""
    if not ranges:
        return
    ranges = sorted(ranges)
    for _ in range(32):
        changed = False
        pos = 0
        for run in list(paragraph.runs):
            run_start = pos
            run_end = pos + len(run.text)
            for start, end in ranges:
                if run_end <= start or run_start >= end:
                    continue
                if run_start < start < run_end:
                    _split_run(run, start - run_start)
                    changed = True
                    break
                if run_start < end < run_end:
                    _split_run(run, end - run_start)
                    changed = True
                    break
                if start <= run_start and run_end <= end:
                    _ensure_strike_single(run)
            if changed:
                break
            pos = run_end
        if not changed:
            break


def _fill_bid_meridiem_mark(paragraph, meridiem: str) -> None:
    """上午：「下」刪除線；下午：「上」刪除線；未選則不標。"""
    if meridiem not in ('am', 'pm'):
        return
    text = paragraph.text
    idx_up = text.find('上')
    idx_lo = text.find('下', idx_up if idx_up >= 0 else 0)
    if idx_up < 0 or idx_lo < 0:
        return
    if meridiem == 'pm':
        _apply_strike_ranges(paragraph, [(idx_up, idx_up + 1)])
    else:
        _apply_strike_ranges(paragraph, [(idx_lo, idx_lo + 1)])


def _normalize_bid_time(ampm: str) -> str:
    """Parse HH:MM for 12-hour bid time slot."""
    m = re.match(r'(\d{1,2})\s*:\s*(\d{2})', (ampm or '').strip())
    if not m:
        return ''
    h, mi = int(m.group(1)), int(m.group(2))
    if h < 1 or h > 12 or mi < 0 or mi > 59:
        return ''
    return f'{h:02d}:{mi:02d}'


def _fill_bid_time_underlined(paragraph, ampm: str) -> None:
    """(上/下午__:__) — 時間填 font underline run，保留底線格式。"""
    time_str = _normalize_bid_time(ampm)
    if not time_str:
        return
    runs = list(paragraph.runs)
    amp_idx = next((i for i, r in enumerate(runs) if '上/下午' in r.text), None)
    if amp_idx is None:
        return
    slot_start = amp_idx + 1
    paren_idx = None
    for i in range(slot_start, len(runs)):
        if ')' in runs[i].text:
            paren_idx = i
            break
    if paren_idx is None:
        return
    slot_runs = runs[slot_start:paren_idx + 1]
    if not slot_runs:
        return
    amp_run = runs[amp_idx]
    parent_el = amp_run._element.getparent()
    for r in slot_runs:
        parent_el.remove(r._element)
    ref = amp_run
    for ch in time_str:
        nr = _insert_run_after(ref, ch)
        _ensure_underline_single(nr)
        _ensure_body_font(nr, half_pt=BID_FONT_HALF_PT)
        ref = nr
    _insert_run_after(ref, ')')


def _fill_bid_ampm_paragraph(paragraph, ampm: str) -> None:
    """Legacy wrapper — 改為 underline 填時間。"""
    _fill_bid_time_underlined(paragraph, ampm)


def _fill_bid_cell(cell, payload) -> None:
    """截標日期及時間：年月日 + (上/下午__:__)；不填則保留 template。"""
    d = _parse_date(payload.get('bid_deadline'))
    if d:
        _fill_date_cell(cell, payload.get('bid_deadline'))
    meridiem = (payload.get('bid_deadline_meridiem') or '').strip().lower()
    if meridiem not in ('am', 'pm'):
        _ensure_cell_font_size(cell, half_pt=BID_FONT_HALF_PT)
        return
    ampm = (payload.get('bid_deadline_ampm') or '').strip()
    for p in cell.paragraphs:
        if '上/下午' in p.text or ('上' in p.text and '午' in p.text):
            if ampm:
                _fill_bid_time_underlined(p, ampm)
            _fill_bid_meridiem_mark(p, meridiem)
            break
    _ensure_cell_font_size(cell, half_pt=BID_FONT_HALF_PT)


def _fill_amount_cell(cell, amount) -> None:
    digits = _money_digits(amount)
    if not digits:
        return
    ul = _underlined_runs(cell)
    if not ul:
        return
    if ul[0].text.strip() == '$':
        _distribute_to_runs(ul, '$' + digits, align='left')
    else:
        _distribute_to_runs(ul, digits, align='left')


def _fill_tender_no_cell(cell, quotation_no) -> None:
    q = (quotation_no or '').strip()
    if not q:
        return
    _fill_underlined_cell(cell, q, align='left')


def _normalize_months(months) -> str:
    if months in (None, ''):
        return ''
    if isinstance(months, (int, float)):
        n = float(months)
        if n <= 0:
            return ''
        if n == int(n):
            return str(int(n))
        return str(n).rstrip('0').rstrip('.')
    s = str(months).strip()
    if s.endswith('月'):
        s = s[:-1].strip()
    if 'month' in s.lower():
        s = s.split()[0]
    try:
        n = float(s.replace(',', ''))
        if n <= 0:
            return ''
        if n == int(n):
            return str(int(n))
        return str(n).rstrip('0').rstrip('.')
    except ValueError:
        return s


_MONTHS_SLOT_RE = re.compile(r'\(共(\s+)月\)')


def _month_slot_runs(paragraph):
    """「(共 ___ 月)」底線 runs 及「月」run（不碰日期區）。"""
    runs = list(paragraph.runs)
    slot_runs = []
    yue_run = None
    past_gong = False
    for r in runs:
        if '共' in r.text:
            past_gong = True
            continue
        if not past_gong:
            continue
        if yue_run is None and '月' in r.text:
            yue_run = r
            break
        if r.font.underline:
            slot_runs.append(r)
    return slot_runs, yue_run


def _fill_contract_months_in_paragraph(paragraph, months) -> None:
    """只填 (共 X 月) 底線槽，不改日期區字元位置。"""
    mv = _normalize_months(months)
    if not mv:
        return
    slot_runs, yue_run = _month_slot_runs(paragraph)
    if not slot_runs:
        return
    total = sum(len(r.text) for r in slot_runs)
    if len(mv) < total:
        content = _center_in(total, mv, ' ')
    else:
        content = mv[:total]
    _distribute_to_runs(slot_runs, content)


def _set_paragraph_text_preserve_runs(paragraph, new_text: str) -> None:
    """替換段落文字但保留各 run 的 rPr（字級／字型與 Template 一致）。"""
    runs = list(paragraph.runs)
    if not runs:
        if new_text:
            paragraph.add_run(new_text)
        return
    orig_len = sum(len(r.text) for r in runs)
    if orig_len <= 0:
        runs[0].text = new_text
        return
    if len(new_text) < orig_len:
        new_text = new_text.ljust(orig_len)
    else:
        new_text = new_text[:orig_len]
    pos = 0
    for r in runs:
        n = len(r.text)
        r.text = new_text[pos:pos + n]
        pos += n


def _clone_run_after(ref_run, text: str) -> Run:
    new_r = OxmlElement('w:r')
    rpr = ref_run._element.find(qn('w:rPr'))
    if rpr is not None:
        new_r.append(deepcopy(rpr))
    t = OxmlElement('w:t')
    if text.startswith(' ') or text.endswith(' '):
        t.set(qn('xml:space'), 'preserve')
    t.text = text
    new_r.append(t)
    ref_run._element.addnext(new_r)
    return Run(new_r, ref_run._parent)


def _split_run(run, char_index: int) -> Run:
    text = run.text
    if char_index <= 0 or char_index >= len(text):
        return run
    tail = text[char_index:]
    run.text = text[:char_index]
    return _clone_run_after(run, tail)


def _apply_underline_ranges(paragraph, ranges: list[tuple[int, int]]) -> None:
    """對字元區間加 font underline（必要時 split run，年/月/日標籤不加底線）。"""
    if not ranges:
        return
    ranges = sorted(ranges)
    for _ in range(32):
        changed = False
        pos = 0
        for run in list(paragraph.runs):
            run_start = pos
            run_end = pos + len(run.text)
            for start, end in ranges:
                if run_end <= start or run_start >= end:
                    continue
                if run_start < start < run_end:
                    _split_run(run, start - run_start)
                    changed = True
                    break
                if run_start < end < run_end:
                    _split_run(run, end - run_start)
                    changed = True
                    break
                if start <= run_start and run_end <= end:
                    _ensure_underline_single(run)
            if changed:
                break
            pos = run_end
        if not changed:
            break


def _fill_literal_date_paragraph(paragraph, iso_date) -> None:
    """在 Template 底線欄填入年月日（置中、數字底下 font underline、保留 run 字級）。"""
    d = _parse_date(iso_date)
    if not d:
        return
    text = paragraph.text
    m = _DATE_SLOT_RE.search(text)
    if not m:
        return
    year, month, day = str(d.year), f'{d.month:02d}', f'{d.day:02d}'
    y_slot, m_slot, d_slot = m.group(1), m.group(2), m.group(3)
    new_y = _center_in(len(y_slot), year, ' ')
    new_m = _center_in(len(m_slot), month, ' ')
    new_d = _center_in(len(d_slot), day, ' ')
    new_text = text[:m.start(1)] + new_y + '年' + new_m + '月' + new_d + text[m.end(3):]
    _set_paragraph_text_preserve_runs(paragraph, new_text)
    _apply_underline_ranges(paragraph, [
        (m.start(1), m.end(1)),
        (m.start(2), m.end(2)),
        (m.start(3), m.end(3)),
    ])


def _fill_contract_start_cell(cell, iso_date) -> None:
    if not _parse_date(iso_date):
        return
    for p in cell.paragraphs:
        if '年' in p.text and '至' in p.text:
            if _DATE_SLOT_RE.search(p.text):
                _fill_literal_date_paragraph(p, iso_date)
            else:
                _fill_date_cell(cell, iso_date)
            return


def _fill_contract_end_cell(cell, iso_date, months) -> None:
    has_date = bool(_parse_date(iso_date))
    for p in cell.paragraphs:
        if '年' not in p.text or '(共' not in p.text:
            continue
        if has_date:
            if _DATE_SLOT_RE.search(p.text):
                _fill_literal_date_paragraph(p, iso_date)
            else:
                _fill_date_cell(cell, iso_date)
        if months not in (None, ''):
            _fill_contract_months_in_paragraph(p, months)
        return


def _set_checkbox_run(run, checked: bool) -> None:
    """審批方格：Unicode ☑/☐（Wingdings w:sym 在本機 Word→PDF 會勾選反了）。"""
    run.text = ''
    for child in list(run._element):
        if child.tag != qn('w:rPr'):
            run._element.remove(child)
    rpr = run._element.find(qn('w:rPr'))
    if rpr is None:
        rpr = OxmlElement('w:rPr')
        run._element.insert(0, rpr)
    rfonts = rpr.find(qn('w:rFonts'))
    if rfonts is None:
        rfonts = OxmlElement('w:rFonts')
        rpr.insert(0, rfonts)
    rfonts.set(qn('w:ascii'), '標楷體')
    rfonts.set(qn('w:eastAsia'), '標楷體')
    rfonts.set(qn('w:hAnsi'), '標楷體')
    rfonts.set(qn('w:cs'), 'Arial')
    bold = rpr.find(qn('w:b'))
    if bold is not None:
        rpr.remove(bold)
    run.text = CHECKBOX_CHECKED if checked else CHECKBOX_UNCHECKED
    _ensure_body_font(run)


def _set_approval_category(table, category: str, other_text: str = '') -> None:
    target = (category or '合約').strip()
    if target not in ('合約', '投標意向書', '其他'):
        target = '合約'
    options = ('合約', '投標意向書', '其他')
    cell = table.rows[1].cells[2]
    for p in cell.paragraphs:
        runs = list(p.runs)
        for i, r in enumerate(runs):
            opt = r.text.strip()
            if opt not in options:
                continue
            tick_run = runs[i - 1] if i > 0 else None
            if tick_run is None:
                continue
            if opt == target:
                _set_checkbox_run(tick_run, True)
            else:
                _set_checkbox_run(tick_run, False)
        _fill_other_underscores(p, other_text if target == '其他' else '')


def _header_logo_bytes() -> bytes | None:
    for name in ('mepork_logo_w.jpeg', 'mepork_logo.png', 'MeporkLogo.png'):
        p = os.path.join(BASE_DIR, 'assets', name)
        if os.path.isfile(p):
            with open(p, 'rb') as f:
                return f.read()
    return None


_HEADER_LOGO_OFFSET_RE = re.compile(
    r'(<wp:positionH relativeFrom="column"><wp:posOffset>)\d+(</wp:posOffset>)'
)


def _patch_header_logo_xml(xml: str) -> str:
    """替換 LOGO 後把 anchor 移左；標題段落維持原右對齊。"""
    return _HEADER_LOGO_OFFSET_RE.sub(r'\g<1>0\2', xml, count=1)


def _patch_docx_header_logo(docx_bytes: bytes) -> bytes:
    logo_data = _header_logo_bytes()
    if not logo_data:
        return docx_bytes
    in_buf = BytesIO(docx_bytes)
    out_buf = BytesIO()
    with zipfile.ZipFile(in_buf, 'r') as zin:
        with zipfile.ZipFile(out_buf, 'w', zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename == 'word/media/image1.jpeg':
                    data = logo_data
                elif item.filename == 'word/header1.xml':
                    data = _patch_header_logo_xml(data.decode('utf-8')).encode('utf-8')
                zout.writestr(item, data)
    return out_buf.getvalue()


def _attachments_text(payload):
    parts = []
    if payload.get('subcon_name'):
        parts.append(f'分判商：{payload["subcon_name"]}')
    if payload.get('subcon_quotation'):
        parts.append(f'分判報價：{payload["subcon_quotation"]}')
    if payload.get('remark'):
        parts.append(payload['remark'])
    if payload.get('attachments'):
        parts.append(payload['attachments'])
    return '\n'.join(parts).strip()


def fill_signoff_template(doc: Document, payload: dict) -> None:
    if not doc.tables:
        return
    t = doc.tables[0]

    _set_approval_category(
        t,
        payload.get('approval_category') or '合約',
        payload.get('approval_other') or '',
    )

    _fill_underlined_cell(t.rows[4].cells[2], (payload.get('quotation_no') or '').strip(), align='left')
    _fill_date_cell(t.rows[4].cells[3], payload.get('submit_date'))

    _fill_underlined_left_full(t.rows[5].cells[2], (payload.get('project_name') or '').strip())

    _fill_bid_cell(t.rows[6].cells[2], payload)
    _fill_date_cell(t.rows[6].cells[3], payload.get('tender_date'))

    _fill_underlined_cell(t.rows[7].cells[2], (payload.get('client_name') or '').strip(), align='left')
    _fill_tender_no_cell(t.rows[7].cells[3], payload.get('quotation_no'))

    _fill_amount_cell(t.rows[8].cells[2], payload.get('amount'))

    _fill_contract_start_cell(t.rows[9].cells[2], payload.get('contract_start_date'))
    _fill_contract_end_cell(
        t.rows[9].cells[3],
        payload.get('contract_end_date'),
        payload.get('contract_months') or payload.get('expected_period'),
    )

    att = _attachments_text(payload)
    if att:
        _fill_text_cell(t.rows[12].cells[2], att)

    if payload.get('submit_date'):
        sig = _parse_date(payload['submit_date'])
        if sig:
            sig_text = f'日期： {sig.year} 年  {sig.month:02d} 月 {sig.day:02d} 日'
            for ri in (13, 14, 15):
                if ri >= len(t.rows):
                    break
                row = t.rows[ri]
                for ci in range(2, len(row.cells)):
                    cell = row.cells[ci]
                    if cell.text.strip().startswith('日期'):
                        for p in cell.paragraphs:
                            if p.runs:
                                p.runs[0].text = sig_text
                                for r in p.runs[1:]:
                                    r.text = ''

    _normalize_form_font_size(t)
    _apply_contract_period_row_fonts(t)

def generate_signoff_docx(payload, template_path=None):
    template_path = template_path or get_signoff_template_path()
    if not template_path or not os.path.isfile(template_path):
        return _generate_signoff_docx_blank(payload)

    with tempfile.TemporaryDirectory() as tmp:
        out_path = os.path.join(tmp, 'out.docx')
        shutil.copy2(template_path, out_path)
        doc = Document(out_path)
        fill_signoff_template(doc, payload)
        doc.save(out_path)
        with open(out_path, 'rb') as f:
            return _patch_docx_header_logo(f.read())


def _generate_signoff_docx_blank(payload):
    doc = Document()
    doc.add_heading('投標合約會簽表', level=1)
    lines = [
        ('項目編號', payload.get('quotation_no')),
        ('項目名稱', payload.get('project_name')),
        ('供方名稱', payload.get('client_name')),
        ('合約總價', _money_digits(payload.get('amount'))),
    ]
    tbl = doc.add_table(rows=len(lines), cols=2)
    for i, (k, v) in enumerate(lines):
        tbl.rows[i].cells[0].text = k
        tbl.rows[i].cells[1].text = str(v or '')
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _replace_fonts_in_xml(xml: str, mapping: dict[str, str]) -> str:
    for old, new in mapping.items():
        for attr in ('ascii', 'eastAsia', 'hAnsi', 'cs'):
            xml = xml.replace(f'w:{attr}="{old}"', f'w:{attr}="{new}"')
    return xml


def _ensure_tbl_layout_fixed(xml: str) -> str:
    """LibreOffice 對無 tblLayout 的表格常自動縮放，與 Word 版面不一致。"""
    if '<w:tblLayout' in xml:
        return xml

    def _inject(m: re.Match[str]) -> str:
        block = m.group(0)
        if 'w:tblLayout' in block:
            return block
        return block.replace('<w:tblPr>', '<w:tblPr><w:tblLayout w:type="fixed"/>', 1)

    return re.sub(r'<w:tblPr>.*?</w:tblPr>', _inject, xml, flags=re.DOTALL)


def _patch_docx_for_linux_pdf(docx_bytes: bytes) -> bytes:
    """Zeabur：字型對應 + 固定表格版面，使 LO 轉 PDF 接近本機 Word。"""
    if sys.platform == 'win32':
        return docx_bytes
    in_buf = BytesIO(docx_bytes)
    out_buf = BytesIO()
    with zipfile.ZipFile(in_buf, 'r') as zin:
        with zipfile.ZipFile(out_buf, 'w', zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename.startswith('word/') and item.filename.endswith('.xml'):
                    text = data.decode('utf-8')
                    text = _replace_fonts_in_xml(text, _LINUX_FONT_MAP)
                    if item.filename == 'word/document.xml':
                        text = _ensure_tbl_layout_fixed(text)
                    data = text.encode('utf-8')
                zout.writestr(item, data)
    return out_buf.getvalue()


def _docx_bytes_to_pdf_win(docx_bytes: bytes) -> bytes | None:
    if sys.platform != 'win32':
        return None
    try:
        import pythoncom
        import win32com.client
    except ImportError:
        return None

    pythoncom.CoInitialize()
    word = None
    try:
        with tempfile.TemporaryDirectory() as tmp:
            docx_path = os.path.abspath(os.path.join(tmp, 'signoff.docx'))
            pdf_path = os.path.abspath(os.path.join(tmp, 'signoff.pdf'))
            with open(docx_path, 'wb') as f:
                f.write(docx_bytes)
            # DispatchEx：避免附著已開 Word 實例導致 Open 代理異常
            word = win32com.client.DispatchEx('Word.Application')
            word.Visible = False
            word.DisplayAlerts = 0
            doc = word.Documents.Open(
                docx_path,
                ReadOnly=True,
                AddToRecentFiles=False,
            )
            # ExportAsFixedFormat 比 SaveAs2 穩定（部分環境 SaveAs2 會 AttributeError）
            doc.ExportAsFixedFormat(pdf_path, ExportFormat=17)
            doc.Close(False)
            with open(pdf_path, 'rb') as f:
                return f.read()
    except Exception:
        return None
    finally:
        if word is not None:
            try:
                word.Quit()
            except Exception:
                pass
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass


def _docx_bytes_to_pdf_libreoffice(docx_bytes: bytes) -> bytes | None:
    """Linux Docker（Zeabur）：LibreOffice headless 轉 PDF，版面接近本機 Word。"""
    docx_bytes = _patch_docx_for_linux_pdf(docx_bytes)
    for binary in ('libreoffice', 'soffice'):
        if not shutil.which(binary):
            continue
        try:
            with tempfile.TemporaryDirectory() as tmp:
                profile_dir = os.path.join(tmp, 'lo_profile')
                os.makedirs(profile_dir, exist_ok=True)
                docx_path = os.path.join(tmp, 'signoff.docx')
                with open(docx_path, 'wb') as f:
                    f.write(docx_bytes)
                env = os.environ.copy()
                env['HOME'] = tmp
                env.setdefault('LANG', 'zh_TW.UTF-8')
                env.setdefault('LC_ALL', 'zh_TW.UTF-8')
                env.setdefault('SAL_USE_VCLPLUGIN', 'svp')
                proc = subprocess.run(
                    [
                        binary,
                        f'-env:UserInstallation=file:///{profile_dir.replace(os.sep, "/")}',
                        '--headless', '--norestore', '--nologo', '--invisible',
                        '--convert-to', _LO_PDF_FILTER,
                        '--outdir', tmp, docx_path,
                    ],
                    capture_output=True,
                    timeout=120,
                    check=False,
                    env=env,
                )
                if proc.returncode != 0:
                    continue
                pdf_path = os.path.join(tmp, 'signoff.pdf')
                if os.path.isfile(pdf_path):
                    with open(pdf_path, 'rb') as f:
                        return f.read()
        except (OSError, subprocess.SubprocessError):
            continue
    return None


def generate_signoff_pdf(payload, template_path=None):
    docx_bytes = generate_signoff_docx(payload, template_path=template_path)
    pdf = _docx_bytes_to_pdf_win(docx_bytes)
    if pdf:
        return pdf
    pdf = _docx_bytes_to_pdf_libreoffice(docx_bytes)
    if pdf:
        return pdf
    return _generate_signoff_pdf_reportlab(payload)


def _generate_signoff_pdf_reportlab(payload):
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    ensure_pdf_font()
    font = FONT
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=16 * mm, bottomMargin=16 * mm)
    title_style = ParagraphStyle('t', fontName=font, fontSize=13, alignment=TA_CENTER, leading=16)
    label_style = ParagraphStyle('l', fontName=font, fontSize=9, alignment=TA_LEFT, leading=12)
    body_style = ParagraphStyle('b', fontName=font, fontSize=9, alignment=TA_LEFT, leading=12)
    rows = [
        ['審批類別', payload.get('approval_category') or '合約'],
        ['項目編號', payload.get('quotation_no') or '—'],
        ['項目名稱', payload.get('project_name') or '—'],
        ['供方名稱', payload.get('client_name') or '—'],
        ['合約總價', _money_digits(payload.get('amount')) or '—'],
    ]
    story = [Paragraph(_esc('投標合約會簽表'), title_style), Spacer(1, 6)]
    data = [[Paragraph(_esc(a), label_style), Paragraph(_esc(b), body_style)] for a, b in rows]
    tbl = Table(data, colWidths=[38 * mm, 132 * mm])
    tbl.setStyle(TableStyle([('GRID', (0, 0), (-1, -1), 0.5, colors.grey)]))
    story.append(tbl)
    doc.build(story)
    return buf.getvalue()
