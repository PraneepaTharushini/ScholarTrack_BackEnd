"""
recommendation_service.py
=========================
Generates human-readable recommendations for each student
based on their ranked task list and behaviour patterns.

Recommendations cover:
  - What to work on RIGHT NOW
  - What to plan/schedule this week
  - Overdue alerts
  - Encouragement when workload is light
"""

from .priority_engine import rank_tasks, _behaviour_score, MIN_TASKS_FOR_BEHAVIOUR


def _behaviour_label(score: float) -> str:
    """Turn a 0–10 behaviour score into a friendly label."""
    if score >= 8.0:
        return "excellent"
    if score >= 6.0:
        return "good"
    if score >= 4.0:
        return "fair"
    return "needs improvement"


def generate_recommendations(
    pending_tasks: list[dict],
    completed_tasks: list[dict],
) -> dict:
    """
    Generate a complete recommendation report for a student.

    Parameters
    ----------
    pending_tasks   : list of task dicts (not yet completed)
    completed_tasks : list of task dicts already finished by this student

    Returns
    -------
    dict with keys:
      - ranked_tasks          : full ranked + scored list
      - do_first              : tasks the student should work on immediately
      - schedule              : tasks to plan time for this week
      - delegate              : lower-importance urgent tasks
      - eliminate             : low urgency + low importance
      - overdue_alerts        : tasks that are already past their deadline
      - behaviour_score       : float (None if < 10 completed tasks)
      - behaviour_label       : str
      - summary_message       : a short overall recommendation string
      - top_recommendation    : single most important action right now
    """
    ranked = rank_tasks(pending_tasks, completed_tasks)

    # Split by quadrant
    do_first  = [t for t in ranked if t["quadrant"] == "DO FIRST"]
    schedule  = [t for t in ranked if t["quadrant"] == "SCHEDULE"]
    delegate  = [t for t in ranked if t["quadrant"] == "DELEGATE"]
    eliminate = [t for t in ranked if t["quadrant"] == "ELIMINATE"]
    overdue   = [t for t in ranked if t["days_left"] < 0]

    # Behaviour
    num_completed = len(completed_tasks)
    if num_completed >= MIN_TASKS_FOR_BEHAVIOUR:
        bscore = _behaviour_score(completed_tasks)
        blabel = _behaviour_label(bscore)
    else:
        bscore = None
        blabel = "not enough data yet"

    # Build summary message
    summary_parts = []

    if overdue:
        names = ", ".join(f'"{t["title"]}"' for t in overdue[:3])
        extra = f" and {len(overdue) - 3} more" if len(overdue) > 3 else ""
        summary_parts.append(
            f"⚠️  You have {len(overdue)} overdue task(s): {names}{extra}. "
            f"Address these immediately."
        )

    if do_first:
        top = do_first[0]
        summary_parts.append(
            f"🔴 Focus on \"{top['title']}\" first "
            f"(due in {top['days_left']} day(s), score {top['priority_score']})."
        )
    elif schedule:
        top = schedule[0]
        summary_parts.append(
            f"🟡 Plan time for \"{top['title']}\" this week "
            f"(due in {top['days_left']} day(s))."
        )
    elif not pending_tasks:
        summary_parts.append("✅ Great job! No pending tasks right now. Stay ahead!")
    else:
        summary_parts.append("📋 Your current workload is manageable. Keep it up!")

    if bscore is not None:
        summary_parts.append(
            f"📊 Your on-time completion behaviour is {blabel} ({bscore}/10)."
        )

    # Single top action
    if overdue:
        top_task = overdue[0]
        top_rec = (
            f"Submit or catch up on \"{top_task['title']}\" immediately — "
            f"it is {abs(top_task['days_left'])} day(s) overdue."
        )
    elif do_first:
        top_task = do_first[0]
        top_rec = (
            f"Start working on \"{top_task['title']}\" today — "
            f"it is due in {top_task['days_left']} day(s) and is your highest priority."
        )
    elif schedule:
        top_task = schedule[0]
        top_rec = (
            f"Block time this week for \"{top_task['title']}\" "
            f"(due in {top_task['days_left']} day(s))."
        )
    else:
        top_rec = "No urgent tasks right now. Review upcoming tasks and plan ahead."

    return {
        "ranked_tasks":       ranked,
        "do_first":           do_first,
        "schedule":           schedule,
        "delegate":           delegate,
        "eliminate":          eliminate,
        "overdue_alerts":     overdue,
        "behaviour_score":    bscore,
        "behaviour_label":    blabel,
        "summary_message":    " ".join(summary_parts),
        "top_recommendation": top_rec,
    }
