"""Ponte MQTT opcional (ativa com MQTT_ENABLED=true)."""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, Optional

from config import settings

logger = logging.getLogger("mqtt_bridge")

try:
    import paho.mqtt.client as mqtt
except ImportError:  # pragma: no cover
    mqtt = None


class MQTTBridge:
    def __init__(self) -> None:
        self.client: Any = None
        self._on_message: Optional[Callable[[str, dict], Any]] = None
        self.connected = False

    def configure(self, on_message: Callable[[str, dict], Any]) -> None:
        self._on_message = on_message

    def start(self) -> None:
        if not settings.mqtt_enabled:
            logger.info("MQTT desabilitado — usando modo simulação/WebSocket.")
            return
        if mqtt is None:
            logger.warning("paho-mqtt não disponível.")
            return

        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=settings.mqtt_client_id,
        )
        if settings.mqtt_username:
            self.client.username_pw_set(settings.mqtt_username, settings.mqtt_password)

        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_mqtt_message
        try:
            self.client.connect(settings.mqtt_host, settings.mqtt_port, 60)
            self.client.loop_start()
            logger.info("MQTT conectando em %s:%s", settings.mqtt_host, settings.mqtt_port)
        except Exception as exc:  # pragma: no cover
            logger.error("Falha ao conectar MQTT: %s", exc)

    def stop(self) -> None:
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            self.connected = False

    def publish(self, topic: str, payload: dict | str) -> None:
        if not self.client or not self.connected:
            return
        data = payload if isinstance(payload, str) else json.dumps(payload)
        self.client.publish(topic, data)

    def _on_connect(self, client, userdata, flags, reason_code, properties=None) -> None:
        self.connected = reason_code == 0
        if not self.connected:
            logger.error("MQTT connect failed: %s", reason_code)
            return
        topics = [
            "house/temp",
            "house/humidity",
            "house/light",
            "house/motion",
            "house/sync",
            "house/status",
        ]
        for topic in topics:
            client.subscribe(topic)
        logger.info("MQTT inscrito nos tópicos house/*")

    def _on_mqtt_message(self, client, userdata, msg) -> None:
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except Exception:
            payload = {"raw": msg.payload.decode("utf-8", errors="ignore")}
        if self._on_message:
            self._on_message(msg.topic, payload)


mqtt_bridge = MQTTBridge()
