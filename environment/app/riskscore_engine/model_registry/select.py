from riskscore_engine.errors import ScoringError
from riskscore_engine.timeutil import parse_timestamp


def pick_model(
    models: list[dict[str, object]], request: dict[str, object]
) -> dict[str, object]:
    event = parse_timestamp(str(request.get("event_time", "")))
    segment = request.get("segment")
    eligible = []
    for model in models:
        if model.get("active") is not True:
            continue
        model_segment = model.get("segment")
        if model_segment not in {segment, "*"}:
            continue
        start = parse_timestamp(str(model.get("valid_from", "")))
        end_value = model.get("valid_to")
        if event < start:
            continue
        if end_value is not None and event >= parse_timestamp(str(end_value)):
            continue
        eligible.append(model)
    if not eligible:
        raise ScoringError("model_unavailable")
    eligible.sort(
        key=lambda item: (
            0 if item.get("segment") == "*" else 1,
            parse_timestamp(str(item["valid_from"])).timestamp(),
            int(item.get("revision", 0)),
            str(item.get("model_id", "")),
        )
    )
    return eligible[0]
