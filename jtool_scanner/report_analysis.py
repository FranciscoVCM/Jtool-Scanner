"""Helpers for summarizing scan report diagnostics."""

from __future__ import annotations

from collections import Counter
from statistics import median
from typing import Any


DETAIL_GROUP_ORDER = (
    "saves",
    "warps",
    "apples",
    "water",
    "walljumps",
    "blocks",
    "full_spikes",
    "mini_spikes",
)


def analyze_report(
    report: dict[str, Any],
    groups: list[str] | None = None,
    limit: int = 5,
) -> list[str]:
    selected_groups = groups or _groups_by_issue_count(report)
    if not selected_groups:
        return ["no detailed diagnostics found"]

    lines = [_report_heading(report)]
    for group in selected_groups:
        rows = _collect_group_rows(report, group)
        unmatched = [row for row in rows if row["status"] == "unmatched_detection"]
        missed = [row for row in rows if row["status"] == "missed_truth"]
        if not unmatched and not missed:
            continue

        lines.append("")
        lines.append(
            f"{group}: {len(unmatched)} unmatched detections, {len(missed)} missed truth"
        )
        lines.extend(_pair_summary(rows, limit))
        if unmatched:
            lines.extend(_unmatched_summary(unmatched, limit))
        if missed:
            lines.extend(_missed_summary(missed, limit))

    return lines


def _report_heading(report: dict[str, Any]) -> str:
    settings = report.get("settings", {})
    manifest = report.get("manifest", "unknown manifest")
    grid_step = settings.get("grid_step", "unknown")
    tolerance = settings.get("tolerance", "unknown")
    return f"report: {manifest} (grid_step={grid_step}, tolerance={tolerance})"


def _groups_by_issue_count(report: dict[str, Any]) -> list[str]:
    counts = []
    for group in DETAIL_GROUP_ORDER:
        rows = _collect_group_rows(report, group)
        if rows:
            counts.append((len(rows), group))
    return [group for _, group in sorted(counts, reverse=True)]


def _collect_group_rows(report: dict[str, Any], group: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for pair in report.get("pairs", []):
        pair_id = pair.get("id", "unknown")
        details = pair.get("details", {}).get(group)
        if not details:
            continue
        for detection in details.get("unmatched_detections", []):
            row = {
                **detection,
                "pair_id": pair_id,
                "status": "unmatched_detection",
                "nearest_distance": _nearest_distance(detection.get("nearest_truth")),
            }
            rows.append(row)
        for truth in details.get("missed_truth", []):
            row = {
                **truth,
                "pair_id": pair_id,
                "status": "missed_truth",
                "nearest_distance": _nearest_distance(truth.get("nearest_detection")),
            }
            rows.append(row)
    return rows


def _pair_summary(rows: list[dict[str, Any]], limit: int) -> list[str]:
    pair_counts: Counter[str] = Counter(row["pair_id"] for row in rows)
    if not pair_counts:
        return []
    chunks = [f"{pair}={count}" for pair, count in pair_counts.most_common(limit)]
    return [f"  by pair: {', '.join(chunks)}"]


def _unmatched_summary(rows: list[dict[str, Any]], limit: int) -> list[str]:
    lines: list[str] = []
    type_counts = Counter(row.get("type_name", "unknown") for row in rows)
    lines.append(f"  unmatched by type: {_format_counter(type_counts, limit)}")
    scores = [row["score"] for row in rows if isinstance(row.get("score"), (int, float))]
    if scores:
        lines.append(f"  unmatched score: {_format_numeric_summary(scores)}")
    lines.append(f"  unmatched nearest distance: {_format_distance_buckets(rows)}")
    lines.append("  highest-score unmatched:")
    for row in sorted(rows, key=lambda item: item.get("score", 0), reverse=True)[:limit]:
        lines.append(f"    {_format_unmatched_example(row)}")
    return lines


def _missed_summary(rows: list[dict[str, Any]], limit: int) -> list[str]:
    lines: list[str] = []
    type_counts = Counter(row.get("type_name", "unknown") for row in rows)
    lines.append(f"  missed by type: {_format_counter(type_counts, limit)}")
    lines.append(f"  missed nearest distance: {_format_distance_buckets(rows)}")

    near_rows = [
        row for row in rows if row.get("nearest_distance") is not None
    ]
    if near_rows:
        lines.append("  nearest missed truth:")
        for row in sorted(near_rows, key=lambda item: item["nearest_distance"])[:limit]:
            lines.append(f"    {_format_missed_example(row)}")

    no_near_rows = [row for row in rows if row.get("nearest_distance") is None]
    if no_near_rows:
        lines.append("  missed truth with no nearby detection:")
        for row in no_near_rows[:limit]:
            lines.append(f"    {row['pair_id']} {row.get('type_name')} ({row['x']},{row['y']})")
    return lines


def _format_counter(counter: Counter[str], limit: int) -> str:
    return ", ".join(f"{name}={count}" for name, count in counter.most_common(limit))


def _format_numeric_summary(values: list[float]) -> str:
    values = sorted(values)
    return (
        f"min={values[0]:.3f}, median={median(values):.3f}, "
        f"max={values[-1]:.3f}"
    )


def _format_distance_buckets(rows: list[dict[str, Any]]) -> str:
    buckets = Counter()
    for row in rows:
        distance = row.get("nearest_distance")
        if distance is None:
            buckets["none"] += 1
        elif distance <= 24:
            buckets["<=24"] += 1
        elif distance <= 48:
            buckets["25-48"] += 1
        elif distance <= 96:
            buckets["49-96"] += 1
        else:
            buckets[">96"] += 1
    labels = ("<=24", "25-48", "49-96", ">96", "none")
    return ", ".join(f"{label}={buckets[label]}" for label in labels if buckets[label])


def _format_unmatched_example(row: dict[str, Any]) -> str:
    nearest = row.get("nearest_truth")
    nearest_text = _format_nearest(nearest)
    return (
        f"{row['pair_id']} {row.get('kind', row.get('type_name'))} "
        f"({row['x']},{row['y']}) score={row.get('score', 0):.3f} "
        f"nearest={nearest_text}"
    )


def _format_missed_example(row: dict[str, Any]) -> str:
    nearest = row.get("nearest_detection")
    nearest_text = _format_nearest(nearest)
    return (
        f"{row['pair_id']} {row.get('type_name')} ({row['x']},{row['y']}) "
        f"nearest={nearest_text}"
    )


def _format_nearest(nearest: dict[str, Any] | None) -> str:
    if not nearest:
        return "none"
    name = nearest.get("kind") or nearest.get("type_name") or "unknown"
    return (
        f"{name} ({nearest.get('x')},{nearest.get('y')}) "
        f"d={nearest.get('distance')}"
    )


def _nearest_distance(nearest: dict[str, Any] | None) -> float | None:
    if not nearest:
        return None
    distance = nearest.get("distance")
    return float(distance) if distance is not None else None
