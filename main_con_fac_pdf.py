"""主合約工程帳目總結算 PDF（PPT 第19頁 · Main Con Final Account）"""
from __future__ import annotations

from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from qs_report_pdf import ensure_pdf_font, ensure_pdf_font_bold
from sc_fac_pdf import (
    CLASSIC_RULE_W,
    CLASSIC_SETTLE_CUR_W,
    CLASSIC_SETTLE_EN_W,
    CLASSIC_SETTLE_NUM_W,
    CLASSIC_SETTLE_ZH_W,
    COLOR_BLACK,
    CONTENT_W,
    PAGE_P,
    P1_BODY_EN_FONT_PT,
    P1_BODY_FONT_PT,
    P1_BODY_LEADING_PT,
    SIG_FOOTER_ZONE,
    TOP_LOGO_ZONE,
    _classic_amt_num_cell,
    _classic_bold_html,
    _classic_settle_cur_cell,
    _classic_settle_row,
    _draw_logo,
    _esc,
    _frame,
    _grid_style,
    _hdr_fields_row_style,
    _on_page_p1,
    _p,
    _p_html,
    _styles,
    normalize_sc_fac_theme,
)

DEFAULT_MAIN_CON_FAC_THEME = 'classic'
DATES_FOOTER_ZONE = 12 * mm


def _fmt_date(raw) -> str:
    if not raw:
        return '—'
    s = str(raw).strip()[:10]
    if len(s) >= 10 and s[4] == '-' and s[7] == '-':
        return f'{s[8:10]}/{s[5:7]}/{s[0:4]}'
    return s or '—'


def _on_page_dates(canvas, doc):
    _draw_logo(canvas, doc)


def _header_block(data: dict, styles) -> list:
    h = data.get('header') or {}
    code = h.get('contract_no') or '—'
    name_zh = (h.get('project_name_zh') or '').strip()
    name_en = (h.get('project_name_en') or '').strip()
    works = name_zh or name_en or h.get('contract_works') or '—'

    title_tbl = Table([
        [_p_html('<para align="center">工程帳目總結算</para>', styles, 'title')],
        [_p_html(
            '<para align="center"><u>Project Account Final Settlement</u></para>',
            styles, 'subtitle',
        )],
    ], colWidths=[CONTENT_W])
    title_tbl.setStyle(TableStyle([
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 2),
        ('BOTTOMPADDING', (0, 1), (-1, 1), 0),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))

    works_html = _esc(works)
    if name_zh and name_en and name_zh != name_en:
        works_html += (
            f'<br/><font size="{P1_BODY_EN_FONT_PT}" color="#0f172a">{_esc(name_en)}</font>'
        )

    from sc_fac_pdf import HDR_COL_WIDTHS, _bi_label

    field_tbl = Table([
        [
            _bi_label('主合約編號:', 'Main Contract No.:', styles),
            _p(code, styles, 'body'),
            _bi_label('工程項目:', 'Contract Works:', styles),
            _p_html(works_html, styles, 'body'),
        ],
    ], colWidths=HDR_COL_WIDTHS)
    field_tbl.setStyle(_hdr_fields_row_style())
    return [title_tbl, Spacer(1, 6 * mm), field_tbl]


def _settlement_table(st: dict, styles, theme: str):
    paid_as_at = _esc(st.get('i_as_at_display') or '—')
    paid_amt = -abs(float(st.get('i_total_paid') or 0))
    contra_amt = -abs(float(st.get('j_contra_charge') or 0))

    if theme == 'classic':
        rows = [
            _classic_settle_row('(A) 主合約總額', 'Original Contract Sum:', st['a_original'], styles),
            _classic_settle_row('(B) 重新測量調整', 'Remeasurement Adjustment:', st['b_remeasurement'], styles),
            _classic_settle_row('(C) 補充合約', 'Supplemental Agreement:', st['c_supplemental'], styles),
            _classic_settle_row('(D) 變更工程總額', 'Variations:', st['d_variations'], styles),
            _classic_settle_row(
                '(E) 暫定工程量調整', 'Adjustment of Provisional Quantities:',
                st['e_provisional_qty'], styles,
            ),
            _classic_settle_row(
                '(F) 暫定金額調整', 'Adjustment of Provisional Sums:',
                st['f_provisional_sums'], styles,
            ),
            _classic_settle_row(
                '(G) 物價波動調整', 'Fluctuations Adjustment:',
                st['g_fluctuations'], styles,
            ),
        ]
        ruled_h = len(rows)
        rows.append(_classic_settle_row(
            '(H) 結算工程總額', 'Final Contract Sum:', st['h_final_sum'], styles,
            bold=True, ruled=True,
        ))
        rows.append([
            _p('(I) (減) 已支付工程額', styles, 'cell'),
            _p_html(
                f'(Less): Total Value Previous Paid'
                f'<br/>(as at {paid_as_at})',
                styles, 'cell',
            ),
            _classic_settle_cur_cell(paid_amt, styles),
            _classic_amt_num_cell(paid_amt, styles),
        ])
        rows.append([
            _p('(J) (減) 扣款費用', styles, 'cell'),
            _p_html('(Less): Contra Charge', styles, 'cell'),
            _classic_settle_cur_cell(contra_amt, styles),
            _classic_amt_num_cell(contra_amt, styles),
        ])
        ruled_k = len(rows)
        rows.append([
            _classic_bold_html('(K) 剩餘應付工程額', styles),
            _classic_bold_html('Outstanding Balance', styles),
            _classic_settle_cur_cell(st['k_outstanding'], styles, bold=True),
            _classic_amt_num_cell(st['k_outstanding'], styles, bold=True, ruled=True),
        ])
        formula = Table([[
            _p_html(
                '<font size="7" color="#64748b">(H) = (A)+(B)+(C)+(D)+(E)+(F)+(G) · '
                '(K) = (H)−(I)−(J)</font>',
                styles, 'cell',
            ),
            Paragraph('', styles['cell']),
            Paragraph('', styles['cell']),
            Paragraph('', styles['cell']),
        ]], colWidths=[
            CLASSIC_SETTLE_ZH_W, CLASSIC_SETTLE_EN_W,
            CLASSIC_SETTLE_CUR_W, CLASSIC_SETTLE_NUM_W,
        ])
        formula.setStyle(TableStyle([
            ('SPAN', (0, 0), (3, 0)),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        tbl = Table(
            rows,
            colWidths=[
                CLASSIC_SETTLE_ZH_W, CLASSIC_SETTLE_EN_W,
                CLASSIC_SETTLE_CUR_W, CLASSIC_SETTLE_NUM_W,
            ],
        )
        ruled_style = []
        for ri in (ruled_h, ruled_k):
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
            ('LEFTPADDING', (3, 0), (3, -1), 0),
            ('RIGHTPADDING', (3, 0), (3, -1), 0),
            ('ALIGN', (3, 0), (3, -1), 'RIGHT'),
            *ruled_style,
        ]))
        return [tbl, formula]

    from sc_fac_pdf import SETTLE_AMT_W, SETTLE_LABEL_W, _bilingual_label, _money_acct, _settle_row

    rows = [
        _settle_row('(A) 主合約總額', 'Original Contract Sum:', st['a_original'], styles),
        _settle_row('(B) 重新測量調整', 'Remeasurement Adjustment:', st['b_remeasurement'], styles),
        _settle_row('(C) 補充合約', 'Supplemental Agreement:', st['c_supplemental'], styles),
        _settle_row('(D) 變更工程總額', 'Variations:', st['d_variations'], styles),
        _settle_row('(E) 暫定工程量調整', 'Adjustment of Provisional Quantities:', st['e_provisional_qty'], styles),
        _settle_row('(F) 暫定金額調整', 'Adjustment of Provisional Sums:', st['f_provisional_sums'], styles),
        _settle_row('(G) 物價波動調整', 'Fluctuations Adjustment:', st['g_fluctuations'], styles),
        _settle_row('(H) 結算工程總額', 'Final Contract Sum:', st['h_final_sum'], styles, bold=True),
        [
            _bilingual_label(
                '(I) (減) 已支付工程額', None, styles,
                note_html=(
                    f'<br/><font size="8" color="#0f172a">(Less): Total Value Previous Paid'
                    f'<br/>(as at {paid_as_at})</font>'
                ),
            ),
            _p(_money_acct(paid_amt), styles, 'cell_r'),
        ],
        [
            _bilingual_label('(J) (減) 扣款費用', '(Less): Contra Charge', styles),
            _p(_money_acct(contra_amt), styles, 'cell_r'),
        ],
        [
            _bilingual_label('(K) 剩餘應付工程額', 'Outstanding Balance', styles, bold=True),
            _p(_money_acct(st['k_outstanding']), styles, 'cell_r'),
        ],
    ]
    tbl = Table(rows, colWidths=[SETTLE_LABEL_W, SETTLE_AMT_W])
    extra = [
        ('LINEABOVE', (0, 7), (-1, 7), 0.75, colors.HexColor('#64748b')),
        ('LINEABOVE', (0, 10), (-1, 10), 0.75, colors.HexColor('#64748b')),
        ('BACKGROUND', (0, 7), (-1, 7), colors.HexColor('#f8fafc')),
        ('BACKGROUND', (0, 10), (-1, 10), colors.HexColor('#f8fafc')),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
    ]
    tbl.setStyle(_grid_style(extra, theme=theme))
    return [tbl]


def _settlement_payload(fac: dict) -> dict:
    s = fac.get('settlement') or {}
    kd = fac.get('key_dates') or {}
    return {
        **s,
        'i_as_at_display': s.get('i_as_at') or kd.get('paid_as_at'),
    }


def _date_row(label_zh, label_en, value, styles, note='', money=False):
    if money and value not in (None, ''):
        from sc_fac_pdf import _money_acct
        try:
            display = _money_acct(float(value))
        except (TypeError, ValueError):
            display = str(value)
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        display = f'{int(value):,}' if float(value).is_integer() else str(value)
    elif value and ('日期' in label_zh or 'Date' in label_en):
        display = _fmt_date(value)
    else:
        display = str(value) if value not in (None, '') else '—'
    if note:
        label_html = (
            f'{_esc(label_zh)}'
            f'<br/><font size="8" color="#0f172a">{_esc(label_en)}</font>'
            f'<br/><font size="7" color="#64748b">{_esc(note)}</font>'
        )
    else:
        label_html = (
            f'{_esc(label_zh)}'
            f'<br/><font size="8" color="#0f172a">{_esc(label_en)}</font>'
        )
    return [
        _p_html(label_html, styles, 'cell'),
        _p(display, styles, 'cell'),
    ]


def _key_dates_table(fac: dict, styles, theme: str) -> Table:
    kd = fac.get('key_dates') or {}
    ed = fac.get('editable') or {}
    rows = [[
        _p_html('<b>項目</b>', styles, 'cell_b'),
        _p_html('<b>資料</b>', styles, 'cell_b'),
    ]]

    dlp_note_parts = []
    if kd.get('retention_pct_display'):
        s = f"合約保固金 {kd['retention_pct_display']}"
        if kd.get('retention_max_pct_display'):
            s += f" · 上限 {kd['retention_max_pct_display']}"
        dlp_note_parts.append(s)
    if kd.get('retention_dlp_hint'):
        dlp_note_parts.append(kd['retention_dlp_hint'])
    dlp_note = ' · '.join(dlp_note_parts)

    period_val = kd.get('contract_period_days')
    if period_val:
        period_val = f'{period_val} days'

    dlp_val = None
    if kd.get('dlp_days'):
        dlp_val = f"{kd['dlp_days']} days"
    elif kd.get('dlp_months'):
        dlp_val = f"{kd['dlp_months']} months"

    static_rows = [
        ('開工日期', 'Commencement Date', kd.get('commencement_date'), ''),
        ('合約完工日期', 'Date for Completion', kd.get('completion_date'), ''),
        ('工期', 'Contract Period', period_val, ''),
        ('保修期', 'Defect Liability Period', dlp_val, dlp_note),
        ('延期罰款單價', 'Rate of LAD', ed.get('fac_lad_rate') or kd.get('lad_rate'), '', True),
        ('延期罰款限額', 'Maximum Sum of LAD', ed.get('fac_lad_max') or kd.get('lad_max'), '', True),
        ('實際完工日期', 'Date of Practical Completion', kd.get('pc_cert_date'), ''),
    ]
    for zh, en, val, note, *rest in static_rows:
        rows.append(_date_row(zh, en, val, styles, note, money=bool(rest and rest[0])))

    for rr in kd.get('retention_rows') or []:
        label = rr.get('label') or ''
        label_en = rr.get('label_en') or ''
        note = rr.get('note') or ''
        rows.append(_date_row(label, label_en, rr.get('date'), styles, note))

    rows.append(_date_row(
        '保修期開始日期', 'Commencement of DLP', kd.get('dlp_commencement_date'), styles,
    ))
    rows.append(_date_row(
        '測試和調試完成日期', 'Testing & Commissioning Completed',
        ed.get('fac_testing_commission_date') or kd.get('testing_commission_date'), styles,
    ))
    rows.append(_date_row(
        '修補缺陷完工日期', 'Make Good Defect Completed',
        ed.get('fac_make_good_date') or kd.get('make_good_date'), styles,
    ))
    rows.append(_date_row(
        'MP 工程帳目總結算日', 'MP FAC Signed', kd.get('mp_fac_signed_date'), styles,
    ))

    col_w = [CONTENT_W * 0.62, CONTENT_W * 0.38]
    tbl = Table(rows, colWidths=col_w)
    if theme == 'classic':
        tbl.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('LINEBELOW', (0, 0), (-1, 0), CLASSIC_RULE_W, COLOR_BLACK),
        ]))
    else:
        tbl.setStyle(_grid_style([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e2e8f0')),
        ], theme=theme))
    return tbl


def _settlement_page(fac: dict, styles, theme: str) -> list:
    st = _settlement_payload(fac)
    story = _header_block(fac, styles)
    story.append(Spacer(1, 6 * mm))
    story.extend(_settlement_table(st, styles, theme))
    return story


def _dates_page(fac: dict, styles, theme: str) -> list:
    title = Table([
        [_p_html('<para align="center">工程完工關鍵日期總覽</para>', styles, 'title')],
        [_p_html(
            '<para align="center"><u>Overview of Project Completion Key Dates</u></para>',
            styles, 'subtitle',
        )],
    ], colWidths=[CONTENT_W])
    title.setStyle(TableStyle([
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 1), (-1, 1), 0),
    ]))
    return [
        title,
        Spacer(1, 6 * mm),
        _key_dates_table(fac, styles, theme),
    ]


def generate_main_con_fac_pdf(fac: dict, theme: str | None = None) -> bytes:
    """主合約 FAC · P1 結算 (A–K) + P2 關鍵日期 · A4 直向"""
    theme = normalize_sc_fac_theme(theme or DEFAULT_MAIN_CON_FAC_THEME)
    font = ensure_pdf_font()
    bold_font = ensure_pdf_font_bold()
    styles = _styles(font, P1_BODY_FONT_PT, P1_BODY_EN_FONT_PT, P1_BODY_LEADING_PT, bold_font=bold_font)
    buf = BytesIO()

    pw, ph = PAGE_P
    h = fac.get('header') or {}
    title_code = h.get('contract_no') or h.get('project_code') or 'MainConFAC'
    doc = BaseDocTemplate(buf, pagesize=PAGE_P, title=f'Main Con FAC {title_code}')

    doc.addPageTemplates([
        PageTemplate(
            id='portrait_p1',
            frames=[_frame(pw, ph, SIG_FOOTER_ZONE, TOP_LOGO_ZONE)],
            pagesize=PAGE_P,
            onPage=_on_page_p1,
        ),
        PageTemplate(
            id='portrait_dates',
            frames=[_frame(pw, ph, DATES_FOOTER_ZONE, TOP_LOGO_ZONE)],
            pagesize=PAGE_P,
            onPage=_on_page_dates,
        ),
    ])

    story = []
    story.append(NextPageTemplate('portrait_p1'))
    story.extend(_settlement_page(fac, styles, theme))
    story.append(NextPageTemplate('portrait_dates'))
    story.append(PageBreak())
    story.extend(_dates_page(fac, styles, theme))

    doc.build(story)
    return buf.getvalue()
