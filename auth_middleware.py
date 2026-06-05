import os
import jwt
from functools import wraps
from flask import request, jsonify
from dotenv import load_dotenv

load_dotenv()

JWT_SECRET = os.getenv("JWT_SECRET")


def require_auth(f):
    """Decorator: verify JWT Bearer token and attach user to request."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")

        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Unauthorized — no token provided"}), 401

        token = auth_header.split(" ")[1]

        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
            request.user = payload  # { "id": ..., "email": ... }
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Unauthorized — token has expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Unauthorized — invalid token"}), 401

        return f(*args, **kwargs)

    return decorated
