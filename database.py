import os
import time
import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# ── Connection helper ──────────────────────────────────────────────────────

def get_connection():
    """Open a new psycopg v3 connection returning rows as dicts."""
    return psycopg.connect(
        DATABASE_URL,
        sslmode="require",
        row_factory=dict_row,
        connect_timeout=15,
    )


def _run(sql: str, label: str = "", retries: int = 3):
    """
    Execute a single DDL/DML statement in its own autocommit connection.
    Retries on transient network errors so a dropped Railway connection
    never aborts the whole migration.
    """
    for attempt in range(1, retries + 1):
        try:
            conn = psycopg.connect(
                DATABASE_URL,
                sslmode="require",
                row_factory=dict_row,
                autocommit=True,          # DDL needs no explicit transaction
                connect_timeout=20,
            )
            with conn:
                conn.execute(sql)
            conn.close()
            return                        # success – stop retrying
        except psycopg.errors.DuplicateTable:
            return                        # table already exists – fine
        except psycopg.errors.DuplicateColumn:
            return                        # column already exists – fine
        except psycopg.errors.DuplicateObject:
            return                        # index already exists – fine
        except Exception as e:
            print(f"  [migrate] step '{label}' attempt {attempt} failed: {e}")
            if attempt < retries:
                time.sleep(2 * attempt)   # back-off before retry
            else:
                print(f"  [migrate] step '{label}' skipped after {retries} attempts")


# ── Migration ──────────────────────────────────────────────────────────────

def migrate():
    """Create / alter all tables. Each statement is independent & retried."""

    steps = [
        # ── users ──────────────────────────────────────────────
        ("users table", """
            CREATE TABLE IF NOT EXISTS users (
                id            SERIAL PRIMARY KEY,
                email         VARCHAR(255) UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                name          VARCHAR(255) NOT NULL,
                role          VARCHAR(50)  DEFAULT 'Student',
                status        VARCHAR(50)  DEFAULT 'Active',
                user_code     VARCHAR(20),
                created_at    TIMESTAMPTZ  DEFAULT NOW()
            )
        """),
        ("users.role",      "ALTER TABLE users ADD COLUMN IF NOT EXISTS role      VARCHAR(50) DEFAULT 'Student'"),
        ("users.status",    "ALTER TABLE users ADD COLUMN IF NOT EXISTS status    VARCHAR(50) DEFAULT 'Active'"),
        ("users.user_code", "ALTER TABLE users ADD COLUMN IF NOT EXISTS user_code VARCHAR(20)"),

        # ── tasks ──────────────────────────────────────────────
        ("tasks table", """
            CREATE TABLE IF NOT EXISTS tasks (
                id            SERIAL PRIMARY KEY,
                user_id       INTEGER REFERENCES users(id) ON DELETE CASCADE,
                task_title    VARCHAR(500) NOT NULL,
                subject       VARCHAR(255),
                deadline      DATE,
                category      VARCHAR(100) DEFAULT 'Other',
                description   TEXT,
                confidence    INTEGER      DEFAULT 100,
                status        VARCHAR(50)  DEFAULT 'pending',
                priority      VARCHAR(50)  DEFAULT 'low',
                has_error     BOOLEAN      DEFAULT FALSE,
                error_message TEXT,
                created_at    TIMESTAMPTZ  DEFAULT NOW(),
                updated_at    TIMESTAMPTZ  DEFAULT NOW()
            )
        """),
        ("tasks.priority", "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS priority VARCHAR(50) DEFAULT 'low'"),

        # ── notifications ──────────────────────────────────────
        ("notifications table", """
            CREATE TABLE IF NOT EXISTS notifications (
                id         SERIAL PRIMARY KEY,
                user_id    INTEGER REFERENCES users(id) ON DELETE CASCADE,
                title      VARCHAR(500) NOT NULL,
                message    TEXT,
                type       VARCHAR(50)  DEFAULT 'info',
                icon       VARCHAR(20)  DEFAULT '!',
                course     VARCHAR(255),
                tags       TEXT[],
                is_unread  BOOLEAN      DEFAULT TRUE,
                created_at TIMESTAMPTZ  DEFAULT NOW()
            )
        """),

        # ── reminder_preferences ───────────────────────────────
        ("reminder_preferences table", """
            CREATE TABLE IF NOT EXISTS reminder_preferences (
                id          SERIAL PRIMARY KEY,
                pref_key    VARCHAR(100) NOT NULL,
                label       VARCHAR(255) NOT NULL,
                description TEXT,
                is_enabled  BOOLEAN DEFAULT TRUE
            )
        """),
        ("reminder_preferences.user_id", """
            ALTER TABLE reminder_preferences
            ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id) ON DELETE CASCADE
        """),
        ("uix_global_prefs", """
            CREATE UNIQUE INDEX IF NOT EXISTS uix_global_prefs
            ON reminder_preferences (pref_key)
            WHERE user_id IS NULL
        """),
        ("uix_user_prefs", """
            CREATE UNIQUE INDEX IF NOT EXISTS uix_user_prefs
            ON reminder_preferences (user_id, pref_key)
            WHERE user_id IS NOT NULL
        """),

        # ── deadlines ──────────────────────────────────────────
        ("deadlines table", """
            CREATE TABLE IF NOT EXISTS deadlines (
                id            SERIAL PRIMARY KEY,
                user_id       INTEGER REFERENCES users(id) ON DELETE CASCADE,
                title         VARCHAR(500) NOT NULL,
                course        VARCHAR(255),
                deadline_time VARCHAR(100),
                urgency_label VARCHAR(50),
                color         VARCHAR(20)  DEFAULT '#6366f1',
                created_at    TIMESTAMPTZ  DEFAULT NOW()
            )
        """),

        # ── ocr_stats ──────────────────────────────────────────
        ("ocr_stats table", """
            CREATE TABLE IF NOT EXISTS ocr_stats (
                id           SERIAL PRIMARY KEY,
                doc_type     VARCHAR(255) NOT NULL,
                processed    INTEGER      DEFAULT 0,
                success_rate NUMERIC(5,2) DEFAULT 0,
                avg_time_sec NUMERIC(6,2) DEFAULT 0,
                status       VARCHAR(50)  DEFAULT 'Optimal',
                updated_at   TIMESTAMPTZ  DEFAULT NOW()
            )
        """),

        # ── system_modules ─────────────────────────────────────
        ("system_modules table", """
            CREATE TABLE IF NOT EXISTS system_modules (
                id     SERIAL PRIMARY KEY,
                num    INTEGER      NOT NULL,
                name   VARCHAR(255) NOT NULL,
                member VARCHAR(255),
                role   VARCHAR(255)
            )
        """),

        # ── activity_logs ──────────────────────────────────────
        ("activity_logs table", """
            CREATE TABLE IF NOT EXISTS activity_logs (
                id         SERIAL PRIMARY KEY,
                message    TEXT        NOT NULL,
                color      VARCHAR(20) DEFAULT '#6366f1',
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """),

        # ── seed data ──────────────────────────────────────────
        ("seed ocr_stats", """
            INSERT INTO ocr_stats (doc_type, processed, success_rate, avg_time_sec, status)
            VALUES
                ('Exam Papers',      1842, 96.4, 2.3, 'Optimal'),
                ('Assignment PDFs',  892,  91.7, 3.1, 'Optimal'),
                ('Lecture Notes',    543,  88.2, 4.7, 'Active'),
                ('Lab Reports',      190,  79.5, 5.2, 'Active')
            ON CONFLICT DO NOTHING
        """),
        ("seed system_modules", """
            INSERT INTO system_modules (num, name, member, role)
            VALUES
                (1, 'Authentication and User Management', 'Banuka Senevirathne',  'Backend Lead'),
                (2, 'OCR and Document Processing',        'Rangi Perera',         'ML Engineer'),
                (3, 'Task Management and Calendar',       'Praneepah Tharushini', 'Full-Stack Dev'),
                (4, 'Analytics and Reporting',            'Dilshan Fernando',     'Data Engineer'),
                (5, 'Notifications and Reminders',        'Sachini Alwis',        'Backend Dev'),
                (6, 'Admin Panel and System Info',        'Kavidu Dissanayake',   'DevOps / Admin')
            ON CONFLICT DO NOTHING
        """),
        ("seed activity_logs", """
            INSERT INTO activity_logs (message, color)
            SELECT 'Scholar Track system initialised successfully', '#10b981'
            WHERE NOT EXISTS (SELECT 1 FROM activity_logs LIMIT 1)
        """),
    ]

    for label, sql in steps:
        _run(sql.strip(), label)

    print("Database migration complete")
