import hashlib
import json
import os
from pathlib import Path


def canonical(value: dict[str, object]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def build_manifest(rows: list[dict[str, object]], payload: bytes) -> dict[str, object]:
    used = {row["model_id"] for row in rows if row.get("status") != "error"}
    return {
        "approve": sum(row.get("decision") == "approve" for row in rows),
        "decline": sum(row.get("decision") == "decline" for row in rows),
        "distinct_models": len(used),
        "error": sum(row.get("status") == "error" for row in rows),
        "outlier": sum(row.get("population_flag") == "outlier" for row in rows),
        "review": sum(row.get("decision") == "review" for row in rows),
        "rows": len(rows),
        "scores_sha256": hashlib.sha256(payload).hexdigest(),
        "success": sum(row.get("status") != "error" for row in rows),
    }


def write_run_outputs(rows: list[dict[str, object]], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    ordered = sorted(rows, key=lambda item: str(item["case_id"]))
    payload = "".join(f"{canonical(row)}\n" for row in ordered).encode()
    manifest = build_manifest(ordered, payload)
    scores_tmp = output_dir / ".scores.jsonl.tmp"
    manifest_tmp = output_dir / ".run_manifest.json.tmp"
    scores_tmp.write_bytes(payload)
    manifest_tmp.write_text(f"{canonical(manifest)}\n", encoding="utf-8")
    os.replace(scores_tmp, output_dir / "scores.jsonl")
    os.replace(manifest_tmp, output_dir / "run_manifest.json")
