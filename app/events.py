import math
import uuid

OUTCOMES = {"completed", "intercepted", "out", "unknown"}


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Angka harus valid.")
    return float(value)


def point(value):
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError("Tandai posisi pada video.")
    result = [number(v) for v in value]
    if any(v < 0 or v > 1 for v in result):
        raise ValueError("Posisi harus berada di dalam video.")
    return result


def validate_event(item, duration):
    start, end = number(item.get("start")), number(item.get("end"))
    if not 0 <= start < end <= duration:
        raise ValueError("Waktu akhir harus setelah awal dan masih di dalam klip.")
    kind = item.get("kind", "pass")
    if kind not in {"pass", "possession"}:
        raise ValueError("Jenis kejadian tidak dikenal.")
    outcome = item.get("outcome", "unknown")
    if outcome not in OUTCOMES:
        raise ValueError("Hasil umpan tidak dikenal.")
    identifier = item.get("id") or str(uuid.uuid4())
    try:
        uuid.UUID(identifier)
    except (ValueError, TypeError, AttributeError):
        raise ValueError("ID kejadian tidak valid.") from None
    note, player = item.get("note", ""), item.get("player", "")
    if not isinstance(note, str) or len(note) > 2000 or not isinstance(player, str) or len(player) > 100:
        raise ValueError("Catatan atau nama pemain terlalu panjang.")
    if not isinstance(item.get("reviewed", False), bool):
        raise ValueError("Status review tidak valid.")
    return dict(id=identifier, kind=kind, start=start, end=end,
                source=point(item.get("source")), target=point(item.get("target")),
                outcome=outcome, reviewed=item.get("reviewed", False),
                note=note, player=player, provenance="coach")


def summary(events):
    passes = [e for e in events if e["kind"] == "pass"]
    known = [e for e in passes if e["reviewed"] and e["outcome"] != "unknown"]
    return dict(total=len(passes),
                completion=round(100 * sum(e["outcome"] == "completed" for e in known) / len(known), 1) if known else None,
                unknown=sum(e["outcome"] == "unknown" for e in passes),
                unreviewed=sum(not e["reviewed"] for e in passes),
                reviewed=len(known))
