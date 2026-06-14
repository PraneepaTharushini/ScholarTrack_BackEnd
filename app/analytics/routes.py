from app.analytics import analytics_bp
from app.auth.routes import token_required


@analytics_bp.get("/summary")
@token_required
def summary(user):
    return {
        "total": 24,
        "completed": 14,
        "pending": 8,
        "overdue": 2,
    }, 200


@analytics_bp.get("/status")
@token_required
def status(user):
    return {
        "status": [
            {"label": "Completed", "value": 14, "pct": 58, "color": "#22C55E"},
            {"label": "Pending", "value": 8, "pct": 33, "color": "#F59E0B"},
            {"label": "Overdue", "value": 2, "pct": 9, "color": "#EF4444"},
        ],
    }, 200


@analytics_bp.get("/categories")
@token_required
def categories(user):
    return {
        "categories": [
            {"label": "Assignments", "count": 9},
            {"label": "Exams", "count": 5},
            {"label": "Projects", "count": 6},
            {"label": "Reading", "count": 4},
        ],
    }, 200


@analytics_bp.get("/insights")
@token_required
def insights(user):
    return {
        "insights": [
            "Most pending work is grouped around assignments and projects.",
            "Two tasks are overdue and should be reviewed first.",
            "Completion progress is steady; keep upcoming deadlines visible in the calendar.",
        ],
    }, 200


@analytics_bp.get("/timeline")
@token_required
def timeline(user):
    return {
        "timeline": [
            {"label": "Week 1", "completed": 3, "created": 5},
            {"label": "Week 2", "completed": 5, "created": 6},
            {"label": "Week 3", "completed": 4, "created": 7},
            {"label": "Week 4", "completed": 2, "created": 6},
        ],
    }, 200
