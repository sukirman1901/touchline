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
            db.execute("CREATE TABLE IF NOT EXISTS dismissed (id TEXT PRIMARY KEY)")

    def merged(self, generated):
        with sqlite3.connect(self.path) as db:
            dismissed = {row[0] for row in db.execute("SELECT id FROM dismissed")}
        events = {event["id"]: event for event in generated if event["id"] not in dismissed}
        events.update({event["id"]: event for event in self.list()})
        return sorted(events.values(), key=lambda event: event["start"])

    def list(self):
        with sqlite3.connect(self.path) as db:
            rows = [json.loads(row[0]) for row in db.execute("SELECT payload FROM events")]
        return sorted(rows, key=lambda e: e["start"])

    def save(self, item, original=None):
        item = validate_event(item, self.duration)
        if original and original.get("trajectory") and all(
                item[key] == original[key] for key in ("kind", "start", "end", "source", "target")):
            item.update(trajectory=original["trajectory"], provenance="automatic",
                        confidence="reviewed" if item["reviewed"] else "candidate")
        with sqlite3.connect(self.path) as db:
            db.execute("DELETE FROM dismissed WHERE id=?", (item["id"],))
            db.execute("INSERT INTO events VALUES (?, ?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload",
                       (item["id"], json.dumps(item, allow_nan=False)))
        return item

    def delete(self, identifier):
        with sqlite3.connect(self.path) as db:
            db.execute("DELETE FROM events WHERE id=?", (identifier,))
            db.execute("INSERT OR IGNORE INTO dismissed VALUES (?)", (identifier,))
