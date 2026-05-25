from flask import Blueprint, request, jsonify
from database import get_connection
from auth_middleware import require_auth

analytics_bp = Blueprint("analytics", __name__)


def sync_overdue(conn, user_id):
    conn.execute(
        """UPDATE tasks
           SET status = 'overdue', updated_at = NOW()
           WHERE user_id = %s
             AND status  = 'pending'
             AND deadline IS NOT NULL
             AND deadline < CURRENT_DATE""",
        (user_id,),
    )


# ── GET /api/analytics/summary ───────────────────────────────
@analytics_bp.route("/summary", methods=["GET"])
@require_auth
def summary():
    uid = request.user["id"]
    with get_connection() as conn:
        sync_overdue(conn, uid)
        row = conn.execute(
            """SELECT
                 COUNT(*)                                      AS total,
                 COUNT(*) FILTER (WHERE status = 'completed') AS completed,
                 COUNT(*) FILTER (WHERE status = 'pending')   AS pending,
                 COUNT(*) FILTER (WHERE status = 'overdue')   AS overdue
               FROM tasks WHERE user_id = %s""",
            (uid,),
        ).fetchone()
        return jsonify({
            "total":     row["total"],
            "completed": row["completed"],
            "pending":   row["pending"],
            "overdue":   row["overdue"],
        })


# ── GET /api/analytics/status ────────────────────────────────
@analytics_bp.route("/status", methods=["GET"])
@require_auth
def status():
    uid = request.user["id"]
    color_map = {"completed": "#22C55E", "pending": "#F59E0B", "overdue": "#EF4444"}

    with get_connection() as conn:
        sync_overdue(conn, uid)
        rows  = conn.execute(
            "SELECT status, COUNT(*) AS value FROM tasks WHERE user_id = %s GROUP BY status",
            (uid,),
        ).fetchall()
        total = sum(r["value"] for r in rows)
        data  = [
            {
                "label": r["status"].capitalize(),
                "value": r["value"],
                "pct":   round(r["value"] / total * 100) if total else 0,
                "color": color_map.get(r["status"], "#6B7280"),
            }
            for r in rows
        ]
        return jsonify({"status": data})


# ── GET /api/analytics/categories ───────────────────────────
@analytics_bp.route("/categories", methods=["GET"])
@require_auth
def categories():
    uid = request.user["id"]
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT category, COUNT(*) AS count
               FROM tasks WHERE user_id = %s
               GROUP BY category ORDER BY count DESC""",
            (uid,),
        ).fetchall()
        return jsonify({"categories": [{"label": r["category"], "count": r["count"]} for r in rows]})


# ── GET /api/analytics/insights ─────────────────────────────
@analytics_bp.route("/insights", methods=["GET"])
@require_auth
def insights():
    uid = request.user["id"]
    with get_connection() as conn:
        sync_overdue(conn, uid)
        row = conn.execute(
            """SELECT
                 COUNT(*)                                              AS total,
                 COUNT(*) FILTER (WHERE status = 'completed')         AS completed,
                 COUNT(*) FILTER (WHERE status = 'overdue')           AS overdue,
                 COUNT(*) FILTER (WHERE status = 'pending')           AS pending,
                 COUNT(*) FILTER (
                   WHERE status = 'completed'
                     AND deadline IS NOT NULL
                     AND DATE(updated_at) <= deadline
                 )                                                     AS on_time,
                 ROUND(AVG(confidence)::numeric, 0)                   AS avg_confidence,
                 (SELECT category FROM tasks
                  WHERE user_id = %(uid)s
                  GROUP BY category ORDER BY COUNT(*) DESC LIMIT 1)   AS top_category
               FROM tasks WHERE user_id = %(uid)s""",
            {"uid": uid},
        ).fetchone()

        total     = row["total"]     or 0
        completed = row["completed"] or 0
        overdue   = row["overdue"]   or 0
        pending   = row["pending"]   or 0
        on_time   = row["on_time"]   or 0
        avg_conf  = float(row["avg_confidence"] or 0)
        top_cat   = row["top_category"]

        tips = []
        if total == 0:
            tips.append("No tasks yet — head to the Review Tasks page to add some!")
        else:
            rate = round(completed / total * 100)
            tips.append(f"Your overall completion rate is {rate}% ({completed} of {total} tasks done).")
            if overdue > 0:
                tips.append(f"⚠️ You have {overdue} overdue task{'s' if overdue > 1 else ''} — try to address them soon.")
            elif completed > 0:
                tips.append("🎉 Great job — no overdue tasks right now!")
            if pending > 0:
                tips.append(f"{pending} task{'s are' if pending > 1 else ' is'} still pending — stay on schedule!")
            if completed > 0 and on_time > 0:
                tips.append(f"{round(on_time / completed * 100)}% of completed tasks were finished on or before the deadline.")
            if avg_conf > 0:
                tips.append(f"Average task confidence score: {int(avg_conf)}%.")
            if top_cat:
                tips.append(f'Your most common task category is "{top_cat}".')

        return jsonify({"insights": tips})


# ── GET /api/analytics/timeline ─────────────────────────────
@analytics_bp.route("/timeline", methods=["GET"])
@require_auth
def timeline():
    uid = request.user["id"]
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT
                 TO_CHAR(DATE_TRUNC('week', updated_at), 'Mon DD') AS week,
                 COUNT(*) AS completed_count
               FROM tasks
               WHERE user_id = %s
                 AND status = 'completed'
                 AND updated_at >= NOW() - INTERVAL '4 weeks'
               GROUP BY DATE_TRUNC('week', updated_at)
               ORDER BY DATE_TRUNC('week', updated_at)""",
            (uid,),
        ).fetchall()
        return jsonify({"timeline": [{"week": r["week"], "completed_count": r["completed_count"]} for r in rows]})
