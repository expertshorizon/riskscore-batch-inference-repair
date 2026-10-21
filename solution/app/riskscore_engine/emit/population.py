TOLERANCE = 3.0


def median(values: list[float]) -> float:
    ordered = sorted(values)
    count = len(ordered)
    middle = count // 2
    if count % 2 == 1:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2.0


def spread(values: list[float], center: float) -> float:
    return median([abs(value - center) for value in values])


def flag_population(rows: list[dict[str, object]]) -> None:
    scores = [
        float(row["calibrated_score"]) for row in rows if row.get("status") != "error"
    ]
    if not scores:
        return
    center = median(scores)
    width = spread(scores, center)
    for row in rows:
        if row.get("status") == "error":
            continue
        deviation = abs(float(row["calibrated_score"]) - center)
        outlier = width > 0 and deviation > TOLERANCE * width
        row["population_flag"] = "outlier" if outlier else "typical"
