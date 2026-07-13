"""
Framework experimental reproduzível para coleta de resultados de tese.

Cada experimento gera:
- metadados (id, hipótese, parâmetros)
- amostras temporais
- métricas agregadas
- export CSV / JSON
"""

from __future__ import annotations

import asyncio
import csv
import io
import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from database import log_action
from state import house_state
from telemetry import telemetry

EXPORT_DIR = Path(__file__).resolve().parent.parent / "experiments" / "exports"
EXPORT_DIR.mkdir(parents=True, exist_ok=True)


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ExperimentResult:
    experiment_id: str
    name: str
    hypothesis: str
    started_at: str
    finished_at: str
    parameters: dict[str, Any]
    samples: list[dict[str, Any]] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ExperimentRunner:
    """Bancada de experimentos controlados Arduino↔Raspberry."""

    CATALOG = {
        "sync_latency": {
            "title": "Latência de sincronização Arduino↔Raspberry",
            "hypothesis": "O desvio temporal entre heartbeats permanece < 100 ms em modo simulado estável.",
            "default_params": {"cycles": 20, "delay_ms": 200},
        },
        "actuator_response": {
            "title": "Tempo de resposta de atuação (porta/servo/LED)",
            "hypothesis": "A mediana de latência de comando fica abaixo de 50 ms no caminho API→estado.",
            "default_params": {"cycles": 15, "delay_ms": 120},
        },
        "fault_injection": {
            "title": "Injeção de falha de sincronia",
            "hypothesis": "O Sync Quality Index cai sob atraso artificial e se recupera após restabelecimento.",
            "default_params": {"delay_ms": 800, "recovery_cycles": 10},
        },
        "end_to_end_scenario": {
            "title": "Cenário ponta a ponta (welcome→garage→night)",
            "hypothesis": "A máquina de estados dos atuadores permanece consistente após sequência composta.",
            "default_params": {},
        },
    }

    def __init__(self) -> None:
        self.history: list[ExperimentResult] = []

    async def run(self, name: str, db: Session, params: dict[str, Any] | None = None) -> ExperimentResult:
        if name not in self.CATALOG:
            raise ValueError(f"Experimento inválido. Opções: {', '.join(self.CATALOG)}")

        meta = self.CATALOG[name]
        parameters = {**meta["default_params"], **(params or {})}
        exp_id = str(uuid.uuid4())[:8]
        started = _utc()
        t0 = time.perf_counter()
        samples: list[dict[str, Any]] = []

        if name == "sync_latency":
            samples = await self._sync_latency(parameters)
        elif name == "actuator_response":
            samples = await self._actuator_response(parameters)
        elif name == "fault_injection":
            samples = await self._fault_injection(parameters)
        elif name == "end_to_end_scenario":
            samples = await self._end_to_end()

        finished = _utc()
        result = ExperimentResult(
            experiment_id=exp_id,
            name=name,
            hypothesis=meta["hypothesis"],
            started_at=started,
            finished_at=finished,
            parameters=parameters,
            samples=samples,
            metrics={
                **telemetry.summary(),
                "wall_time_s": round(time.perf_counter() - t0, 3),
                "sample_count": len(samples),
            },
            notes=meta["title"],
        )
        self.history.append(result)
        self._persist_files(result)
        log_action(db, "research-lab", "experiment", f"{name}:{exp_id}")
        return result

    async def _sync_latency(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        cycles = int(params.get("cycles", 20))
        delay_ms = int(params.get("delay_ms", 200))
        samples: list[dict[str, Any]] = []
        for i in range(cycles):
            t0 = time.perf_counter()
            await house_state.heartbeat("arduino")
            await asyncio.sleep(delay_ms / 1000.0)
            await house_state.heartbeat("raspberry")
            dt = (time.perf_counter() - t0) * 1000.0
            telemetry.record_command("sync_cycle", dt)
            samples.append(
                {
                    "cycle": i + 1,
                    "cycle_ms": round(dt, 3),
                    "pair_skew_ms": telemetry.last_sync_pair_ms,
                    "sqi": telemetry.sync_quality_index(),
                }
            )
        return samples

    async def _actuator_response(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        cycles = int(params.get("cycles", 15))
        delay_ms = int(params.get("delay_ms", 120))
        samples: list[dict[str, Any]] = []
        for i in range(cycles):
            for action_name, coro in (
                ("led", house_state.set_led(i % 2 == 0)),
                ("door", house_state.set_door("main", i % 2 == 0)),
                ("servo", house_state.set_servo("arm", 30 + (i * 10) % 120)),
            ):
                t0 = time.perf_counter()
                await coro
                dt = (time.perf_counter() - t0) * 1000.0
                telemetry.record_command(action_name, dt)
                samples.append({"cycle": i + 1, "action": action_name, "latency_ms": round(dt, 3)})
            await asyncio.sleep(delay_ms / 1000.0)
        return samples

    async def _fault_injection(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        delay_ms = int(params.get("delay_ms", 800))
        recovery = int(params.get("recovery_cycles", 10))
        samples: list[dict[str, Any]] = []

        await house_state.heartbeat("arduino")
        samples.append({"phase": "pre_fault", "sqi": telemetry.sync_quality_index(), "skew": telemetry.last_sync_pair_ms})

        # Atraso artificial entre placas (simula jitter/rede)
        await asyncio.sleep(delay_ms / 1000.0)
        await house_state.heartbeat("raspberry")
        samples.append({"phase": "fault", "sqi": telemetry.sync_quality_index(), "skew": telemetry.last_sync_pair_ms})

        for i in range(recovery):
            await house_state.heartbeat("arduino")
            await asyncio.sleep(0.05)
            await house_state.heartbeat("raspberry")
            samples.append(
                {
                    "phase": "recovery",
                    "cycle": i + 1,
                    "sqi": telemetry.sync_quality_index(),
                    "skew": telemetry.last_sync_pair_ms,
                }
            )
        return samples

    async def _end_to_end(self) -> list[dict[str, Any]]:
        from simulator import simulator
        from database import SessionLocal

        samples: list[dict[str, Any]] = []
        db = SessionLocal()
        try:
            for scenario in ("welcome", "garage", "night"):
                t0 = time.perf_counter()
                await simulator.run_scenario(scenario, db)
                dt = (time.perf_counter() - t0) * 1000.0
                telemetry.record_command(f"scenario:{scenario}", dt)
                snap = house_state.snapshot()
                samples.append(
                    {
                        "scenario": scenario,
                        "latency_ms": round(dt, 3),
                        "doors": snap["actuators"]["door"],
                        "relays": snap["actuators"]["relay"],
                        "led": snap["actuators"]["led"],
                    }
                )
        finally:
            db.close()
        return samples

    def _persist_files(self, result: ExperimentResult) -> None:
        base = EXPORT_DIR / f"{result.name}_{result.experiment_id}"
        json_path = base.with_suffix(".json")
        csv_path = base.with_suffix(".csv")
        json_path.write_text(json.dumps(result.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

        if result.samples:
            # união de chaves para CSV tabular
            keys: list[str] = []
            for row in result.samples:
                for k in row.keys():
                    if k not in keys:
                        keys.append(k)
            buf = io.StringIO()
            writer = csv.DictWriter(buf, fieldnames=keys)
            writer.writeheader()
            writer.writerows(result.samples)
            csv_path.write_text(buf.getvalue(), encoding="utf-8")

    def export_bundle(self, experiment_id: str) -> dict[str, Any]:
        for item in reversed(self.history):
            if item.experiment_id == experiment_id:
                base = EXPORT_DIR / f"{item.name}_{item.experiment_id}"
                return {
                    "experiment": item.to_dict(),
                    "json_path": str(base.with_suffix(".json")),
                    "csv_path": str(base.with_suffix(".csv")),
                }
        raise ValueError("Experimento não encontrado")


experiment_runner = ExperimentRunner()
