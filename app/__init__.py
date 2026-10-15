from pathlib import Path
import sqlite3
from flask import Flask


def create_app():
    app = Flask(__name__)
    app.secret_key = "mock-interview-demo-secret"
    app.config["UPLOAD_FOLDER"] = Path(app.root_path) / "uploads"
    app.config["UPLOAD_FOLDER"].mkdir(parents=True, exist_ok=True)
    app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

    db = Path(app.root_path) / "demo.db"
    app.config["DB_PATH"] = db

    with sqlite3.connect(db) as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            cv_name TEXT,
            cv_text TEXT,
            jd_text TEXT,
            position TEXT,
            level TEXT,
            job_profile TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            position TEXT,
            level TEXT,
            question TEXT,
            answer TEXT,
            cleaned TEXT,
            score REAL,
            details TEXT,
            duration INTEGER DEFAULT 0,
            audio_name TEXT,
            run_id TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        """)
        cols = {row[1] for row in conn.execute("PRAGMA table_info(sessions)").fetchall()}
        if "run_id" not in cols:
            conn.execute("ALTER TABLE sessions ADD COLUMN run_id TEXT")
        conn.execute("INSERT OR IGNORE INTO users(username,password,role) VALUES('admin','admin123','admin')")
        conn.execute("INSERT OR IGNORE INTO users(username,password,role) VALUES('guest','guest123','guest')")

    from .routes import bp
    app.register_blueprint(bp)
    return app
