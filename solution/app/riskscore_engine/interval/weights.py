from riskscore_engine.errors import ScoringError
from riskscore_engine.feature_prep.transform import require_number


def effective_sample_size(weights: list[float]) -> float:
    total = sum(weights)
    squared = sum(weight * weight for weight in weights)
    if squared <= 0.0:
        return 0.0
    return (total * total) / squared


def sample_floor(model: dict[str, object]) -> float:
    value = model.get("min_effective_samples")
    if value is None:
        return 1.0
    limit = require_number(value)
    if limit < 0:
        raise ScoringError("invalid_model")
    return limit
