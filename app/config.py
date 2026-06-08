import os


class Config:
    def __init__(self) -> None:
        self.SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")
        self.ADMIN_EMAILS = {
            email.strip().lower()
            for email in os.getenv("ADMIN_EMAILS", "").split(",")
            if email.strip()
        }
        self.SQLALCHEMY_DATABASE_URI = os.getenv(
            "DATABASE_URL",
            "sqlite:///scholar_track.db",
        )
        self.SQLALCHEMY_TRACK_MODIFICATIONS = False
        self.CREATE_DB_ON_START = os.getenv("CREATE_DB_ON_START", "0") == "1"
        self.SMTP_HOST = os.getenv("SMTP_HOST", "")
        self.SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
        self.SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
        self.SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
        self.SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", self.SMTP_USERNAME)
        self.SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "1") == "1"
