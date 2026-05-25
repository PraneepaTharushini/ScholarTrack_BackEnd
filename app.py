import os
from flask import Flask, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

from database import migrate
from routes_auth import auth_bp
from routes_tasks import tasks_bp
from routes_analytics import analytics_bp

load_dotenv()

# ── App factory ───────────────────────────────────────────────
app = Flask(__name__)

CORS(app, origins=[
    "http://localhost:5173",
    "http://localhost:3000",
    "http://localhost:4173",
], supports_credentials=True)

# ── Register blueprints ───────────────────────────────────────
app.register_blueprint(auth_bp,      url_prefix="/api/auth")
app.register_blueprint(tasks_bp,     url_prefix="/api/tasks")
app.register_blueprint(analytics_bp, url_prefix="/api/analytics")

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

    PORT = int(os.getenv("PORT", 5000))
    print(f"\nScholar Track API (Flask) running at http://localhost:{PORT}")
    print(f"   Health:    GET  /api/health")
    print(f"   Auth:      POST /api/auth/register | /login  GET /me")
    print(f"   Tasks:     GET/POST/PUT/DELETE /api/tasks")
    print(f"   Analytics: GET  /api/analytics/summary | /status | /categories | /insights | /timeline\n")

    app.run(host="0.0.0.0", port=PORT, debug=True)
