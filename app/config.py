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
