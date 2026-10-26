"""Pure metrics helpers for Research OS capacity evidence.

Network/load generation is deliberately separate from this module so metric
calculations can be tested deterministically without contacting a service.
"""
from __future__ import annotations

import math
import statistics
from collections import Counter
from typing import Any, Iterable


def nearest_rank_percentile(values: Iterable[float], percentile: float) -> float | None:
    """Calculate a nearest-rank percentile; return None when no samples exist."""
    if not 0 < percentile <= 100:
        raise ValueError("percentile must be in the interval (0, 100]")
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return None
    rank = max(1, math.ceil(percentile * len(ordered) / 100))
    return round(ordered[rank - 1], 3)


def summarize_samples(samples: list[dict[str, Any]], elapsed_seconds: float) -> dict[str, Any]:
    """Summarize normalized per-request observations without inventing missing data."""
    latencies = [
        float(item["latency_ms"])
        for item in samples
        if item.get("latency_ms") is not None
    ]
    failures = sum(bool(item.get("error")) for item in samples)
    statuses = Counter(
        str(item["status"]) for item in samples if item.get("status") is not None
    )
    count = len(samples)
    return {
        "requests_completed": count,
        "requests_succeeded": count - failures,
        "requests_failed": failures,
        "error_rate": round(failures / count, 6) if count else None,
        "elapsed_seconds": round(elapsed_seconds, 3),
        "throughput_requests_per_second": (
            round(count / elapsed_seconds, 3) if elapsed_seconds > 0 else None
        ),
        "http_status_counts": dict(sorted(statuses.items())),
        "latency_ms": {
            "min": round(min(latencies), 3) if latencies else None,
            "mean": round(statistics.fmean(latencies), 3) if latencies else None,
            "p50": nearest_rank_percentile(latencies, 50),
            "p95": nearest_rank_percentile(latencies, 95),
            "p99": nearest_rank_percentile(latencies, 99),
            "max": round(max(latencies), 3) if latencies else None,
        },
    }
