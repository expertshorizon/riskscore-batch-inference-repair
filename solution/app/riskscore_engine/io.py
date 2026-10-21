import json
from pathlib import Path

from riskscore_engine.errors import ScoringError


def read_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ScoringError("invalid_input") from exc


def read_jsonl(path: Path) -> list[dict[str, object]]:
    rows = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ScoringError("invalid_input")
                rows.append(value)
    except (OSError, json.JSONDecodeError) as exc:
        raise ScoringError("invalid_input") from exc
    return rows
