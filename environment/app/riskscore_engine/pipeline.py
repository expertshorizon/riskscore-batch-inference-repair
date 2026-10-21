import hashlib
from pathlib import Path

from riskscore_engine.calibration.blend import blended_score
from riskscore_engine.calibration.isotonic import apply_isotonic
from riskscore_engine.decisioning.policy import choose_decision, detect_drift
from riskscore_engine.emit.population import flag_population
from riskscore_engine.emit.writer import canonical, write_run_outputs
from riskscore_engine.errors import ScoringError
from riskscore_engine.feature_prep.freshness import apply_decay, decay_factor
from riskscore_engine.feature_prep.snapshot import pick_snapshot
from riskscore_engine.feature_prep.transform import build_features
from riskscore_engine.interval.quantile import interval_radius
from riskscore_engine.io import read_json, read_jsonl
from riskscore_engine.model_registry.select import pick_model
from riskscore_engine.scoring.linear import score_model


def round6(value: float) -> float:
    return round(value + 0.0, 6)


def score_request(
    request: dict[str, object],
    models: list[dict[str, object]],
    snapshots: list[dict[str, object]],
    calibrators: list[dict[str, object]],
    residuals: list[dict[str, object]],
    fits: list[dict[str, object]],
) -> dict[str, object]:
    case_id = request.get("case_id")
    entity_id = request.get("entity_id")
    bad_case_id = not isinstance(case_id, str) or not case_id
    bad_entity_id = not isinstance(entity_id, str) or not entity_id
    if bad_case_id or bad_entity_id:
        raise ScoringError("invalid_request")
    model = pick_model(models, request)
    snapshot, age = pick_snapshot(snapshots, request)
    standardized = build_features(model, snapshot)
    encoded = apply_decay(standardized, decay_factor(model, age))
    raw = score_model(model, encoded)
    adjusted = apply_isotonic(fits, model, request, raw)
    calibrated = blended_score(calibrators, model, adjusted)
    width = interval_radius(residuals, model, request)
    lower = calibrated - width
    upper = calibrated + width
    drift = detect_drift(model, encoded)
    decision = choose_decision(request, lower, upper, drift)
    feature_digest = hashlib.sha256(canonical(snapshot.get("values", {})).encode())
    return {
        "calibrated_score": round6(calibrated),
        "case_id": case_id,
        "confidence_interval": [round6(lower), round6(upper)],
        "decision": decision,
        "drift": drift,
        "entity_id": entity_id,
        "feature_digest": feature_digest.hexdigest(),
        "model_id": model["model_id"],
        "raw_score": round6(raw),
        "snapshot_id": snapshot["snapshot_id"],
    }


def run_batch(fixtures: Path, output: Path) -> None:
    requests = read_jsonl(fixtures / "scoring_requests.jsonl")
    snapshots = read_jsonl(fixtures / "feature_snapshots.jsonl")
    models = read_json(fixtures / "model_catalog.json")
    calibrators = read_json(fixtures / "calibrators.json")
    residuals = read_jsonl(fixtures / "residual_samples.jsonl")
    fits = read_jsonl(fixtures / "isotonic_fits.jsonl")
    if not isinstance(models, list) or not isinstance(calibrators, list):
        raise ScoringError("invalid_input")
    rows = []
    for request in requests:
        try:
            row = score_request(
                request, models, snapshots, calibrators, residuals, fits
            )
            rows.append(row)
        except (ScoringError, KeyError, TypeError) as exc:
            code = exc.code if isinstance(exc, ScoringError) else "invalid_input"
            rows.append(
                {
                    "case_id": request.get("case_id"),
                    "entity_id": request.get("entity_id"),
                    "error_code": code,
                    "status": "error",
                }
            )
    flag_population(rows)
    write_run_outputs(rows, output)
