import os
import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


def get_connection():
    """Open a new psycopg v3 connection returning rows as dicts."""
    return psycopg.connect(
        DATABASE_URL,
        sslmode="require",
        row_factory=dict_row,
    )


def migrate():
    """Create tables if they don't exist."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id            SERIAL PRIMARY KEY,
                email         VARCHAR(255) UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                name          VARCHAR(255) NOT NULL,
                created_at    TIMESTAMPTZ DEFAULT NOW()
            );
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id            SERIAL PRIMARY KEY,
                user_id       INTEGER REFERENCES users(id) ON DELETE CASCADE,
                task_title    VARCHAR(500) NOT NULL,
                subject       VARCHAR(255),
                deadline      DATE,
                category      VARCHAR(100) DEFAULT 'Other',
                description   TEXT,
                confidence    INTEGER DEFAULT 100,
                status        VARCHAR(50) DEFAULT 'pending',
                priority      VARCHAR(50) DEFAULT 'low',
                has_error     BOOLEAN DEFAULT FALSE,
                error_message TEXT,
                created_at    TIMESTAMPTZ DEFAULT NOW(),
                updated_at    TIMESTAMPTZ DEFAULT NOW()
            );
        """)

        # Migrate existing databases that don't yet have the priority column
        conn.execute("""
            ALTER TABLE tasks
            ADD COLUMN IF NOT EXISTS priority VARCHAR(50) DEFAULT 'low';
        """)

    print("Database migration complete")
