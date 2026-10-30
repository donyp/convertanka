from server.main import detect_bank_id, sanitize_header_value


def test_detect_bank_bca():
    assert detect_bank_id("BANK CENTRAL ASIA") == "bca"
    assert detect_bank_id("bank central asia") == "bca"
    assert detect_bank_id("REKENING KORAN") == "bca"
    assert detect_bank_id("NO REKENING : 123") == "bca"


def test_detect_bank_bsi():
    assert detect_bank_id("BANK SYARIAH INDONESIA") == "bsi"
    assert detect_bank_id("STATEMENT OF ACCOUNT") == "bsi"
    assert detect_bank_id("FT NUMBER 123") == "bsi"


def test_detect_bank_muamalat():
    assert detect_bank_id("MUAMALAT") == "muamalat"
    assert detect_bank_id("REFERENCE NUMBER") == "muamalat"
    assert detect_bank_id("TRANSACTION DATE") == "muamalat"
    assert detect_bank_id("EFFECTIVE DATE") == "muamalat"


def test_detect_bank_fallback_rules():
    assert detect_bank_id("BANK BCA MUTASI") == "bca"
    assert detect_bank_id("BSI ACCOUNT") == "bsi"


def test_detect_bank_with_extra_spaces():
    assert detect_bank_id("BANK   CENTRAL   ASIA") == "bca"


def test_detect_bank_unknown():
    assert detect_bank_id("RANDOM TEXT") == "unknown"
    assert detect_bank_id("") == "unknown"


def test_sanitize_header_value_empty():
    assert sanitize_header_value("") == "Unknown"
    assert sanitize_header_value(None) == "Unknown"


def test_sanitize_header_value_removes_newlines_and_tabs():
    assert sanitize_header_value("BCA\r\nBank") == "BCA Bank"
    assert sanitize_header_value("A\tB") == "A B"


def test_sanitize_header_value_strips_special_chars():
    assert sanitize_header_value("A/B:C?D") == "ABCD"


def test_sanitize_header_value_strips_non_ascii():
    assert sanitize_header_value("Héllo") == "Hllo"
