from server.models import ConversionRecord
from tests.db import TestSessionLocal
from tests.helpers import make_user, get_user, build_pdf
from tests.conftest import auth_headers_for
import server.main as main


def make_headers(user):
    return auth_headers_for(user)


def pdf_file(name="mutasi.pdf", num_pages=1):
    return {"file": (name, build_pdf(num_pages), "application/pdf")}


# --- analyze-pdf ---------------------------------------------------------------

def test_analyze_pdf_success(client, user, user_headers):
    r = client.post("/api/analyze-pdf", files=pdf_file(num_pages=3),
                    data={"bank": "bca"}, headers=user_headers)
    assert r.status_code == 200
    b = r.json()
    assert b["page_count"] == 3
    assert b["coin_cost"] == 2
    assert b["can_afford"] is True
    assert b["detected_bank"] == "unknown"
    assert b["detected_name"] == "Tidak Dikenali"
    assert "tidak dikenali" in b["mismatch_warning"].lower()


def test_analyze_pdf_bank_mismatch(client, user, user_headers, monkeypatch):
    monkeypatch.setattr(main, "detect_bank_id", lambda text: "bsi")
    r = client.post("/api/analyze-pdf", files=pdf_file(),
                    data={"bank": "bca"}, headers=user_headers)
    assert r.status_code == 200
    b = r.json()
    assert b["detected_bank"] == "bsi"
    assert "BSI" in b["mismatch_warning"] and "BCA" in b["mismatch_warning"]


def test_analyze_pdf_cannot_afford(client):
    u = make_user(coins=0)
    r = client.post("/api/analyze-pdf", files=pdf_file(num_pages=3),
                    data={"bank": "bca"}, headers=make_headers(u))
    assert r.status_code == 200
    assert r.json()["can_afford"] is False


def test_analyze_pdf_rejects_non_pdf(client, user, user_headers):
    r = client.post("/api/analyze-pdf",
                    files={"file": ("data.txt", b"hello", "text/plain")},
                    data={"bank": "bca"}, headers=user_headers)
    assert r.status_code == 400
    assert "must be a PDF" in r.json()["detail"]


def test_analyze_pdf_requires_auth(client):
    r = client.post("/api/analyze-pdf", files=pdf_file(), data={"bank": "bca"})
    assert r.status_code == 401


# --- convert -------------------------------------------------------------------

def test_convert_success(client, user, user_headers, monkeypatch):
    monkeypatch.setattr(main, "parse_bca", lambda path: (
        [["01/02", "TRANSFER", "", 1000.0, "CR", 5000.0]],
        {"bank": "BCA", "headers": ["Tanggal", "Keterangan", "Mutasi", "Saldo"]},
    ))
    r = client.post("/api/convert", files=pdf_file(),
                    data={"bank": "bca"}, headers=user_headers)
    assert r.status_code == 200
    assert r.headers["x-new-balance"] == "49"
    assert "attachment" in r.headers["content-disposition"]
    assert r.content[:2] == b"PK"  # valid xlsx zip

    db = TestSessionLocal()
    recs = db.query(ConversionRecord).filter(
        ConversionRecord.user_id == user.id).all()
    db.close()
    assert len(recs) == 1
    assert recs[0].bank == "bca"
    assert recs[0].page_count == 1
    assert recs[0].coin_cost == 1
    assert get_user(user.email).coins == 49


def test_convert_insufficient_coins(client):
    u = make_user(coins=0)
    r = client.post("/api/convert", files=pdf_file(),
                    data={"bank": "bca"}, headers=make_headers(u))
    assert r.status_code == 402
    assert "tidak mencukupi" in r.json()["detail"]
    assert get_user(u.email).coins == 0


def test_convert_unknown_bank(client, user, user_headers):
    r = client.post("/api/convert", files=pdf_file(),
                    data={"bank": "mandiri"}, headers=user_headers)
    assert r.status_code == 400
    assert "tidak didukung" in r.json()["detail"]


def test_convert_empty_data(client, user, user_headers, monkeypatch):
    monkeypatch.setattr(main, "parse_bca", lambda path: ([], {"bank": "BCA"}))
    r = client.post("/api/convert", files=pdf_file(),
                    data={"bank": "bca"}, headers=user_headers)
    assert r.status_code == 400
    assert "Tidak ada data transaksi" in r.json()["detail"]


def test_convert_rejects_non_pdf(client, user, user_headers):
    r = client.post("/api/convert",
                    files={"file": ("data.txt", b"hello", "text/plain")},
                    data={"bank": "bca"}, headers=user_headers)
    assert r.status_code == 400


def test_convert_requires_auth(client):
    r = client.post("/api/convert", files=pdf_file(), data={"bank": "bca"})
    assert r.status_code == 401
