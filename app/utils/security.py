import base64
import binascii
import hashlib
import hmac
import json
import time
from typing import Optional, Tuple


def validate_password(password: str) -> Tuple[bool, str]:
    if not password:
        return False, "Password is required."
    if len(password) < 6:
        return False, "Password must be at least 6 characters."
    return True, ""


def _base64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _base64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(f"{data}{padding}".encode("ascii"))


def _json_dumps(data: dict) -> bytes:
    return json.dumps(data, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _sign(message: str, secret: str) -> str:
    signature = hmac.new(secret.encode("utf-8"), message.encode("ascii"), hashlib.sha256).digest()
    return _base64url_encode(signature)


def create_auth_token(app, user_id: int) -> str:
    now = int(time.time())
    expires_in = int(app.config.get("JWT_EXPIRATION_SECONDS", 60 * 60 * 24))
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + expires_in,
    }

    encoded_header = _base64url_encode(_json_dumps(header))
    encoded_payload = _base64url_encode(_json_dumps(payload))
    signing_input = f"{encoded_header}.{encoded_payload}"
    return f"{signing_input}.{_sign(signing_input, app.config['SECRET_KEY'])}"


def verify_auth_token(app, token: str) -> Optional[int]:
    try:
        encoded_header, encoded_payload, signature = token.split(".")
        signing_input = f"{encoded_header}.{encoded_payload}"
        expected_signature = _sign(signing_input, app.config["SECRET_KEY"])
        if not hmac.compare_digest(signature, expected_signature):
            return None

        header = json.loads(_base64url_decode(encoded_header))
        if header.get("alg") != "HS256" or header.get("typ") != "JWT":
            return None

        data = json.loads(_base64url_decode(encoded_payload))
        if int(data.get("exp", 0)) <= int(time.time()):
            return None

        return int(data.get("sub"))
    except (ValueError, TypeError, binascii.Error, json.JSONDecodeError):
        return None
