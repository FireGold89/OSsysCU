"""投標合約會簽表 PDF（ReportLab · 僅 SIGNOFF_PDF_ENGINE=reportlab 或緊急 fallback）

正式出表請用 Template.docx 填表 + Word/LibreOffice，對齊 Ref/投標合約會簽表Template.docx|.pdf。
"""
from __future__ import annotations

import os
import re
from datetime import datetime
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from config import BASE_DIR
from qs_report_pdf import _esc, ensure_pdf_font, ensure_pdf_font_bold

MARGIN = 16 * mm
PAGE_W, PAGE_H = A4
CONTENT_W = PAGE_W - 2 * MARGIN
LOGO_H = 11 * mm
LOGO_W_MAX = CONTENT_W * 0.42
LOGO_LIFT = 4 * mm

COL_W = [32 * mm, 32 * mm, (CONTENT_W - 64 * mm) * 0.55, (CONTENT_W - 64 * mm) * 0.45]

COMPANY_ZH = '美博工程服務有限公司'
DEPT_ZH = '美博'
CHECKBOX_CHECKED = '\u2611'
CHECKBOX_UNCHECKED = '\u2610'

FOOTNOTE = (
    '注：1、投標金額＜500萬美博公司審批；500萬≤投標金額＜1,000萬集團港澳公司分管領導簽批；'
    '投標金額≥1,000萬港澳公司招投标管理委员会審批。2、招標合約會簽表一式兩份。'
)


def _parse_date(iso):
    if not iso:
        return None
    try:
        return datetime.strptime(str(iso)[:10], '%Y-%m-%d')
    except ValueError:
        return None


def _money_digits(val) -> str:
    if val in (None, ''):
        return ''
    try:
        n = float(val)
    except (TypeError, ValueError):
        return ''
    return f'{n:,.2f}'


def _normalize_months(months) -> str:
    if months in (None, ''):
        return ''
    try:
        n = float(str(months).replace(',', '').replace('月', '').strip())
        if n <= 0:
            return ''
        if n == int(n):
            return str(int(n))
        return str(n).rstrip('0').rstrip('.')
    except (TypeError, ValueError):
        s = str(months).strip()
        return s


def _normalize_bid_time(ampm: str) -> str:
    m = re.match(r'(\d{1,2})\s*:\s*(\d{2})', (ampm or '').strip())
    if not m:
        return ''
    h, mi = int(m.group(1)), int(m.group(2))
    if h < 1 or h > 12 or mi < 0 or mi > 59:
        return ''
    return f'{h:02d}:{mi:02d}'


def _attachments_text(payload: dict) -> str:
    parts = []
    if payload.get('subcon_name'):
        parts.append(f'分判商：{payload["subcon_name"]}')
    if payload.get('subcon_quotation'):
        parts.append(f'分判報價：{payload["subcon_quotation"]}')
    if payload.get('remark'):
        parts.append(str(payload['remark']))
    if payload.get('attachments'):
        parts.append(str(payload['attachments']))
    return '\n'.join(parts).strip()


def _logo_path() -> str | None:
    for name in ('mepork_logo_w.jpeg', 'mepork_logo.png', 'MeporkLogo.png'):
        p = os.path.join(BASE_DIR, 'assets', name)
        if os.path.isfile(p):
            return p
    return None


def _draw_logo(canvas, doc):
    path = _logo_path()
    if not path:
        return
    try:
        from PIL import Image
        with Image.open(path) as im:
            iw, ih = im.size
        aspect = iw / ih if ih else 3
        draw_h = LOGO_H
        draw_w = min(LOGO_W_MAX, draw_h * aspect)
    except Exception:
        draw_w, draw_h = LOGO_W_MAX, LOGO_H
    canvas.saveState()
    y = PAGE_H - MARGIN - draw_h + LOGO_LIFT
    canvas.drawImage(
        path, MARGIN, y, width=draw_w, height=draw_h,
        preserveAspectRatio=True, anchor='sw', mask='auto',
    )
    canvas.restoreState()


def _styles(font: str, bold: str):
    return {
        'title': ParagraphStyle(
            'signoff_title', fontName=font, fontSize=14, leading=18, alignment=TA_CENTER,
        ),
        'section': ParagraphStyle(
            'signoff_sec', fontName=bold, fontSize=10, leading=13, alignment=TA_CENTER,
        ),
        'label': ParagraphStyle(
            'signoff_lbl', fontName=font, fontSize=9, leading=12, alignment=TA_LEFT,
        ),
        'body': ParagraphStyle(
            'signoff_body', fontName=font, fontSize=9, leading=12, alignment=TA_LEFT,
        ),
        'body_center': ParagraphStyle(
            'signoff_body_c', fontName=font, fontSize=9, leading=12, alignment=TA_CENTER,
        ),
        'small': ParagraphStyle(
            'signoff_small', fontName=font, fontSize=7, leading=9, alignment=TA_LEFT,
        ),
        'bid': ParagraphStyle(
            'signoff_bid', fontName=font, fontSize=8.5, leading=11, alignment=TA_LEFT,
        ),
    }


def _cell(text, styles, kind='body'):
    return Paragraph(_esc(text or ''), styles[kind])


def _cell_html(html, styles, kind='body'):
    return Paragraph(html, styles[kind])


def _underline_val(val: str, width: int = 28) -> str:
    s = (val or '').strip()
    if not s:
        return ' ' * min(width, 20)
    return f'<u>{_esc(s)}</u>'


def _ymd_html(iso, *, slot='      年    月    日') -> str:
    d = _parse_date(iso)
    if not d:
        return _esc(slot)
    y, m, day = d.year, f'{d.month:02d}', f'{d.day:02d}'
    return f'<u>{y:4d}</u> 年 <u>{m}</u> 月 <u>{day}</u> 日'


def _sig_date_html(iso) -> str:
    d = _parse_date(iso)
    if not d:
        return '日期： ________ 年 ____ 月 ____ 日'
    return f'日期： {d.year} 年  {d.month:02d} 月 {d.day:02d} 日'


def _approval_html(category: str, other: str, styles) -> str:
    target = (category or '合約').strip()
    if target not in ('合約', '投標意向書', '其他'):
        target = '合約'
    chunks = []
    for opt in ('合約', '投標意向書', '其他'):
        mark = CHECKBOX_CHECKED if opt == target else CHECKBOX_UNCHECKED
        chunks.append(f'{mark}{_esc(opt)}')
    line = '        '.join(chunks)
    if target == '其他' and (other or '').strip():
        line += f'  {_underline_val(other.strip(), 12)}'
    return line


def _bid_datetime_html(payload) -> str:
    date_part = _ymd_html(payload.get('bid_deadline'))
    mer = (payload.get('bid_deadline_meridiem') or '').strip().lower()
    time_str = _normalize_bid_time(payload.get('bid_deadline_ampm') or '')
    up = '上'
    lo = '下'
    if mer == 'pm':
        up = f'<strike>{up}</strike>'
    elif mer == 'am':
        lo = f'<strike>{lo}</strike>'
    time_slot = f'<u>{_esc(time_str)}</u>' if time_str else '__:__'
    return f'{date_part}({up}/{lo}午{time_slot})'


def _contract_end_html(iso_end, months) -> str:
    date_part = _ymd_html(iso_end, slot='       年    月    日')
    mv = _normalize_months(months)
    month_slot = f'<u>{_esc(mv)}</u>' if mv else '     '
    return f'{date_part} (共 {month_slot} 月)'


def _amount_html(amount) -> str:
    digits = _money_digits(amount)
    if not digits:
        return '* (HKD)$ ' + ('_' * 18)
    return f'* (HKD)$ {_underline_val(digits, len(digits))}'


def _build_table(payload: dict, styles) -> Table:
    cat = payload.get('approval_category') or '合約'
    other = payload.get('approval_other') or ''
    qno = (payload.get('quotation_no') or '').strip()
    proj = (payload.get('project_name') or '').strip()
    client = (payload.get('client_name') or '').strip()
    att = _attachments_text(payload)
    sig_iso = payload.get('submit_date')
    months = payload.get('contract_months') or payload.get('expected_period')

    def lbl(text):
        return _cell(text, styles, 'label')

    def body(text, center=False):
        return _cell(text, styles, 'body_center' if center else 'body')

    data = [
        [_cell('部份一 (申請人須填寫下列所有資料)', styles, 'section')] * 4,
        [lbl('審批類別'), lbl(''), _cell_html(_approval_html(cat, other, styles), styles), _cell_html(_approval_html(cat, other, styles), styles)],
        [lbl('申請公司'), lbl(''), body(COMPANY_ZH), body(COMPANY_ZH)],
        [lbl('申請部門'), lbl(''), body(DEPT_ZH), body(DEPT_ZH)],
        [
            lbl('項目編號'), lbl(''),
            _cell_html(_underline_val(qno, 24), styles),
            _cell_html(f'遞交日期 {_ymd_html(payload.get("submit_date"))}', styles),
        ],
        [
            lbl('項目名稱'), lbl(''),
            _cell_html(_underline_val(proj, 40), styles, 'body'),
            _cell_html(_underline_val(proj, 40), styles, 'body'),
        ],
        [
            lbl('截標日期及時間'), lbl(''),
            _cell_html(_bid_datetime_html(payload), styles, 'bid'),
            _cell_html(f'招標日期 {_ymd_html(payload.get("tender_date"))}', styles, 'bid'),
        ],
        [
            lbl('供方名稱'), lbl(''),
            _cell_html(_underline_val(client, 24), styles),
            _cell_html(f'標書編號 {_underline_val(qno, 20)}', styles),
        ],
        [
            lbl('合約總價'), lbl(''),
            _cell_html(_amount_html(payload.get('amount')), styles),
            _cell_html(_amount_html(payload.get('amount')), styles),
        ],
        [
            lbl('合約年期'), lbl(''),
            _cell_html(f'{_ymd_html(payload.get("contract_start_date"))}     至', styles, 'bid'),
            _cell_html(_contract_end_html(payload.get('contract_end_date'), months), styles, 'bid'),
        ],
        [
            lbl('上次合約年期(*如有)'), lbl(''),
            _cell_html(f'{_ymd_html(None)}     至', styles, 'bid'),
            _cell_html(_contract_end_html(None, None), styles, 'bid'),
        ],
        [
            lbl('上次合約總價(*如有)'), lbl(''),
            _cell_html('(HKD) ' + ('_' * 20), styles),
            _cell_html('(HKD) ' + ('_' * 20), styles),
        ],
        [
            lbl('附件及其他事項'), lbl(''),
            body(att or ' '),
            body(att or ' '),
        ],
        [
            lbl('美博公司'), body('经办人'),
            body(_sig_date_html(sig_iso)),
            body(_sig_date_html(sig_iso)),
        ],
        [
            lbl('美博公司'), body('合約部/項目部覆核'),
            body(_sig_date_html(sig_iso)),
            body(_sig_date_html(sig_iso)),
        ],
        [
            lbl('美博公司'), body('美博公司总经理批示'),
            body(_sig_date_html(sig_iso)),
            body(_sig_date_html(sig_iso)),
        ],
        [_cell(FOOTNOTE, styles, 'small')] * 4,
    ]

    tbl = Table(data, colWidths=COL_W, repeatRows=0)
    grey = colors.HexColor('#94a3b8')
    cmds = [
        ('GRID', (0, 0), (-1, -1), 0.4, grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('SPAN', (0, 0), (3, 0)),
        ('SPAN', (0, 16), (3, 16)),
    ]
    for ri in range(1, 16):
        cmds.append(('SPAN', (0, ri), (1, ri)))
    tbl.setStyle(TableStyle(cmds))
    return tbl


def generate_signoff_pdf_reportlab(payload: dict) -> bytes:
    """完整會簽表單頁 PDF（與 Template 欄位對齊；不依 Word/LibreOffice）。"""
    font = ensure_pdf_font()
    bold = ensure_pdf_font_bold()
    styles = _styles(font, bold)
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN + LOGO_H + 2 * mm,
        bottomMargin=MARGIN,
        title='投標合約會簽表',
    )
    story = [
        Paragraph(_esc('投標合約會簽表'), styles['title']),
        Spacer(1, 4 * mm),
        _build_table(payload, styles),
    ]
    doc.build(story, onFirstPage=_draw_logo, onLaterPages=_draw_logo)
    return buf.getvalue()
