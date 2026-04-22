import smtplib
from email.message import EmailMessage
import os

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", 465))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
SMTP_FROM = os.getenv("SMTP_FROM", "noreply@dataconverter.pro")

def send_otp_email(to_email: str, otp: str):
    subject = "Reset Password DataConverter PRO"
    body = f"""Halo,

Berikut adalah kode OTP untuk pengaturan ulang password Anda:

{otp}

Kode ini hanya berlaku selama 15 menit. Jika Anda tidak meminta pengaturan ulang password, abaikan pesan ini.

Tim DataConverter PRO"""
    
    if SMTP_HOST and SMTP_USER and SMTP_PASS:
        try:
            msg = EmailMessage()
            msg.set_content(body)
            msg['Subject'] = subject
            msg['From'] = SMTP_FROM
            msg['To'] = to_email

            # Use SMTP_SSL (port 465) for faster direct connection
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=10) as server:
                server.login(SMTP_USER, SMTP_PASS)
                server.send_message(msg)
            print(f"Email OTP dikirim ke {to_email}")
        except Exception as e:
            print(f"Gagal mengirim email: {str(e)}")
            print(f"Fallback MOCK EMAIL - OTP untuk {to_email}: {otp}")
    else:
        print(f"--- MOCK EMAIL ---")
        print(f"To: {to_email}")
        print(f"OTP: {otp}")
        print(f"------------------")
