"""Testes de engenharia / reprodutibilidade."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "python_server"
sys.path.insert(0, str(ROOT))

from protocol import PROTOCOL_VERSION, TOPIC_SCHEMA, wrap  # noqa: E402
from telemetry import TelemetryEngine  # noqa: E402


def test_protocol_version():
    assert PROTOCOL_VERSION.count(".") == 2
    assert "house/sync" in TOPIC_SCHEMA


def test_envelope_wrap():
    msg = wrap("server", {"on": True})
    assert msg["protocol"] == PROTOCOL_VERSION
    assert msg["source"] == "server"
    assert msg["payload"]["on"] is True


def test_sqi_bounds():
    eng = TelemetryEngine()
    assert eng.sync_quality_index() == 0.0
    eng.record_heartbeat("arduino")
    eng.record_heartbeat("raspberry")
    sqi = eng.sync_quality_index()
    assert 0.0 <= sqi <= 100.0


def test_latency_stats():
    eng = TelemetryEngine()
    for v in (10, 20, 30, 40, 50):
        eng.record_command("led", v)
    stats = eng.summary()["command_latency_ms"]
    assert stats["n"] == 5
    assert stats["mean"] == 30.0
    assert stats["p50"] == 30.0


async def _state_roundtrip():
    from state import HouseState

    st = HouseState()
    await st.set_led(True)
    await st.set_door("main", True)
    snap = st.snapshot()
    assert snap["actuators"]["led"] is True
    assert snap["actuators"]["door"]["main"] is True
    assert snap["actuators"]["servo"]["porta-1"] == 90
    assert "sync_quality_index" in snap


def test_state_machine():
    asyncio.run(_state_roundtrip())


if __name__ == "__main__":
    test_protocol_version()
    test_envelope_wrap()
    test_sqi_bounds()
    test_latency_stats()
    test_state_machine()
    print("OK — todos os testes de engenharia passaram")
