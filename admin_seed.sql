-- ============================================================
-- Create 1 admin account for MutasiConvert
-- Password: admin123  (ganti setelah login!)
-- ============================================================

INSERT INTO users (
    email,
    hashed_password,
    coins,
    unique_code,
    is_admin,
    is_active,
    email_verified,
    full_name
)
VALUES (
    'admin@mutasiconvert.com',
    '$pbkdf2-sha256$29000$qjWG0BrDGOPce09JyblXig$W8F7GU9Zs.tCXuEw9j47d2b/.c.ESZPtxbiTuRJGPNg',
    9999,
    'MC-ADMIN001',
    TRUE,
    TRUE,
    TRUE,
    'Administrator'
)
ON CONFLICT (email) DO NOTHING;

-- Verifikasi
SELECT id, email, is_admin, coins, unique_code FROM users WHERE email = 'admin@mutasiconvert.com';
