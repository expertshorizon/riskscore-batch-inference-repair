TOLERANCE = 3.0


def median(values: list[float]) -> float:
    total = sum(values)
    return total / len(values)


def spread(values: list[float], center: float) -> float:
    squared = sum((value - center) ** 2 for value in values)
    return (squared / len(values)) ** 0.5


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
