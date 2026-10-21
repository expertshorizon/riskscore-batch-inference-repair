from datetime import datetime, timezone


def parse_timestamp(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("invalid_time")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid_time") from exc
    if parsed.tzinfo is None:
        raise ValueError("invalid_time")
    return parsed.astimezone(timezone.utc)
