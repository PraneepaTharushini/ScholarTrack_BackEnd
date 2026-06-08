from functools import wraps
from datetime import datetime, timedelta
from secrets import randbelow

from flask import current_app, request
from werkzeug.security import check_password_hash, generate_password_hash

from app.auth import auth_bp
from app.extensions import db
from app.models import PasswordResetCode, User
from app.utils.email import send_password_reset_email
from app.utils.security import create_auth_token, validate_password, verify_auth_token


def role_for_email(email):
    if email in current_app.config.get("ADMIN_EMAILS", set()):
        return "admin"
    return "student"


def token_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        token = auth_header.strip()
        if token.startswith("Bearer "):
            token = token[7:].strip()

        if not token:
            return {"error": "Authorization token is required."}, 401

        user_id = verify_auth_token(current_app, token)
        if not user_id:
            return {"error": "Invalid or expired token."}, 401

        user = db.session.get(User, user_id)
        if not user:
            return {"error": "User not found."}, 404

        return view(user, *args, **kwargs)

    return wrapped


@auth_bp.post("/register")
def register():
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""
    confirm_password = payload.get("confirm_password") or payload.get("confirmPassword") or ""

    if not name or not email or not password or not confirm_password:
        return {"error": "Name, email, password, and confirm password are required."}, 400

    if password != confirm_password:
        return {"error": "Passwords do not match."}, 400

    is_valid, message = validate_password(password)
    if not is_valid:
        return {"error": message}, 400

    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        return {"error": "Email is already registered."}, 409

    user = User(
        name=name,
        email=email,
        password_hash=generate_password_hash(password),
        role=role_for_email(email),
    )
    db.session.add(user)
    db.session.commit()

    token = create_auth_token(current_app, user.id)

    return {
        "message": "Registration successful",
        "token": token,
        "user": user.to_public_dict(),
    }, 201


@auth_bp.post("/login")
def login():
    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""

    if not email or not password:
        return {"error": "Email and password are required."}, 400

    user = User.query.filter_by(email=email).first()
    if not user or not check_password_hash(user.password_hash, password):
        return {"error": "Invalid email or password."}, 401

    updated_role = role_for_email(email)
    if user.role != updated_role:
        user.role = updated_role
        db.session.commit()

    token = create_auth_token(current_app, user.id)

    return {
        "message": "Login successful",
        "token": token,
        "user": user.to_public_dict(),
    }, 200


@auth_bp.post("/forgot-password")
def forgot_password():
    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or "").strip().lower()

    if not email:
        return {"error": "Email is required."}, 400

    user = User.query.filter_by(email=email).first()
    if not user:
        return {"error": "No account was found for that email."}, 404

    code = f"{randbelow(1000000):06d}"
    PasswordResetCode.query.filter_by(user_id=user.id, used_at=None).update({
        "used_at": datetime.utcnow(),
    })
    reset_code = PasswordResetCode(
        user_id=user.id,
        code_hash=generate_password_hash(code),
        expires_at=datetime.utcnow() + timedelta(minutes=5),
    )
    db.session.add(reset_code)
    db.session.commit()

    email_sent = send_password_reset_email(current_app, email, code)
    response = {"message": "A password reset confirmation code has been sent to your email."}
    if not email_sent and current_app.config.get("FLASK_ENV") == "development":
        response["message"] = "Email is not configured. Use the development reset code to continue."
        response["dev_code"] = code
    elif not email_sent:
        return {"error": "Email service is not configured. Please contact the system administrator."}, 503

    return response, 200


@auth_bp.post("/reset-password")
def reset_password():
    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or "").strip().lower()
    code = (payload.get("code") or "").strip()
    password = payload.get("password") or ""
    confirm_password = payload.get("confirm_password") or payload.get("confirmPassword") or ""

    if not email or not code or not password or not confirm_password:
        return {"error": "Email, confirmation code, password, and confirm password are required."}, 400

    if password != confirm_password:
        return {"error": "Passwords do not match."}, 400

    is_valid, message = validate_password(password)
    if not is_valid:
        return {"error": message}, 400

    user = User.query.filter_by(email=email).first()
    if not user:
        return {"error": "No account was found for that email."}, 404

    reset_code = (
        PasswordResetCode.query
        .filter_by(user_id=user.id, used_at=None)
        .order_by(PasswordResetCode.created_at.desc())
        .first()
    )
    if not reset_code or reset_code.expires_at < datetime.utcnow():
        return {"error": "Confirmation code is invalid or expired."}, 400

    if not check_password_hash(reset_code.code_hash, code):
        return {"error": "Confirmation code is invalid or expired."}, 400

    user.password_hash = generate_password_hash(password)
    reset_code.used_at = datetime.utcnow()
    db.session.commit()

    return {"message": "Password reset successful. Please sign in."}, 200


@auth_bp.get("/me")
@token_required
def me(user):
    return {"user": user.to_public_dict()}, 200
