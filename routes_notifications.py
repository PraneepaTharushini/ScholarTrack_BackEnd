"""
routes_notifications.py
Endpoints consumed by notifications.html

GET    /api/notifications                    - list notifications for a user (or all)
DELETE /api/notifications/<id>              - dismiss / delete a notification
PATCH  /api/notifications/mark-all-read     - mark every notification as read
PATCH  /api/notifications/<id>/read         - mark a single notification as read
POST   /api/notifications                   - create a notification (internal / admin)

GET    /api/reminders/preferences           - list reminder toggle settings
PATCH  /api/reminders/preferences/<key>     - toggle a reminder preference

GET    /api/reminders/deadlines             - upcoming deadlines panel"""

from flask import Blueprint, request, jsonify
from datetime import datetime, timezone
from database import get_connection

notifications_bp = Blueprint("notifications", __name__)


# ── helpers ────────────────────────────────────────────────────────────────

DEFAULT_PREFS = [
    {
        "pref_key":    "deadline_24h",
        "label":       "24-Hour Deadline Alert",
        "description": "Notify me 24 hours before a task is due",
    },
    {
        "pref_key":    "deadline_1h",
        "label":       "1-Hour Reminder",
        "description": "Alert me 1 hour before deadline",
    },
    {
        "pref_key":    "ai_suggestions",
        "label":       "AI Study Suggestions",
        "description": "Receive AI-powered study schedule recommendations",
    },
    {
        "pref_key":    "task_created",
        "label":       "New Task Extracted",
        "description": "Notify when OCR extracts a new task",
    },
    {
        "pref_key":    "weekly_summary",
        "label":       "Weekly Progress Summary",
        "description": "Send a weekly academic progress digest",
    },
    {
        "pref_key":    "email_alerts",
        "label":       "Email Notifications",
        "description": "Forward urgent alerts to your email",
    },
]

SAMPLE_NOTIFICATIONS = [
    {
        "title":   "Database Project Due Tomorrow!",
        "message": "Your CS3042 Database Systems project is due in 24 hours. You have completed 60% of the tasks.",
        "type":    "urgent",
        "icon":    "🚨",
        "course":  "CS3042",
        "tags":    ["urgent", "reminder"],
        "is_unread": True,
    },
    {
        "title":   "Algebra Assignment Reminder",
        "message": "Math 201 assignment is due in 3 days. Don't forget to submit!",
        "type":    "reminder",
        "icon":    "⏰",
        "course":  "Math 201",
        "tags":    ["reminder"],
        "is_unread": True,
    },
    {
        "title":   "AI Study Insight",
        "message": "Based on your deadline patterns, studying Statistics tonight will improve your readiness by 34%.",
        "type":    "ai",
        "icon":    "🤖",
        "course":  "STAT 301",
        "tags":    ["ai"],
        "is_unread": True,
    },
    {
        "title":   "Document Processed Successfully",
        "message": "Your Physics Lab Report has been processed. 4 new tasks were extracted.",
        "type":    "success",
        "icon":    "✅",
        "course":  "PHY 201",
        "tags":    ["success"],
        "is_unread": False,
    },
    {
        "title":   "Exam Schedule Released",
        "message": "The end-semester exam timetable has been published. Check your calendar.",
        "type":    "info",
        "icon":    "📅",
        "course":  "General",
        "tags":    ["info"],
        "is_unread": False,
    },
]

SAMPLE_DEADLINES = [
    {
        "title":         "Database Project",
        "course":        "CS3042",
        "deadline_time": "Tomorrow, 11:59 PM",
        "urgency_label": "🔴 Critical",
        "color":         "#ef4444",
    },
    {
        "title":         "Algebra Assignment",
        "course":        "Math 201",
        "deadline_time": "In 3 days",
        "urgency_label": "🟠 Soon",
        "color":         "#f59e0b",
    },
    {
        "title":         "Physics Lab Report",
        "course":        "PHY 201",
        "deadline_time": "Next week",
        "urgency_label": "🟡 Upcoming",
        "color":         "#10b981",
    },
    {
        "title":         "Statistics Mid-term",
        "course":        "STAT 301",
        "deadline_time": "In 10 days",
        "urgency_label": "🟢 Comfortable",
        "color":         "#6366f1",
    },
]


def _ensure_seeded(conn):
    """Seed sample data if notifications table is empty."""
    row = conn.execute("SELECT COUNT(*) AS cnt FROM notifications").fetchone()
    if row["cnt"] == 0:
        for n in SAMPLE_NOTIFICATIONS:
            conn.execute(
                """
                INSERT INTO notifications (title, message, type, icon, course, tags, is_unread)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (n["title"], n["message"], n["type"], n["icon"],
                 n["course"], n["tags"], n["is_unread"]),
            )

    row2 = conn.execute("SELECT COUNT(*) AS cnt FROM deadlines").fetchone()
    if row2["cnt"] == 0:
        for d in SAMPLE_DEADLINES:
            conn.execute(
                """
                INSERT INTO deadlines (title, course, deadline_time, urgency_label, color)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (d["title"], d["course"], d["deadline_time"], d["urgency_label"], d["color"]),
            )


def _ensure_prefs(conn, user_id: int):
    """Upsert default reminder preferences for a user."""
    for p in DEFAULT_PREFS:
        conn.execute(
            """
            INSERT INTO reminder_preferences (user_id, pref_key, label, description, is_enabled)
            VALUES (%s, %s, %s, %s, TRUE)
            ON CONFLICT (user_id, pref_key) DO NOTHING
            """,
            (user_id, p["pref_key"], p["label"], p["description"]),
        )


# ── Notifications ──────────────────────────────────────────────────────────

@notifications_bp.route("", methods=["GET"])
def list_notifications():
    """GET /api/notifications"""
    conn = get_connection()
    try:
        _ensure_seeded(conn)
        rows = conn.execute(
            "SELECT * FROM notifications ORDER BY created_at DESC"
        ).fetchall()

        results = []
        for r in rows:
            d = dict(r)
            # Compute a human-friendly time label
            created = d.get("created_at")
            if created:
                delta = datetime.now(timezone.utc) - created
                secs  = int(delta.total_seconds())
                if secs < 60:
                    d["time_label"] = "Just now"
                elif secs < 3600:
                    d["time_label"] = f"{secs // 60}m ago"
                elif secs < 86400:
                    d["time_label"] = f"{secs // 3600}h ago"
                else:
                    d["time_label"] = f"{secs // 86400}d ago"
            results.append(d)
        return jsonify(results)
    finally:
        conn.close()


@notifications_bp.route("", methods=["POST"])
def create_notification():
    """POST /api/notifications"""
    data = request.get_json() or {}
    conn = get_connection()
    try:
        row = conn.execute(
            """
            INSERT INTO notifications (user_id, title, message, type, icon, course, tags, is_unread)
            VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE)
            RETURNING *
            """,
            (
                data.get("user_id"),
                data.get("title", "Notification"),
                data.get("message", ""),
                data.get("type", "info"),
                data.get("icon", "🔔"),
                data.get("course"),
                data.get("tags", []),
            ),
        ).fetchone()
        conn.commit()
        return jsonify(dict(row)), 201
    except Exception as e:
        conn.rollback()
        print("create_notification error:", e)
        return jsonify({"error": "Failed to create notification"}), 500
    finally:
        conn.close()


@notifications_bp.route("/mark-all-read", methods=["PATCH"])
def mark_all_read():
    """PATCH /api/notifications/mark-all-read"""
    conn = get_connection()
    try:
        conn.execute("UPDATE notifications SET is_unread = FALSE")
        conn.commit()
        return jsonify({"success": True})
    finally:
        conn.close()


@notifications_bp.route("/<int:notif_id>/read", methods=["PATCH"])
def mark_read(notif_id):
    """PATCH /api/notifications/<id>/read"""
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE notifications SET is_unread = FALSE WHERE id = %s",
            (notif_id,),
        )
        conn.commit()
        return jsonify({"success": True})
    finally:
        conn.close()


@notifications_bp.route("/<int:notif_id>", methods=["DELETE"])
def delete_notification(notif_id):
    """DELETE /api/notifications/<id>"""
    conn = get_connection()
    try:
        conn.execute("DELETE FROM notifications WHERE id = %s", (notif_id,))
        conn.commit()
        return jsonify({"success": True})
    finally:
        conn.close()


# ── Reminder preferences ───────────────────────────────────────────────────

@notifications_bp.route("/preferences", methods=["GET"])
def get_preferences():
    """GET /api/reminders/preferences — returns global defaults (no user FK needed)"""
    conn = get_connection()
    try:
        # Seed global prefs (user_id IS NULL) if table is empty
        count = conn.execute(
            "SELECT COUNT(*) AS c FROM reminder_preferences WHERE user_id IS NULL"
        ).fetchone()["c"]
        if count == 0:
            for p in DEFAULT_PREFS:
                conn.execute(
                    """
                    INSERT INTO reminder_preferences (user_id, pref_key, label, description, is_enabled)
                    VALUES (NULL, %s, %s, %s, TRUE)
                    ON CONFLICT DO NOTHING
                    """,
                    (p["pref_key"], p["label"], p["description"]),
                )
            conn.commit()

        rows = conn.execute(
            "SELECT * FROM reminder_preferences WHERE user_id IS NULL ORDER BY id",
        ).fetchall()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        print("get_preferences error:", e)
        return jsonify([]), 200
    finally:
        conn.close()


@notifications_bp.route("/preferences/<string:pref_key>", methods=["PATCH"])
def toggle_preference(pref_key):
    """PATCH /api/reminders/preferences/<key>"""
    data    = request.get_json() or {}
    enabled = data.get("is_enabled")

    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE reminder_preferences
            SET is_enabled = %s
            WHERE user_id IS NULL AND pref_key = %s
            """,
            (enabled, pref_key),
        )
        conn.commit()
        return jsonify({"success": True, "pref_key": pref_key, "is_enabled": enabled})
    except Exception as e:
        conn.rollback()
        print("toggle_preference error:", e)
        return jsonify({"error": "Failed to update preference"}), 500
    finally:
        conn.close()


# ── Deadlines ──────────────────────────────────────────────────────────────

@notifications_bp.route("/deadlines", methods=["GET"])
def get_deadlines():
    """GET /api/reminders/deadlines"""
    conn = get_connection()
    try:
        _ensure_seeded(conn)
        conn.commit()
        rows = conn.execute(
            "SELECT * FROM deadlines ORDER BY id"
        ).fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        conn.close()
