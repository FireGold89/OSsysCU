"""分判工程帳目總結算 PDF（每判項 · 3 頁 · 對照 Final Account Excel）"""
from __future__ import annotations

import os
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from qs_report_pdf import _esc, _money, ensure_pdf_font, ensure_pdf_font_bold
from config import BASE_DIR

PAGE_P = A4
PAGE_L = landscape(A4)
MARGIN = 15 * mm
CONTENT_W = PAGE_P[0] - 2 * MARGIN
FOOTER_ZONE = 28 * mm          # P2/P3 分判商雙簽 footer
SIG_FOOTER_ZONE = 46 * mm      # P1 內部四行簽名 footer
TITLE_FONT_PT = 16             # 與 title 樣式 fontSize 一致
TITLE_LEADING_PT = 20          # 與 title 樣式 leading 一致
BODY_FONT_PT = 10              # P2/P3 內文
BODY_LEADING_PT = 13
BODY_EN_FONT_PT = 8            # 內文雙語英文副行
P1_BODY_FONT_PT = 8            # P1 內文
P1_BODY_LEADING_PT = 11
P1_BODY_EN_FONT_PT = 7
TOP_LOGO_ZONE = 14 * mm         # 頁首 LOGO 區
LOGO_H = 12 * mm                 # LOGO 高度（略小於標題行）
LOGO_W_MAX = CONTENT_W * 0.42    # 橫向 banner 最闊
LOGO_LIFT = 6 * mm               # LOGO 向上微調（貼近頁頂）
SIG_LINE_W = 72 * mm           # P1 簽名底線
DATE_LINE_W = 52 * mm          # P1 日期底線
DUAL_SIG_LINE_W = 88 * mm      # P2/P3 左右簽名線
SETTLE_LABEL_W = CONTENT_W * 0.68
SETTLE_AMT_W = CONTENT_W * 0.32
CLASSIC_SETTLE_ZH_W = CONTENT_W * 0.30
CLASSIC_SETTLE_EN_W = CONTENT_W * 0.45
CLASSIC_SETTLE_CUR_W = CONTENT_W * 0.07   # HK$
CLASSIC_SETTLE_NUM_W = CONTENT_W * 0.18   # 金額數字
CLASSIC_SETTLE_AMT_W = CLASSIC_SETTLE_CUR_W + CLASSIC_SETTLE_NUM_W
COLOR_RED = colors.HexColor('#dc2626')
COLOR_BLACK = colors.HexColor('#0f172a')
CLASSIC_RULE_W = 0.5          # Word 框線 1/2 pt
CLASSIC_DOUBLE_GAP = 1.0      # 雙下線間距（pt）
# P1 表頭欄寬（對照 Word 手工版面 · 左標籤/左值/右標籤/右值 mm）
HDR_COL_MM_REF = (34.41, 77.51, 30.0, 43.99)
_HDR_COL_REF_SUM = sum(HDR_COL_MM_REF)
HDR_COL_WIDTHS = [CONTENT_W * (w / _HDR_COL_REF_SUM) for w in HDR_COL_MM_REF]
COMPANY = 'Mepork Engineering Services Limited'
COMPANY_ZH = '美博工程服務有限公司'

# 打印主題：mepork_grid＝清新格線（現行格線版）；classic＝傳統會計（PPT p20 無框線）
SC_FAC_THEMES = {
    'mepork_grid': '清新格線',
    'classic': '傳統會計',
}
DEFAULT_SC_FAC_THEME = 'mepork_grid'
_FONT_NAME = None
_LOGO_PATH = None


def normalize_sc_fac_theme(raw=None) -> str:
    t = (raw or DEFAULT_SC_FAC_THEME).strip().lower()
    if t in ('classic', 'traditional', 'ppt20', 'ppt_20'):
        return 'classic'
    return DEFAULT_SC_FAC_THEME


def _appendix_has_vo(data: dict) -> bool:
    meta = data.get('appendix_meta') or {}
    if 'has_vo' in meta:
        return bool(meta['has_vo'])
    return bool(data.get('variations'))


def _appendix_has_contra(data: dict) -> bool:
    meta = data.get('appendix_meta') or {}
    if 'has_contra' in meta:
        return bool(meta['has_contra'])
    total = data.get('contra_charges_total') or 0
    try:
        if abs(float(total)) > 0:
            return True
    except (TypeError, ValueError):
        pass
    for row in data.get('contra_charges') or []:
        try:
            if abs(float(row.get('amount') or 0)) > 0:
                return True
        except (TypeError, ValueError):
            continue
    st = data.get('settlement') or {}
    try:
        if float(st.get('deduction_total') or 0) > 0:
            return True
    except (TypeError, ValueError):
        pass
    return False


def resolve_appendix_pages(data: dict, *, print_vo_empty=False, print_contra_empty=False) -> tuple[bool, bool]:
    """有 VO／Contra 資料 → 自動列印；無資料 → 依使用者勾選"""
    has_vo = _appendix_has_vo(data)
    has_contra = _appendix_has_contra(data)
    return (
        has_vo or print_vo_empty,
        has_contra or print_contra_empty,
    )


def list_sc_fac_themes():
    return [{'id': k, 'label': v} for k, v in SC_FAC_THEMES.items()]


def _logo_path():
    global _LOGO_PATH
    if _LOGO_PATH is not None:
        return _LOGO_PATH or None
    for name in ('mepork_logo.png', 'MeporkLogo.png'):
        p = os.path.join(BASE_DIR, 'assets', name)
        if os.path.isfile(p):
            _LOGO_PATH = p
            return p
    _LOGO_PATH = ''
    return None


def _logo_draw_size():
    """LOGO 繪製尺寸（高度 LOGO_H，橫向按比例）"""
    path = _logo_path()
    target_h = LOGO_H
    if not path:
        return LOGO_W_MAX, target_h
    try:
        from PIL import Image
        with Image.open(path) as im:
            iw, ih = im.size
        if iw <= 0 or ih <= 0:
            return LOGO_W_MAX, target_h
        aspect = iw / ih
        if aspect >= 2.2:
            h = target_h
            w = min(LOGO_W_MAX, h * aspect)
            return w, h
        return target_h, target_h
    except Exception:
        return LOGO_W_MAX, target_h


def _frame(page_w, page_h, footer_h=0, top_h=0):
    return Frame(
        MARGIN, MARGIN + footer_h,
        page_w - 2 * MARGIN, page_h - 2 * MARGIN - footer_h - top_h,
        leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
    )


def _sig_font():
    global _FONT_NAME
    if not _FONT_NAME:
        _FONT_NAME = ensure_pdf_font()
    return _FONT_NAME


def _draw_sig_line(canvas, x1, x2, y):
    canvas.setStrokeColor(colors.HexColor('#334155'))
    canvas.setLineWidth(0.6)
    canvas.line(x1, y, x2, y)


def _draw_logo(canvas, doc):
    """每頁左上角 Mepork LOGO"""
    path = _logo_path()
    if not path:
        return
    draw_w, draw_h = _logo_draw_size()
    canvas.saveState()
    _page_w, page_h = canvas._pagesize
    y = page_h - MARGIN - draw_h + LOGO_LIFT
    canvas.drawImage(
        path, MARGIN, y,
        width=draw_w, height=draw_h,
        preserveAspectRatio=True, anchor='sw', mask='auto',
    )
    canvas.restoreState()


def _on_page_p1(canvas, doc):
    _draw_logo(canvas, doc)
    _draw_internal_footer(canvas, doc)


def _on_page_dual(canvas, doc):
    _draw_logo(canvas, doc)
    _draw_dual_footer(canvas, doc)


def _draw_internal_footer(canvas, doc):
    """P1 頁底：編制者／合約部／項目部／總經理（底線供簽署）"""
    font = _sig_font()
    canvas.saveState()
    left = MARGIN
    label_w = 30 * mm
    sig_gap = 4 * mm
    date_label_w = 18 * mm
    row_h = 10.5 * mm

    rows = (
        ('編制者', 'Prepared by'),
        ('合約部', 'Contracts Dept.'),
        ('項目部', 'Project Dept.'),
        ('總經理', 'General Manager'),
    )

    # 由 footer 區頂部向下排四行；底線在下，線上空間簽署
    footer_top = MARGIN + SIG_FOOTER_ZONE - 3 * mm
    for i, (zh, en) in enumerate(rows):
        line_y = footer_top - (i + 1) * row_h
        label_y = line_y + 4 * mm

        canvas.setFont(font, 8)
        canvas.setFillColor(COLOR_BLACK)
        canvas.drawString(left, label_y, f'{zh}:')
        canvas.setFont(font, 7)
        canvas.setFillColor(COLOR_BLACK)
        canvas.drawString(left, label_y - 3.2 * mm, f'{en}:')

        sig_x1 = left + label_w
        sig_x2 = sig_x1 + SIG_LINE_W
        _draw_sig_line(canvas, sig_x1, sig_x2, line_y)

        canvas.setFont(font, 8)
        canvas.setFillColor(colors.HexColor('#0f172a'))
        date_x = sig_x2 + sig_gap
        canvas.drawString(date_x, label_y, 'Date 日期:')
        date_x1 = date_x + date_label_w
        date_x2 = date_x1 + DATE_LINE_W
        _draw_sig_line(canvas, date_x1, date_x2, line_y)

    canvas.restoreState()


def _draw_dual_footer(canvas, doc):
    """P2/P3 頁底：左 Mepork · 右分判商簽章（底線供簽署，不過長）"""
    font = _sig_font()
    canvas.saveState()
    page_w, _page_h = canvas._pagesize
    left_x = MARGIN
    right_x = page_w - MARGIN
    line_y = 20 * mm
    line_w = DUAL_SIG_LINE_W

    left_x2 = left_x + line_w
    right_x1 = right_x - line_w

    _draw_sig_line(canvas, left_x, left_x2, line_y)
    _draw_sig_line(canvas, right_x1, right_x, line_y)

    canvas.setFont(font, 8)
    canvas.setFillColor(colors.HexColor('#0f172a'))

    y = line_y - 4.5 * mm
    canvas.drawString(left_x, y, COMPANY)
    y -= 4 * mm
    canvas.drawString(left_x, y, COMPANY_ZH)
    y -= 4 * mm
    canvas.drawString(left_x, y, 'Date 日期:')

    y = line_y - 4.5 * mm
    rx = right_x1
    canvas.drawString(rx, y, 'Authorized Signature by Sub-contractor')
    y -= 4 * mm
    canvas.drawString(rx, y, '分判商簽章')
    y -= 4 * mm
    canvas.drawString(rx, y, 'Date 日期:')

    canvas.restoreState()


def _styles(font, body_pt=BODY_FONT_PT, en_pt=BODY_EN_FONT_PT, leading_pt=None, bold_font=None):
    lead = leading_pt or (body_pt + 3)
    en_lead = en_pt + 2
    bf = bold_font or font
    return {
        'title': ParagraphStyle(
            'scfac_title', fontName=font, fontSize=TITLE_FONT_PT, leading=TITLE_LEADING_PT,
            alignment=TA_CENTER, textColor=COLOR_BLACK, spaceAfter=2,
        ),
        'subtitle': ParagraphStyle(
            'scfac_sub', fontName=font, fontSize=11, leading=14,
            alignment=TA_CENTER, textColor=COLOR_BLACK, spaceAfter=8,
        ),
        'label': ParagraphStyle(
            'scfac_label', fontName=font, fontSize=body_pt, leading=lead,
            textColor=COLOR_BLACK,
        ),
        'label_en': ParagraphStyle(
            'scfac_label_en', fontName=font, fontSize=en_pt, leading=en_lead,
            textColor=COLOR_BLACK,
        ),
        'body': ParagraphStyle(
            'scfac_body', fontName=font, fontSize=body_pt, leading=lead,
            textColor=COLOR_BLACK,
        ),
        'small': ParagraphStyle(
            'scfac_small', fontName=font, fontSize=body_pt, leading=lead,
            textColor=COLOR_BLACK,
        ),
        'cell': ParagraphStyle(
            'scfac_cell', fontName=font, fontSize=body_pt, leading=lead,
            textColor=COLOR_BLACK,
        ),
        'cell_r': ParagraphStyle(
            'scfac_cell_r', fontName=font, fontSize=body_pt, leading=lead,
            alignment=TA_RIGHT, textColor=COLOR_BLACK,
        ),
        'cell_b': ParagraphStyle(
            'scfac_cell_b', fontName=bf, fontSize=body_pt, leading=lead,
            textColor=COLOR_BLACK,
        ),
        'sig': ParagraphStyle(
            'scfac_sig', fontName=font, fontSize=9, leading=12,
            textColor=COLOR_BLACK,
        ),
    }


def _p(text, styles, style='cell'):
    return Paragraph(_esc(str(text if text is not None else '')), styles[style])


def _p_html(html, styles, style='cell'):
    return Paragraph(html, styles[style])


def _bi_label(zh, en, styles, en_pt=None, align=None):
    ep = en_pt if en_pt is not None else styles['label_en'].fontSize
    en_part = f'<br/><font size="{ep}" color="#0f172a">{_esc(en)}</font>' if en else ''
    inner = f'{_esc(zh)}{en_part}'
    if align:
        inner = f'<para align="{align}">{inner}</para>'
    return _p_html(inner, styles, 'label')


def _money_split(val):
    """P1 結算表：HK$ 左欄 · 數字右欄（負數紅色括號）"""
    try:
        n = float(val or 0)
    except (TypeError, ValueError):
        return 'HK$', '—', False
    if n == 0:
        return 'HK$', '0.00', False
    abs_s = f'{abs(n):,.2f}'
    if n < 0:
        return 'HK$', f'({abs_s})', True
    return 'HK$', abs_s, False


def _money_acct(val) -> str:
    try:
        n = float(val or 0)
    except (TypeError, ValueError):
        return '—'
    if n == 0:
        return 'HK$0.00'
    abs_s = f'HK${abs(n):,.2f}'
    return f'({abs_s})' if n < 0 else abs_s


def _money_contra_amt(val) -> str:
    """P3 Contra 附錄：金額正數、純黑（PPT p21 · 不用括號/紅色）"""
    try:
        n = float(val or 0)
    except (TypeError, ValueError):
        return '—'
    if n == 0:
        return 'HK$0.00'
    return f'HK${abs(n):,.2f}'


def _vo_net_amount(val) -> float:
    try:
        return float(val or 0)
    except (TypeError, ValueError):
        return 0.0


def _variations_settle_labels(amount) -> tuple[str, str]:
    """P1 加減工程列：依淨額切換 (加)/(減) · 零值不加括號（P20 QS）"""
    n = _vo_net_amount(amount)
    if n > 0:
        return '(加): 加減工程 (詳附錄一)', '(Add): Variations (refer to Appendix I)'
    if n < 0:
        return '(減): 加減工程 (詳附錄一)', '(Less): Variations (refer to Appendix I)'
    return '加減工程 (詳附錄一)', 'Variations (refer to Appendix I)'


def _vo_total_label_parts(amount) -> list[tuple[str, bool]]:
    """P2 合計列：淨額正→劃 Additions · 淨額負→劃 Omissions · 零→原樣"""
    n = _vo_net_amount(amount)
    suffix = ' Carried to Final Account'
    if n > 0:
        return [('Net ', False), ('Additions', True), (' / Omissions', False), (suffix, False)]
    if n < 0:
        return [('Net Additions / ', False), ('Omissions', True), (suffix, False)]
    return [('Net Additions / Omissions Carried to Final Account', False)]


def _vo_total_label_html(amount) -> str:
    return ''.join(
        f'<strike>{_esc(t)}</strike>' if strike else _esc(t)
        for t, strike in _vo_total_label_parts(amount)
    )


def _vo_total_label_cell(total, styles):
    return _p_html(f'<b>{_vo_total_label_html(total)}</b>', styles, 'cell_b')


def _p_amt(val, styles, bold=False, align='right'):
    text = _money_acct(val)
    sty = 'cell_b' if bold else ('cell_r' if align == 'right' else 'cell')
    inner = f'<b>{_esc(text)}</b>' if bold else _esc(text)
    if text.startswith('('):
        red = f'<font color="#dc2626">{_esc(text)}</font>'
        inner = f'<b>{red}</b>' if bold else red
    if align and align != 'left':
        inner = f'<para align="{align}">{inner}</para>'
        return _p_html(inner, styles, sty)
    return _p_html(inner, styles, sty) if bold else _p(text, styles, sty)


def _p_amt_contra(val, styles, bold=False):
    """P3 Contra AMOUNT 欄（PPT p21）"""
    text = _money_contra_amt(val)
    sty = 'cell_b' if bold else 'cell_r'
    inner = f'<b>{_esc(text)}</b>' if bold else _esc(text)
    return _p_html(f'<para align="right">{inner}</para>', styles, sty)


def _p_center(text, styles, style='cell'):
    return _p_html(f'<para align="center">{_esc(str(text if text is not None else ""))}</para>', styles, style)


def _p_underline(text, styles, style='body', align=None, bold=False):
    inner = f'<b>{_esc(text)}</b>' if bold else _esc(text)
    if align:
        return _p_html(f'<para align="{align}"><u>{inner}</u></para>', styles, style)
    return _p_html(f'<u>{inner}</u>', styles, style)


def _p_underline_val(text, styles):
    return _p_html(f'<u>{_esc(text if text is not None else "—")}</u>', styles, 'body')


def _p1_amt_num_parts(val):
    """P1 數字欄：回傳 (數字字串, 是否負數/括號)"""
    try:
        n = float(val or 0)
    except (TypeError, ValueError):
        return None, False
    if n == 0:
        return '0.00', False
    return f'{abs(n):,.2f}', n < 0


def _draw_p1_amt_num(c, x_right, y, font, font_size, val):
    """P1 數字對齊：預留 ) 位 · 小數點一致 · ) 落在上/下框線內"""
    num, neg = _p1_amt_num_parts(val)
    c.setFont(font, font_size)
    if num is None:
        c.setFillColor(COLOR_BLACK)
        c.drawRightString(x_right, y, '—')
        return
    rp = c.stringWidth(')', font, font_size)
    lp = c.stringWidth('(', font, font_size)
    digit_right = x_right - rp - 0.25
    c.setFillColor(COLOR_RED if neg else COLOR_BLACK)
    c.drawRightString(digit_right, y, num)
    if neg:
        iw = c.stringWidth(num, font, font_size)
        c.drawString(digit_right - iw - lp, y, '(')
        c.drawString(digit_right + 0.25, y, ')')


class _P1AmtNumFlowable(Flowable):
    """P1 結算數字欄（canvas 對齊 · 避開 Paragraph 括號錯位）"""

    def __init__(self, val, font_name, font_size):
        super().__init__()
        self.val = val
        self.font_name = font_name
        self.font_size = font_size
        self.width = 0

    def wrap(self, availWidth, availHeight):
        self.width = availWidth
        return self.width, P1_BODY_LEADING_PT

    def draw(self):
        y = (P1_BODY_LEADING_PT - self.font_size) / 2 + 1
        _draw_p1_amt_num(
            self.canv, self.width, y, self.font_name, self.font_size, self.val,
        )


class _ClassicDoubleRule(Flowable):
    """附錄 AMOUNT 欄下雙線"""

    def wrap(self, availWidth, availHeight):
        self.width = availWidth
        return self.width, CLASSIC_DOUBLE_GAP + 2

    def draw(self):
        c = self.canv
        c.setStrokeColor(COLOR_BLACK)
        c.setLineWidth(CLASSIC_RULE_W)
        y1 = CLASSIC_DOUBLE_GAP + 1
        y2 = 1
        c.line(0, y1, self.width, y1)
        c.line(0, y2, self.width, y2)


class _ClassicRuledAmt(Flowable):
    """Word 式：上單線 + 下雙線；或僅下雙線（附錄總計 · 填滿欄寬）"""

    def __init__(self, val, font_name, width=None, bold=False, top_line=True, fill_cell=False, font_size=None, num_only=False, contra_display=False):
        super().__init__()
        self.val = val
        self.font_name = font_name
        self._width_hint = width
        self.fill_cell = fill_cell
        self.width = width or 0
        self.bold = bold
        self.top_line = top_line
        self.num_only = num_only
        self.font_size = font_size or BODY_FONT_PT
        if contra_display:
            self.text = _money_contra_amt(val)
            self.red = False
        elif num_only:
            self._num_val = val
            self.red = _p1_amt_num_parts(val)[1]
            self.text = ''  # draw via _draw_p1_amt_num
        else:
            self.text = _money_acct(val)
            self.red = self.text.startswith('(')
        if top_line and num_only:
            self._height = self.font_size + 5
        else:
            self._height = self.font_size + (10 if top_line else 8)
        if fill_cell:
            self.hAlign = 'LEFT'

    def wrap(self, availWidth, availHeight):
        # 附錄總計：雙下框線與 AMOUNT 欄同寬
        if self.fill_cell or self._width_hint is None:
            self.width = availWidth
        else:
            self.width = min(self._width_hint, availWidth)
        return self.width, self._height

    def draw(self):
        c = self.canv
        c.setStrokeColor(COLOR_BLACK)
        c.setLineWidth(CLASSIC_RULE_W)
        y_bot1 = 3.5
        y_bot2 = y_bot1 - CLASSIC_DOUBLE_GAP
        if self.top_line and self.num_only:
            y_bot1 = 1.8
            y_bot2 = y_bot1 - CLASSIC_DOUBLE_GAP
        c.line(0, y_bot1, self.width, y_bot1)
        c.line(0, y_bot2, self.width, y_bot2)
        if self.top_line:
            y_top = self._height - 1
            c.line(0, y_top, self.width, y_top)
            if self.num_only:
                text_y = y_top - self.font_size - 0.5
            else:
                text_y = (y_top + y_bot1) / 2 - self.font_size / 3
        else:
            text_y = y_bot1 + 2
        c.setFont(self.font_name, self.font_size)
        if self.num_only:
            _draw_p1_amt_num(c, self.width, text_y, self.font_name, self.font_size, self._num_val)
        else:
            c.setFillColor(COLOR_RED if self.red else COLOR_BLACK)
            c.drawRightString(self.width, text_y, self.text)


def _classic_ruled_amt(val, styles, bold=False, top_line=True, col_w=None, num_only=False, contra_display=False):
    """col_w 有值：附錄 AMOUNT 欄填滿寬度；num_only：P1 結算僅數字欄"""
    font = styles['cell_r'].fontName
    fs = styles['cell_r'].fontSize
    fill = col_w is not None
    w = col_w if fill else CLASSIC_SETTLE_NUM_W
    return _ClassicRuledAmt(
        val, font, width=w, bold=bold, top_line=top_line, fill_cell=fill,
        font_size=fs, num_only=num_only, contra_display=contra_display,
    )


def _p_amt_split(val, styles, bold=False):
    cur, num, red = _money_split(val)
    sty = 'cell_b' if bold else 'cell'
    sty_r = 'cell_b' if bold else 'cell_r'
    cur_cell = _p_html(f'<b>{_esc(cur)}</b>' if bold else _esc(cur), styles, sty)
    if red:
        num_inner = f'<font color="#dc2626">{_esc(num)}</font>'
    else:
        num_inner = _esc(num)
    if bold:
        num_inner = f'<b>{num_inner}</b>'
    num_cell = _p_html(f'<para align="right">{num_inner}</para>', styles, sty_r)
    return cur_cell, num_cell


def _appendix_hdr_cell(text, styles, center=False):
    if center:
        return _p_html(f'<para align="center"><b>{_esc(text)}</b></para>', styles, 'cell')
    return _p(text, styles, 'cell_b')


def _appendix_total_amt(total, styles, col_w, contra=False):
    """附錄總計金額：嵌套單欄表，雙下線填滿 AMOUNT 欄"""
    flow = _classic_ruled_amt(
        total, styles, bold=True, top_line=False, col_w=col_w, contra_display=contra,
    )
    inner = Table([[flow]], colWidths=[col_w])
    inner.setStyle(TableStyle([
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    return inner


def _appendix_contra_total_cell(total, styles, col_w):
    """P3 Contra 總計：Paragraph 與明細同排版 + 下雙線"""
    para = _p_amt_contra(total, styles, bold=True)
    rule = _ClassicDoubleRule()
    inner = Table([[para], [rule]], colWidths=[col_w])
    inner.setStyle(TableStyle([
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('VALIGN', (0, 0), (0, 0), 'BOTTOM'),
    ]))
    return inner


def _classic_bold_html(text, styles, *, align=None, red=False):
    """P1 粗體列：Bold 字型 · 字級與內文一致"""
    inner = _esc(text)
    if red:
        inner = f'<font color="#dc2626">{inner}</font>'
    if align == 'right':
        inner = f'<para align="right">{inner}</para>'
    return _p_html(inner, styles, 'cell_b')


def _classic_settle_cur_cell(val, styles, bold=False):
    cur, _, _ = _money_split(val)
    if bold:
        return _classic_bold_html(cur, styles)
    return _p_html(_esc(cur), styles, 'cell')


def _classic_amt_num_cell(val, styles, bold=False, ruled=False):
    fs = P1_BODY_FONT_PT
    font = styles['cell_b'].fontName if bold else styles['cell_r'].fontName
    if ruled:
        return _ClassicRuledAmt(
            val, font, bold=bold, top_line=True, fill_cell=True,
            font_size=fs, num_only=True,
        )
    return _P1AmtNumFlowable(val, font, fs)


def _classic_settle_blank_row(styles):
    """P1 結算表空白行（P20 間隔）"""
    z = _p(' ', styles, 'cell')
    return [z, z, z, z]


def _classic_settle_row(zh, en, amount, styles, bold=False, ruled=False):
    if bold:
        zh_cell = _classic_bold_html(zh, styles)
        en_cell = _classic_bold_html(en or '', styles)
    else:
        zh_cell = _p(zh, styles, 'cell')
        en_cell = _p_html(_esc(en or ''), styles, 'cell')
    return [
        zh_cell,
        en_cell,
        _classic_settle_cur_cell(amount, styles, bold=bold),
        _classic_amt_num_cell(amount, styles, bold=bold, ruled=ruled),
    ]


def _classic_appendix_head(h, styles, appendix, section_title, content_w):
    """P2/P3：左工程名稱 · 右附錄標題（文字底線）；下一行左欄章節標題底線靠左"""
    row1 = Table([
        [
            _p_underline(h.get('main_contract_works', '—'), styles, 'body'),
            _p_underline(appendix, styles, 'subtitle', align='right', bold=True),
        ],
    ], colWidths=[content_w * 0.55, content_w * 0.45])
    row1.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    section = _p_html(
        f'<para align="left"><u><b>{_esc(section_title)}</b></u></para>',
        styles, 'label',
    )
    row2 = Table([
        [section, ''],
    ], colWidths=[content_w * 0.55, content_w * 0.45])
    row2.setStyle(TableStyle([
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
    ]))
    return [row1, Spacer(1, 2 * mm), row2, Spacer(1, 4 * mm)]


def _grid_style(extra=None, theme=DEFAULT_SC_FAC_THEME):
    pad = [
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]
    if theme == 'classic':
        style = list(pad)
    else:
        style = [
            ('BOX', (0, 0), (-1, -1), 0.75, colors.HexColor('#334155')),
            ('INNERGRID', (0, 0), (-1, -1), 0.35, colors.HexColor('#cbd5e1')),
            *pad,
        ]
    if extra:
        style.extend(extra)
    return TableStyle(style)


def _bilingual_label(zh, en, styles, bold=False, note_html=None):
    sty = 'cell_b' if bold else 'cell'
    html = _esc(zh)
    if en:
        html += f'<br/><font size="{BODY_EN_FONT_PT}" color="#0f172a">{_esc(en)}</font>'
    if note_html:
        html += note_html
    return _p_html(html, styles, sty)


def _settle_row(zh, en, amount, styles, bold=False, note_html=None):
    return [
        _bilingual_label(zh, en, styles, bold=bold, note_html=note_html),
        _p(_money_acct(amount), styles, 'cell_r'),
    ]


def _hdr_fields_row_style():
    """P1 表頭：標籤左對齊 · 左右數值欄垂直對齊 · 底線填滿數值欄"""
    return TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (0, -1), 0),
        ('RIGHTPADDING', (2, 0), (2, -1), 0),
        ('LEFTPADDING', (1, 0), (1, -1), 1),
        ('LEFTPADDING', (3, 0), (3, -1), 1),
        ('LEFTPADDING', (2, 0), (2, -1), 2),
        ('RIGHTPADDING', (1, 0), (1, -1), 0),
        ('RIGHTPADDING', (3, 0), (3, -1), 0),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('LINEBELOW', (1, 0), (1, -1), CLASSIC_RULE_W, COLOR_BLACK),
        ('LINEBELOW', (3, 0), (3, -1), CLASSIC_RULE_W, COLOR_BLACK),
    ])


def _span_row(text, styles, style='small'):
    return [_p(text, styles, style), '']


def _header_block(data, styles, theme=DEFAULT_SC_FAC_THEME):
    h = data['header']
    sub_lines = [x for x in (h.get('subcontractor_zh'), h.get('subcontractor_en')) if x]
    if not sub_lines:
        sub_lines = [h.get('subcontractor') or '—']
    sub_html = '<br/>'.join(_esc(x) for x in sub_lines)
    from sc_contract_ref import display_p1_sub_contract_no
    sub_contract_no = display_p1_sub_contract_no(h.get('sub_contract_no'))

    title_rows = [
        [_p_html(f'<para align="center">{_esc("工程帳目總結算")}</para>', styles, 'title')],
        [
            _p_html(
                f'<para align="center">'
                f'{"<u>" if theme == "classic" else ""}'
                f'{_esc("Statement of Final Accounts")}'
                f'{"</u>" if theme == "classic" else ""}'
                f'</para>',
                styles, 'subtitle',
            ),
        ],
    ]
    field_rows = [
        [
            _bi_label('總承判合約/工程編號:', 'Main Contract / Job No.:', styles),
            _p(h.get('main_contract_works', '—'), styles, 'body'),
            _bi_label('分判合約編號:', 'Sub-Contracts No.:', styles),
            _p(sub_contract_no, styles, 'body'),
        ],
        [
            _bi_label('分判商:', 'Sub-contractor:', styles),
            _p_html(sub_html, styles, 'body'),
            _bi_label('分判合約:', 'Sub-Contract Works:', styles),
            _p(h.get('sc_works', '—'), styles, 'body'),
        ],
    ]
    if theme == 'classic':
        title_tbl = Table(title_rows, colWidths=[CONTENT_W])
        title_tbl.setStyle(TableStyle([
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 2),
            ('BOTTOMPADDING', (0, 1), (-1, 1), 0),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ]))
        field_tbl = Table(field_rows, colWidths=HDR_COL_WIDTHS)
        field_tbl.setStyle(_hdr_fields_row_style())
        return [title_tbl, Spacer(1, 6 * mm), field_tbl]

    rows = [
        [title_rows[0][0], '', '', ''],
        [title_rows[1][0], '', '', ''],
        *field_rows,
    ]
    tbl = Table(rows, colWidths=HDR_COL_WIDTHS)
    base_style = [
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('SPAN', (0, 0), (-1, 0)),
        ('SPAN', (0, 1), (-1, 1)),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
    ]
    if theme == 'mepork_grid':
        base_style.extend([
            ('BOX', (0, 2), (-1, -1), 0.75, colors.HexColor('#334155')),
            ('INNERGRID', (0, 2), (-1, -1), 0.35, colors.HexColor('#cbd5e1')),
            ('BACKGROUND', (0, 2), (0, -1), colors.HexColor('#f1f5f9')),
            ('BACKGROUND', (2, 2), (2, -1), colors.HexColor('#f1f5f9')),
        ])
    tbl.setStyle(TableStyle(base_style))
    return tbl


def _settlement_table_classic(st, styles, mp_mode=False):
    """傳統會計：中文 · 英文 · HK$ · 金額（四欄 · 對照 Word DOCX）"""
    paid_en = (
        f'(Less): Total Value Previous Paid'
        f'<br/>(as at {_esc(st.get("paid_as_at_display") or "—")})'
    )
    vo_zh, vo_en = _variations_settle_labels(st['variations'])
    paid_amt = -abs(st['total_paid'])
    ruled_rows = []
    rows = [
        _classic_settle_row('分判合約總額', 'Original Sub-contract Sum:', st['original_sum'], styles),
        _classic_settle_row(vo_zh, vo_en, st['variations'], styles),
    ]
    ruled_rows.append(len(rows))
    rows.append(_classic_settle_row(
        '結算工程總額', 'Final Sub-Contract Sum:', st['final_sum'], styles,
        bold=True, ruled=True,
    ))
    rows.append([
        _p('(減) 已付工程額', styles, 'cell'),
        _p_html(paid_en, styles, 'cell'),
        _classic_settle_cur_cell(paid_amt, styles),
        _classic_amt_num_cell(paid_amt, styles),
    ])
    if not mp_mode:
        for line in st.get('deduction_lines') or []:
            rows.append(_classic_settle_row(
                f'(減) {line.get("label_zh", "扣款")}',
                f'(Less): {line.get("label_en", "Deduction")}',
                line.get('amount', 0),
                styles,
            ))
    ob_as_at = _esc(st.get('paid_as_at_display') or '—')
    ob_en = f'Outstanding Balance (as at {ob_as_at})'
    ob_spacer_start = len(rows)
    rows.append(_classic_settle_blank_row(styles))
    rows.append(_classic_settle_blank_row(styles))
    ruled_rows.append(len(rows))
    rows.append([
        _classic_bold_html('剩餘應付工程額', styles),
        _classic_bold_html(ob_en, styles),
        _classic_settle_cur_cell(st['outstanding'], styles, bold=True),
        _classic_amt_num_cell(st['outstanding'], styles, bold=True, ruled=True),
    ])
    payment_hdr_idx = len(rows)
    rows.append([
        _p('根據上述餘應付工程額/保固金，按以下期數支付:', styles, 'cell'),
        '', '', '',
    ])
    pay_row_idx = len(rows)
    rows.append(_classic_settle_row(
        st.get('final_payment_label_zh', '第一期糧款（尾款）'),
        st.get('final_payment_label_en', 'Payment IP01 (Final Payment)'),
        st.get('final_payment_amount', 0),
        styles,
    ))
    total_out_idx = len(rows)
    ruled_rows.append(total_out_idx)
    rows.append(_classic_settle_row(
        '剩餘應付工程額', 'Total Outstanding Payment',
        st.get('total_outstanding', 0), styles, bold=True, ruled=True,
    ))
    tbl = Table(
        rows,
        colWidths=[
            CLASSIC_SETTLE_ZH_W, CLASSIC_SETTLE_EN_W,
            CLASSIC_SETTLE_CUR_W, CLASSIC_SETTLE_NUM_W,
        ],
    )
    ruled_style = []
    for ri in ruled_rows:
        ruled_style.extend([
            ('VALIGN', (2, ri), (3, ri), 'MIDDLE'),
            ('TOPPADDING', (2, ri), (3, ri), 0),
            ('BOTTOMPADDING', (2, ri), (2, ri), 0),
            ('LEFTPADDING', (3, ri), (3, ri), 0),
            ('RIGHTPADDING', (3, ri), (3, ri), 0),
        ])
    tbl.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('SPAN', (0, payment_hdr_idx), (1, payment_hdr_idx)),
        ('TOPPADDING', (0, ob_spacer_start), (-1, ob_spacer_start + 1), 0),
        ('BOTTOMPADDING', (0, ob_spacer_start), (-1, ob_spacer_start + 1), 0),
        ('BOTTOMPADDING', (0, payment_hdr_idx), (-1, payment_hdr_idx), 0),
        ('TOPPADDING', (0, pay_row_idx), (-1, pay_row_idx), 0),
        ('TOPPADDING', (0, total_out_idx), (-1, total_out_idx), 14),
        ('LEFTPADDING', (3, 0), (3, -1), 0),
        ('RIGHTPADDING', (3, 0), (3, -1), 0),
        ('ALIGN', (3, 0), (3, -1), 'RIGHT'),
        *ruled_style,
    ]))
    return tbl


def _settlement_table(st, styles, mp_mode=False, theme=DEFAULT_SC_FAC_THEME):
    if theme == 'classic':
        return _settlement_table_classic(st, styles, mp_mode=mp_mode)
    paid_note = (
        f'<br/><font size="{BODY_EN_FONT_PT}" color="#0f172a">(Less): Total Value Previous Paid'
        f'<br/>(as at {_esc(st.get("paid_as_at_display") or "—")})</font>'
    )
    ob_note = (
        f'<br/><font size="{BODY_EN_FONT_PT}" color="#0f172a">Outstanding Balance'
        f'<br/>(as at {_esc(st.get("paid_as_at_display") or "—")})</font>'
    )
    vo_zh, vo_en = _variations_settle_labels(st['variations'])
    rows = [
        _settle_row('分判合約總額', 'Original Sub-contract Sum:', st['original_sum'], styles),
        _settle_row(vo_zh, vo_en, st['variations'], styles),
        _settle_row('結算工程總額', 'Final Sub-Contract Sum:', st['final_sum'], styles, bold=True),
        [
            _bilingual_label('(減) 已付工程額', None, styles, note_html=paid_note),
            _p(_money_acct(-abs(st['total_paid'])), styles, 'cell_r'),
        ],
    ]
    if not mp_mode:
        for line in st.get('deduction_lines') or []:
            rows.append(_settle_row(
                f'(減) {line.get("label_zh", "扣款")}',
                f'(Less): {line.get("label_en", "Deduction")}',
                line.get('amount', 0),
                styles,
            ))
    rows.extend([
        [
            _bilingual_label('剩餘應付工程額', None, styles, bold=True, note_html=ob_note),
            _p(_money_acct(st['outstanding']), styles, 'cell_r'),
        ],
    ])
    payment_hdr_idx = len(rows)
    if mp_mode:
        payment_hdr = '就上述剩餘應付工程額/保證金，按以下分期支付:'
        pay_zh_def = '尾款'
        pay_en_def = 'Payment (Final Payment)'
    else:
        payment_hdr = '根據上述餘應付工程額/保固金，按以下期數支付:'
        pay_zh_def = '第一期糧款（尾款）'
        pay_en_def = 'Payment IP01 (Final Payment)'
    rows.append(_span_row(payment_hdr, styles))
    rows.append(_settle_row(
        st.get('final_payment_label_zh', pay_zh_def),
        st.get('final_payment_label_en', pay_en_def),
        st.get('final_payment_amount', 0),
        styles,
    ))
    note_idx = None
    if mp_mode:
        note_idx = len(rows)
        rows.append([
            _p_html(
                '(保證金收訖後發出竣工證書後支付)'
                f'<br/><font size="{BODY_EN_FONT_PT}" color="#0f172a">(to be paid after Make Good Certificate issued)</font>',
                styles, 'small'),
            '',
        ])
    total_idx = len(rows)
    rows.append(_settle_row('剩餘應付工程額', 'Total Outstanding Payment', st.get('total_outstanding', 0), styles, bold=True))
    final_idx = 2
    settle_extra = [
        ('SPAN', (0, payment_hdr_idx), (-1, payment_hdr_idx)),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
    ]
    if note_idx is not None:
        settle_extra.append(('SPAN', (0, note_idx), (-1, note_idx)))
    if theme == 'mepork_grid':
        settle_extra.extend([
            ('LINEABOVE', (0, final_idx), (-1, final_idx), 0.75, colors.HexColor('#64748b')),
            ('LINEABOVE', (0, total_idx), (-1, total_idx), 0.75, colors.HexColor('#64748b')),
            ('BACKGROUND', (0, final_idx), (-1, final_idx), colors.HexColor('#f8fafc')),
            ('BACKGROUND', (0, total_idx), (-1, total_idx), colors.HexColor('#f8fafc')),
        ])
    tbl = Table(rows, colWidths=[SETTLE_LABEL_W, SETTLE_AMT_W])
    tbl.setStyle(_grid_style(settle_extra, theme=theme))
    return tbl


def _disclaimers(styles):
    return [
        '分判商同意上述工程帳目無誤及無遺漏，並且不會就該工程再提出任何額外要求。',
        '分判商保證當工程因分判商須作修補時，分判商無條件負責修補該等問題。工程總承判商保留追究及索償之權利。',
        '*僅供糧款參考，每宗糧款均以糧款計算書及相關文件為準。',
    ]


def _appendix_table_vo(items, total, styles, theme, content_w):
    """P2 VO 附錄表（Word 參考：8 欄 · No.–AMOUNT）"""
    col_w = [
        content_w * 0.067, content_w * 0.089, content_w * 0.089, content_w * 0.240,
        content_w * 0.128, content_w * 0.128, content_w * 0.128, content_w * 0.131,
    ]
    amt_col_w = col_w[7]
    hdr = ['No.', 'AI REF', 'QUO. REF.', 'DESCRIPTION', 'QTY', 'UNIT', 'RATE', 'AMOUNT']
    if theme == 'classic':
        rows = [[
            _appendix_hdr_cell(c, styles, center=(i in (4, 5, 6, 7)))
            for i, c in enumerate(hdr)
        ]]
    else:
        rows = [[
            _p(c, styles, 'cell_b') if i not in (4, 5, 6, 7)
            else _p_html(f'<para align="center"><b>{_esc(c)}</b></para>', styles, 'cell_b')
            for i, c in enumerate(hdr)
        ]]
    for i, v in enumerate(items or [], 1):
        if theme == 'classic':
            rows.append([
                _p(str(i), styles, 'cell'),
                _p(v.get('ai_ref', ''), styles, 'cell'),
                _p(v.get('quo_ref', ''), styles, 'cell'),
                _p(v.get('description', ''), styles, 'cell'),
                _p_center(v.get('qty', ''), styles),
                _p_center(v.get('unit', ''), styles),
                _p_amt(v.get('rate'), styles, align='center'),
                _p_amt(v.get('amount'), styles),
            ])
        else:
            rows.append([
                _p(str(i), styles, 'cell'),
                _p(v.get('ai_ref', ''), styles, 'cell'),
                _p(v.get('quo_ref', ''), styles, 'cell'),
                _p(v.get('description', ''), styles, 'cell'),
                _p_center(v.get('qty', ''), styles),
                _p_center(v.get('unit', ''), styles),
                _p_amt(v.get('rate'), styles, align='center'),
                _p_amt(v.get('amount'), styles),
            ])
    if len(rows) == 1:
        blank_tail = [
            _p_center('—', styles),
            _p_center('—', styles),
            _p_center('—', styles),
            _p_html('<para align="right">—</para>', styles, 'cell'),
        ]
        if theme == 'classic':
            rows.append([
                _p('—', styles, 'cell'),
                _p('—', styles, 'cell'),
                _p('—', styles, 'cell'),
                _p('—', styles, 'cell'),
                *blank_tail,
            ])
        else:
            rows.append([_p('—', styles, 'cell')] * 4 + blank_tail)
    tbl_style = [
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]
    if theme == 'classic':
        spacer_idx = len(rows)
        rows.append([''] * 8)
        total_idx = len(rows)
        rows.append([
            '', '', '',
            _vo_total_label_cell(total, styles),
            '', '', '',
            _appendix_total_amt(total, styles, amt_col_w),
        ])
        tbl_style.extend([
            ('LINEBELOW', (0, 0), (-1, 0), CLASSIC_RULE_W, COLOR_BLACK),
            ('LINEBELOW', (5, spacer_idx), (7, spacer_idx), CLASSIC_RULE_W, COLOR_BLACK),
            ('SPAN', (3, total_idx), (6, total_idx)),
            ('ALIGN', (4, 0), (6, 0), 'CENTER'),
            ('ALIGN', (7, 0), (7, 0), 'CENTER'),
            ('ALIGN', (4, 1), (6, spacer_idx), 'CENTER'),
            ('ALIGN', (7, 1), (7, spacer_idx), 'RIGHT'),
            ('LEFTPADDING', (7, total_idx), (7, total_idx), 0),
            ('RIGHTPADDING', (7, total_idx), (7, total_idx), 0),
            ('TOPPADDING', (7, total_idx), (7, total_idx), 0),
            ('BOTTOMPADDING', (7, total_idx), (7, total_idx), 0),
        ])
    else:
        rows.append([
            '', '', '',
            _vo_total_label_cell(total, styles),
            '', '', '',
            _p(_money(total), styles, 'cell_r'),
        ])
        total_idx = len(rows) - 1
        tbl_style = [
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e2e8f0')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#1e293b')),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
            ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#e2e8f0')),
            ('LINEABOVE', (0, total_idx), (-1, total_idx), 0.75, colors.HexColor('#64748b')),
            ('SPAN', (3, total_idx), (6, total_idx)),
            ('ALIGN', (4, 0), (6, 0), 'CENTER'),
            ('ALIGN', (7, 0), (7, 0), 'CENTER'),
            ('ALIGN', (4, 1), (6, total_idx - 1), 'CENTER'),
            ('ALIGN', (7, 1), (7, total_idx), 'RIGHT'),
            *tbl_style,
        ]
    tbl = Table(rows, colWidths=col_w)
    tbl.setStyle(TableStyle(tbl_style))
    return tbl


def _appendix_table_contra(items, total, total_label, styles, theme, content_w):
    """P3 Contra 附錄表（Word 參考：NO · DESCRIPTION · 空白 · AMOUNT）"""
    col_w = [
        content_w * 0.093, content_w * 0.510, content_w * 0.066, content_w * 0.331,
    ]
    amt_col_w = col_w[3]
    hdr = ['NO', 'DESCRIPTION', '', 'AMOUNT']
    if theme == 'classic':
        rows = [[
            _appendix_hdr_cell('NO', styles),
            _appendix_hdr_cell('DESCRIPTION', styles),
            '',
            _appendix_hdr_cell('AMOUNT', styles, center=True),
        ]]
    else:
        rows = [[
            _p('NO', styles, 'cell_b'),
            _p('DESCRIPTION', styles, 'cell_b'),
            '',
            _p_html('<para align="center"><b>AMOUNT</b></para>', styles, 'cell_b'),
        ]]
    for i, v in enumerate(items or [], 1):
        no = v.get('ai_ref') or str(i)
        rows.append([
            _p(no, styles, 'cell'),
            _p(v.get('description', ''), styles, 'cell'),
            '',
            _p_amt_contra(v.get('amount'), styles),
        ])
    if len(rows) == 1:
        rows.append([
            _p('—', styles, 'cell'),
            _p('—', styles, 'cell'),
            '',
            _p_html('<para align="right">—</para>', styles, 'cell'),
        ])
    tbl_style = [
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (3, 0), (3, -1), 0),
        ('RIGHTPADDING', (3, 0), (3, -1), 0),
        ('ALIGN', (3, 1), (3, -1), 'RIGHT'),
    ]
    if theme == 'classic':
        spacer_idx = len(rows)
        rows.append(['', '', '', ''])
        total_idx = len(rows)
        rows.append([
            '',
            _p(total_label, styles, 'cell_b'),
            '',
            _appendix_contra_total_cell(total, styles, amt_col_w),
        ])
        tbl_style.extend([
            ('LINEBELOW', (0, 0), (1, 0), CLASSIC_RULE_W, COLOR_BLACK),
            ('LINEBELOW', (3, 0), (3, 0), CLASSIC_RULE_W, COLOR_BLACK),
            ('LINEBELOW', (3, spacer_idx), (3, spacer_idx), CLASSIC_RULE_W, COLOR_BLACK),
            ('ALIGN', (3, 0), (3, 0), 'CENTER'),
        ])
    else:
        spacer_idx = len(rows)
        rows.append(['', '', '', ''])
        total_idx = len(rows)
        rows.append([
            '',
            _p(total_label, styles, 'cell_b'),
            '',
            _appendix_contra_total_cell(total, styles, amt_col_w),
        ])
        tbl_style = [
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e2e8f0')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#1e293b')),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
            ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#e2e8f0')),
            ('LINEABOVE', (0, total_idx), (-1, total_idx), 0.75, colors.HexColor('#64748b')),
            ('LINEBELOW', (3, spacer_idx), (3, spacer_idx), 0.75, colors.HexColor('#64748b')),
            ('ALIGN', (3, 0), (3, 0), 'CENTER'),
            *tbl_style,
        ]
    tbl = Table(rows, colWidths=col_w)
    tbl.setStyle(TableStyle(tbl_style))
    return tbl


def _variations_page(data, styles, theme=DEFAULT_SC_FAC_THEME):
    h = data['header']
    lw = landscape(A4)[0] - 2 * MARGIN
    story = []
    if theme == 'classic':
        story.extend(_classic_appendix_head(
            h, styles, 'APPENDIX I', 'SUMMARY OF VARIATIONS', lw,
        ))
    else:
        story.extend([
            _p('APPENDIX I', styles, 'subtitle'),
            _p(h.get('main_contract_works', '—'), styles, 'subtitle'),
            _p('SUMMARY OF VARIATIONS', styles, 'subtitle'),
            Spacer(1, 4 * mm),
        ])
    story.append(_appendix_table_vo(
        data.get('variations') or [],
        data.get('variations_total', 0),
        styles, theme, lw,
    ))
    story.append(Spacer(1, 6 * mm))
    story.append(_p(
        '分判商同意上述後加工程結算所詳列之帳目正確無誤。分判商本人/本公司亦承諾不會再向美博工程服務有限公司根據上述後加工程作出任何索償。',
        styles, 'small'))
    return story


def _contra_charge_page(data, styles, theme=DEFAULT_SC_FAC_THEME):
    h = data['header']
    cw = CONTENT_W
    if theme == 'classic':
        story = _classic_appendix_head(
            h, styles, 'APPENDIX II', 'SUMMARY OF CONTRA CHARGE', cw,
        )
    else:
        story = [
            _p('APPENDIX II', styles, 'subtitle'),
            _p(h.get('main_contract_works', '—'), styles, 'subtitle'),
            _p('SUMMARY OF CONTRA CHARGE', styles, 'subtitle'),
            Spacer(1, 4 * mm),
        ]
    story.append(_appendix_table_contra(
        data.get('contra_charges') or [],
        data.get('contra_charges_total', 0),
        'Net Contra Charges Carried to Final Account',
        styles, theme, cw,
    ))
    story.append(Spacer(1, 6 * mm))
    story.append(_p(
        '分判商同意上述所詳列之帳目正確無誤。分判商本人/本公司亦承諾不會再向美博工程服務有限公司根據上述之支項目作出任何索償。',
        styles, 'small'))
    return story


def _statement_page(data, styles, mp_mode=False, theme=DEFAULT_SC_FAC_THEME, show_disclaimers=True):
    gap = 8 * mm if theme == 'classic' and not mp_mode else 3 * mm
    hdr = _header_block(data, styles, theme=theme)
    story = hdr if isinstance(hdr, list) else [hdr]
    story.extend([
        Spacer(1, gap),
        _settlement_table(data['settlement'], styles, mp_mode=mp_mode, theme=theme),
    ])
    if show_disclaimers:
        story.append(Spacer(1, 3 * mm))
        for t in _disclaimers(styles):
            story.append(_p(t, styles, 'small'))
            story.append(Spacer(1, 1.5 * mm))
    return story


def generate_sc_fac_pdf(
    data: dict,
    theme: str | None = None,
    *,
    print_appendix_vo_empty: bool = False,
    print_appendix_contra_empty: bool = False,
) -> bytes:
    """P1 直向結算 · 附錄 I/II 依資料或使用者選擇"""
    theme = normalize_sc_fac_theme(theme)
    include_vo, include_contra = resolve_appendix_pages(
        data,
        print_vo_empty=print_appendix_vo_empty,
        print_contra_empty=print_appendix_contra_empty,
    )
    font = ensure_pdf_font()
    bold_font = ensure_pdf_font_bold()
    p1_styles = _styles(font, P1_BODY_FONT_PT, P1_BODY_EN_FONT_PT, P1_BODY_LEADING_PT, bold_font=bold_font)
    apx_styles = _styles(font)
    buf = BytesIO()

    pw, ph = PAGE_P
    lw, lh = PAGE_L
    doc = BaseDocTemplate(buf, pagesize=PAGE_P, title=f"SC FAC {data.get('header', {}).get('sc_no', '')}")
    doc.addPageTemplates([
        PageTemplate(
            id='portrait_p1',
            frames=[_frame(pw, ph, SIG_FOOTER_ZONE, TOP_LOGO_ZONE)],
            pagesize=PAGE_P,
            onPage=_on_page_p1,
        ),
        PageTemplate(
            id='landscape_footer',
            frames=[_frame(lw, lh, FOOTER_ZONE, TOP_LOGO_ZONE)],
            pagesize=PAGE_L,
            onPage=_on_page_dual,
        ),
        PageTemplate(
            id='portrait_footer',
            frames=[_frame(pw, ph, FOOTER_ZONE, TOP_LOGO_ZONE)],
            pagesize=PAGE_P,
            onPage=_on_page_dual,
        ),
    ])

    story = []
    story.append(NextPageTemplate('portrait_p1'))
    story.extend(_statement_page(data, p1_styles, mp_mode=False, theme=theme, show_disclaimers=False))
    if include_vo:
        story.append(NextPageTemplate('landscape_footer'))
        story.append(PageBreak())
        story.extend(_variations_page(data, apx_styles, theme=theme))
    if include_contra:
        story.append(NextPageTemplate('portrait_footer'))
        story.append(PageBreak())
        story.extend(_contra_charge_page(data, apx_styles, theme=theme))

    doc.build(story)
    return buf.getvalue()
