import json
import sqlite3
from pathlib import Path

from .events import validate_event


class Store:
    def __init__(self, path, duration):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.duration = duration
        with sqlite3.connect(self.path) as db:
            db.execute("CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, payload TEXT NOT NULL)")

    def list(self):
        with sqlite3.connect(self.path) as db:
            rows = [json.loads(row[0]) for row in db.execute("SELECT payload FROM events")]
        return sorted(rows, key=lambda e: e["start"])

    def save(self, item):
        item = validate_event(item, self.duration)
        with sqlite3.connect(self.path) as db:
            db.execute("INSERT INTO events VALUES (?, ?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload",
                       (item["id"], json.dumps(item, allow_nan=False)))
        return item

    def delete(self, identifier):
        with sqlite3.connect(self.path) as db:
            db.execute("DELETE FROM events WHERE id=?", (identifier,))
