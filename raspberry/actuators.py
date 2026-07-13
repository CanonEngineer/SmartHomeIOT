"""Atuadores locais da Raspberry (GPIO real ou stub)."""

from __future__ import annotations

import logging
import platform

import config

logger = logging.getLogger("actuators")


class Actuators:
    def __init__(self) -> None:
        self.led = False
        self.buzzer = False
        self.relays = {"1": False, "2": False}
        self.servos = {"porta-1": 0, "porta-2": 0, "arm": 45}
        self.doors = {"main": False, "garage": False}
        self._gpio = None
        self._init_gpio()

    def _init_gpio(self) -> None:
        want = config.USE_GPIO
        machine = platform.machine().lower()
        is_pi = machine.startswith("arm") or machine.startswith("aarch64")
        enable = want == "true" or (want == "auto" and is_pi)
        if not enable:
            logger.info("GPIO desabilitado — modo simulação no agente.")
            return
        try:
            import RPi.GPIO as GPIO  # type: ignore

            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            for pin in (config.PIN_LED, config.PIN_BUZZER, config.PIN_RELAY1, config.PIN_RELAY2):
                GPIO.setup(pin, GPIO.OUT)
                GPIO.output(pin, GPIO.LOW)
            self._gpio = GPIO
            logger.info("GPIO inicializado na Raspberry.")
        except Exception as exc:  # pragma: no cover
            logger.warning("Falha GPIO (%s). Continuando em stub.", exc)
            self._gpio = None

    def set_led(self, on: bool) -> None:
        self.led = on
        if self._gpio:
            self._gpio.output(config.PIN_LED, self._gpio.HIGH if on else self._gpio.LOW)
        logger.info("LED=%s", on)

    def set_buzzer(self, on: bool) -> None:
        self.buzzer = on
        if self._gpio:
            self._gpio.output(config.PIN_BUZZER, self._gpio.HIGH if on else self._gpio.LOW)
        logger.info("BUZZER=%s", on)

    def set_relay(self, channel: str, on: bool) -> None:
        channel = str(channel)
        self.relays[channel] = on
        if self._gpio:
            pin = config.PIN_RELAY1 if channel == "1" else config.PIN_RELAY2
            self._gpio.output(pin, self._gpio.HIGH if on else self._gpio.LOW)
        logger.info("RELAY %s=%s", channel, on)

    def set_servo(self, servo_id: str, angle: int) -> None:
        angle = max(0, min(180, int(angle)))
        self.servos[servo_id] = angle
        if servo_id == "porta-1":
            self.doors["main"] = angle >= 70
        elif servo_id == "porta-2":
            self.doors["garage"] = angle >= 70
        logger.info("SERVO %s=%s", servo_id, angle)

    def set_door(self, door_id: str, open_: bool) -> None:
        self.doors[door_id] = open_
        angle = 90 if open_ else 0
        if door_id == "main":
            self.servos["porta-1"] = angle
        elif door_id == "garage":
            self.servos["porta-2"] = angle
        logger.info("DOOR %s=%s", door_id, open_)

    def cleanup(self) -> None:
        if self._gpio:
            self._gpio.cleanup()
