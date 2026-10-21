from riskscore_engine.errors import ScoringError
from riskscore_engine.feature_prep.transform import require_number
from riskscore_engine.timeutil import parse_timestamp


def merge_duplicates(points: list[tuple[float, float, float]]) -> list[list[float]]:
    grouped: dict[float, list[float]] = {}
    for x_value, y_value, weight in points:
        bucket = grouped.setdefault(x_value, [0.0, 0.0])
        bucket[0] += y_value * weight
        bucket[1] += weight
    merged = []
    for x_value in sorted(grouped):
        total_y, total_weight = grouped[x_value]
        merged.append([x_value, x_value, total_y / total_weight, total_weight])
    return merged


def pool_adjacent_violators(blocks: list[list[float]]) -> list[list[float]]:
    stack: list[list[float]] = []
    for block in blocks:
        stack.append(list(block))
        while len(stack) >= 2 and stack[-2][2] > stack[-1][2]:
            right = stack.pop()
            left = stack.pop()
            weight = left[3] + right[3]
            level = (left[2] * left[3] + right[2] * right[3]) / weight
            stack.append([left[0], right[1], level, weight])
    return stack


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


def segment_ancestors(segment: object) -> list[str]:
    parts = str(segment).split(".")
    return [".".join(parts[:count]) for count in range(len(parts) - 1, 0, -1)]


def in_window(entry: dict[str, object], event: object) -> bool:
    start = parse_timestamp(str(entry.get("valid_from", "")))
    if event < start:
        return False
    end = entry.get("valid_to")
    if end is None:
        return True
    return event < parse_timestamp(str(end))


def pick_entry(
    fits: list[dict[str, object]], name: object, request: dict[str, object]
) -> dict[str, object] | None:
    event = parse_timestamp(str(request.get("event_time", "")))
    segment = request.get("segment")
    eligible = [
        item
        for item in fits
        if item.get("isotonic_id") == name and in_window(item, event)
    ]
    for candidate in [segment, *segment_ancestors(segment), "*"]:
        matched = [item for item in eligible if item.get("segment") == candidate]
        if matched:
            matched.sort(
                key=lambda item: (
                    -parse_timestamp(str(item.get("valid_from", ""))).timestamp()
                )
            )
            return matched[0]
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
