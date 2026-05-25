"""
priority_routes.py
==================
Flask Blueprint for priority scoring and recommendations.

NO DATABASE calls here. The frontend (React) sends all task data
in the request body as JSON. This module is pure logic only.

All routes are prefixed with /api/priority

Endpoints:
  POST /api/priority/score-all       → rank all pending tasks
  POST /api/priority/recommendations → full recommendation report
  POST /api/priority/score-task      → score a single task (live preview)
  GET  /api/priority/quadrants       → tasks grouped by Eisenhower quadrant
  GET  /api/priority/categories      → category list + default importance values
"""

from flask import Blueprint, jsonify, request
from ..services.priority_engine import score_task, rank_tasks, CATEGORY_IMPORTANCE
from ..services.recommendation_service import generate_recommendations

priority_bp = Blueprint("priority", __name__)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _serialise(task: dict) -> dict:
    """Convert any date/datetime fields to ISO strings for JSON."""
    return {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in task.items()}


def _require_json_field(data, *fields):
    """Return (None, error_response) if any required field is missing."""
    missing = [f for f in fields if f not in data]
    if missing:
        return None, (jsonify({"error": f"Missing required fields: {missing}"}), 400)
    return data, None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@priority_bp.route("/score-all", methods=["POST"])
def score_all():
    """
    Score and rank all pending tasks sent by the frontend.

    Request body (JSON):
    {
      "pending_tasks": [
        {
          "task_id":             1,
          "title":               "Lab Report",
          "deadline":            "2025-02-10",
          "category":            "Lab",
          "importance_override": 8.0        (optional)
        },
        ...
      ],
      "completed_tasks": [
        {
          "deadline":     "2025-01-20",
          "completed_at": "2025-01-19"
        },
        ...
      ]
    }

    Response:
    {
      "total_pending":   3,
      "total_completed": 12,
      "formula_used":    "experienced_user",
      "ranked_tasks":    [ ...scored task dicts ]
    }
    """
    data = request.get_json(force=True) or {}
    pending   = data.get("pending_tasks", [])
    completed = data.get("completed_tasks", [])

    if not isinstance(pending, list):
        return jsonify({"error": "pending_tasks must be a list"}), 400

    ranked = rank_tasks(pending, completed)

    return jsonify({
        "total_pending":   len(pending),
        "total_completed": len(completed),
        "formula_used":    ranked[0]["formula_used"] if ranked else "new_user",
        "ranked_tasks":    [_serialise(t) for t in ranked],
    })


@priority_bp.route("/recommendations", methods=["POST"])
def get_recommendations():
    """
    Full recommendation report.

    Same request body as /score-all.

    Response:
    {
      "top_recommendation": "Start working on ...",
      "summary_message":    "...",
      "behaviour_score":    7.5,
      "behaviour_label":    "good",
      "do_first":           [ ...tasks ],
      "schedule":           [ ...tasks ],
      "delegate":           [ ...tasks ],
      "eliminate":          [ ...tasks ],
      "overdue_alerts":     [ ...tasks ],
      "ranked_tasks":       [ ...all tasks ranked ]
    }
    """
    data = request.get_json(force=True) or {}
    pending   = data.get("pending_tasks", [])
    completed = data.get("completed_tasks", [])

    report = generate_recommendations(pending, completed)

    return jsonify({
        "top_recommendation": report["top_recommendation"],
        "summary_message":    report["summary_message"],
        "behaviour_score":    report["behaviour_score"],
        "behaviour_label":    report["behaviour_label"],
        "do_first":           [_serialise(t) for t in report["do_first"]],
        "schedule":           [_serialise(t) for t in report["schedule"]],
        "delegate":           [_serialise(t) for t in report["delegate"]],
        "eliminate":          [_serialise(t) for t in report["eliminate"]],
        "overdue_alerts":     [_serialise(t) for t in report["overdue_alerts"]],
        "ranked_tasks":       [_serialise(t) for t in report["ranked_tasks"]],
    })


@priority_bp.route("/score-task", methods=["POST"])
def score_single_task():
    """
    Score one task — useful for live preview while student fills in the form.

    Request body (JSON):
    {
      "task_id":             1,           (optional)
      "title":               "Exam",
      "deadline":            "2025-02-05",
      "category":            "Exam",
      "importance_override": 9.0,         (optional)
      "completed_tasks":     [ ... ]      (optional, for behaviour)
    }

    Response: single scored task dict with urgency, importance, priority_score, quadrant
    """
    data = request.get_json(force=True) or {}
    _, err = _require_json_field(data, "deadline", "category")
    if err:
        return err

    task = {
        "task_id":             data.get("task_id", 0),
        "title":               data.get("title", "Untitled"),
        "deadline":            data["deadline"],
        "category":            data["category"],
        "importance_override": data.get("importance_override"),
    }
    completed = data.get("completed_tasks", [])
    scored    = score_task(task, completed)

    return jsonify(_serialise(scored))


@priority_bp.route("/quadrants", methods=["POST"])
def get_quadrants():
    """
    Return tasks already grouped into the 4 Eisenhower quadrants.

    Same request body as /score-all.

    Response:
    {
      "DO FIRST":  [ ...tasks ],
      "SCHEDULE":  [ ...tasks ],
      "DELEGATE":  [ ...tasks ],
      "ELIMINATE": [ ...tasks ]
    }
    """
    data = request.get_json(force=True) or {}
    pending   = data.get("pending_tasks", [])
    completed = data.get("completed_tasks", [])

    ranked = rank_tasks(pending, completed)

    quadrant_map: dict = {"DO FIRST": [], "SCHEDULE": [], "DELEGATE": [], "ELIMINATE": []}
    for task in ranked:
        quadrant_map.setdefault(task["quadrant"], []).append(_serialise(task))

    return jsonify(quadrant_map)


@priority_bp.route("/categories", methods=["GET"])
def get_categories():
    """
    Return all categories with their default importance scores.
    Use this to populate the category dropdown in the task creation form.

    No request body needed.

    Response:
    {
      "categories": [
        { "name": "Exam", "default_importance": 10.0 },
        ...
      ]
    }
    """
    cats = [
        {"name": name, "default_importance": score}
        for name, score in sorted(CATEGORY_IMPORTANCE.items(), key=lambda x: x[1], reverse=True)
    ]
    return jsonify({"categories": cats})
