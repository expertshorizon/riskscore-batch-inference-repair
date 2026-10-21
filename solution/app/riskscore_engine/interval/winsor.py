from riskscore_engine.errors import ScoringError
from riskscore_engine.feature_prep.transform import require_number


def winsor_level(model: dict[str, object]) -> float | None:
    value = model.get("winsor_quantile")
    if value is None:
        return None
    level = require_number(value)
    if not 0.0 < level <= 1.0:
        raise ScoringError("invalid_model")
    return level


def winsorize(
    samples: list[tuple[float, float]], level: float | None, radius_of: object
) -> list[tuple[float, float]]:
    if level is None:
        return samples
    cap = radius_of(list(samples), level)
    return [(min(value, cap), weight) for value, weight in samples]
