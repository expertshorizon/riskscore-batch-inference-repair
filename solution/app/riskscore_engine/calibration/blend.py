from riskscore_engine.calibration.piecewise import apply_calibration
from riskscore_engine.errors import ScoringError
from riskscore_engine.feature_prep.transform import require_number


def rollout_weight(model: dict[str, object]) -> float:
    if model.get("rollout_weight") is None:
        raise ScoringError("invalid_model")
    weight = require_number(model.get("rollout_weight"))
    if not 0.0 <= weight <= 1.0:
        raise ScoringError("invalid_model")
    return weight


def blended_score(
    configs: list[dict[str, object]], model: dict[str, object], raw: float
) -> float:
    primary = apply_calibration(configs, model.get("calibrator_id"), raw)
    shadow_id = model.get("shadow_calibrator_id")
    if shadow_id is None:
        return primary
    weight = rollout_weight(model)
    shadow = apply_calibration(configs, shadow_id, raw)
    return (1.0 - weight) * primary + weight * shadow
