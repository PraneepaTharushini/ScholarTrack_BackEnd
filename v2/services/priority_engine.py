"""
priority_engine.py
==================
Core scoring and quadrant logic for Scholar-Track.

How it works (plain English):
  1.  Given a task, calculate how many days are left until its deadline.
  2.  Look up URGENCY from a threshold table (0–10 scale).
  3.  Look up IMPORTANCE from the task's category (0–10 scale),
      but if the student has overridden it, use their value instead.
  4.  Combine urgency + importance into a PRIORITY SCORE.
      - New students (< 10 completed tasks):  score = U*0.6 + I*0.4
      - Experienced students (>= 10 tasks):   score = U*0.5 + I*0.3 + B*0.2
        where B (behaviour) is derived from the student's completion speed history.
  5.  Place the task in one of the 4 Eisenhower quadrants.
  6.  Return a ranked list, overdue tasks always at the top.
"""

from datetime import date, datetime
from typing import Optional


# ---------------------------------------------------------------------------
# Configuration tables
# ---------------------------------------------------------------------------

# (days_left, urgency_score)
# If days_left <= threshold, assign that urgency score.
# The list is checked from top (most urgent) to bottom.
URGENCY_THRESHOLDS = [
    (0,  10.0),   # overdue or due today
    (1,   9.5),   # due tomorrow
    (2,   9.0),
    (3,   8.0),
    (5,   7.0),
    (7,   6.0),
    (10,  5.0),
    (14,  4.0),
    (21,  3.0),
    (30,  2.0),
]
DEFAULT_URGENCY = 1.0   # > 30 days away

CATEGORY_IMPORTANCE = {
    "Exam":         10.0,
    "Project":       8.5,
    "Presentation":  7.5,
    "Assignment":    7.0,
    "Lab":           6.5,
    "Scholarship":   6.0,
    "Quiz":          6.0,
    "Other":         4.0,
}
DEFAULT_IMPORTANCE = 4.0   # fallback for unknown categories

# Eisenhower matrix boundaries
URGENCY_BOUNDARY    = 6.0   # >= this → "urgent"
IMPORTANCE_BOUNDARY = 6.5   # >= this → "important"

MIN_TASKS_FOR_BEHAVIOUR = 10   # need at least this many completed tasks


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _days_left(deadline) -> int:
    """
    Return days remaining until deadline (negative = overdue).
    Accepts a date, datetime, or ISO string ('YYYY-MM-DD').
    """
    today = date.today()

    if isinstance(deadline, datetime):
        deadline = deadline.date()
    elif isinstance(deadline, str):
        deadline = date.fromisoformat(deadline[:10])   # handles 'YYYY-MM-DD HH:MM:SS' too

    return (deadline - today).days


def _get_urgency(days: int) -> float:
    """Map days_left → urgency score using the threshold table."""
    for threshold, score in URGENCY_THRESHOLDS:
        if days <= threshold:
            return score
    return DEFAULT_URGENCY


def _get_importance(category: str, override: Optional[float]) -> float:
    """
    Return importance score.
    If the student supplied an override (1–10), clamp and use it.
    Otherwise, look up the category table.
    """
    if override is not None:
        return max(1.0, min(10.0, float(override)))
    return CATEGORY_IMPORTANCE.get(category, DEFAULT_IMPORTANCE)


def _get_quadrant(urgency: float, importance: float) -> str:
    """
    Eisenhower Matrix:
      High urgency + high importance  → DO FIRST
      Low urgency  + high importance  → SCHEDULE
      High urgency + low importance   → DELEGATE
      Low urgency  + low importance   → ELIMINATE
    """
    is_urgent    = urgency    >= URGENCY_BOUNDARY
    is_important = importance >= IMPORTANCE_BOUNDARY

    if is_urgent and is_important:
        return "DO FIRST"
    if not is_urgent and is_important:
        return "SCHEDULE"
    if is_urgent and not is_important:
        return "DELEGATE"
    return "ELIMINATE"


def _behaviour_score(completed_tasks: list[dict]) -> float:
    """
    Compute a behaviour score (0–10) from the student's past completed tasks.

    Logic:
      For each completed task we check if it was finished before its deadline.
      on_time_ratio = (tasks finished on time) / (total completed tasks)
      behaviour_score = on_time_ratio * 10

    Each completed task dict must have:
      - 'deadline'      : date / datetime / ISO string
      - 'completed_at'  : date / datetime / ISO string  (when the student marked it done)
    """
    if not completed_tasks:
        return 5.0   # neutral default

    on_time = 0
    for t in completed_tasks:
        deadline     = t.get("deadline")
        completed_at = t.get("completed_at")
        if deadline is None or completed_at is None:
            continue

        # normalise to date objects
        if isinstance(deadline, str):
            deadline = date.fromisoformat(deadline[:10])
        elif isinstance(deadline, datetime):
            deadline = deadline.date()

        if isinstance(completed_at, str):
            completed_at = date.fromisoformat(completed_at[:10])
        elif isinstance(completed_at, datetime):
            completed_at = completed_at.date()

        if completed_at <= deadline:
            on_time += 1

    return round((on_time / len(completed_tasks)) * 10, 2)


# ---------------------------------------------------------------------------
# Main scoring function
# ---------------------------------------------------------------------------

def score_task(
    task: dict,
    completed_tasks: list[dict],
) -> dict:
    """
    Score a single task and return an enriched dict.

    Parameters
    ----------
    task : dict
        Must contain:
          - 'task_id'   : any unique id
          - 'title'     : str
          - 'deadline'  : date | datetime | 'YYYY-MM-DD' string
          - 'category'  : str  (e.g. 'Exam', 'Assignment')
        Optional:
          - 'importance_override' : float 1–10  (student's own importance rating)
          - 'status'    : str  ('pending', 'completed', etc.)

    completed_tasks : list[dict]
        All tasks the student has already completed.
        Each dict needs 'deadline' and 'completed_at'.

    Returns
    -------
    dict
        Original task fields plus:
          - days_left        : int
          - urgency          : float
          - importance       : float
          - priority_score   : float
          - quadrant         : str
          - formula_used     : str   ('new_user' or 'experienced_user')
    """
    days    = _days_left(task["deadline"])
    urgency = _get_urgency(days)
    importance = _get_importance(
        task.get("category", "Other"),
        task.get("importance_override"),
    )

    num_completed = len(completed_tasks)

    if num_completed >= MIN_TASKS_FOR_BEHAVIOUR:
        behaviour = _behaviour_score(completed_tasks)
        score = round(urgency * 0.50 + importance * 0.30 + behaviour * 0.20, 4)
        formula = "experienced_user"
    else:
        score = round(urgency * 0.60 + importance * 0.40, 4)
        formula = "new_user"

    quadrant = _get_quadrant(urgency, importance)

    return {
        **task,
        "days_left":      days,
        "urgency":        urgency,
        "importance":     importance,
        "priority_score": score,
        "quadrant":       quadrant,
        "formula_used":   formula,
    }


def rank_tasks(
    pending_tasks: list[dict],
    completed_tasks: list[dict],
) -> list[dict]:
    """
    Score and rank all pending tasks.

    Sorting rules (in order of priority):
      1. Overdue tasks (days_left < 0)  → always first, sorted by most overdue
      2. Everything else → sorted by priority_score descending

    Parameters
    ----------
    pending_tasks   : tasks that are not yet completed
    completed_tasks : student's finished tasks (used for behaviour scoring)

    Returns
    -------
    Ranked list of scored task dicts.
    """
    scored = [score_task(t, completed_tasks) for t in pending_tasks]

    overdue  = sorted([t for t in scored if t["days_left"] < 0],
                      key=lambda t: t["days_left"])          # most overdue first
    upcoming = sorted([t for t in scored if t["days_left"] >= 0],
                      key=lambda t: t["priority_score"],
                      reverse=True)

    return overdue + upcoming
