"""DB-backed rate limiting (works across serverless instances, unlike slowapi's memory storage)."""

from datetime import datetime, timedelta

from fastapi import HTTPException, Request
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError

from server.models import RateLimitEntry


def get_client_ip(request: Request) -> str:
    # On Vercel the leftmost X-Forwarded-For value is the real client IP
    # (the proxy appends to any client-supplied header, so it can't be spoofed).
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def check_rate_limit(db, key: str, limit: int, window_seconds: int) -> bool:
    """Increments the counter for `key` and returns True if still within limit."""
    now = datetime.utcnow()
    cutoff = now - timedelta(seconds=window_seconds)

    db.query(RateLimitEntry).filter(
        RateLimitEntry.key == key,
        RateLimitEntry.window_start < cutoff,
    ).delete(synchronize_session=False)
    db.commit()

    result = db.execute(
        update(RateLimitEntry)
        .where(RateLimitEntry.key == key)
        .values(count=RateLimitEntry.count + 1)
    )
    if result.rowcount == 0:
        db.add(RateLimitEntry(key=key, window_start=now, count=1))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            db.execute(
                update(RateLimitEntry)
                .where(RateLimitEntry.key == key)
                .values(count=RateLimitEntry.count + 1)
            )
            db.commit()
    else:
        db.commit()

    entry = db.query(RateLimitEntry).filter(RateLimitEntry.key == key).first()
    return entry.count <= limit


def enforce_rate_limit(db, key: str, limit: int, window_seconds: int):
    if not check_rate_limit(db, key, limit, window_seconds):
        raise HTTPException(
            status_code=429,
            detail="Terlalu banyak percobaan. Silakan coba lagi nanti.",
        )
