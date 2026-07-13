"""
Telemetria de engenharia: latência, jitter, índice de sincronia e séries temporais.

Projetado para coleta de evidências experimentais em apresentação de doutorado.
"""

from __future__ import annotations

import math
import statistics
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class TelemetryEngine:
    window: int = 240
    command_latencies_ms: deque[float] = field(default_factory=lambda: deque(maxlen=240))
    sync_intervals_ms: deque[float] = field(default_factory=lambda: deque(maxlen=240))
    heartbeats: dict[str, float] = field(default_factory=dict)
    series: deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=240))
    total_commands: int = 0
    total_sync_events: int = 0
    desync_events: int = 0
    last_sync_pair_ms: float | None = None
    started_at: float = field(default_factory=time.perf_counter)

    def record_command(self, name: str, latency_ms: float) -> None:
        self.total_commands += 1
        self.command_latencies_ms.append(max(0.0, float(latency_ms)))
        self._push_series("command", name, latency_ms)

    def record_heartbeat(self, board: str) -> dict[str, Any]:
        now = time.perf_counter()
        prev = self.heartbeats.get(board)
        self.heartbeats[board] = now
        self.total_sync_events += 1

        if prev is not None:
            self.sync_intervals_ms.append((now - prev) * 1000.0)

        # Latência lógica Arduino↔Raspberry: diferença entre últimos heartbeats
        ar = self.heartbeats.get("arduino")
        rp = self.heartbeats.get("raspberry")
        pair_ms = None
        synced = False
        if ar is not None and rp is not None:
            pair_ms = abs(ar - rp) * 1000.0
            self.last_sync_pair_ms = pair_ms
            synced = pair_ms < 2500.0  # janela de sincronia operacional
            if not synced:
                self.desync_events += 1

        sample = {
            "ts": _utc(),
            "board": board,
            "pair_skew_ms": round(pair_ms, 3) if pair_ms is not None else None,
            "synced": synced,
        }
        self.series.append({"kind": "heartbeat", **sample})
        return sample

    def _push_series(self, kind: str, name: str, latency_ms: float) -> None:
        self.series.append(
            {
                "kind": kind,
                "name": name,
                "latency_ms": round(float(latency_ms), 3),
                "ts": _utc(),
            }
        )

    def _stats(self, values: deque[float]) -> dict[str, float | None]:
        if not values:
            return {"n": 0, "mean": None, "p50": None, "p95": None, "p99": None, "stdev": None, "min": None, "max": None}
        data = list(values)
        data_sorted = sorted(data)

        def pct(p: float) -> float:
            if len(data_sorted) == 1:
                return data_sorted[0]
            k = (len(data_sorted) - 1) * (p / 100.0)
            f = math.floor(k)
            c = math.ceil(k)
            if f == c:
                return data_sorted[int(k)]
            return data_sorted[f] * (c - k) + data_sorted[c] * (k - f)

        return {
            "n": len(data),
            "mean": round(statistics.fmean(data), 3),
            "p50": round(pct(50), 3),
            "p95": round(pct(95), 3),
            "p99": round(pct(99), 3),
            "stdev": round(statistics.pstdev(data), 3) if len(data) > 1 else 0.0,
            "min": round(min(data), 3),
            "max": round(max(data), 3),
        }

    def sync_quality_index(self) -> float:
        """
        SQI ∈ [0, 100]: combina sincronia temporal, estabilidade de intervalo e taxa de desync.
        """
        if self.total_sync_events == 0:
            return 0.0

        skew = self.last_sync_pair_ms
        skew_score = 100.0 if skew is None else max(0.0, 100.0 - min(skew, 5000.0) / 50.0)

        interval_stats = self._stats(self.sync_intervals_ms)
        jitter = interval_stats["stdev"] or 0.0
        jitter_score = max(0.0, 100.0 - float(jitter) / 10.0)

        desync_rate = self.desync_events / max(1, self.total_sync_events)
        reliability_score = max(0.0, 100.0 * (1.0 - min(1.0, desync_rate * 4)))

        sqi = 0.45 * skew_score + 0.30 * jitter_score + 0.25 * reliability_score
        return round(sqi, 2)

    def summary(self) -> dict[str, Any]:
        uptime_s = time.perf_counter() - self.started_at
        return {
            "uptime_s": round(uptime_s, 1),
            "protocol_metrics": {
                "total_commands": self.total_commands,
                "total_sync_events": self.total_sync_events,
                "desync_events": self.desync_events,
                "last_pair_skew_ms": round(self.last_sync_pair_ms, 3) if self.last_sync_pair_ms is not None else None,
            },
            "command_latency_ms": self._stats(self.command_latencies_ms),
            "heartbeat_interval_ms": self._stats(self.sync_intervals_ms),
            "sync_quality_index": self.sync_quality_index(),
            "boards_last_seen_s": {
                board: round(time.perf_counter() - ts, 3) for board, ts in self.heartbeats.items()
            },
            "series_tail": list(self.series)[-40:],
            "generated_at": _utc(),
        }


telemetry = TelemetryEngine()
