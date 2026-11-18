from sc_contract_ref import _parse_registry_amount


def test_margin_text_b_cb():
    raw = "B單: - 13.8535%\nCB單/通渠M 單: -6%"
    amount, note = _parse_registry_amount(raw)
    assert amount == 0.0
    assert note == raw


def test_decimal_fraction_percent():
    amount, note = _parse_registry_amount(-0.15401)
    assert amount == 0.0
    assert note and "比例" in note


def test_plain_hkd():
    amount, note = _parse_registry_amount(870000)
    assert amount == 870000.0
    assert note is None


def test_plain_hkd_string():
    amount, note = _parse_registry_amount("2,239,305")
    assert amount == 2239305.0
    assert note is None


def test_scheme_options_no_auto_pick():
    raw = "方案一: 956,361\n方案二: 460,987"
    amount, note = _parse_registry_amount(raw)
    assert amount == 0.0
    assert note == raw


def test_scheme_hkd_prefix():
    raw = "方案一: HK$11,550,000.00\n方案二: HK$12,350,000.00"
    amount, note = _parse_registry_amount(raw)
    assert amount == 0.0
    assert note == raw