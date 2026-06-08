import smtplib
from email.message import EmailMessage


def send_password_reset_email(app, recipient_email: str, code: str) -> bool:
    smtp_host = app.config.get("SMTP_HOST")
    smtp_username = app.config.get("SMTP_USERNAME")
    smtp_password = app.config.get("SMTP_PASSWORD")
    from_email = app.config.get("SMTP_FROM_EMAIL") or smtp_username

    if not smtp_host or not smtp_username or not smtp_password or not from_email:
        return False

    message = EmailMessage()
    message["Subject"] = "Scholar Track password reset code"
    message["From"] = from_email
    message["To"] = recipient_email
    message.set_content(
        "Use this confirmation code to reset your Scholar Track password:\n\n"
        f"{code}\n\n"
        "This code expires in 5 minutes. If you did not request this, you can ignore this email."
    )

    try:
        with smtplib.SMTP(smtp_host, app.config.get("SMTP_PORT", 587), timeout=20) as server:
            if app.config.get("SMTP_USE_TLS", True):
                server.starttls()
            server.login(smtp_username, smtp_password)
            server.send_message(message)
    except OSError:
        return False

    return True
