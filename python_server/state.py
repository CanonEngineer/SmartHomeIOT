"""Estado em memória do sistema (sincronizado com UI e MQTT)."""

from __future__ import annotations

import asyncio
import time
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine

from protocol import PROTOCOL_VERSION
from telemetry import telemetry


BroadcastFn = Callable[[dict[str, Any]], Coroutine[Any, Any, None]]


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


class HouseState:
    """Estado vivo da casa inteligente + placas (fonte de verdade em runtime)."""

    def __init__(self) -> None:
        self.sensors = {
            "temperature": 24.5,
            "humidity": 55.0,
            "light": 62.0,
            "motion": False,
        }
        self.actuators = {
            "led": False,
            "buzzer": False,
            "relay": {"1": False, "2": False, "3": False, "4": False},
            "servo": {"porta-1": 0, "porta-2": 0, "arm": 45},
            "door": {"main": False, "garage": False},
        }
        self.boards = {
            "arduino": {
                "id": "arduino-sala",
                "name": "Arduino Sala",
                "online": True,
                "sync": True,
                "last_heartbeat": _utc(),
                "role": "perception + local actuation",
                "layer": "L1",
            },
            "raspberry": {
                "id": "raspberry-hub",
                "name": "Raspberry Pi Hub",
                "online": True,
                "sync": True,
                "last_heartbeat": _utc(),
                "role": "edge coordination + state mirroring",
                "layer": "L3",
            },
        }
        self.sync_pulse = 0
        self.last_event = "Sistema iniciado"
        self.state_version = 0
        self._listeners: list[BroadcastFn] = []
        self._lock = asyncio.Lock()

    def snapshot(self) -> dict[str, Any]:
        return {
            "protocol_version": PROTOCOL_VERSION,
            "state_version": self.state_version,
            "sensors": deepcopy(self.sensors),
            "actuators": deepcopy(self.actuators),
            "boards": deepcopy(self.boards),
            "sync_pulse": self.sync_pulse,
            "last_event": self.last_event,
            "sync_quality_index": telemetry.sync_quality_index(),
            "pair_skew_ms": telemetry.last_sync_pair_ms,
            "timestamp": _utc(),
        }

    def add_listener(self, fn: BroadcastFn) -> None:
        self._listeners.append(fn)

    def remove_listener(self, fn: BroadcastFn) -> None:
        if fn in self._listeners:
            self._listeners.remove(fn)

    async def broadcast(self, event: str | None = None, extra: dict[str, Any] | None = None) -> None:
        if event:
            self.last_event = event
        payload = {"type": "state", "data": self.snapshot()}
        if extra:
            payload["extra"] = extra
        dead: list[BroadcastFn] = []
        for listener in list(self._listeners):
            try:
                await listener(payload)
            except Exception:
                dead.append(listener)
        for listener in dead:
            self.remove_listener(listener)

    async def set_led(self, on: bool) -> dict[str, Any]:
        t0 = time.perf_counter()
        async with self._lock:
            self.actuators["led"] = on
            self._mark_sync("LED ON" if on else "LED OFF")
            telemetry.record_command("led", (time.perf_counter() - t0) * 1000.0)
            await self.broadcast(f"LED {'ligado' if on else 'desligado'}")
            return self.snapshot()

    async def set_buzzer(self, on: bool) -> dict[str, Any]:
        t0 = time.perf_counter()
        async with self._lock:
            self.actuators["buzzer"] = on
            self._mark_sync("BUZZER ON" if on else "BUZZER OFF")
            telemetry.record_command("buzzer", (time.perf_counter() - t0) * 1000.0)
            await self.broadcast(f"Buzzer {'ativo' if on else 'silenciado'}")
            return self.snapshot()

    async def set_relay(self, channel: str, on: bool) -> dict[str, Any]:
        t0 = time.perf_counter()
        async with self._lock:
            channel = str(channel)
            if channel not in self.actuators["relay"]:
                raise ValueError(f"Canal de relé inválido: {channel}")
            self.actuators["relay"][channel] = on
            self._mark_sync(f"RELAY {channel}={'ON' if on else 'OFF'}")
            telemetry.record_command("relay", (time.perf_counter() - t0) * 1000.0)
            await self.broadcast(f"Relé {channel} {'ligado' if on else 'desligado'}")
            return self.snapshot()

    async def set_servo(self, servo_id: str, angle: int) -> dict[str, Any]:
        t0 = time.perf_counter()
        async with self._lock:
            if servo_id not in self.actuators["servo"]:
                raise ValueError(f"Servo inválido: {servo_id}")
            angle = max(0, min(180, int(angle)))
            self.actuators["servo"][servo_id] = angle
            if servo_id == "porta-1":
                self.actuators["door"]["main"] = angle >= 70
            elif servo_id == "porta-2":
                self.actuators["door"]["garage"] = angle >= 70
            self._mark_sync(f"SERVO {servo_id}={angle}°")
            telemetry.record_command("servo", (time.perf_counter() - t0) * 1000.0)
            await self.broadcast(f"Servo {servo_id} → {angle}°")
            return self.snapshot()

    async def set_door(self, door_id: str, open_: bool) -> dict[str, Any]:
        t0 = time.perf_counter()
        async with self._lock:
            if door_id not in self.actuators["door"]:
                raise ValueError(f"Porta inválida: {door_id}")
            self.actuators["door"][door_id] = open_
            angle = 90 if open_ else 0
            if door_id == "main":
                self.actuators["servo"]["porta-1"] = angle
            elif door_id == "garage":
                self.actuators["servo"]["porta-2"] = angle
            self._mark_sync(f"DOOR {door_id}={'OPEN' if open_ else 'CLOSE'}")
            telemetry.record_command("door", (time.perf_counter() - t0) * 1000.0)
            await self.broadcast(f"Porta {door_id} {'aberta' if open_ else 'fechada'}")
            return self.snapshot()

    async def update_sensors(self, **kwargs: Any) -> dict[str, Any]:
        async with self._lock:
            for key, value in kwargs.items():
                if key in self.sensors:
                    self.sensors[key] = value
            self._mark_sync("SENSORS")
            await self.broadcast("Sensores atualizados")
            return self.snapshot()

    async def heartbeat(self, board: str) -> dict[str, Any]:
        async with self._lock:
            if board not in self.boards:
                raise ValueError(f"Placa inválida: {board}")
            self.boards[board]["online"] = True
            self.boards[board]["last_heartbeat"] = _utc()
            sample = telemetry.record_heartbeat(board)
            synced = bool(sample.get("synced"))
            self.boards["arduino"]["sync"] = synced
            self.boards["raspberry"]["sync"] = synced
            self.sync_pulse = (self.sync_pulse + 1) % 1000
            self.state_version += 1
            await self.broadcast(f"Heartbeat {board}", extra={"board": board, "telemetry": sample})
            return self.snapshot()

    def _mark_sync(self, action: str) -> None:
        now = _utc()
        self.boards["arduino"]["last_heartbeat"] = now
        self.boards["raspberry"]["last_heartbeat"] = now
        self.boards["arduino"]["sync"] = True
        self.boards["raspberry"]["sync"] = True
        self.sync_pulse = (self.sync_pulse + 1) % 1000
        self.state_version += 1
        self.last_event = action


house_state = HouseState()
