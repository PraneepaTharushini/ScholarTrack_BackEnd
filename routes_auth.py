import os
import jwt
import bcrypt
import traceback
from flask import Blueprint, request, jsonify
from datetime import datetime, timezone, timedelta
from database import get_connection
from auth_middleware import require_auth
from dotenv import load_dotenv

load_dotenv()

JWT_SECRET = os.getenv("JWT_SECRET")

auth_bp = Blueprint("auth", __name__)


def make_token(user_id, email):
    payload = {
        "id": user_id,
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


# ── POST /api/auth/register ──────────────────────────────────
@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json() or {}
    name     = (data.get("name") or "").strip()
    email    = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not name or not email or not password:
        return jsonify({"error": "Name, email and password are required"}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400
    if "@" not in email:
        return jsonify({"error": "Invalid email format"}), 400

    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cur.fetchone():
            return jsonify({"error": "An account with this email already exists"}), 409

        password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        cur.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (%s, %s, %s) RETURNING id, name, email",
            (name, email, password_hash),
        )
        user = cur.fetchone()
        conn.commit()

        token = make_token(user["id"], user["email"])
        return jsonify({
            "token": token,
            "user":  {"id": user["id"], "name": user["name"], "email": user["email"]},
        }), 201

    except Exception as e:
        conn.rollback()
        traceback.print_exc()
        print("Register error:", e)
        return jsonify({"error": "Server error during registration"}), 500
    finally:
        cur.close()
        conn.close()


# ── POST /api/auth/login ─────────────────────────────────────
@auth_bp.route("/login", methods=["POST"])
def login():
    data     = request.get_json() or {}
    email    = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cur.fetchone()

        if not user:
            return jsonify({"error": "Invalid email or password"}), 401

        if not bcrypt.checkpw(password.encode(), user["password_hash"].encode()):
            return jsonify({"error": "Invalid email or password"}), 401

        token = make_token(user["id"], user["email"])
        return jsonify({
            "token": token,
            "user":  {"id": user["id"], "name": user["name"], "email": user["email"]},
        })

    except Exception as e:
        traceback.print_exc()
        print("Login error:", e)
        return jsonify({"error": "Server error during login"}), 500
    finally:
        cur.close()
        conn.close()


# ── GET /api/auth/me ─────────────────────────────────────────
@auth_bp.route("/me", methods=["GET"])
@require_auth
def me():
    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute(
            "SELECT id, name, email, created_at FROM users WHERE id = %s",
            (request.user["id"],),
        )
        user = cur.fetchone()
        if not user:
            return jsonify({"error": "User not found"}), 404
        return jsonify({"user": dict(user)})
    except Exception as e:
        traceback.print_exc()
        print("Me error:", e)
        return jsonify({"error": "Server error"}), 500
    finally:
        cur.close()
        conn.close()