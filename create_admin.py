import os
import secrets

from server.database import SessionLocal
from server.models import User
from server.auth import get_password_hash

def create_admin():
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.is_admin == True).first()
        if admin:
            print(f"Admin sudah ada: {admin.email}")
            return

        email = os.getenv("ADMIN_EMAIL", "admin@mutasiconvert.com")
        password = os.getenv("ADMIN_PASSWORD") or secrets.token_urlsafe(16)

        new_admin = User(
            email=email,
            hashed_password=get_password_hash(password),
            is_admin=True,
            coins=9999
        )
        db.add(new_admin)
        db.commit()

        print(f"Admin dibuat: {email}")
        if os.getenv("ADMIN_PASSWORD"):
            print("Password diambil dari environment variable ADMIN_PASSWORD.")
        else:
            print(f"Password (acak, simpan sekarang): {password}")
    finally:
        db.close()

if __name__ == "__main__":
    create_admin()
