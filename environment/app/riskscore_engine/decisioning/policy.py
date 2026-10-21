from riskscore_engine.errors import ScoringError
from riskscore_engine.feature_prep.transform import require_number


def detect_drift(model: dict[str, object], encoded: dict[str, float]) -> bool:
    limits = model.get("drift_limits", {})
    if not isinstance(limits, dict):
        raise ScoringError("invalid_model")
    for name, limit in limits.items():
        threshold = require_number(limit)
        if threshold < 0:
            raise ScoringError("invalid_model")
        if abs(encoded.get(name, 0.0)) >= threshold:
            return True
    return False


def choose_decision(
    request: dict[str, object], lower: float, upper: float, drift: bool
) -> str:
    approve = require_number(request.get("approve_threshold"))
    decline = require_number(request.get("decline_threshold"))
    if not 0.0 <= decline <= approve <= 1.0:
        raise ScoringError("invalid_request")
    if not drift and upper >= approve:
        return "approve"
    if not drift and lower < decline:
        return "decline"
    return "review"
