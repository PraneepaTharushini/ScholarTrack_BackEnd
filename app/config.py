import os


class Config:
    def __init__(self) -> None:
        self.SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")
        self.SQLALCHEMY_DATABASE_URI = os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg2://postgres:postgres@localhost:5432/scholar_track",
        )
        self.SQLALCHEMY_TRACK_MODIFICATIONS = False
        self.CREATE_DB_ON_START = os.getenv("CREATE_DB_ON_START", "0") == "1"
