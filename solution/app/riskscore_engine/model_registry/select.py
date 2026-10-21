from riskscore_engine.errors import ScoringError
from riskscore_engine.timeutil import parse_timestamp


def segment_ancestors(segment: object) -> list[str]:
    parts = str(segment).split(".")
    return [".".join(parts[:count]) for count in range(len(parts) - 1, 0, -1)]


def segment_rank(model_segment: object, request_segment: object) -> int | None:
    if model_segment == request_segment:
        return 0
    ancestors = segment_ancestors(request_segment)
    if model_segment in ancestors:
        return ancestors.index(model_segment) + 1
    if model_segment == "*":
        return len(ancestors) + 1
    return None


def pick_model(
    models: list[dict[str, object]], request: dict[str, object]
) -> dict[str, object]:
    event = parse_timestamp(str(request.get("event_time", "")))
    segment = request.get("segment")
    eligible = []
    for model in models:
        if model.get("active") is not True:
            continue
        rank = segment_rank(model.get("segment"), segment)
        if rank is None:
            continue
        start = parse_timestamp(str(model.get("valid_from", "")))
        end_value = model.get("valid_to")
        if event < start:
            continue
        if end_value is not None and event >= parse_timestamp(str(end_value)):
            continue
        eligible.append((rank, model))
    if not eligible:
        raise ScoringError("model_unavailable")
    eligible.sort(
        key=lambda item: (
            item[0],
            -parse_timestamp(str(item[1]["valid_from"])).timestamp(),
            -int(item[1].get("revision", 0)),
            str(item[1].get("model_id", "")),
        )
    )
    return eligible[0][1]
