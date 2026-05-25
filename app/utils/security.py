from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from typing import Optional, Tuple


def validate_password(password: str) -> Tuple[bool, str]:
    if not password:
        return False, "Password is required."
    if len(password) < 6:
        return False, "Password must be at least 6 characters."
    return True, ""


def create_auth_token(app, user_id: int) -> str:
    serializer = URLSafeTimedSerializer(app.config["SECRET_KEY"])
    return serializer.dumps({"user_id": user_id}, salt="auth-token")


def verify_auth_token(app, token: str, max_age: int = 60 * 60 * 24 * 7) -> Optional[int]:
    serializer = URLSafeTimedSerializer(app.config["SECRET_KEY"])
    try:
        data = serializer.loads(token, salt="auth-token", max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None

    return data.get("user_id")
