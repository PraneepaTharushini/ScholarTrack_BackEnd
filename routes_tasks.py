import psycopg
from flask import Blueprint, request, jsonify
from datetime import date, datetime
from database import get_connection
from auth_middleware import require_auth

tasks_bp = Blueprint("tasks", __name__)


def validate_deadline(value: str | None) -> tuple[str | None, str | None]:
    """
    Validate and normalise a deadline string.

    Returns (clean_value, error_message).
    - ``clean_value`` is the original string (or None) when valid.
    - ``error_message`` is a non-empty string when the value is rejected.
    """
    if not value:
        return None, None  # Optional field; no deadline is fine
    try:
        parts = value.split("-")
        year = int(parts[0])
        if year < 2000 or year > 9999:
            return None, f"Deadline year must be between 2000 and 9999, got {year}"
        # Let psycopg/PostgreSQL do final DATE parsing; we just guard the year.
        return value, None
    except (ValueError, IndexError):
        return None, f"Invalid deadline format: '{value}'"


def compute_priority(deadline_str: str | None) -> str:
    """
    Derive priority automatically from the deadline:
      - 1 day  from today  -> 'critical'
      - 2 days from today  -> 'high'
      - 3 days from today  -> 'medium'
      - 4+ days / no deadline -> 'low'
    Overdue tasks (deadline already passed) are also 'critical'.
    """
    if not deadline_str:
        return "low"
    try:
        deadline_date = datetime.strptime(deadline_str[:10], "%Y-%m-%d").date()
        days_left = (deadline_date - date.today()).days
        if days_left <= 1:
            return "critical"
        elif days_left == 2:
            return "high"
        elif days_left == 3:
            return "medium"
        else:
            return "low"
    except (ValueError, TypeError):
        return "low"


def sync_overdue(conn, user_id):
    """Mark pending tasks whose deadline has passed as overdue."""
    conn.execute(
        """UPDATE tasks
           SET status = 'overdue', updated_at = NOW()
           WHERE user_id = %s
             AND status  = 'pending'
             AND deadline IS NOT NULL
             AND deadline < CURRENT_DATE""",
        (user_id,),
    )


def sync_priorities(conn, user_id):
    """
    Recompute priority for every task that has a deadline, based on today's date.
    Rules (server-side, cannot be overridden by the client):
      deadline - today <= 1  ->  critical
      deadline - today == 2  ->  high
      deadline - today == 3  ->  medium
      deadline - today >= 4  ->  low
      no deadline            ->  low
    """
    conn.execute(
        """UPDATE tasks
           SET priority = CASE
               WHEN deadline IS NULL                          THEN 'low'
               WHEN (deadline - CURRENT_DATE) <= 1           THEN 'critical'
               WHEN (deadline - CURRENT_DATE) = 2            THEN 'high'
               WHEN (deadline - CURRENT_DATE) = 3            THEN 'medium'
               ELSE 'low'
           END,
           updated_at = NOW()
           WHERE user_id = %s""",
        (user_id,),
    )


# ── GET /api/tasks ───────────────────────────────────────────
@tasks_bp.route("/", methods=["GET"])
@require_auth
def get_tasks():
    with get_connection() as conn:
        sync_overdue(conn, request.user["id"])
        sync_priorities(conn, request.user["id"])   # always recalculate from today
        rows = conn.execute(
            "SELECT * FROM tasks WHERE user_id = %s ORDER BY created_at DESC",
            (request.user["id"],),
        ).fetchall()
        return jsonify({"tasks": [dict(r) for r in rows]})


# ── POST /api/tasks/batch ────────────────────────────────────
@tasks_bp.route("/batch", methods=["POST"])
@require_auth
def batch_save():
    data  = request.get_json() or {}
    tasks = data.get("tasks", [])

    if not isinstance(tasks, list) or len(tasks) == 0:
        return jsonify({"error": "tasks array is required and must not be empty"}), 400

    inserted = []
    with get_connection() as conn:
        for t in tasks:
            title = (t.get("task_title") or "").strip()
            if not title:
                continue

            deadline_raw = t.get("deadline") or None
            deadline_clean, dl_err = validate_deadline(deadline_raw)
            if dl_err:
                return jsonify({"error": dl_err}), 400

            # Auto-calculate priority from deadline (ignores any client-sent value)
            priority = compute_priority(deadline_clean)

            row = conn.execute(
                """INSERT INTO tasks
                     (user_id, task_title, subject, deadline, category,
                      description, confidence, priority, has_error, error_message)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   RETURNING *""",
                (
                    request.user["id"],
                    title,
                    t.get("subject") or None,
                    deadline_clean,
                    t.get("category") or "Other",
                    t.get("description") or None,
                    t.get("confidence", 100),
                    priority,
                    bool(t.get("has_error", False)),
                    t.get("error_message") or None,
                ),
            ).fetchone()
            inserted.append(dict(row))

    return jsonify({"tasks": inserted, "count": len(inserted)}), 201


# ── POST /api/tasks ──────────────────────────────────────────
@tasks_bp.route("/", methods=["POST"])
@require_auth
def create_task():
    data  = request.get_json() or {}
    title = (data.get("task_title") or "").strip()

    if not title:
        return jsonify({"error": "task_title is required"}), 400

    deadline_raw = data.get("deadline") or None
    deadline_clean, dl_err = validate_deadline(deadline_raw)
    if dl_err:
        return jsonify({"error": dl_err}), 400

    # Auto-calculate priority from deadline
    priority = compute_priority(deadline_clean)

    with get_connection() as conn:
        row = conn.execute(
            """INSERT INTO tasks
                 (user_id, task_title, subject, deadline, category,
                  description, confidence, priority, has_error, error_message)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               RETURNING *""",
            (
                request.user["id"],
                title,
                data.get("subject") or None,
                deadline_clean,
                data.get("category") or "Other",
                data.get("description") or None,
                data.get("confidence", 100),
                priority,
                bool(data.get("has_error", False)),
                data.get("error_message") or None,
            ),
        ).fetchone()
        return jsonify({"task": dict(row)}), 201


# ── PUT /api/tasks/<id> ──────────────────────────────────────
@tasks_bp.route("/<int:task_id>", methods=["PUT"])
@require_auth
def update_task(task_id):
    data = request.get_json() or {}

    deadline_raw = data.get("deadline") or None
    deadline_clean, dl_err = validate_deadline(deadline_raw)
    if dl_err:
        return jsonify({"error": dl_err}), 400

    # Re-compute priority whenever a deadline update is present;
    # if no new deadline is sent, leave existing priority unchanged via COALESCE.
    new_priority = compute_priority(deadline_clean) if deadline_clean else None

    with get_connection() as conn:
        row = conn.execute(
            """UPDATE tasks SET
                 task_title    = COALESCE(%s, task_title),
                 subject       = COALESCE(%s, subject),
                 deadline      = COALESCE(%s::date, deadline),
                 category      = COALESCE(%s, category),
                 description   = COALESCE(%s, description),
                 confidence    = COALESCE(%s, confidence),
                 status        = COALESCE(%s, status),
                 priority      = COALESCE(%s, priority),
                 has_error     = COALESCE(%s, has_error),
                 error_message = COALESCE(%s, error_message),
                 updated_at    = NOW()
               WHERE id = %s AND user_id = %s
               RETURNING *""",
            (
                data.get("task_title"),
                data.get("subject"),
                deadline_clean,
                data.get("category"),
                data.get("description"),
                data.get("confidence"),
                data.get("status"),
                new_priority,
                data.get("has_error"),
                data.get("error_message"),
                task_id,
                request.user["id"],
            ),
        ).fetchone()

        if not row:
            return jsonify({"error": "Task not found"}), 404
        return jsonify({"task": dict(row)})


# ── DELETE /api/tasks/<id> ───────────────────────────────────
@tasks_bp.route("/<int:task_id>", methods=["DELETE"])
@require_auth
def delete_task(task_id):
    with get_connection() as conn:
        row = conn.execute(
            "DELETE FROM tasks WHERE id = %s AND user_id = %s RETURNING id",
            (task_id, request.user["id"]),
        ).fetchone()

        if not row:
            return jsonify({"error": "Task not found"}), 404
        return jsonify({"message": "Task deleted successfully"})
