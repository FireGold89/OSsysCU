"""QS 地盤財務匯報 PDF（A4 · 老細版）"""
from __future__ import annotations

import os
import re
from datetime import datetime
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from config import BASE_DIR, DATA_DIR

FONT = 'NotoSansTC'
FONT_URL = (
    'https://github.com/googlefonts/noto-cjk/raw/main/Sans/TTF/TraditionalChinese/'
    'NotoSansCJKtc-Regular.ttf'
)
_FONT_READY = False
PAGE_W, PAGE_H = A4
MARGIN = 15 * mm

STATUS_LABELS = {
    'Active': '進行中',
    'Completed': '已完成',
    'On Hold': '暫停',
}


def _esc(text) -> str:
    s = str(text if text is not None else '')
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def _resolve_font_path() -> str:
    win = os.environ.get('WINDIR', r'C:\Windows')
    candidates = [
        os.path.join(win, 'Fonts', 'msjh.ttc'),
        os.path.join(win, 'Fonts', 'msjhbd.ttc'),
        os.path.join(BASE_DIR, 'assets', 'fonts', 'NotoSansCJKtc-Regular.ttf'),
        os.path.join(DATA_DIR, 'fonts', 'NotoSansCJKtc-Regular.ttf'),
        '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
        '/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc',
    ]
    for path in candidates:
        if path and os.path.isfile(path):
            return path
    dest = os.path.join(DATA_DIR, 'fonts', 'NotoSansCJKtc-Regular.ttf')
    if os.path.isfile(dest):
        return dest
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    import urllib.request
    urllib.request.urlretrieve(FONT_URL, dest)
    return dest


def ensure_pdf_font() -> str:
    """註冊並嵌入繁體中文字型（避免 MSung CID 亂碼）"""
    global _FONT_READY, FONT
    if _FONT_READY:
        return FONT
    path = _resolve_font_path()
    if path.lower().endswith('.ttc'):
        pdfmetrics.registerFont(TTFont(FONT, path, subfontIndex=0))
    else:
        pdfmetrics.registerFont(TTFont(FONT, path))
    _FONT_READY = True
    return FONT


def _money(val) -> str:
    try:
        n = float(val or 0)
    except (TypeError, ValueError):
        return '—'
    if n == 0:
        return 'HK$0.00'
    sign = '-' if n < 0 else ''
    return f'{sign}HK${abs(n):,.2f}'


def _pct(val) -> str:
    try:
        n = float(val or 0)
    except (TypeError, ValueError):
        return '—'
    return f'{n:.2f}%'


def _plain(val, max_len=60) -> str:
    s = re.sub(r'\s+', ' ', str(val or '')).strip()
    if not s:
        return '—'
    return s if len(s) <= max_len else s[: max_len - 1] + '…'


def _sc_category(sc_no: str) -> str:
    s = (sc_no or '').upper().strip()
    if s.startswith('M'):
        return '物料'
    if s.startswith('SC'):
        return '分判'
    if s.startswith('O'):
        return '其他支出'
    return '—'


def _project_titles(project: dict) -> tuple[str, str]:
    en = (project.get('project_name_en') or '').strip()
    zh = (project.get('project_name_zh') or '').strip()
    legacy = (project.get('project_name') or '').strip()
    if not en and not zh and legacy:
        if re.search(r'[\u4e00-\u9fff]', legacy) and re.search(r'[A-Za-z]', legacy):
            for sep in (' / ', ' · ', '｜', ' | '):
                if sep in legacy:
                    a, b = legacy.split(sep, 1)
                    return a.strip(), b.strip()
        if re.search(r'[\u4e00-\u9fff]', legacy):
            return '', legacy
        return legacy, ''
    return en, zh


def _styles(font_name: str):
    return {
        'title': ParagraphStyle(
            'title', fontName=font_name, fontSize=18, leading=22, alignment=TA_CENTER,
            textColor=colors.HexColor('#1e3a5f'), spaceAfter=4,
        ),
        'subtitle': ParagraphStyle(
            'subtitle', fontName=font_name, fontSize=11, leading=14, alignment=TA_CENTER,
            textColor=colors.HexColor('#64748b'), spaceAfter=10,
        ),
        'h2': ParagraphStyle(
            'h2', fontName=font_name, fontSize=12, leading=15, textColor=colors.HexColor('#1e3a5f'),
            spaceBefore=8, spaceAfter=6,
        ),
        'body': ParagraphStyle(
            'body', fontName=font_name, fontSize=9, leading=12, textColor=colors.HexColor('#334155'),
        ),
        'small': ParagraphStyle(
            'small', fontName=font_name, fontSize=8, leading=10, textColor=colors.HexColor('#64748b'),
        ),
        'bullet': ParagraphStyle(
            'bullet', fontName=font_name, fontSize=9, leading=13, leftIndent=10,
            textColor=colors.HexColor('#334155'), spaceAfter=2,
        ),
        'cell': ParagraphStyle(
            'cell', fontName=font_name, fontSize=8, leading=10, textColor=colors.HexColor('#334155'),
        ),
        'cell_r': ParagraphStyle(
            'cell_r', fontName=font_name, fontSize=8, leading=10, alignment=TA_RIGHT,
            textColor=colors.HexColor('#334155'),
        ),
        'cell_b': ParagraphStyle(
            'cell_b', fontName=font_name, fontSize=8, leading=10, textColor=colors.HexColor('#0f172a'),
        ),
        'cell_w': ParagraphStyle(
            'cell_w', fontName=font_name, fontSize=8, leading=10, textColor=colors.white,
        ),
    }


def _p(text, styles, style='cell'):
    if isinstance(text, Paragraph):
        return text
    return Paragraph(_esc(text), styles[style])


def _table_row(cells, styles, styles_map=None):
    """表格儲存格一律用 Paragraph，確保中文正確嵌入"""
    styles_map = styles_map or {}
    return [_p(c, styles, styles_map.get(i, 'cell')) for i, c in enumerate(cells)]


def _header_footer(canvas, doc, company_name: str, project_code: str, font_name: str):
    canvas.saveState()
    canvas.setFont(font_name, 8)
    canvas.setFillColor(colors.HexColor('#94a3b8'))
    canvas.drawString(MARGIN, 10 * mm, company_name or 'Mepork Engineering Services Limited')
    canvas.drawRightString(PAGE_W - MARGIN, 10 * mm, f'第 {doc.page} 頁')
    if doc.page == 1:
        canvas.setStrokeColor(colors.HexColor('#1e3a5f'))
        canvas.setLineWidth(1.2)
        canvas.line(MARGIN, PAGE_H - 12 * mm, PAGE_W - MARGIN, PAGE_H - 12 * mm)
    canvas.restoreState()


def _attention_items(summary: dict, sc_list: list) -> list[str]:
    items = []
    calc = summary.get('contract_calc') or {}
    ip = summary.get('ip_period') or {}
    totals = ip.get('totals') or {}
    profit = float(calc.get('profit_e') or 0)
    rate = float(calc.get('profit_rate') or 0)
    advance = float(totals.get('advance') or 0)
    remainder = float(summary.get('total_remainder') or 0)
    contract_a = float(calc.get('main_contract_amount') or 0)
    total_paid = float(summary.get('total_paid') or 0)

    if contract_a > 0 and profit < 0:
        items.append(f'預計利潤為負（{_money(profit)}），地盤成本已超過承建金額，需立即檢視。')
    elif contract_a > 0 and rate < 5:
        items.append(f'預計利潤率僅 {_pct(rate)}，低於一般目標，建議檢視分判及支出。')
    if advance < 0:
        items.append(f'墊支為負（{_money(advance)}），公司資金已墊付地盤，需留意現金流。')
    if remainder > 0 and contract_a > 0 and remainder > contract_a * 0.15:
        items.append(f'未付餘額 {_money(remainder)} 佔承建金額比例偏高，需跟進分包付款計劃。')
    if contract_a > 0:
        pay_pct = total_paid / contract_a * 100
        if pay_pct > 85 and rate < 10:
            items.append(f'付款進度已達 {_pct(pay_pct)}，但利潤率仍偏低，留意尾期 VO 及索賠。')

    risky = []
    for sc in sc_list or []:
        ca = float(sc.get('contract_amount') or 0)
        paid = float(sc.get('total_paid') or 0)
        rem = ca - paid
        if ca <= 0:
            continue
        pct = paid / ca * 100
        if rem > 50000 and pct < 40:
            risky.append((rem, sc.get('sc_no'), _plain(sc.get('company_name_en') or sc.get('company_name_zh'), 24)))
    risky.sort(reverse=True)
    for rem, sc_no, company in risky[:3]:
        items.append(f'判項 {sc_no}（{company}）未付 {_money(rem)}，付款進度偏慢。')

    if not items:
        items.append('目前財務指標正常，請持續跟進糧期批款及分判付款進度。')
    return items


def _category_rows(sc_list: list) -> list[list[str]]:
    cats = {'物料': [0, 0], '分判': [0, 0], '其他支出': [0, 0]}
    for sc in sc_list or []:
        cat = _sc_category(sc.get('sc_no'))
        if cat not in cats:
            continue
        ca = float(sc.get('contract_amount') or 0)
        paid = float(sc.get('total_paid') or 0)
        cats[cat][0] += ca
        cats[cat][1] += paid
    rows = [['類別', '判項金額 (J)', '累計已付', '未付餘額']]
    for cat, (ca, paid) in cats.items():
        rows.append([cat, _money(ca), _money(paid), _money(ca - paid)])
    return rows


def generate_boss_qs_report(summary: dict, sc_list: list | None = None,
                              company_name: str = '', payment_count: int = 0) -> bytes:
    """生成 A4 QS 地盤財務匯報 PDF bytes"""
    font_name = ensure_pdf_font()
    sc_list = sc_list or []
    project = summary.get('project') or {}
    calc = summary.get('contract_calc') or {}
    ip = summary.get('ip_period') or {}
    ip_items = ip.get('items') or []
    ip_totals = ip.get('totals') or {}
    styles = _styles(font_name)
    report_date = datetime.now().strftime('%Y-%m-%d %H:%M')
    code = project.get('project_code') or 'PROJECT'
    en, zh = _project_titles(project)
    company = company_name or 'Mepork Engineering Services Limited'

    contract_a = float(calc.get('main_contract_amount') or 0)
    total_paid = float(summary.get('total_paid') or 0)
    total_rem = float(summary.get('total_remainder') or 0)
    pay_progress = (total_paid / contract_a * 100) if contract_a else 0

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=18 * mm,
        bottomMargin=16 * mm,
        title=f'QS匯報_{code}',
        author=company,
    )

    story = []

    # ── 封面標題 ──
    story.append(Paragraph('QS 地盤財務匯報', styles['title']))
    story.append(Paragraph('Quantity Surveying · Site Financial Summary', styles['subtitle']))
    story.append(Spacer(1, 4 * mm))

    meta_rows = [
        _table_row(['項目代碼', code, '報告日期', report_date], styles,
                   {1: 'cell', 3: 'cell'}),
        _table_row(['項目名稱（英）', _plain(en or '—', 80), '客戶', _plain(project.get('client'))], styles),
        _table_row(['項目名稱（中）', _plain(zh or '—', 80), '主承建商', _plain(project.get('main_contractor'), 40)], styles),
        _table_row([
            '工期', _plain(project.get('site_period_text') or ip.get('site_period_text'), 50),
            '狀態', STATUS_LABELS.get(project.get('status'), project.get('status') or '—'),
        ], styles),
    ]
    meta = Table(meta_rows, colWidths=[28 * mm, 62 * mm, 28 * mm, 52 * mm])
    meta.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f1f5f9')),
        ('BACKGROUND', (2, 0), (2, -1), colors.HexColor('#f1f5f9')),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#475569')),
        ('TEXTCOLOR', (2, 0), (2, -1), colors.HexColor('#475569')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(meta)
    story.append(Spacer(1, 6 * mm))

    # ── 老細關注重點 KPI ──
    story.append(Paragraph('一、重點摘要', styles['h2']))
    kpi = Table([
        _table_row(['承建金額 (A)', '預計利潤 (E)', '預計利潤率'], styles, {0: 'cell_w', 1: 'cell_w', 2: 'cell_w'}),
        _table_row([
            _money(calc.get('main_contract_amount')),
            _money(calc.get('profit_e')),
            _pct(calc.get('profit_rate')),
        ], styles, {0: 'cell', 1: 'cell', 2: 'cell'}),
        _table_row(['累計已付', '未付餘額', '付款進度 / 墊支'], styles, {0: 'cell_w', 1: 'cell_w', 2: 'cell_w'}),
        _table_row([
            _money(total_paid), _money(total_rem),
            f'{_pct(pay_progress)} / {_money(ip_totals.get("advance"))}',
        ], styles),
    ], colWidths=[56 * mm, 56 * mm, 56 * mm])
    profit_color = colors.HexColor('#dc2626') if float(calc.get('profit_e') or 0) < 0 else colors.HexColor('#059669')
    kpi.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e3a5f')),
        ('BACKGROUND', (0, 2), (-1, 2), colors.HexColor('#1e3a5f')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TEXTCOLOR', (1, 1), (1, 1), profit_color),
        ('TEXTCOLOR', (2, 1), (2, 1), profit_color),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(kpi)
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(
        f'判項/支出 {len(sc_list)} 項 · 付款登記 {payment_count} 筆 · '
        f'糧期 {len(ip_items)} 期',
        styles['small'],
    ))
    story.append(Spacer(1, 4 * mm))

    # ── 關注事項 ──
    story.append(Paragraph('二、關注事項', styles['h2']))
    for line in _attention_items(summary, sc_list):
        story.append(Paragraph(f'• {line}', styles['bullet']))
    story.append(Spacer(1, 4 * mm))

    # ── 合約金額結算 A–E ──
    story.append(Paragraph('三、合約金額結算 (A–E)', styles['h2']))
    calc_rows = [
        _table_row(['項目', '金額 (HK$)'], styles, {0: 'cell_w', 1: 'cell_w'}),
        _table_row(['(A) 承建金額', _money(calc.get('main_contract_amount'))], styles, {1: 'cell_r'}),
        _table_row(['(B) 分判及代支小計', _money(calc.get('sub_total_b'))], styles, {1: 'cell_r'}),
        _table_row(['(C) 除外合約收費項目', _money(calc.get('excluded_c'))], styles, {1: 'cell_r'}),
        _table_row(['財務會作調撥（人工分攤）', _money(calc.get('labour_allocation'))], styles, {1: 'cell_r'}),
        _table_row(['(D) = (B)+(C)+調撥', _money(calc.get('total_d'))], styles, {1: 'cell_r'}),
        _table_row(['(E) = (A)−(D) 預計利潤', _money(calc.get('profit_e'))], styles, {1: 'cell_r'}),
        _table_row(['預計利潤率', _pct(calc.get('profit_rate'))], styles, {1: 'cell_r'}),
    ]
    calc_tbl = Table(calc_rows, colWidths=[110 * mm, 58 * mm])
    calc_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#334155')),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('BACKGROUND', (0, 5), (-1, 5), colors.HexColor('#f8fafc')),
        ('BACKGROUND', (0, 6), (-1, 7), colors.HexColor('#eff6ff')),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(calc_tbl)
    story.append(Spacer(1, 5 * mm))

    # ── 費用類別 ──
    story.append(Paragraph('四、費用類別概覽', styles['h2']))
    cat_tbl = Table(
        [_table_row(r, styles, {0: 'cell_w', 1: 'cell_r', 2: 'cell_r', 3: 'cell_r'}) if i == 0
         else _table_row(r, styles, {1: 'cell_r', 2: 'cell_r', 3: 'cell_r'})
         for i, r in enumerate(_category_rows(sc_list))],
        colWidths=[35 * mm, 45 * mm, 45 * mm, 43 * mm],
    )
    cat_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#475569')),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(cat_tbl)
    story.append(Spacer(1, 5 * mm))

    # ── 糧期狀況 ──
    story.append(Paragraph('五、地盤糧期狀況', styles['h2']))
    ip_sum = Table([
        _table_row(['總收入', '總支出', '墊支'], styles, {0: 'cell_w', 1: 'cell_w', 2: 'cell_w'}),
        _table_row([
            _money(ip_totals.get('total_income')),
            _money(-abs(float(ip_totals.get('total_expenditure') or 0))),
            _money(ip_totals.get('advance')),
        ], styles),
    ], colWidths=[56 * mm, 56 * mm, 56 * mm])
    ip_sum.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e3a5f')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(ip_sum)
    story.append(Spacer(1, 3 * mm))

    if ip_items:
        ip_hdr = ['期數', '申請日期', '申請金額', '累計%', '批款收入', '分包支出']
        ip_rows = [
            _table_row(ip_hdr, styles, {i: 'cell_w' for i in range(len(ip_hdr))}),
        ]
        for it in ip_items:
            ip_rows.append(_table_row([
                _plain(it.get('ip_no'), 8),
                _plain(it.get('applied_date'), 12),
                _money(it.get('application_amount')),
                _pct(it.get('application_pct')),
                _money(it.get('certified_income')),
                _money(it.get('subcon_paid')),
            ], styles, {2: 'cell_r', 3: 'cell_r', 4: 'cell_r', 5: 'cell_r'}))
        ip_tbl = Table(ip_rows, colWidths=[18 * mm, 24 * mm, 30 * mm, 18 * mm, 30 * mm, 30 * mm], repeatRows=1)
        ip_tbl.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#64748b')),
            ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
            ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#e2e8f0')),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        story.append(ip_tbl)
    else:
        story.append(Paragraph('暫無糧期記錄', styles['body']))
    story.append(Spacer(1, 5 * mm))

    # ── 分判及支出明細 ──
    story.append(Paragraph('六、分判及支出明細', styles['h2']))
    if sc_list:
        sc_hdr = ['判項', '類別', '公司', '判項金額', '已付', '未付', '進度']
        sc_rows = [
            _table_row(sc_hdr, styles, {i: 'cell_w' for i in range(len(sc_hdr))}),
        ]
        sum_ca = sum_paid = 0.0
        for sc in sorted(sc_list, key=lambda x: (x.get('sc_no') or '')):
            ca = float(sc.get('contract_amount') or 0)
            paid = float(sc.get('total_paid') or 0)
            rem = ca - paid
            pct = (paid / ca * 100) if ca else 0
            sum_ca += ca
            sum_paid += paid
            sc_rows.append(_table_row([
                _plain(sc.get('sc_no'), 10),
                _sc_category(sc.get('sc_no')),
                _plain(sc.get('company_name_en') or sc.get('company_name_zh'), 28),
                _money(ca), _money(paid), _money(rem), _pct(pct),
            ], styles, {3: 'cell_r', 4: 'cell_r', 5: 'cell_r', 6: 'cell_r'}))
        sc_rows.append(_table_row(
            ['合計', '', '', _money(sum_ca), _money(sum_paid), _money(sum_ca - sum_paid), ''],
            styles, {3: 'cell_r', 4: 'cell_r', 5: 'cell_r'},
        ))
        sc_tbl = Table(
            sc_rows,
            colWidths=[18 * mm, 16 * mm, 38 * mm, 26 * mm, 26 * mm, 26 * mm, 16 * mm],
            repeatRows=1,
        )
        sc_tbl.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#334155')),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#f1f5f9')),
            ('ALIGN', (3, 0), (-2, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
            ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#e2e8f0')),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        story.append(sc_tbl)
    else:
        story.append(Paragraph('暫無判項/支出項', styles['body']))

    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph(
        f'本報告由 QS 付款管理系統自動生成 · {report_date} · 僅供內部管理參考',
        styles['small'],
    ))

    doc.build(
        story,
        onFirstPage=lambda c, d: _header_footer(c, d, company, code, font_name),
        onLaterPages=lambda c, d: _header_footer(c, d, company, code, font_name),
    )
    return buffer.getvalue()
