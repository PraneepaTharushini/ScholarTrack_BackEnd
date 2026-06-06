from functools import wraps

from flask import current_app, request
from werkzeug.security import check_password_hash, generate_password_hash

from app.auth import auth_bp
from app.extensions import db
from app.models import User
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
    password = payload.get("password") or ""
    confirm_password = payload.get("confirm_password") or payload.get("confirmPassword") or ""

    if not email or not password or not confirm_password:
        return {"error": "Email, password, and confirm password are required."}, 400

    if password != confirm_password:
        return {"error": "Passwords do not match."}, 400

    is_valid, message = validate_password(password)
    if not is_valid:
        return {"error": message}, 400

    user = User.query.filter_by(email=email).first()
    if not user:
        return {"error": "No account was found for that email."}, 404

    user.password_hash = generate_password_hash(password)
    db.session.commit()

    return {"message": "Password reset successful. Please sign in."}, 200


@auth_bp.get("/me")
@token_required
def me(user):
    return {"user": user.to_public_dict()}, 200
