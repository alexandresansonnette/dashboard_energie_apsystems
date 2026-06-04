import json
import sqlite3
from pathlib import Path
from typing import Any, Dict

DB_PATH = Path("data/energie.sqlite")


def connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS api_snapshots (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at  TEXT    DEFAULT CURRENT_TIMESTAMP,
            source      TEXT    NOT NULL,
            level       TEXT,
            date_range  TEXT,
            payload     TEXT    NOT NULL
        )
    """)
    conn.commit()
    return conn


def save_snapshot(
    source: str,
    payload: Dict[str, Any],
    level: str = "",
    date_range: str = "",
) -> None:
    conn = connect()
    conn.execute(
        "INSERT INTO api_snapshots(source, level, date_range, payload) VALUES (?, ?, ?, ?)",
        (source, level, date_range, json.dumps(payload, ensure_ascii=False)),
    )
    conn.commit()
    conn.close()