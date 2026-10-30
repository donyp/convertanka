from server.parsers.muamalat import clean_number, parse_muamalat
from tests.helpers import FakePage, FakePDF, W


# --- clean_number --------------------------------------------------------------

def test_clean_number_id_format():
    assert clean_number("1.234,56") == 1234.56


def test_clean_number_us_format():
    assert clean_number("1,234.56") == 1234.56


def test_clean_number_strips_db_cr():
    assert clean_number("1.000,00DB") == 1000.0
    assert clean_number("1.000,00CR") == 1000.0


def test_clean_number_empty_and_invalid():
    assert clean_number("") == 0.0
    assert clean_number(None) == 0.0
    assert clean_number("xyz") == 0.0


# --- parse_muamalat ------------------------------------------------------------

def test_parse_muamalat_extracts_rows(monkeypatch):
    page = FakePage(
        text="Account No. : 987654321\nPeriod : 01-2024",
        words=[
            # Header line
            W("REFERENCE", 10, 100), W("TRANSACTION", 150, 100),
            W("EFFECTIVE", 220, 100), W("DEBIT", 300, 100),
            W("CREDIT", 400, 100), W("BALANCE", 500, 100),
            W("DESCRIPTION", 640, 100),
            # Transaction line
            W("REF001", 10, 130), W("01-Jan-2024", 150, 130),
            W("01-Jan-2024", 220, 130), W("500,00", 300, 130),
            W("1.000,00", 400, 130), W("9.500,00", 500, 130),
            W("Transfer", 640, 130), W("gaji", 680, 130),
            # Continuation line
            W("ke", 640, 145), W("rekening", 660, 145),
        ],
    )
    monkeypatch.setattr("server.parsers.muamalat.pdfplumber.open",
                        lambda path: FakePDF([page]))

    data, metadata = parse_muamalat("fake.pdf")

    assert metadata["bank"] == "Bank Muamalat"
    assert metadata["account_no"] == "987654321"
    assert metadata["period"] == "01-2024"
    assert data == [[
        "REF001", "01-Jan-2024", "01-Jan-2024",
        500.0, 1000.0, 9500.0, "Transfer gaji ke rekening",
    ]]


def test_parse_muamalat_filters_junk_rows(monkeypatch):
    page = FakePage(
        words=[
            W("REFERENCE", 10, 100), W("TRANSACTION", 150, 100),
            W("EFFECTIVE", 220, 100), W("DEBIT", 300, 100),
            W("CREDIT", 400, 100), W("BALANCE", 500, 100),
            W("DESCRIPTION", 640, 100),
            # Junk row
            W("REF002", 10, 130), W("02-Jan-2024", 150, 130),
            W("02-Jan-2024", 220, 130), W("1.000,00", 300, 130),
            W("9.000,00", 500, 130), W("SALDO", 640, 130), W("AWAL", 660, 130),
            # Valid row
            W("REF003", 10, 145), W("03-Jan-2024", 150, 145),
            W("03-Jan-2024", 220, 145), W("200,00", 300, 145),
            W("9.200,00", 500, 145), W("Bayar", 640, 145), W("listrik", 660, 145),
        ],
    )
    monkeypatch.setattr("server.parsers.muamalat.pdfplumber.open",
                        lambda path: FakePDF([page]))

    data, _ = parse_muamalat("fake.pdf")
    assert len(data) == 1
    assert data[0][0] == "REF003"
    assert data[0][3] == 200.0
    assert data[0][5] == 9200.0
    assert data[0][6] == "Bayar listrik"


def test_parse_muamalat_empty_pdf(monkeypatch):
    monkeypatch.setattr("server.parsers.muamalat.pdfplumber.open",
                        lambda path: FakePDF([FakePage()]))

    data, metadata = parse_muamalat("fake.pdf")
    assert data == []
    assert metadata["bank"] == "Bank Muamalat"
    assert metadata["account_no"] == "Unknown"
