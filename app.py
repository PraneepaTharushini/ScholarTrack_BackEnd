import os
from flask import Flask, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

from database import migrate
from routes_auth import auth_bp
from routes_tasks import tasks_bp
from routes_analytics import analytics_bp
from routes_notifications import notifications_bp
from routes_admin import admin_bp

load_dotenv()

# ── App factory ───────────────────────────────────────────────
app = Flask(__name__)

CORS(app, origins=[
    "http://localhost:5173",
    "http://localhost:3000",
    "http://localhost:4173",
    # allow file:// based HTML pages (Scholar_Track frontend)
    "null",
], supports_credentials=True)

# ── Register blueprints ───────────────────────────────────────
app.register_blueprint(auth_bp,           url_prefix="/api/auth")
app.register_blueprint(tasks_bp,          url_prefix="/api/tasks")
app.register_blueprint(analytics_bp,     url_prefix="/api/analytics")

# Notifications & Reminders  →  /api/notifications  +  /api/reminders
app.register_blueprint(notifications_bp,  url_prefix="/api/notifications")
app.register_blueprint(notifications_bp,  url_prefix="/api/reminders",
                        name="reminders")

# Admin & System  →  /api/users  +  /api/system  +  /api/activity-logs
app.register_blueprint(admin_bp,          url_prefix="/api")

# ── Health check ──────────────────────────────────────────────
@app.route("/api/health")
def health():
    from datetime import datetime, timezone
    return jsonify({
        "status":    "ok",
        "service":   "Scholar Track API (Flask)",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

# ── 404 handler ───────────────────────────────────────────────
@app.errorhandler(404)
def not_found(_):
    return jsonify({"error": "Route not found"}), 404

# ── 500 handler ───────────────────────────────────────────────
@app.errorhandler(Exception)
def server_error(e):
    print("Unhandled error:", e)
    return jsonify({"error": "Internal server error"}), 500


# ── Entry point ───────────────────────────────────────────────
if __name__ == "__main__":
    print("Running database migrations...")
    migrate()

    PORT = int(os.getenv("PORT", 3000))
    print(f"\n[OK] Scholar Track API (Flask) running at http://localhost:{PORT}")
    print(f"   Health:         GET  /api/health")
    print(f"   Auth:           POST /api/auth/register | /login   GET /me")
    print(f"   Tasks:          GET/POST/PUT/DELETE /api/tasks")
    print(f"   Analytics:      GET  /api/analytics/summary | /status | /categories")
    print(f"   Notifications:  GET/POST/PATCH/DELETE /api/notifications")
    print(f"   Reminders:      GET/PATCH /api/reminders/preferences | /deadlines")
    print(f"   Users (admin):  GET/POST/PUT/DELETE /api/users")
    print(f"   System:         GET  /api/system/health | /metrics | /ocr-stats | /modules")
    print(f"   Activity Logs:  GET/POST /api/activity-logs\n")

    app.run(host="0.0.0.0", port=PORT, debug=True)
