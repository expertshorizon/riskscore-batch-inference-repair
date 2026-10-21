import math

from riskscore_engine.errors import ScoringError


def require_number(value: object) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ScoringError("invalid_feature")
    number = float(value)
    if not math.isfinite(number):
        raise ScoringError("invalid_feature")
    return number


def build_features(
    model: dict[str, object], snapshot: dict[str, object]
) -> dict[str, float]:
    values = snapshot.get("values")
    if not isinstance(values, dict):
        raise ScoringError("invalid_feature")
    defaults = model.get("defaults", {})
    required = model.get("required", [])
    clip = model.get("clip", {})
    mean = model.get("mean", {})
    scale = model.get("scale", {})
    if not all(isinstance(item, dict) for item in [defaults, clip, mean, scale]):
        raise ScoringError("invalid_model")
    if not isinstance(required, list):
        raise ScoringError("invalid_model")
    names = set(model.get("weights", {}))
    for group in model.get("interactions", []):
        if isinstance(group, list) and len(group) >= 3:
            names.update(group[:-1])
    encoded = {}
    for name in names:
        raw = values.get(name, defaults.get(name))
        if raw is None and name in required:
            raise ScoringError("missing_feature")
        if raw is None:
            continue
        number = require_number(raw)
        bounds = clip.get(name)
        if bounds is not None:
            if not isinstance(bounds, list) or len(bounds) != 2:
                raise ScoringError("invalid_model")
            low = require_number(bounds[0])
            high = require_number(bounds[1])
            if low > high:
                raise ScoringError("invalid_model")
            number = min(max(number, low), high)
        center = require_number(mean.get(name, 0.0))
        spread = require_number(scale.get(name, 1.0))
        if spread <= 0:
            raise ScoringError("invalid_model")
        encoded[name] = (number - center) / spread
    return encoded
