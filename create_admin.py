from server.database import SessionLocal
from server.models import User
from server.auth import get_password_hash

def create_admin():
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.is_admin == True).first()
        if admin:
            print(f"Admin already exists: {admin.email}")
            return
        
        # Create a default admin if none exists
        new_admin = User(
            email="admin@mutasiconvert.com",
            hashed_password=get_password_hash("admin123"),
            is_admin=True,
            coins=9999
        )
        db.add(new_admin)
        db.commit()
        print("Default admin created: admin@mutasiconvert.com / admin123")
    finally:
        db.close()

if __name__ == "__main__":
    create_admin()
