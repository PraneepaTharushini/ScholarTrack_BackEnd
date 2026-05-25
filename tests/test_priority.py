"""
tests/test_priority.py
======================
Run with:  python -m pytest tests/test_priority.py -v

These tests do NOT need a database — they test the pure logic only.
"""

import sys
import os
from datetime import date, timedelta

# Make sure Python can find the parent package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.priority_engine import (
    _days_left,
    _get_urgency,
    _get_importance,
    _get_quadrant,
    _behaviour_score,
    score_task,
    rank_tasks,
    URGENCY_BOUNDARY,
    IMPORTANCE_BOUNDARY,
)
from services.recommendation_service import generate_recommendations


# ---------------------------------------------------------------------------
# Helper to build a task dict quickly
# ---------------------------------------------------------------------------

def make_task(title, days_from_today, category="Assignment", override=None, task_id=1):
    deadline = date.today() + timedelta(days=days_from_today)
    t = {
        "task_id":  task_id,
        "title":    title,
        "deadline": deadline.isoformat(),
        "category": category,
    }
    if override is not None:
        t["importance_override"] = override
    return t


def make_completed(days_late=0):
    """days_late > 0 means submitted after deadline."""
    deadline     = date.today() - timedelta(days=5)
    completed_at = deadline + timedelta(days=days_late)
    return {
        "deadline":     deadline.isoformat(),
        "completed_at": completed_at.isoformat(),
    }


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------

class TestDaysLeft:
    def test_today_is_zero(self):
        assert _days_left(date.today().isoformat()) == 0

    def test_tomorrow_is_one(self):
        assert _days_left((date.today() + timedelta(1)).isoformat()) == 1

    def test_overdue_is_negative(self):
        assert _days_left((date.today() - timedelta(3)).isoformat()) == -3


class TestUrgency:
    def test_overdue_max_urgency(self):
        assert _get_urgency(-1) == 10.0

    def test_today_max_urgency(self):
        assert _get_urgency(0) == 10.0

    def test_tomorrow(self):
        assert _get_urgency(1) == 9.5

    def test_far_future(self):
        assert _get_urgency(60) == 1.0   # DEFAULT_URGENCY


class TestImportance:
    def test_category_lookup(self):
        assert _get_importance("Exam", None) == 10.0
        assert _get_importance("Quiz", None) == 6.0

    def test_override_used(self):
        assert _get_importance("Exam", 3.0) == 3.0

    def test_override_clamped_high(self):
        assert _get_importance("Exam", 15.0) == 10.0

    def test_override_clamped_low(self):
        assert _get_importance("Exam", -2.0) == 1.0

    def test_unknown_category_default(self):
        assert _get_importance("Yoga", None) == 4.0


class TestQuadrant:
    def test_do_first(self):
        assert _get_quadrant(URGENCY_BOUNDARY, IMPORTANCE_BOUNDARY) == "DO FIRST"

    def test_schedule(self):
        assert _get_quadrant(1.0, IMPORTANCE_BOUNDARY) == "SCHEDULE"

    def test_delegate(self):
        assert _get_quadrant(URGENCY_BOUNDARY, 1.0) == "DELEGATE"

    def test_eliminate(self):
        assert _get_quadrant(1.0, 1.0) == "ELIMINATE"


class TestBehaviourScore:
    def test_all_on_time(self):
        tasks = [make_completed(0) for _ in range(5)]   # all on time
        assert _behaviour_score(tasks) == 10.0

    def test_all_late(self):
        tasks = [make_completed(3) for _ in range(5)]   # all late
        assert _behaviour_score(tasks) == 0.0

    def test_half_on_time(self):
        tasks = [make_completed(0) for _ in range(5)] + \
                [make_completed(3) for _ in range(5)]
        assert _behaviour_score(tasks) == 5.0

    def test_empty_returns_neutral(self):
        assert _behaviour_score([]) == 5.0


class TestScoreTask:
    def test_new_user_formula(self):
        task   = make_task("Exam tomorrow", 1, "Exam")
        result = score_task(task, [])   # 0 completed → new user formula
        # expected: 9.5 * 0.6 + 10.0 * 0.4 = 5.7 + 4.0 = 9.7
        assert result["formula_used"] == "new_user"
        assert abs(result["priority_score"] - 9.7) < 0.01

    def test_experienced_user_formula(self):
        completed = [make_completed(0) for _ in range(10)]   # 10 on time
        task      = make_task("Lab", 7, "Lab")
        result    = score_task(task, completed)
        assert result["formula_used"] == "experienced_user"
        # urgency=6.0, importance=6.5, behaviour=10.0
        # 6.0*0.5 + 6.5*0.3 + 10.0*0.2 = 3.0 + 1.95 + 2.0 = 6.95
        assert abs(result["priority_score"] - 6.95) < 0.01

    def test_days_left_field(self):
        task = make_task("Quiz", 3, "Quiz")
        assert score_task(task, [])["days_left"] == 3

    def test_quadrant_field_present(self):
        task = make_task("Project", 2, "Project")
        result = score_task(task, [])
        assert result["quadrant"] in {"DO FIRST", "SCHEDULE", "DELEGATE", "ELIMINATE"}


class TestRankTasks:
    def test_overdue_first(self):
        tasks = [
            make_task("Future task", 10, task_id=1),
            make_task("Overdue task", -2, task_id=2),
            make_task("Tomorrow task", 1, task_id=3),
        ]
        ranked = rank_tasks(tasks, [])
        assert ranked[0]["task_id"] == 2   # overdue must be first

    def test_higher_score_first_among_upcoming(self):
        tasks = [
            make_task("Low priority", 20, "Other",  task_id=1),
            make_task("Exam tomorrow", 1,  "Exam",  task_id=2),
        ]
        ranked = rank_tasks(tasks, [])
        # Exam tomorrow should rank higher than low-priority future task
        non_overdue = [t for t in ranked if t["days_left"] >= 0]
        assert non_overdue[0]["task_id"] == 2


class TestRecommendations:
    def test_no_tasks(self):
        report = generate_recommendations([], [])
        assert "No pending tasks" in report["summary_message"] or \
               "manageable" in report["summary_message"]

    def test_overdue_alert_present(self):
        tasks  = [make_task("Overdue!", -3, "Exam", task_id=1)]
        report = generate_recommendations(tasks, [])
        assert len(report["overdue_alerts"]) == 1
        assert "overdue" in report["summary_message"].lower() or \
               "⚠️" in report["summary_message"]

    def test_quadrant_groups_correct(self):
        tasks = [
            make_task("Exam due today", 0,  "Exam",  task_id=1),  # DO FIRST
            make_task("Far assignment", 25, "Assignment", task_id=2),  # SCHEDULE or ELIMINATE
        ]
        report = generate_recommendations(tasks, [])
        assert len(report["do_first"]) >= 1

    def test_top_recommendation_string(self):
        tasks  = [make_task("Quiz tomorrow", 1, "Quiz", task_id=1)]
        report = generate_recommendations(tasks, [])
        assert isinstance(report["top_recommendation"], str)
        assert len(report["top_recommendation"]) > 10


# ---------------------------------------------------------------------------
# Run manually
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import traceback

    test_classes = [
        TestDaysLeft, TestUrgency, TestImportance, TestQuadrant,
        TestBehaviourScore, TestScoreTask, TestRankTasks, TestRecommendations,
    ]

    passed = failed = 0
    for cls in test_classes:
        instance = cls()
        for name in [m for m in dir(cls) if m.startswith("test_")]:
            try:
                getattr(instance, name)()
                print(f"  ✅  {cls.__name__}.{name}")
                passed += 1
            except Exception as e:
                print(f"  ❌  {cls.__name__}.{name}: {e}")
                traceback.print_exc()
                failed += 1

    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed")
