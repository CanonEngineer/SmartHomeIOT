"""
Agente Raspberry Pi — espelha comandos MQTT e envia heartbeat de sincronia.

Uso (sem broker, só API):
    set USE_MQTT=0
    python agent.py

Uso com Mosquitto:
    set MQTT_HOST=127.0.0.1
    python agent.py
"""

from __future__ import annotations

import json
import logging
import os
import signal
import sys
import threading
import time

import requests

import config
from actuators import Actuators

logging.basicConfig(level=logging.INFO, format="%(asctime)s [raspberry] %(message)s")
logger = logging.getLogger("agent")

USE_MQTT = os.getenv("USE_MQTT", "1") == "1"
actuators = Actuators()
_stop = threading.Event()


def handle_command(topic: str, payload: dict) -> None:
    if topic.endswith("/led"):
        actuators.set_led(bool(payload.get("on")))
    elif topic.endswith("/buzzer"):
        actuators.set_buzzer(bool(payload.get("on")))
    elif topic.endswith("/relay"):
        actuators.set_relay(str(payload.get("channel", "1")), bool(payload.get("on")))
    elif topic.endswith("/servo"):
        actuators.set_servo(str(payload.get("servo_id", "arm")), int(payload.get("angle", 0)))
    elif topic.endswith("/door"):
        actuators.set_door(str(payload.get("door_id", "main")), bool(payload.get("open")))


def heartbeat_loop() -> None:
    while not _stop.is_set():
        try:
            requests.post(
                f"{config.API_BASE}/api/heartbeat",
                json={"board": "raspberry"},
                timeout=2,
            )
        except Exception as exc:
            logger.debug("heartbeat falhou: %s", exc)
        _stop.wait(2.0)


def poll_api_loop() -> None:
    """Sem MQTT: consulta status e aplica atuadores (espelhamento via API)."""
    last = None
    while not _stop.is_set():
        try:
            resp = requests.get(f"{config.API_BASE}/api/status", timeout=2)
            data = resp.json().get("state", {})
            act = data.get("actuators", {})
            blob = json.dumps(act, sort_keys=True)
            if blob != last:
                last = blob
                actuators.set_led(bool(act.get("led")))
                actuators.set_buzzer(bool(act.get("buzzer")))
                for ch, on in (act.get("relay") or {}).items():
                    actuators.set_relay(str(ch), bool(on))
                for sid, angle in (act.get("servo") or {}).items():
                    actuators.set_servo(str(sid), int(angle))
                for did, open_ in (act.get("door") or {}).items():
                    actuators.set_door(str(did), bool(open_))
                logger.info("Estado espelhado da API.")
        except Exception as exc:
            logger.debug("poll API: %s", exc)
        _stop.wait(1.0)


def run_mqtt() -> None:
    import paho.mqtt.client as mqtt

    def on_connect(client, userdata, flags, reason_code, properties=None):
        logger.info("MQTT conectado (%s)", reason_code)
        for t in ("house/led", "house/buzzer", "house/relay", "house/servo", "house/door"):
            client.subscribe(t)

    def on_message(client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except Exception:
            payload = {}
        handle_command(msg.topic, payload)
        client.publish("house/sync", json.dumps({"board": "raspberry", "ok": True}))

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=config.MQTT_CLIENT_ID)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(config.MQTT_HOST, config.MQTT_PORT, 60)
    client.loop_start()
    try:
        while not _stop.is_set():
            client.publish("house/sync", json.dumps({"board": "raspberry", "ok": True}))
            _stop.wait(1.5)
    finally:
        client.loop_stop()
        client.disconnect()


def main() -> None:
    def _sig(*_a):
        _stop.set()

    signal.signal(signal.SIGINT, _sig)
    signal.signal(signal.SIGTERM, _sig)

    threading.Thread(target=heartbeat_loop, daemon=True).start()

    if USE_MQTT:
        try:
            run_mqtt()
            return
        except Exception as exc:
            logger.warning("MQTT indisponível (%s). Caindo para espelhamento via API.", exc)

    poll_api_loop()
    actuators.cleanup()


if __name__ == "__main__":
    main()
    sys.exit(0)
