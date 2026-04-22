import smtplib
from email.message import EmailMessage
import os

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", 465))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
SMTP_FROM = os.getenv("SMTP_FROM", "noreply@dataconverter.pro")

def send_otp_email(to_email: str, otp: str, subject: str = "Reset Password DataConverter PRO", context: str = "pengaturan ulang password"):
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            .email-container {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background-color: #0f172a;
                color: #f8fafc;
                padding: 40px 20px;
                max-width: 600px;
                margin: 0 auto;
            }}
            .card {{
                background-color: #1e293b;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 16px;
                padding: 32px;
                text-align: center;
                box-shadow: 0 10px 25px rgba(0, 0, 0, 0.2);
            }}
            .logo {{
                color: #10b981;
                font-size: 24px;
                font-weight: bold;
                margin-bottom: 24px;
                display: block;
                text-decoration: none;
            }}
            h1 {{
                font-size: 20px;
                margin-bottom: 16px;
                color: #f8fafc;
            }}
            p {{
                color: #94a3b8;
                line-height: 1.6;
                margin-bottom: 24px;
            }}
            .otp-code {{
                font-size: 36px;
                font-weight: 800;
                color: #10b981;
                letter-spacing: 8px;
                padding: 16px;
                background: rgba(16, 185, 129, 0.1);
                border-radius: 12px;
                display: inline-block;
                margin: 20px 0;
                border: 1px dashed rgba(16, 185, 129, 0.3);
            }}
            .footer {{
                margin-top: 32px;
                font-size: 12px;
                color: #64748b;
                text-align: center;
            }}
            .divider {{
                height: 1px;
                background: rgba(255, 255, 255, 0.05);
                margin: 24px 0;
            }}
        </style>
    </head>
    <body style="margin: 0; padding: 0; background-color: #0f172a;">
        <div class="email-container">
            <div class="card">
                <a href="https://dataconverter.pro" class="logo">DataConverter PRO</a>
                <h1>Kode Keamanan Anda</h1>
                <p>Halo,<br>Berikut adalah kode OTP untuk <strong>{context}</strong> akun Anda. Silakan masukkan kode ini di aplikasi untuk melanjutkan.</p>
                <div class="otp-code">{otp}</div>
                <div class="divider"></div>
                <p style="font-size: 13px; margin-bottom: 0;">Kode ini hanya berlaku selama <strong>15 menit</strong>.<br>Jika Anda tidak merasa melakukan permintaan ini, abaikan pesan ini.</p>
            </div>
            <div class="footer">
                &copy; 2026 DataConverter PRO. All rights reserved.<br>
                Solusi konversi mutasi bank tercepat & teraman.
            </div>
        </div>
    </body>
    </html>
    """
    
    text_body = f"Halo, berikut adalah kode OTP untuk {context} Anda:\n\n{otp}\n\nKode ini berlaku 15 menit.\n\nTim DataConverter PRO"
    
    if SMTP_HOST and SMTP_USER and SMTP_PASS:
        try:
            msg = EmailMessage()
            msg['Subject'] = subject
            msg['From'] = SMTP_FROM
            msg['To'] = to_email
            msg.set_content(text_body)
            msg.add_alternative(html_body, subtype='html')

            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=10) as server:
                server.login(SMTP_USER, SMTP_PASS)
                server.send_message(msg)
            print(f"Email HTML OTP dikirim ke {to_email}")
        except Exception as e:
            print(f"Gagal mengirim email: {str(e)}")
            print(f"Fallback MOCK EMAIL - OTP untuk {to_email}: {otp}")
    else:
        print(f"--- MOCK EMAIL ---")
        print(f"To: {to_email}")
        print(f"OTP: {otp}")
        print(f"------------------")
