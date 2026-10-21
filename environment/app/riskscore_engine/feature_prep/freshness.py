import math

from riskscore_engine.errors import ScoringError
from riskscore_engine.feature_prep.transform import require_number


def decay_factor(model: dict[str, object], age_sec: float) -> float:
    half_life = model.get("feature_half_life_sec")
    if half_life is None:
        return 1.0
    span = require_number(half_life)
    if span <= 0:
        raise ScoringError("invalid_model")
    return math.exp(-age_sec / span)


def apply_decay(encoded: dict[str, float], factor: float) -> dict[str, float]:
    return {name: value * factor for name, value in encoded.items()}
