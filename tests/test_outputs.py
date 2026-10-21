import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, "/app")

from riskscore_engine.errors import ScoringError
from riskscore_engine.pipeline import run_batch

BatchResult = tuple[list[dict[str, object]], dict[str, object]]

PAYLOAD = json.loads(Path("/tests/cases.json").read_text(encoding="utf-8"))
CASES = PAYLOAD["cases"]
FOCUS = PAYLOAD["focus"]
GOLDEN_SCORES_TEXT = Path("/tests/golden/scores.jsonl").read_text(encoding="utf-8")
GOLDEN_SCORES = [json.loads(line) for line in GOLDEN_SCORES_TEXT.splitlines()]
GOLDEN_MANIFEST = json.loads(
    Path("/tests/golden/run_manifest.json").read_text(encoding="utf-8")
)
GOLDEN_BY_CASE_ID = {row["case_id"]: row for row in GOLDEN_SCORES}
CASE_IDS = [row["case_id"] for row in GOLDEN_SCORES]
SUCCESS_FIELDS = {
    "calibrated_score",
    "case_id",
    "confidence_interval",
    "decision",
    "drift",
    "entity_id",
    "feature_digest",
    "model_id",
    "population_flag",
    "raw_score",
    "snapshot_id",
}
ERROR_FIELDS = {"case_id", "entity_id", "error_code", "status"}
MANIFEST_FIELDS = [
    "approve",
    "decline",
    "distinct_models",
    "error",
    "outlier",
    "review",
    "rows",
    "success",
]


def run_batch_once() -> BatchResult:
    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp) / "out"
        run_batch(Path("/app/fixtures"), output_dir)
        scores_text = (output_dir / "scores.jsonl").read_text(encoding="utf-8")
        scores = [json.loads(line) for line in scores_text.splitlines()]
        manifest_text = (output_dir / "run_manifest.json").read_text(encoding="utf-8")
        return scores, json.loads(manifest_text)


@pytest.fixture(scope="session")
def batch_result() -> BatchResult:
    return run_batch_once()


@pytest.fixture(scope="session")
def batch_rows_by_case_id(batch_result: BatchResult) -> dict[str, object]:
    rows, _ = batch_result
    return {row["case_id"]: row for row in rows}


def evaluate(case: dict[str, object]) -> tuple[dict[str, object] | None, str | None]:
    from riskscore_engine.pipeline import score_request

    try:
        result = score_request(
            case["request"],
            case["models"],
            case["snapshots"],
            case["calibrators"],
            case["residuals"],
            case["fits"],
        )
    except ScoringError as exc:
        return None, exc.code
    except (KeyError, TypeError, ValueError):
        return None, "invalid_input"
    return result, None


@pytest.mark.parametrize("case_index", range(len(CASES)))
def test_scenario_result(case_index: int) -> None:
    """Checks the full score_request result or error code for one scenario."""
    case = CASES[case_index]
    actual, code = evaluate(case)
    assert code == case["expected_error"]
    assert actual == case["expected"]


@pytest.mark.parametrize("case_index", FOCUS["blend"])
def test_rollout_blend_calibrated_score(case_index: int) -> None:
    """Checks the calibrated score for a shadow-calibrator rollout scenario."""
    case = CASES[case_index]
    actual, code = evaluate(case)
    if case["expected_error"] is not None:
        assert code == case["expected_error"]
        return
    assert code is None
    assert actual["calibrated_score"] == case["expected"]["calibrated_score"]
    assert actual["raw_score"] == case["expected"]["raw_score"]


@pytest.mark.parametrize("case_index", FOCUS["interval"])
def test_residual_interval_bounds(case_index: int) -> None:
    """Checks the uncertainty interval for a residual selection scenario."""
    case = CASES[case_index]
    actual, code = evaluate(case)
    if case["expected_error"] is not None:
        assert code == case["expected_error"]
        return
    assert code is None
    assert actual["confidence_interval"] == case["expected"]["confidence_interval"]
    assert actual["decision"] == case["expected"]["decision"]


@pytest.mark.parametrize("case_index", FOCUS["isotonic"])
def test_isotonic_recalibration(case_index: int) -> None:
    """Checks the isotonic-recalibrated score for a monotone-fit scenario."""
    case = CASES[case_index]
    actual, code = evaluate(case)
    if case["expected_error"] is not None:
        assert code == case["expected_error"]
        return
    assert code is None
    assert actual["calibrated_score"] == case["expected"]["calibrated_score"]
    assert actual["confidence_interval"] == case["expected"]["confidence_interval"]


@pytest.mark.parametrize("case_index", FOCUS["isoseg"])
def test_isotonic_segment_resolution(case_index: int) -> None:
    """Checks which isotonic entry a hierarchical segment resolves to."""
    case = CASES[case_index]
    actual, code = evaluate(case)
    if case["expected_error"] is not None:
        assert code == case["expected_error"]
        return
    assert code is None
    assert actual["calibrated_score"] == case["expected"]["calibrated_score"]
    assert actual["decision"] == case["expected"]["decision"]


@pytest.mark.parametrize("case_index", FOCUS["winsor"])
def test_winsorized_residual_radius(case_index: int) -> None:
    """Checks the interval when extreme residuals are capped before the radius."""
    case = CASES[case_index]
    actual, code = evaluate(case)
    if case["expected_error"] is not None:
        assert code == case["expected_error"]
        return
    assert code is None
    assert actual["confidence_interval"] == case["expected"]["confidence_interval"]


@pytest.mark.parametrize("case_index", FOCUS["ess"])
def test_effective_sample_gating(case_index: int) -> None:
    """Checks the interval when a residual level is skipped for weak sample weight."""
    case = CASES[case_index]
    actual, code = evaluate(case)
    if case["expected_error"] is not None:
        assert code == case["expected_error"]
        return
    assert code is None
    assert actual["confidence_interval"] == case["expected"]["confidence_interval"]


@pytest.mark.parametrize("case_index", FOCUS["drift"])
def test_drift_and_feature_digest(case_index: int) -> None:
    """Checks the drift flag and encoded-feature digest for a freshness scenario."""
    case = CASES[case_index]
    actual, code = evaluate(case)
    if case["expected_error"] is not None:
        assert code == case["expected_error"]
        return
    assert code is None
    assert actual["drift"] == case["expected"]["drift"]
    assert actual["feature_digest"] == case["expected"]["feature_digest"]


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_batch_row_matches_golden(
    case_id: str, batch_rows_by_case_id: dict[str, object]
) -> None:
    """Checks that one batch request produces the exact golden success or error row."""
    assert case_id in batch_rows_by_case_id
    assert batch_rows_by_case_id[case_id] == GOLDEN_BY_CASE_ID[case_id]


@pytest.mark.parametrize("field", MANIFEST_FIELDS)
def test_manifest_count_field(field: str, batch_result: BatchResult) -> None:
    """Checks that a single manifest count field matches the golden value."""
    _, manifest = batch_result
    assert manifest[field] == GOLDEN_MANIFEST[field]


@pytest.mark.parametrize("field", MANIFEST_FIELDS)
def test_manifest_field_matches_recomputation(
    field: str, batch_result: BatchResult
) -> None:
    """Checks a manifest count against the same count recomputed from the rows."""
    rows, manifest = batch_result
    success = [row for row in rows if row.get("status") != "error"]
    recomputed = {
        "approve": sum(row.get("decision") == "approve" for row in rows),
        "decline": sum(row.get("decision") == "decline" for row in rows),
        "distinct_models": len({row["model_id"] for row in success}),
        "error": len(rows) - len(success),
        "outlier": sum(row.get("population_flag") == "outlier" for row in success),
        "review": sum(row.get("decision") == "review" for row in rows),
        "rows": len(rows),
        "success": len(success),
    }
    assert manifest[field] == recomputed[field]


def test_manifest_hash_matches_recomputed_digest(batch_result: BatchResult) -> None:
    """Checks that the manifest hash equals the sha256 of the scores.jsonl bytes."""
    rows, manifest = batch_result
    lines = (json.dumps(row, sort_keys=True, separators=(",", ":")) for row in rows)
    payload = "".join(f"{line}\n" for line in lines).encode()
    assert manifest["scores_sha256"] == hashlib.sha256(payload).hexdigest()
    assert manifest["scores_sha256"] == GOLDEN_MANIFEST["scores_sha256"]


def test_scores_ordered_by_case_id(batch_result: BatchResult) -> None:
    """Checks that output rows are ordered ascending by case_id."""
    rows, _ = batch_result
    ids = [str(row["case_id"]) for row in rows]
    assert ids == sorted(ids)


def test_success_rows_have_exact_field_set(batch_result: BatchResult) -> None:
    """Checks that every successful row carries exactly the specified fields."""
    rows, _ = batch_result
    success = [row for row in rows if row.get("status") != "error"]
    assert success
    for row in success:
        assert set(row) == SUCCESS_FIELDS
        assert len(row["confidence_interval"]) == 2
        assert row["confidence_interval"][0] <= row["confidence_interval"][1]
        assert row["population_flag"] in {"outlier", "typical"}
        assert 0.0 <= row["confidence_interval"][0] <= 1.0
        assert 0.0 <= row["confidence_interval"][1] <= 1.0


def test_error_rows_have_exact_field_set(batch_result: BatchResult) -> None:
    """Checks that every error row carries exactly the specified fields."""
    rows, _ = batch_result
    failures = [row for row in rows if row.get("status") == "error"]
    assert failures
    for row in failures:
        assert set(row) == ERROR_FIELDS
        assert isinstance(row["error_code"], str)


def test_manifest_is_canonical_sorted_json() -> None:
    """Checks that the manifest file is canonical JSON with sorted keys."""
    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp) / "out"
        run_batch(Path("/app/fixtures"), output_dir)
        text = (output_dir / "run_manifest.json").read_text(encoding="utf-8")
        manifest = json.loads(text)
        expected = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
        assert text.strip() == expected
        assert set(manifest) == set(MANIFEST_FIELDS) | {"scores_sha256"}


def test_repeated_runs_are_byte_identical() -> None:
    """Checks that running the batch twice yields byte-matching output files."""
    with tempfile.TemporaryDirectory() as tmp:
        out_a = Path(tmp) / "a"
        out_b = Path(tmp) / "b"
        run_batch(Path("/app/fixtures"), out_a)
        run_batch(Path("/app/fixtures"), out_b)
        left = (out_a / "scores.jsonl").read_bytes()
        right = (out_b / "scores.jsonl").read_bytes()
        assert left == right
        assert (out_a / "run_manifest.json").read_bytes() == (
            out_b / "run_manifest.json"
        ).read_bytes()


def test_rerun_replaces_existing_output_files() -> None:
    """Checks that a second run replaces stale output and leaves no temp files."""
    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp) / "out"
        output_dir.mkdir(parents=True)
        (output_dir / "scores.jsonl").write_text("stale\n", encoding="utf-8")
        (output_dir / "run_manifest.json").write_text("stale\n", encoding="utf-8")
        run_batch(Path("/app/fixtures"), output_dir)
        lines = (output_dir / "scores.jsonl").read_text(encoding="utf-8").splitlines()
        assert lines and lines[0] != "stale"
        assert json.loads(lines[0])["case_id"] == GOLDEN_SCORES[0]["case_id"]
        manifest = json.loads(
            (output_dir / "run_manifest.json").read_text(encoding="utf-8")
        )
        assert manifest["rows"] == GOLDEN_MANIFEST["rows"]
        leftovers = sorted(item.name for item in output_dir.iterdir())
        assert leftovers == ["run_manifest.json", "scores.jsonl"]


def test_cli_entrypoint_produces_matching_digest() -> None:
    """Checks that the score_batch.py subprocess reproduces the golden digest."""
    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp) / "out"
        env = dict(os.environ)
        env["PYTHONPATH"] = "/app"
        command = [
            sys.executable,
            "/app/score_batch.py",
            "--fixtures",
            "/app/fixtures",
            "--output",
            str(output_dir),
        ]
        result = subprocess.run(
            command, env=env, capture_output=True, text=True, timeout=300, check=False
        )
        assert result.returncode == 0
        manifest = json.loads(
            (output_dir / "run_manifest.json").read_text(encoding="utf-8")
        )
        assert manifest["scores_sha256"] == GOLDEN_MANIFEST["scores_sha256"]
        assert manifest["distinct_models"] == GOLDEN_MANIFEST["distinct_models"]
