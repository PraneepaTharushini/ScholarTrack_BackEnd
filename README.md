<<<<<<< HEAD
# Scholar-Track — Priority & Recommendation Module

> **Your module only.** This folder is self-contained and plugs into the shared Flask app.

---

## Folder structure

```
scholar_track_priority/
├── __init__.py                          ← registers the Blueprint
├── migration_add_priority_columns.sql   ← run once on PostgreSQL
├── routes/
│   └── priority_routes.py              ← API endpoints
├── services/
│   ├── priority_engine.py              ← core scoring logic
│   └── recommendation_service.py       ← recommendation report builder
├── models/
│   └── db_queries.py                   ← all DB calls (PostgreSQL)
└── tests/
    └── test_priority.py                ← 30 unit tests (no DB needed)
```

---

## Step-by-step: how the code works

### 1 · Urgency (how soon is it due?)

```
days_left = deadline - today

days_left ≤ 0  →  urgency = 10.0  (overdue / due today)
days_left ≤ 1  →  urgency = 9.5
days_left ≤ 2  →  urgency = 9.0
...
days_left > 30 →  urgency = 1.0
```

### 2 · Importance (how critical is this type of task?)

Default values by category:

| Category     | Default Importance |
|--------------|--------------------|
| Exam         | 10.0               |
| Project      | 8.5                |
| Presentation | 7.5                |
| Assignment   | 7.0                |
| Lab          | 6.5                |
| Scholarship  | 6.0                |
| Quiz         | 6.0                |
| Other        | 4.0                |

Students can **override** this with their own value (1–10) via the frontend form.

### 3 · Priority Score formula

**New students** (< 10 completed tasks):
```
score = Urgency × 0.60 + Importance × 0.40
```

**Experienced students** (≥ 10 completed tasks):
```
score = Urgency × 0.50 + Importance × 0.30 + Behaviour × 0.20

Behaviour = (tasks finished on or before deadline) / (total completed) × 10
```

### 4 · Eisenhower Quadrant

```
                    HIGH IMPORTANCE
                          │
         SCHEDULE         │        DO FIRST
  (plan time this week)   │   (work on this NOW)
                          │
 ─────────────────────────┼──────────────────────  urgency boundary = 6.0
                          │
         ELIMINATE        │        DELEGATE
    (low priority)        │  (urgent but less important)
                          │
                    LOW IMPORTANCE

importance boundary = 6.5
```

### 5 · Ranking output

```
1. Overdue tasks  (days_left < 0)  → always at top, most overdue first
2. Remaining tasks                 → sorted by priority_score descending
```

---

## Step-by-step: how to merge into the shared backend

### Step 1 — Copy this folder into the backend repo

Place the whole `scholar_track_priority/` folder next to your main `app.py`:

```
backend/
├── app.py               ← main Flask app (Thinushanth's)
├── extensions.py        ← db = SQLAlchemy() lives here
├── scholar_track_priority/   ← ← ← paste here
└── ...
```

### Step 2 — Run the SQL migration

Open pgAdmin (or any PostgreSQL client) and run:

```sql
-- file: migration_add_priority_columns.sql
```

This adds 5 new columns to the existing `task` table. It is safe to run multiple times (uses `IF NOT EXISTS`).

### Step 3 — Register the Blueprint in `app.py`

Find the `create_app()` function in `app.py` and add two lines:

```python
from scholar_track_priority import register_priority_module   # ADD THIS

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)

    # ... existing blueprints ...

    register_priority_module(app)   # ADD THIS

    return app
```

### Step 4 — Fix the db import in `db_queries.py`

Open `models/db_queries.py` and find the `_get_db()` function.
Change the import to match how **your team's** db is defined:

```python
# If db is in extensions.py  (most common setup):
from extensions import db

# If db is defined directly in app.py:
from app import db
```

### Step 5 — Fix the auth in `priority_routes.py`

Open `routes/priority_routes.py` and find `get_current_student_id()`.
Replace the placeholder with your team's JWT logic:

```python
# Example if you use Flask-JWT-Extended:
from flask_jwt_extended import get_jwt_identity

def get_current_student_id():
    return get_jwt_identity()
```

### Step 6 — Test without the database

```bash
cd backend/scholar_track_priority
python tests/test_priority.py
```

All 30 tests should pass. ✅

### Step 7 — Test the live API

Start the Flask server, then use these curl commands (replace the student-id header with your JWT once auth is wired):

```bash
# Score all pending tasks
curl -X POST http://localhost:5000/api/priority/score-all \
     -H "X-Student-ID: 1"

# Get recommendations
curl http://localhost:5000/api/priority/recommendations \
     -H "X-Student-ID: 1"

# Preview score for a task being created (no DB write)
curl -X POST http://localhost:5000/api/priority/score-task \
     -H "X-Student-ID: 1" \
     -H "Content-Type: application/json" \
     -d '{"title":"Lab Report","deadline":"2025-02-10","category":"Lab"}'

# Get tasks grouped by quadrant
curl http://localhost:5000/api/priority/quadrants \
     -H "X-Student-ID: 1"

# Get category list (no auth needed)
curl http://localhost:5000/api/priority/categories
```

---

## How the frontend (React) connects

Tell **Thinushanth** (Full Stack) or **Wanasinghe** (Mobile/Frontend) to call these endpoints:

| What to show in UI              | Endpoint                            | Method |
|---------------------------------|-------------------------------------|--------|
| Ranked task list on dashboard   | `/api/priority/score-all`           | POST   |
| Recommendation banner           | `/api/priority/recommendations`     | GET    |
| Eisenhower matrix view          | `/api/priority/quadrants`           | GET    |
| Live score preview (task form)  | `/api/priority/score-task`          | POST   |
| Category dropdown options       | `/api/priority/categories`          | GET    |

### Example React fetch call:

```javascript
// Get recommendations and show them on the dashboard
const fetchRecommendations = async () => {
  const res = await fetch("/api/priority/recommendations", {
    headers: {
      Authorization: `Bearer ${yourJwtToken}`,
    },
  });
  const data = await res.json();

  // data.top_recommendation  → show as a banner/card
  // data.do_first            → show as "DO FIRST" task list
  // data.overdue_alerts      → show red warning badges
  // data.ranked_tasks        → show in the main task list
  // data.behaviour_score     → show in analytics dashboard
};
```

### Example — live score preview when student creates a task:

```javascript
// Call this when the student fills in category or deadline in the form
const previewScore = async (title, deadline, category, importanceOverride) => {
  const res = await fetch("/api/priority/score-task", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${yourJwtToken}`,
    },
    body: JSON.stringify({
      title,
      deadline,        // "YYYY-MM-DD"
      category,
      importance_override: importanceOverride || null,
    }),
  });
  const scored = await res.json();
  // scored.priority_score → show e.g. "Priority: 8.7 / 10"
  // scored.quadrant       → show e.g. "DO FIRST"
  // scored.days_left      → show e.g. "Due in 3 days"
};
```

---

## API Response reference

### `/api/priority/recommendations` response shape:

```json
{
  "student_id": 42,
  "top_recommendation": "Start working on \"Lab Report\" today...",
  "summary_message": "🔴 Focus on \"Lab Report\" first...",
  "behaviour_score": 7.5,
  "behaviour_label": "good",
  "do_first":  [ { "task_id": 1, "title": "...", "priority_score": 9.7, "quadrant": "DO FIRST", ... } ],
  "schedule":  [ ... ],
  "delegate":  [ ... ],
  "eliminate": [ ... ],
  "overdue_alerts": [ ... ],
  "ranked_tasks":   [ ... ]
}
```

---

## Git workflow

```bash
# 1. Create your feature branch
git checkout -b feature/priority-module

# 2. Add your files
git add scholar_track_priority/
git add migration_add_priority_columns.sql

# 3. Commit
git commit -m "feat: add ML priority scoring and recommendation module"

# 4. Push
git push origin feature/priority-module

# 5. Open a Pull Request → ask Thinushanth to review app.py integration
```
=======
# ScholarTrack_BackEnd
>>>>>>> e6bec361977f5b1a19a6b277575ee500205d3685
