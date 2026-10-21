from itertools import pairwise

from riskscore_engine.errors import ScoringError
from riskscore_engine.feature_prep.transform import require_number


def apply_calibration(
    configs: list[dict[str, object]], name: object, value: float
) -> float:
    selected = next(
        (item for item in configs if item.get("calibrator_id") == name), None
    )
    if selected is None:
        raise ScoringError("calibrator_unavailable")
    points = selected.get("points")
    if not isinstance(points, list) or len(points) < 2:
        raise ScoringError("invalid_calibrator")
    clean = []
    last_x = None
    last_y = None
    for point in points:
        if not isinstance(point, list) or len(point) != 2:
            raise ScoringError("invalid_calibrator")
        x_value = require_number(point[0])
        y_value = require_number(point[1])
        if not 0.0 <= y_value <= 1.0:
            raise ScoringError("invalid_calibrator")
        if last_x is not None and x_value <= last_x:
            raise ScoringError("invalid_calibrator")
        if last_y is not None and y_value < last_y:
            raise ScoringError("invalid_calibrator")
        clean.append((x_value, y_value))
        last_x = x_value
        last_y = y_value
    if value <= clean[0][0]:
        return clean[0][1]
    if value >= clean[-1][0]:
        return clean[-1][1]
    for left, right in pairwise(clean):
        if left[0] <= value <= right[0]:
            ratio = (value - left[0]) / (right[0] - left[0])
            return left[1] + ratio * (right[1] - left[1])
    raise ScoringError("invalid_calibrator")
