from riskscore_engine.errors import ScoringError
from riskscore_engine.feature_prep.transform import require_number
from riskscore_engine.timeutil import parse_timestamp


def pick_snapshot(
    rows: list[dict[str, object]], request: dict[str, object]
) -> tuple[dict[str, object], float]:
    event = parse_timestamp(str(request.get("event_time", "")))
    entity = request.get("entity_id")
    limit = require_number(request.get("max_age_sec"))
    if limit < 0:
        raise ScoringError("invalid_request")
    candidates = []
    for row in rows:
        if row.get("entity_id") != entity:
            continue
        observed = parse_timestamp(str(row.get("observed_at", "")))
        if observed <= event:
            candidates.append((observed, str(row.get("snapshot_id", "")), row))
    if not candidates:
        raise ScoringError("snapshot_unavailable")
    candidates.sort(key=lambda item: (-item[0].timestamp(), item[1]))
    observed, _, selected = candidates[0]
    age = (event - observed).total_seconds()
    if age > limit:
        raise ScoringError("snapshot_stale")
    return selected, age
