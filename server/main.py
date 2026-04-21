from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, status, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
import os
import shutil
import tempfile
from typing import Optional, List
import io
import re
import math
from datetime import datetime
import pdfplumber

from server.parsers.bca import parse_bca
from server.parsers.muamalat import parse_muamalat
from server.parsers.bsi import parse_bsi
from server.excel_writer import generate_excel
from server.coin_manager import calculate_cost # Keeping logic, but will use DB balance

from server.database import engine, Base, get_db
from server.models import User, ConversionRecord
from server.auth import get_password_hash, verify_password, create_access_token, get_current_user, get_admin_user

from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from dotenv import load_dotenv

# Load Environment Variables
load_dotenv()

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="MutasiConvert API")

# --- SECURITY MIDDLEWARES ---

# 1. Enforce HTTPS (Disabled by default for local dev, enable in .env)
env = os.getenv("ENV", "development")
if env == "production" and os.getenv("ENFORCE_HTTPS") == "true":
    app.add_middleware(HTTPSRedirectMiddleware)

# 2. Trusted Host Validation
# On Vercel, the internal host might vary. For production, we can be more permissive
# or add the specific Vercel domain.
allowed_hosts = os.getenv("ALLOWED_HOSTS", "*").split(",")
app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)

# 3. CORS Policy
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Update in production .env via ALLOWED_HOSTS if needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def sanitize_header_value(value: str) -> str:
    if not value: return "Unknown"
    sanitized = re.sub(r'[\r\n\t]+', ' ', value)
    sanitized = sanitized.encode('ascii', 'ignore').decode('ascii')
    sanitized = re.sub(r'[:"<>|?*\\/]', '', sanitized)
    return sanitized.strip()

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def read_index():
    return FileResponse("static/index.html")

@app.get("/admin")
async def read_admin():
    return FileResponse("static/admin.html")

# --- AUTH ENDPOINTS ---

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Initialize Limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.post("/api/auth/register")
@limiter.limit("5/minute")
async def register(request: Request, email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    # ... existing logic ...
    # Check if user exists
    db_user = db.query(User).filter(User.email == email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email sudah terdaftar.")
    
    new_user = User(
        email=email,
        hashed_password=get_password_hash(password)
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # Create first admin if no users exist
    if new_user.id == 1:
        new_user.is_admin = True
        db.commit()

    return {"message": "Registrasi berhasil.", "unique_code": new_user.unique_code}

@app.post("/api/auth/login")
@limiter.limit("10/minute")
async def login(request: Request, db: Session = Depends(get_db), form_data: OAuth2PasswordRequestForm = Depends()):
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email atau password salah.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/api/auth/me")
async def get_me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "coins": current_user.coins,
        "unique_code": current_user.unique_code,
        "is_admin": current_user.is_admin
    }

@app.post("/api/user/update-profile")
async def update_profile(
    full_name: str = Form(None),
    current_password: str = Form(None),
    new_password: str = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if full_name is not None:
        current_user.full_name = full_name
    
    if new_password:
        if not current_password:
            raise HTTPException(status_code=400, detail="Password lama diperlukan untuk mengubah password.")
        if not verify_password(current_password, current_user.hashed_password):
            raise HTTPException(status_code=400, detail="Password lama salah.")
        current_user.hashed_password = get_password_hash(new_password)
    
    db.commit()
    return {"message": "Profil berhasil diperbarui."}

@app.get("/api/user/history", response_model=List[dict])
async def get_history(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Strict isolation: only fetch records where user_id matches the current user
    records = db.query(ConversionRecord).filter(ConversionRecord.user_id == current_user.id).order_by(ConversionRecord.created_at.desc()).all()
    return [{
        "id": r.id,
        "bank": r.bank.upper(),
        "filename": r.filename,
        "page_count": r.page_count,
        "coin_cost": r.coin_cost,
        "created_at": r.created_at
    } for r in records]

@app.get("/api/balance")
async def get_coin_balance(current_user: User = Depends(get_current_user)):
    return {"balance": current_user.coins}

# --- ADMIN ENDPOINTS ---

@app.post("/api/admin/create-admin")
async def create_admin(
    email: str = Form(...),
    password: str = Form(...),
    full_name: str = Form(None),
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    # Check if user exists
    db_user = db.query(User).filter(User.email == email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="User dengan email ini sudah terdaftar.")
    
    new_admin = User(
        email=email,
        hashed_password=get_password_hash(password),
        full_name=full_name,
        is_admin=True,
        coins=1000 # Give admins some initial koin just in case
    )
    db.add(new_admin)
    db.commit()
    return {"message": f"Admin {email} berhasil dibuat."}

@app.get("/api/admin/users", response_model=List[dict])
async def list_users(db: Session = Depends(get_db), admin: User = Depends(get_admin_user)):
    users = db.query(User).all()
    return [{
        "id": u.id,
        "email": u.email,
        "coins": u.coins,
        "unique_code": u.unique_code,
        "is_admin": u.is_admin,
        "created_at": u.created_at
    } for u in users]

@app.post("/api/admin/add-coins")
async def add_coins(unique_code: str = Form(...), amount: int = Form(...), db: Session = Depends(get_db), admin: User = Depends(get_admin_user)):
    user = db.query(User).filter(User.unique_code == unique_code).first()
    if not user:
        raise HTTPException(status_code=404, detail="User tidak ditemukan dengan kode tersebut.")
    
    user.coins += amount
    db.commit()
    return {"message": f"Berhasil menambahkan {amount} koin ke {user.email}.", "new_balance": user.coins}

# --- CONVERSION ENDPOINTS ---

def detect_bank_id(text: str) -> str:
    text_upper = text.upper()
    if "BANK CENTRAL ASIA" in text_upper or "REKENING KORAN" in text_upper or "NO. REKENING" in text_upper:
        return "bca"
    if "BANK SYARIAH INDONESIA" in text_upper or "STATEMENT OF ACCOUNT" in text_upper or "FT NUMBER" in text_upper:
        return "bsi"
    if "BANK MUAMALAT" in text_upper or "REFERENCE NUMBER" in text_upper or "TRANSACTION DATE" in text_upper:
        return "muamalat"
    return "unknown"

@app.post("/api/analyze-pdf")
async def analyze_pdf(
    file: UploadFile = File(...), 
    bank: str = Form("bca"), 
    current_user: User = Depends(get_current_user)
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    try:
        content = await file.read()
        pdf_file = io.BytesIO(content)
        
        with pdfplumber.open(pdf_file) as pdf:
            page_count = len(pdf.pages)
            sample_text = ""
            for i in range(min(2, page_count)):
                sample_text += pdf.pages[i].extract_text() or ""
            detected_bank = detect_bank_id(sample_text)
        
        coin_cost = calculate_cost(page_count)
        can_afford = current_user.coins >= coin_cost
        
        mismatch_warning = None
        detected_name = {
            "bca": "BCA", "bsi": "BSI", "muamalat": "Muamalat", "unknown": "Tidak Dikenali"
        }.get(detected_bank)

        if detected_bank != "unknown" and detected_bank != bank:
            mismatch_warning = f"Dokumen terdeteksi sebagai {detected_name}, tetapi Anda memilih {bank.upper()}."
        elif detected_bank == "unknown":
            mismatch_warning = "Format bank tidak dikenali. Pastikan file adalah PDF Mutasi Bank asli."

        return {
            "page_count": page_count,
            "coin_cost": coin_cost,
            "can_afford": can_afford,
            "detected_bank": detected_bank,
            "detected_name": detected_name,
            "mismatch_warning": mismatch_warning
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal menganalisa PDF: {str(e)}")

@app.post("/api/convert")
async def convert_pdf(
    file: UploadFile = File(...),
    bank: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Hanya file PDF yang diperbolehkan.")

    # We need to save the file temporarily for the parsers
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        with pdfplumber.open(tmp_path) as pdf:
            page_count = len(pdf.pages)
        
        cost = calculate_cost(page_count)
        if current_user.coins < cost:
            raise HTTPException(
                status_code=402, 
                detail=f"Saldo koin tidak mencukupi (Butuh: {cost}, Saldo: {current_user.coins})."
            )

        # Deduct coins from DB
        current_user.coins -= cost
        
        # Log conversion record
        history_record = ConversionRecord(
            user_id=current_user.id,
            bank=bank,
            filename=file.filename,
            page_count=page_count,
            coin_cost=cost
        )
        db.add(history_record)
        db.commit()

        # Parse
        if bank.lower() == "bca": data, metadata = parse_bca(tmp_path)
        elif bank.lower() == "muamalat": data, metadata = parse_muamalat(tmp_path)
        elif bank.lower() == "bsi": data, metadata = parse_bsi(tmp_path)
        else: raise HTTPException(status_code=400, detail="Bank tidak didukung.")

        if not data:
            raise HTTPException(status_code=400, detail="Tidak ada data transaksi ditemukan.")

        output = io.BytesIO()
        generate_excel(data, metadata, output)
        output.seek(0)

        # Generate simplified filename: MUTASI_NAMABANK_TANGGALKONVERSI
        current_time = datetime.now().strftime("%d-%b-%Y_%H-%M").upper()
        bank_name = sanitize_header_value(metadata.get('bank', bank.upper())).upper()
        
        filename = f"MUTASI_{bank_name}_{current_time}.xlsx"

        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "X-New-Balance": str(current_user.coins)
            }
        )
    except HTTPException: raise
    except Exception as e:
        print(f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(tmp_path): os.remove(tmp_path)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


