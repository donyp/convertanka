from server.parsers.bca import clean_number, parse_bca
from tests.helpers import FakePage, FakePDF, W


# --- clean_number --------------------------------------------------------------

def test_clean_number_id_format():
    assert clean_number("1.234,56") == (1234.56, False)


def test_clean_number_us_format():
    assert clean_number("1,234.56") == (1234.56, False)


def test_clean_number_db_flag():
    assert clean_number("500,00 DB") == (500.0, True)


def test_clean_number_cr_flag():
    assert clean_number("500,00 CR") == (500.0, False)


def test_clean_number_empty():
    assert clean_number("") == (0.0, False)
    assert clean_number(None) == (0.0, False)


def test_clean_number_plain():
    assert clean_number("100") == (100.0, False)


def test_clean_number_invalid():
    assert clean_number("abc") == (0.0, False)


# --- parse_bca -----------------------------------------------------------------

def test_parse_bca_extracts_rows_and_metadata(monkeypatch):
    page = FakePage(
        width=612,
        text="NO. REKENING : 1234567890\nPERIODE : Jan 2024",
        words=[
            # Header line
            W("TANGGAL", 20, 100), W("KETERANGAN", 60, 100), W("CBG", 320, 100),
            W("MUTASI", 400, 100), W("SALDO", 530, 100),
            # Transaction line
            W("01/02", 20, 130), W("TRANSFER", 70, 130), W("0012", 320, 130),
            W("1.000,00 DB", 400, 130), W("5.000,00", 530, 130),
            # Continuation line (description wraps)
            W("KE", 70, 145), W("TOKO", 90, 145),
        ],
    )
    monkeypatch.setattr("server.parsers.bca.pdfplumber.open",
                        lambda path: FakePDF([page]))

    data, metadata = parse_bca("fake.pdf")

    assert metadata["bank"] == "BCA"
    assert metadata["account_no"] == "1234567890"
    assert metadata["period"] == "Jan 2024"
    assert data == [["01/02", "TRANSFER KE TOKO", "0012", 1000.0, "DB", 5000.0]]


def test_parse_bca_credit_transaction(monkeypatch):
    page = FakePage(
        words=[
            W("TANGGAL", 20, 100), W("KETERANGAN", 60, 100), W("CBG", 320, 100),
            W("MUTASI", 400, 100), W("SALDO", 530, 100),
            W("05/03", 20, 130), W("KREDIT", 70, 130), W("0099", 320, 130),
            W("250,00 CR", 400, 130), W("7.500,00", 530, 130),
        ],
    )
    monkeypatch.setattr("server.parsers.bca.pdfplumber.open",
                        lambda path: FakePDF([page]))

    data, metadata = parse_bca("fake.pdf")
    assert data == [["05/03", "KREDIT", "0099", 250.0, "CR", 7500.0]]
    assert metadata["account_no"] == "Unknown"


def test_parse_bca_empty_pdf(monkeypatch):
    monkeypatch.setattr("server.parsers.bca.pdfplumber.open",
                        lambda path: FakePDF([FakePage()]))

    data, metadata = parse_bca("fake.pdf")
    assert data == []
    assert metadata["bank"] == "BCA"
    assert metadata["account_no"] == "Unknown"


def test_parse_bca_skips_summary_lines(monkeypatch):
    page = FakePage(
        words=[
            W("TANGGAL", 20, 100), W("KETERANGAN", 60, 100), W("CBG", 320, 100),
            W("MUTASI", 400, 100), W("SALDO", 530, 100),
            W("MUTASI", 20, 130), W("CR", 400, 130),
            W("SALDO", 20, 145), W("AKHIR", 60, 145), W("9.000,00", 530, 145),
        ],
    )
    monkeypatch.setattr("server.parsers.bca.pdfplumber.open",
                        lambda path: FakePDF([page]))

    data, _ = parse_bca("fake.pdf")
    assert data == []
