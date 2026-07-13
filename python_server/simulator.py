"""Simulador de sensores e cenários de teste."""

from __future__ import annotations

import asyncio
import math
import random
from datetime import datetime

from sqlalchemy.orm import Session

from config import settings
from database import log_action
from models import SensorReading
from state import house_state


class SensorSimulator:
    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._running = False
        self._t0 = datetime.utcnow().timestamp()

    async def start(self, db_factory) -> None:
        if not settings.simulation_mode:
            return
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop(db_factory))

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _loop(self, db_factory) -> None:
        while self._running:
            elapsed = datetime.utcnow().timestamp() - self._t0
            temp = 23.5 + 2.5 * math.sin(elapsed / 18) + random.uniform(-0.2, 0.2)
            humidity = 50 + 8 * math.sin(elapsed / 25 + 1) + random.uniform(-1, 1)
            light = max(5, min(100, 55 + 30 * math.sin(elapsed / 30) + random.uniform(-3, 3)))
            motion = house_state.actuators["door"]["main"] or random.random() < 0.08

            await house_state.update_sensors(
                temperature=round(temp, 1),
                humidity=round(humidity, 1),
                light=round(light, 1),
                motion=bool(motion),
            )

            db: Session = db_factory()
            try:
                db.add(
                    SensorReading(
                        temperature=round(temp, 1),
                        humidity=round(humidity, 1),
                        light=round(light, 1),
                        motion=bool(motion),
                    )
                )
                db.commit()
            finally:
                db.close()

            await house_state.heartbeat("arduino")
            await asyncio.sleep(0.4)
            await house_state.heartbeat("raspberry")
            await asyncio.sleep(settings.sensor_interval_seconds)

    async def run_scenario(self, name: str, db: Session) -> dict:
        """Cenários prontos para validar sincronia e mecanismos."""
        name = name.lower().strip()

        if name == "welcome":
            await house_state.set_led(True)
            await house_state.set_relay("1", True)
            await house_state.set_door("main", True)
            await house_state.set_servo("arm", 120)
            log_action(db, "system", "scenario", "welcome")
            return {"ok": True, "scenario": name, "state": house_state.snapshot()}

        if name == "alarm":
            await house_state.set_buzzer(True)
            await house_state.set_led(True)
            await house_state.set_relay("1", True)
            await house_state.set_relay("2", True)
            await house_state.update_sensors(motion=True)
            log_action(db, "system", "scenario", "alarm")
            return {"ok": True, "scenario": name, "state": house_state.snapshot()}

        if name == "night":
            await house_state.set_door("main", False)
            await house_state.set_door("garage", False)
            await house_state.set_relay("1", False)
            await house_state.set_relay("2", False)
            await house_state.set_led(False)
            await house_state.set_buzzer(False)
            await house_state.set_servo("arm", 0)
            log_action(db, "system", "scenario", "night")
            return {"ok": True, "scenario": name, "state": house_state.snapshot()}

        if name == "garage":
            await house_state.set_door("garage", True)
            await house_state.set_relay("2", True)
            await house_state.set_servo("arm", 90)
            log_action(db, "system", "scenario", "garage")
            return {"ok": True, "scenario": name, "state": house_state.snapshot()}

        if name == "sync_test":
            # Alterna ações para visualizar Arduino ↔ Raspberry em sincronia
            for angle in (0, 45, 90, 135, 90, 0):
                await house_state.set_servo("porta-1", angle)
                await house_state.set_led(angle >= 90)
                await house_state.heartbeat("arduino")
                await asyncio.sleep(0.35)
                await house_state.heartbeat("raspberry")
                await asyncio.sleep(0.35)
            log_action(db, "system", "scenario", "sync_test")
            return {"ok": True, "scenario": name, "state": house_state.snapshot()}

        raise ValueError(
            "Cenário inválido. Use: welcome, alarm, night, garage, sync_test"
        )


simulator = SensorSimulator()
