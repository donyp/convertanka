-- ============================================================
-- MutasiConvert - Supabase (PostgreSQL) Migration Script
-- Re-create full database schema (tables, indexes, constraints)
-- Run this in Supabase SQL Editor (new project) before starting app.
-- ============================================================

-- Optional: clean slate (UNCOMMENT only if you want to drop existing)
-- DROP TABLE IF EXISTS coin_purchases CASCADE;
-- DROP TABLE IF EXISTS broadcast_notifications CASCADE;
-- DROP TABLE IF EXISTS admin_logs CASCADE;
-- DROP TABLE IF EXISTS conversion_records CASCADE;
-- DROP TABLE IF EXISTS pending_registrations CASCADE;
-- DROP TABLE IF EXISTS coin_packages CASCADE;
-- DROP TABLE IF EXISTS users CASCADE;

-- 1. users
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email VARCHAR NOT NULL UNIQUE,
    hashed_password VARCHAR NOT NULL,
    coins INTEGER DEFAULT 30,
    unique_code VARCHAR UNIQUE,
    is_admin BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    full_name VARCHAR,
    created_at TIMESTAMP DEFAULT now(),
    reset_otp VARCHAR,
    reset_otp_expiry TIMESTAMP,
    ip_address VARCHAR,
    device_fingerprint VARCHAR,
    email_verified BOOLEAN DEFAULT FALSE,
    verification_otp VARCHAR,
    verification_otp_expiry TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_users_email ON users (email);
CREATE INDEX IF NOT EXISTS ix_users_unique_code ON users (unique_code);
CREATE INDEX IF NOT EXISTS ix_users_device_fingerprint ON users (device_fingerprint);

-- 2. conversion_records
CREATE TABLE IF NOT EXISTS conversion_records (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users (id) ON DELETE CASCADE,
    bank VARCHAR,
    filename VARCHAR,
    page_count INTEGER,
    coin_cost INTEGER,
    created_at TIMESTAMP DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_conversion_records_user_id ON conversion_records (user_id);

-- 3. admin_logs
CREATE TABLE IF NOT EXISTS admin_logs (
    id SERIAL PRIMARY KEY,
    admin_id INTEGER REFERENCES users (id) ON DELETE SET NULL,
    action VARCHAR NOT NULL,
    target_info VARCHAR,
    created_at TIMESTAMP DEFAULT now()
);

-- 4. coin_packages
CREATE TABLE IF NOT EXISTS coin_packages (
    id SERIAL PRIMARY KEY,
    name VARCHAR NOT NULL,
    coin_amount INTEGER NOT NULL,
    price INTEGER NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT now()
);

-- 5. coin_purchases
CREATE TABLE IF NOT EXISTS coin_purchases (
    id SERIAL PRIMARY KEY,
    order_number VARCHAR UNIQUE,
    user_id INTEGER REFERENCES users (id) ON DELETE CASCADE,
    package_id INTEGER REFERENCES coin_packages (id) ON DELETE SET NULL,
    buyer_name VARCHAR NOT NULL,
    buyer_phone VARCHAR NOT NULL,
    buyer_unique_code VARCHAR,
    payment_method VARCHAR NOT NULL,
    package_name VARCHAR NOT NULL,
    coin_amount INTEGER NOT NULL,
    price INTEGER NOT NULL,
    status VARCHAR DEFAULT 'pending',
    proof_filename VARCHAR,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_coin_purchases_order_number ON coin_purchases (order_number);
CREATE INDEX IF NOT EXISTS ix_coin_purchases_user_id ON coin_purchases (user_id);

-- 6. broadcast_notifications
CREATE TABLE IF NOT EXISTS broadcast_notifications (
    id SERIAL PRIMARY KEY,
    admin_id INTEGER REFERENCES users (id) ON DELETE SET NULL,
    title VARCHAR NOT NULL,
    message TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT now()
);

-- 7. pending_registrations
CREATE TABLE IF NOT EXISTS pending_registrations (
    id SERIAL PRIMARY KEY,
    email VARCHAR NOT NULL,
    hashed_password VARCHAR NOT NULL,
    ip_address VARCHAR,
    device_fingerprint VARCHAR,
    otp VARCHAR NOT NULL,
    otp_expiry TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_pending_registrations_email ON pending_registrations (email);

-- ============================================================
-- Optional seed: default admin user (password: admin123)
-- Ganti hash sesuai kebutuhan (bcrypt). Gunakan create_admin.py bila ada.
-- INSERT INTO users (email, hashed_password, is_admin, coins, email_verified)
-- VALUES ('admin@gmail.com', '<bcrypt_hash>', TRUE, 1000, TRUE);
-- ============================================================
