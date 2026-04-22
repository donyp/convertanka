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
from datetime import datetime, timedelta
import secrets
import pdfplumber
from fastapi import BackgroundTasks

from server.parsers.bca import parse_bca
from server.parsers.muamalat import parse_muamalat
from server.parsers.bsi import parse_bsi
from server.excel_writer import generate_excel
from server.coin_manager import calculate_cost # Keeping logic, but will use DB balance

from server.database import engine, Base, get_db
from server.models import User, ConversionRecord, AdminLog, CoinPackage, BroadcastNotification, PendingRegistration
from server.auth import get_password_hash, verify_password, create_access_token, get_current_user, get_admin_user
from server.email_sender import send_otp_email

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
async def read_landing():
    return FileResponse("static/landing.html")

@app.get("/app")
async def read_app():
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
async def register(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    device_fingerprint: str = Form(""),
    db: Session = Depends(get_db)
):
    ip_address = request.client.host
    
    # Check domain
    if not email.endswith("@gmail.com"):
        raise HTTPException(status_code=400, detail="Pendaftaran ditolak: Hanya email dengan domain @gmail.com yang dizinkan.")
    
    # Check if user already exists
    db_user = db.query(User).filter(User.email == email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email sudah terdaftar.")
            
    # Create user with 0 coins and unverified status
    new_user = User(
        email=email,
        hashed_password=get_password_hash(password),
        ip_address=ip_address,
        device_fingerprint=device_fingerprint,
        coins=2,
        email_verified=False
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    access_token = create_access_token(data={"sub": new_user.email})
    return {
        "message": "Registrasi berhasil. Silakan verifikasi email Anda di panel untuk mendapatkan 30 koin gratis!",
        "access_token": access_token,
        "token_type": "bearer",
        "unique_code": new_user.unique_code
    }

@app.post("/api/auth/request-verification")
@limiter.limit("3/minute")
async def request_verification(
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.email_verified:
        raise HTTPException(status_code=400, detail="Email Anda sudah terverifikasi.")
        
    otp = "{:06d}".format(secrets.randbelow(1000000))
    current_user.verification_otp = otp
    current_user.verification_otp_expiry = datetime.utcnow() + timedelta(minutes=15)
    db.commit()
    
    background_tasks.add_task(
        send_otp_email, 
        current_user.email, 
        otp, 
        "Verifikasi Email DataConverter PRO", 
        "verifikasi email Anda"
    )
    
    return {"message": "Kode OTP telah dikirim ke email Anda."}

@app.post("/api/auth/verify-email")
@limiter.limit("5/minute")
async def verify_email(
    request: Request,
    otp: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.email_verified:
        raise HTTPException(status_code=400, detail="Email Anda sudah terverifikasi.")
        
    if not current_user.verification_otp or current_user.verification_otp != otp:
        raise HTTPException(status_code=400, detail="Kode OTP salah.")
        
    if current_user.verification_otp_expiry < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Kode OTP sudah kedaluwarsa.")
        
    # Success: Verify email and add 30 coins
    current_user.email_verified = True
    current_user.coins += 30
    current_user.verification_otp = None
    current_user.verification_otp_expiry = None
    db.commit()
    
    return {"message": "Verifikasi berhasil! 30 koin gratis telah ditambahkan ke akun Anda.", "coins": current_user.coins}

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
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Akun Anda telah dinonaktifkan. Hubungi admin.",
        )
    
    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/api/auth/forgot-password")
@limiter.limit("3/minute")
async def forgot_password(request: Request, background_tasks: BackgroundTasks, email: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email).first()
    if not user:
        # Prevent email enumeration by returning generic success even if not found
        return {"message": "Jika email terdaftar, OTP telah dikirim."}
    
    otp = "".join([str(secrets.randbelow(10)) for _ in range(6)])
    user.reset_otp = otp
    user.reset_otp_expiry = datetime.utcnow() + timedelta(minutes=15)
    db.commit()
    
    from server.email_sender import send_otp_email
    background_tasks.add_task(send_otp_email, user.email, otp)
    
    return {"message": "Jika email terdaftar, OTP telah dikirim."}

@app.post("/api/auth/verify-otp")
@limiter.limit("5/minute")
async def verify_otp(request: Request, email: str = Form(...), otp: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email).first()
    if not user or user.reset_otp != otp:
        raise HTTPException(status_code=400, detail="OTP salah atau tidak cocok.")
    
    if not user.reset_otp_expiry or datetime.utcnow() > user.reset_otp_expiry:
        raise HTTPException(status_code=400, detail="OTP sudah kedaluwarsa.")
        
    return {"message": "OTP valid."}

@app.post("/api/auth/reset-password")
@limiter.limit("3/minute")
async def reset_password(request: Request, email: str = Form(...), otp: str = Form(...), new_password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email).first()
    if not user or user.reset_otp != otp:
        raise HTTPException(status_code=400, detail="OTP salah atau tidak cocok.")
    
    if not user.reset_otp_expiry or datetime.utcnow() > user.reset_otp_expiry:
        raise HTTPException(status_code=400, detail="OTP sudah kedaluwarsa.")
        
    user.hashed_password = get_password_hash(new_password)
    user.reset_otp = None
    user.reset_otp_expiry = None
    db.commit()
    
    return {"message": "Password berhasil diubah. Silakan login."}

@app.get("/api/auth/me")
async def get_me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "coins": current_user.coins,
        "unique_code": current_user.unique_code,
        "is_admin": current_user.is_admin,
        "is_active": current_user.is_active,
        "email_verified": current_user.email_verified,
        "low_balance_warning": current_user.coins < 5
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
        "created_at": r.created_at.isoformat() + "Z"
    } for r in records]

@app.get("/api/balance")
async def get_coin_balance(current_user: User = Depends(get_current_user)):
    return {"balance": current_user.coins}

# --- ADMIN ENDPOINTS ---

def log_admin_action(db: Session, admin_id: int, action: str, target_info: str = None):
    log = AdminLog(admin_id=admin_id, action=action, target_info=target_info)
    db.add(log)

@app.post("/api/admin/create-admin")
async def create_admin(
    email: str = Form(...),
    password: str = Form(...),
    full_name: str = Form(None),
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    db_user = db.query(User).filter(User.email == email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="User dengan email ini sudah terdaftar.")
    
    new_admin = User(
        email=email,
        hashed_password=get_password_hash(password),
        full_name=full_name,
        is_admin=True,
        coins=1000
    )
    db.add(new_admin)
    log_admin_action(db, admin.id, "Buat Admin Baru", email)
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
        "is_active": u.is_active,
        "created_at": u.created_at.isoformat() + "Z"
    } for u in users]

@app.post("/api/admin/add-coins")
async def add_coins(unique_code: str = Form(...), amount: int = Form(...), db: Session = Depends(get_db), admin: User = Depends(get_admin_user)):
    user = db.query(User).filter(User.unique_code == unique_code).first()
    if not user:
        raise HTTPException(status_code=404, detail="User tidak ditemukan dengan kode tersebut.")
    
    user.coins += amount
    log_admin_action(db, admin.id, f"Tambah {amount} koin", user.email)
    db.commit()
    return {"message": f"Berhasil menambahkan {amount} koin ke {user.email}.", "new_balance": user.coins}

# --- DASHBOARD STATS ---

from sqlalchemy import func

@app.get("/api/admin/stats")
async def get_admin_stats(db: Session = Depends(get_db), admin: User = Depends(get_admin_user)):
    total_users = db.query(User).filter(User.is_admin == False).count()
    total_admins = db.query(User).filter(User.is_admin == True).count()
    total_conversions = db.query(ConversionRecord).count()
    
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    conversions_today = db.query(ConversionRecord).filter(ConversionRecord.created_at >= today).count()
    
    first_day_month = today.replace(day=1)
    conversions_month = db.query(ConversionRecord).filter(ConversionRecord.created_at >= first_day_month).count()
    
    total_coins_circulating = db.query(func.sum(User.coins)).filter(User.is_admin == False).scalar() or 0
    
    bank_stats = db.query(ConversionRecord.bank, func.count(ConversionRecord.id)).group_by(ConversionRecord.bank).order_by(func.count(ConversionRecord.id).desc()).all()
    popular_bank = bank_stats[0][0].upper() if bank_stats else "-"
    
    active_users = db.query(User).filter(User.is_admin == False, User.is_active == True).count()
    inactive_users = db.query(User).filter(User.is_admin == False, User.is_active == False).count()
    
    return {
        "total_users": total_users,
        "total_admins": total_admins,
        "total_conversions": total_conversions,
        "conversions_today": conversions_today,
        "conversions_month": conversions_month,
        "total_coins_circulating": total_coins_circulating,
        "popular_bank": popular_bank,
        "active_users": active_users,
        "inactive_users": inactive_users,
        "bank_stats": [{"bank": b[0].upper(), "count": b[1]} for b in bank_stats]
    }

# --- ADMIN LOGS ---

@app.get("/api/admin/logs")
async def get_admin_logs(db: Session = Depends(get_db), admin: User = Depends(get_admin_user)):
    logs = db.query(AdminLog).order_by(AdminLog.created_at.desc()).limit(100).all()
    result = []
    for l in logs:
        admin_user = db.query(User).filter(User.id == l.admin_id).first()
        result.append({
            "id": l.id,
            "admin_email": admin_user.email if admin_user else "Unknown",
            "action": l.action,
            "target_info": l.target_info,
            "created_at": l.created_at.isoformat() + "Z"
        })
    return result

# --- USER MANAGEMENT ---

@app.post("/api/admin/toggle-user/{user_id}")
async def toggle_user(user_id: int, db: Session = Depends(get_db), admin: User = Depends(get_admin_user)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User tidak ditemukan.")
    if user.is_admin:
        raise HTTPException(status_code=400, detail="Tidak bisa mengubah status admin.")
    
    user.is_active = not user.is_active
    status_text = "diaktifkan" if user.is_active else "dinonaktifkan"
    log_admin_action(db, admin.id, f"User {status_text}", user.email)
    db.commit()
    return {"message": f"User {user.email} berhasil {status_text}.", "is_active": user.is_active}

@app.delete("/api/admin/delete-user/{user_id}")
async def delete_user(user_id: int, db: Session = Depends(get_db), admin: User = Depends(get_admin_user)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User tidak ditemukan.")
    if user.is_admin:
        raise HTTPException(status_code=400, detail="Tidak bisa menghapus admin.")
    
    email = user.email
    db.query(ConversionRecord).filter(ConversionRecord.user_id == user_id).delete()
    db.delete(user)
    log_admin_action(db, admin.id, "Hapus User", email)
    db.commit()
    return {"message": f"User {email} berhasil dihapus."}

# --- COIN PACKAGES ---

@app.post("/api/admin/packages")
async def create_package(
    name: str = Form(...),
    coin_amount: int = Form(...),
    price: int = Form(...),
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    pkg = CoinPackage(name=name, coin_amount=coin_amount, price=price)
    db.add(pkg)
    log_admin_action(db, admin.id, "Buat Paket Koin", f"{name} ({coin_amount} koin - Rp{price:,}")
    db.commit()
    return {"message": f"Paket '{name}' berhasil dibuat."}

@app.get("/api/packages")
async def list_packages(db: Session = Depends(get_db)):
    packages = db.query(CoinPackage).filter(CoinPackage.is_active == True).order_by(CoinPackage.price.asc()).all()
    return [{
        "id": p.id,
        "name": p.name,
        "coin_amount": p.coin_amount,
        "price": p.price
    } for p in packages]

@app.delete("/api/admin/packages/{pkg_id}")
async def delete_package(pkg_id: int, db: Session = Depends(get_db), admin: User = Depends(get_admin_user)):
    pkg = db.query(CoinPackage).filter(CoinPackage.id == pkg_id).first()
    if not pkg:
        raise HTTPException(status_code=404, detail="Paket tidak ditemukan.")
    name = pkg.name
    db.delete(pkg)
    log_admin_action(db, admin.id, "Hapus Paket Koin", name)
    db.commit()
    return {"message": f"Paket '{name}' berhasil dihapus."}

# --- BROADCAST NOTIFICATIONS ---

@app.post("/api/admin/broadcast")
async def create_broadcast(
    title: str = Form(...),
    message: str = Form(...),
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    notif = BroadcastNotification(admin_id=admin.id, title=title, message=message)
    db.add(notif)
    log_admin_action(db, admin.id, "Kirim Broadcast", title)
    db.commit()
    return {"message": "Notifikasi broadcast berhasil dikirim."}

@app.get("/api/admin/broadcasts")
async def list_broadcasts(db: Session = Depends(get_db), admin: User = Depends(get_admin_user)):
    notifs = db.query(BroadcastNotification).order_by(BroadcastNotification.created_at.desc()).limit(50).all()
    return [{
        "id": n.id,
        "title": n.title,
        "message": n.message,
        "created_at": n.created_at.isoformat() + "Z"
    } for n in notifs]

@app.get("/api/notifications")
async def get_notifications(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Return latest 5 broadcast notifications from the last 7 days
    week_ago = datetime.utcnow() - timedelta(days=7)
    notifs = db.query(BroadcastNotification).filter(BroadcastNotification.created_at >= week_ago).order_by(BroadcastNotification.created_at.desc()).limit(5).all()
    return [{
        "id": n.id,
        "title": n.title,
        "message": n.message,
        "created_at": n.created_at.isoformat() + "Z"
    } for n in notifs]

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


