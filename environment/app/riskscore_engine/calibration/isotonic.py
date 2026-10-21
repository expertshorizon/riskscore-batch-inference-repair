from riskscore_engine.errors import ScoringError
from riskscore_engine.feature_prep.transform import require_number


def merge_duplicates(points: list[tuple[float, float, float]]) -> list[list[float]]:
    grouped: dict[float, list[float]] = {}
    for x_value, y_value, weight in points:
        bucket = grouped.setdefault(x_value, [0.0, 0.0, 0.0])
        bucket[0] += y_value
        bucket[1] += weight
        bucket[2] += 1.0
    merged = []
    for x_value in sorted(grouped):
        total_y, total_weight, count = grouped[x_value]
        merged.append([x_value, x_value, total_y / count, total_weight])
    return merged


def pool_adjacent_violators(blocks: list[list[float]]) -> list[list[float]]:
    fitted = []
    running = None
    for block in blocks:
        level = block[2] if running is None else max(running, block[2])
        running = level
        fitted.append([block[0], block[1], level, block[3]])
    return fitted


def read_observations(entry: dict[str, object]) -> list[tuple[float, float, float]]:
    observations = entry.get("observations")
    if not isinstance(observations, list) or len(observations) < 2:
        raise ScoringError("invalid_isotonic")
    points = []
    for item in observations:
        if not isinstance(item, list) or len(item) != 3:
            raise ScoringError("invalid_isotonic")
        x_value = require_number(item[0])
        y_value = require_number(item[1])
        weight = require_number(item[2])
        if not 0.0 <= y_value <= 1.0:
            raise ScoringError("invalid_isotonic")
        if weight <= 0:
            raise ScoringError("invalid_isotonic")
        points.append((x_value, y_value, weight))
    return points


def evaluate(blocks: list[list[float]], value: float) -> float:
    if value <= blocks[0][0]:
        return blocks[0][2]
    if value >= blocks[-1][1]:
        return blocks[-1][2]
    for index, block in enumerate(blocks):
        if block[0] <= value <= block[1]:
            return block[2]
        if index + 1 < len(blocks) and block[1] < value < blocks[index + 1][0]:
            following = blocks[index + 1]
            span = following[0] - block[1]
            ratio = (value - block[1]) / span
            return block[2] + ratio * (following[2] - block[2])
    return blocks[-1][2]


def pick_entry(
    fits: list[dict[str, object]], name: object, request: dict[str, object]
) -> dict[str, object] | None:
    segment = request.get("segment")
    for item in fits:
        if item.get("isotonic_id") != name:
            continue
        if item.get("segment") in {segment, "*"}:
            return item
    return None


def apply_isotonic(
    fits: list[dict[str, object]],
    model: dict[str, object],
    request: dict[str, object],
    value: float,
) -> float:
    name = model.get("isotonic_id")
    if name is None:
        return value
    entry = pick_entry(fits, name, request)
    if entry is None:
        raise ScoringError("isotonic_unavailable")
    points = read_observations(entry)
    merged = merge_duplicates(points)
    if len(merged) < 2:
        raise ScoringError("invalid_isotonic")
    return evaluate(pool_adjacent_violators(merged), value)
