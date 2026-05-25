import os

from flask import Flask

from app.config import Config
from app.extensions import db
from app.auth.routes import auth_bp


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config())

    db.init_app(app)

    app.register_blueprint(auth_bp, url_prefix="/api/auth")

    if app.config.get("CREATE_DB_ON_START"):
        with app.app_context():
            db.create_all()

    @app.get("/health")
    def health_check():
        return {"status": "ok"}, 200

    return app
