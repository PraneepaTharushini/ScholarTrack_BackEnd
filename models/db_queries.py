"""
db_queries.py
=============
All database interactions for the priority module.
Uses SQLAlchemy (already installed in most Flask projects).

You only need to call two functions from your Flask routes:
  - get_pending_tasks(student_id)
  - get_completed_tasks(student_id)

The rest of the business logic lives in priority_engine.py.
"""

from datetime import datetime

# Import the shared db instance from the local extensions module.
# This keeps the routes independent from the app entrypoint.


def _get_db():
    """Lazy import of db to avoid circular import issues."""
    from extensions import db
    return db


def get_pending_tasks(student_id: int) -> list[dict]:
    """
    Fetch all non-completed tasks for a student from PostgreSQL.

    Returns a list of dicts ready for priority_engine.score_task().
    """
    db = _get_db()

    query = """
        SELECT
            t.task_id,
            t.title,
            t.description,
            t.deadline_date          AS deadline,
            t.status,
            t.priority_score,
            t.category_id,
            c.category_name          AS category,
            t.importance_override,
            t.student_id
        FROM task t
        LEFT JOIN category c ON t.category_id = c.category_id
        WHERE t.student_id = :student_id
          AND t.status != 'completed'
        ORDER BY t.deadline_date ASC
        """

    with db.engine.connect() as conn:
        rows = conn.execute(query, {"student_id": student_id}).mappings().all()

    return [dict(row) for row in rows]


def get_completed_tasks(student_id: int) -> list[dict]:
    """
    Fetch all completed tasks for behaviour scoring.

    Each returned dict has 'deadline' and 'completed_at' so
    priority_engine._behaviour_score() can use them.
    """
    db = _get_db()
    query = """
        SELECT
            t.task_id,
            t.title,
            t.deadline_date     AS deadline,
            t.completed_at,
            c.category_name     AS category
        FROM task t
        LEFT JOIN category c ON t.category_id = c.category_id
        WHERE t.student_id = :student_id
          AND t.status = 'completed'
          AND t.completed_at IS NOT NULL
        ORDER BY t.completed_at DESC
        """

    with db.engine.connect() as conn:
        rows = conn.execute(query, {"student_id": student_id}).mappings().all()

    return [dict(row) for row in rows]


def save_priority_score(task_id: int, score: float, quadrant: str) -> None:
    """
    Persist the calculated priority_score and quadrant back to the task row.

    Call this after scoring so the frontend can also read scores directly
    from the DB without calling the API every time.
    """
    db = _get_db()
    query = """
        UPDATE task
        SET priority_score = :score,
            quadrant       = :quadrant,
            scored_at      = :now
        WHERE task_id = :task_id
    """

    with db.engine.begin() as conn:   # begin() auto-commits
        conn.execute(query, {
            "score":    score,
            "quadrant": quadrant,
            "now":      datetime.utcnow(),
            "task_id":  task_id,
        })
