"""W11: bucket recent alarms into an alarm-storm timeline for the console."""

from __future__ import annotations

import datetime
from typing import Any


def _iso(ts: datetime.datetime) -> str:
    return ts.replace(tzinfo=datetime.UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def build_timeline(
    alarms: list[dict[str, Any]],
    bucket_seconds: int = 60,
    max_buckets: int = 120,
) -> dict[str, Any]:
    if not alarms:
        return {"bucketSeconds": bucket_seconds, "buckets": [], "total": 0, "peak": 0}

    # parse times
    times = []
    for alarm in alarms:
        ts_str = alarm.get("alarmRaisedTime")
        if not isinstance(ts_str, str):
            continue
        try:
            dt = datetime.datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=datetime.UTC)
            else:
                dt = dt.astimezone(datetime.UTC)
            times.append((dt, alarm))
        except ValueError:
            continue

    if not times:
        return {"bucketSeconds": bucket_seconds, "buckets": [], "total": 0, "peak": 0}

    times.sort(key=lambda x: x[0])
    first = times[0][0]
    last = times[-1][0]

    # align to bucket boundaries
    epoch = datetime.datetime(1970, 1, 1, tzinfo=datetime.UTC)
    start_ts = int((first - epoch).total_seconds())
    start_bucket = (start_ts // bucket_seconds) * bucket_seconds
    end_ts = int((last - epoch).total_seconds())
    end_bucket = ((end_ts // bucket_seconds) + 1) * bucket_seconds

    # create buckets
    bucket_count = (end_bucket - start_bucket) // bucket_seconds
    buckets = [
        {
            "start": _iso(epoch + datetime.timedelta(seconds=start_bucket + i * bucket_seconds)),
            "total": 0,
            "bySeverity": {"critical": 0, "major": 0, "minor": 0, "warning": 0, "cleared": 0},
        }
        for i in range(bucket_count)
    ]

    # map bucket index
    for dt, alarm in times:
        sec = int((dt - epoch).total_seconds())
        idx = (sec - start_bucket) // bucket_seconds
        bucket = buckets[idx]
        bucket["total"] += 1
        sev = str(alarm.get("perceivedSeverity") or "").lower()
        if sev in bucket["bySeverity"]:
            bucket["bySeverity"][sev] += 1

    # keep only last max_buckets
    if len(buckets) > max_buckets:
        buckets = buckets[-max_buckets:]
    total = sum(b["total"] for b in buckets)
    peak = max((b["total"] for b in buckets), default=0)

    return {
        "bucketSeconds": bucket_seconds,
        "buckets": buckets,
        "total": total,
        "peak": peak,
    }
