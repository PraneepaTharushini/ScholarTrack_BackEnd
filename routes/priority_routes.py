"""
priority_routes.py
==================
Flask Blueprint that exposes the priority & recommendation API.

All routes are prefixed with  /api/priority  (set when registering the blueprint).

Available endpoints:
  POST  /api/priority/score-all          → score + rank all pending tasks
  GET   /api/priority/recommendations    → full recommendation report
  POST  /api/priority/score-task         → score a single task (quick utility)
  GET   /api/priority/quadrants          → tasks grouped by Eisenhower quadrant
  GET   /api/priority/categories         → return available categories + default importance
"""

from functools import wraps

from flask import Blueprint, jsonify, request

from services.priority_engine import score_task, rank_tasks, CATEGORY_IMPORTANCE
from services.recommendation_service import generate_recommendations
from models.db_queries import (
    get_pending_tasks,
    get_completed_tasks,
    save_priority_score,
)

# ---------------------------------------------------------------------------
# Blueprint setup
# ---------------------------------------------------------------------------

priority_bp = Blueprint("priority", __name__)


# ---------------------------------------------------------------------------
# Auth helper  (replace with your real JWT / session logic)
# ---------------------------------------------------------------------------

def get_current_student_id() -> int | None:
    """
    Extract student_id from the request.

    This is a placeholder.  Replace the body with however your team
    handles authentication (JWT decode, Flask-Login current_user, etc.)

    Example with JWT (Flask-JWT-Extended):
        from flask_jwt_extended import get_jwt_identity
        return get_jwt_identity()
    """
    # Temporary compatibility: accept student_id from multiple common sources.
    sid = request.headers.get("X-Student-ID")
    if not sid:
        sid = request.args.get("student_id")
    if not sid:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.lower().startswith("bearer "):
            sid = auth_header.split(None, 1)[1].strip()
    if sid and sid.isdigit():
        return int(sid)
    return None


def require_auth(f):
    """Decorator: return 401 if no student is authenticated."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        student_id = get_current_student_id()
        if student_id is None:
            return jsonify({"error": "Unauthorized. Please log in."}), 401
        return f(*args, student_id=student_id, **kwargs)
    return wrapper


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@priority_bp.route("/score-all", methods=["POST"])
@require_auth
def score_all_tasks(student_id: int):
    """
    Score and rank ALL pending tasks for the authenticated student.

    Also persists the priority_score and quadrant back to the DB.

    Response JSON:
    {
      "student_id": 42,
      "total_pending": 5,
      "total_completed": 12,
      "formula_used": "experienced_user",
      "ranked_tasks": [ { ...task fields + urgency, importance, priority_score, quadrant } ]
    }
    """
    pending   = get_pending_tasks(student_id)
    completed = get_completed_tasks(student_id)

    ranked = rank_tasks(pending, completed)

    # Persist scores back to DB so frontend can read them directly
    for task in ranked:
        save_priority_score(task["task_id"], task["priority_score"], task["quadrant"])

    return jsonify({
        "student_id":      student_id,
        "total_pending":   len(pending),
        "total_completed": len(completed),
        "formula_used":    ranked[0]["formula_used"] if ranked else "new_user",
        "ranked_tasks":    _serialise_tasks(ranked),
    })


@priority_bp.route("/recommendations", methods=["GET"])
@require_auth
def get_recommendations(student_id: int):
    """
    Full recommendation report for the authenticated student.

    Response JSON:
    {
      "student_id": 42,
      "top_recommendation": "Start working on ...",
      "summary_message": "...",
      "behaviour_score": 7.5,
      "behaviour_label": "good",
      "do_first":   [ ...tasks ],
      "schedule":   [ ...tasks ],
      "delegate":   [ ...tasks ],
      "eliminate":  [ ...tasks ],
      "overdue_alerts": [ ...tasks ],
      "ranked_tasks": [ ...all tasks ranked ]
    }
    """
    pending   = get_pending_tasks(student_id)
    completed = get_completed_tasks(student_id)

    report = generate_recommendations(pending, completed)

    return jsonify({
        "student_id":         student_id,
        "top_recommendation": report["top_recommendation"],
        "summary_message":    report["summary_message"],
        "behaviour_score":    report["behaviour_score"],
        "behaviour_label":    report["behaviour_label"],
        "do_first":           _serialise_tasks(report["do_first"]),
        "schedule":           _serialise_tasks(report["schedule"]),
        "delegate":           _serialise_tasks(report["delegate"]),
        "eliminate":          _serialise_tasks(report["eliminate"]),
        "overdue_alerts":     _serialise_tasks(report["overdue_alerts"]),
        "ranked_tasks":       _serialise_tasks(report["ranked_tasks"]),
    })


@priority_bp.route("/score-task", methods=["POST"])
@require_auth
def score_single_task(student_id: int):
    """
    Score a single task without touching the DB.
    Useful for live preview when a student is CREATING or EDITING a task.

    Request body (JSON):
    {
      "task_id":             1,            (optional for preview)
      "title":               "Lab Report",
      "deadline":            "2025-02-10",
      "category":            "Lab",
      "importance_override": 8.0           (optional)
    }

    Response JSON: scored task dict
    """
    data = request.get_json(force=True)

    if not data or "deadline" not in data or "category" not in data:
        return jsonify({"error": "deadline and category are required fields."}), 400

    task = {
        "task_id":             data.get("task_id", 0),
        "title":               data.get("title", "Untitled"),
        "deadline":            data["deadline"],
        "category":            data["category"],
        "importance_override": data.get("importance_override"),
    }

    completed = get_completed_tasks(student_id)
    scored    = score_task(task, completed)

    return jsonify(_serialise_task(scored))


@priority_bp.route("/quadrants", methods=["GET"])
@require_auth
def get_quadrants(student_id: int):
    """
    Return tasks already grouped by Eisenhower quadrant.

    Reads the quadrant column that was saved by /score-all.
    This is a lightweight endpoint — no re-scoring, just DB read + group.

    Response JSON:
    {
      "DO FIRST":  [ ...tasks ],
      "SCHEDULE":  [ ...tasks ],
      "DELEGATE":  [ ...tasks ],
      "ELIMINATE": [ ...tasks ]
    }
    """
    pending   = get_pending_tasks(student_id)
    completed = get_completed_tasks(student_id)
    ranked    = rank_tasks(pending, completed)

    quadrant_map: dict[str, list] = {
        "DO FIRST":  [],
        "SCHEDULE":  [],
        "DELEGATE":  [],
        "ELIMINATE": [],
    }
    for task in ranked:
        q = task.get("quadrant", "ELIMINATE")
        quadrant_map.setdefault(q, []).append(_serialise_task(task))

    return jsonify(quadrant_map)


@priority_bp.route("/categories", methods=["GET"])
def get_categories():
    """
    Return the list of task categories with their default importance scores.
    The frontend uses this to populate the category dropdown and show students
    the default importance before they decide whether to override it.

    No auth required — this is static config data.

    Response JSON:
    {
      "categories": [
        { "name": "Exam", "default_importance": 10.0 },
        ...
      ]
    }
    """
    cats = [
        {"name": name, "default_importance": score}
        for name, score in sorted(
            CATEGORY_IMPORTANCE.items(), key=lambda x: x[1], reverse=True
        )
    ]
    return jsonify({"categories": cats})


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------

def _serialise_task(task: dict) -> dict:
    """Convert date/datetime objects to ISO strings so JSON can handle them."""
    out = {}
    for k, v in task.items():
        if hasattr(v, "isoformat"):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


def _serialise_tasks(tasks: list[dict]) -> list[dict]:
    return [_serialise_task(t) for t in tasks]
