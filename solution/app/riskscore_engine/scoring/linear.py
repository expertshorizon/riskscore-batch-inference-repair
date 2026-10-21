import math

from riskscore_engine.errors import ScoringError
from riskscore_engine.feature_prep.transform import require_number


def logistic(score: float) -> float:
    if score >= 0:
        value = math.exp(-score)
        return 1.0 / (1.0 + value)
    value = math.exp(score)
    return value / (1.0 + value)


def score_model(model: dict[str, object], encoded: dict[str, float]) -> float:
    weights = model.get("weights")
    interactions = model.get("interactions", [])
    if not isinstance(weights, dict) or not isinstance(interactions, list):
        raise ScoringError("invalid_model")
    score = require_number(model.get("intercept", 0.0))
    for name, weight in weights.items():
        score += require_number(weight) * encoded.get(name, 0.0)
    for item in interactions:
        if not isinstance(item, list) or len(item) < 3:
            raise ScoringError("invalid_model")
        *factors, weight = item
        product = 1.0
        for factor in factors:
            product *= encoded.get(str(factor), 0.0)
        score += require_number(weight) * product
    return logistic(score)
