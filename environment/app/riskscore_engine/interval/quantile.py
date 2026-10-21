from riskscore_engine.errors import ScoringError
from riskscore_engine.feature_prep.transform import require_number
from riskscore_engine.interval.weights import effective_sample_size, sample_floor
from riskscore_engine.interval.winsor import winsor_level, winsorize
from riskscore_engine.timeutil import parse_timestamp


def collect_samples(
    rows: list[dict[str, object]],
    model_id: object,
    event_ts: object,
    max_age: float,
) -> list[tuple[object, float, float]]:
    valid = []
    for row in rows:
        if row.get("model_id") != model_id:
            continue
        recorded = parse_timestamp(str(row.get("recorded_at", "")))
        age = (event_ts - recorded).total_seconds()
        if age < 0 or age > max_age:
            continue
        residual = abs(require_number(row.get("residual")))
        weight = require_number(row.get("weight", 1.0))
        if weight <= 0:
            raise ScoringError("invalid_residual")
        valid.append((row.get("segment"), residual, weight))
    return valid


def weighted_radius(samples: list[tuple[float, float]], coverage: float) -> float:
    samples.sort(key=lambda item: item[0])
    target = coverage * len(samples)
    total = 0.0
    for value, _weight in samples:
        total += 1.0
        if total >= target:
            return value
    return samples[-1][0]


def interval_radius(
    rows: list[dict[str, object]], model: dict[str, object], request: dict[str, object]
) -> float:
    event = parse_timestamp(str(request.get("event_time", "")))
    max_age = require_number(model.get("residual_max_age_sec"))
    coverage = require_number(model.get("coverage"))
    if max_age < 0:
        raise ScoringError("invalid_model")
    if not 0.0 < coverage <= 1.0:
        raise ScoringError("invalid_model")
    floor = sample_floor(model)
    level = winsor_level(model)
    segment = request.get("segment")
    valid = collect_samples(rows, model.get("model_id"), event, max_age)
    selected = [
        (value, weight) for group, value, weight in valid if group in {segment, "*"}
    ]
    if not selected:
        raise ScoringError("residual_unavailable")
    if effective_sample_size([weight for _, weight in selected]) < floor:
        raise ScoringError("residual_unavailable")
    capped = winsorize(selected, level, weighted_radius)
    return weighted_radius(capped, coverage)
