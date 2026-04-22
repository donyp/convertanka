from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
import secrets
from server.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    coins = Column(Integer, default=30)
    unique_code = Column(String, unique=True, index=True)
    is_admin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    full_name = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    reset_otp = Column(String, nullable=True)
    reset_otp_expiry = Column(DateTime, nullable=True)
    ip_address = Column(String, nullable=True)
    device_fingerprint = Column(String, index=True, nullable=True)
    email_verified = Column(Boolean, default=False)
    verification_otp = Column(String, nullable=True)
    verification_otp_expiry = Column(DateTime, nullable=True)

    # Relationships
    records = relationship("ConversionRecord", back_populates="owner")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.unique_code:
            self.unique_code = f"MC-{secrets.token_hex(4).upper()}"

class ConversionRecord(Base):
    __tablename__ = "conversion_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    bank = Column(String)
    filename = Column(String)
    page_count = Column(Integer)
    coin_cost = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    owner = relationship("User", back_populates="records")

class AdminLog(Base):
    __tablename__ = "admin_logs"

    id = Column(Integer, primary_key=True, index=True)
    admin_id = Column(Integer, ForeignKey("users.id"))
    action = Column(String, nullable=False)
    target_info = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    admin = relationship("User")

class CoinPackage(Base):
    __tablename__ = "coin_packages"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    coin_amount = Column(Integer, nullable=False)
    price = Column(Integer, nullable=False)  # in IDR
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class BroadcastNotification(Base):
    __tablename__ = "broadcast_notifications"

    id = Column(Integer, primary_key=True, index=True)
    admin_id = Column(Integer, ForeignKey("users.id"))
    title = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    admin = relationship("User")

class PendingRegistration(Base):
    __tablename__ = "pending_registrations"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    ip_address = Column(String, nullable=True)
    device_fingerprint = Column(String, nullable=True)
    otp = Column(String, nullable=False)
    otp_expiry = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
