from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
import secrets
from server.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    coins = Column(Integer, default=30)  # Initial 30 coins as requested
    unique_code = Column(String, unique=True, index=True)
    is_admin = Column(Boolean, default=False)
    full_name = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

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
