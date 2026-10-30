from server.parsers.bsi import clean_number, parse_bsi
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
    assert clean_number("abc") == 0.0


# --- parse_bsi -----------------------------------------------------------------

def test_parse_bsi_table_format(monkeypatch):
    page = FakePage(
        text="Rekening : 1234567890\nDate : 01-05-2024",
        tables=[[
            ["TANGGAL", "TRX TIME", "D/K", "MUTASI", "SALDO", "KETERANGAN", "TRXID"],
            ["20240501", "11.07.25", "D", "1.000,00", "9.000,00", "Transfer", "FT001"],
            ["20240502", "", "K", "500,00", "9.500,00", "Deposit", "FT002"],
        ]],
    )
    monkeypatch.setattr("server.parsers.bsi.pdfplumber.open",
                        lambda path: FakePDF([page]))

    data, metadata = parse_bsi("fake.pdf")

    assert metadata["bank"] == "Bank BSI"
    assert metadata["account_no"] == "1234567890"
    assert metadata["period"] == "01-05-2024"
    assert data == [
        ["2024-05-01 11:07:25", "FT001", "Transfer", "IDR", 1000.0, "DB", "", 9000.0],
        ["2024-05-02", "FT002", "Deposit", "IDR", 500.0, "", "CR", 9500.0],
    ]


def test_parse_bsi_words_format(monkeypatch):
    page = FakePage(
        words=[
            W("2024-05-01", 20, 100),
            W("11:07:25FT123", 90, 100),
            W("TRANSFER", 200, 100),
            W("1.000,00", 450, 100),
            W("DB", 470, 100),
        ],
    )
    monkeypatch.setattr("server.parsers.bsi.pdfplumber.open",
                        lambda path: FakePDF([page]))

    data, metadata = parse_bsi("fake.pdf")
    assert data == [["2024-05-01 11:07:25", "FT123", "TRANSFER", "", 1000.0, "DB", "", 0.0]]


def test_parse_bsi_empty_pdf(monkeypatch):
    monkeypatch.setattr("server.parsers.bsi.pdfplumber.open",
                        lambda path: FakePDF([FakePage()]))

    data, metadata = parse_bsi("fake.pdf")
    assert data == []
    assert metadata["account_no"] == "Unknown"
