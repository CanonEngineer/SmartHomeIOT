"""
Contratos de mensagem do SmartHome IoT Platform (versão de protocolo).

Usado para validação, documentação e reprodutibilidade experimental.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


PROTOCOL_VERSION = "1.0.0"
NAMESPACE = "house"


class QoSLevel(int, Enum):
    AT_MOST_ONCE = 0
    AT_LEAST_ONCE = 1
    EXACTLY_ONCE = 2


class BoardId(str, Enum):
    ARDUINO = "arduino"
    RASPBERRY = "raspberry"


class Envelope(BaseModel):
    """Envelope comum a todas as mensagens do barramento lógico."""

    protocol: str = PROTOCOL_VERSION
    message_id: str = Field(default_factory=lambda: str(uuid4()))
    correlation_id: str | None = None
    source: str
    timestamp_utc: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    qos: QoSLevel = QoSLevel.AT_LEAST_ONCE
    payload: dict[str, Any]


class SensorPayload(BaseModel):
    value: float | bool
    unit: str | None = None
    quality: Literal["good", "uncertain", "bad"] = "good"


class ActuatorCommand(BaseModel):
    target: str
    value: Any
    idempotent: bool = True


class SyncHeartbeat(BaseModel):
    board: BoardId
    ok: bool = True
    sequence: int = 0
    clock_ms: int | None = None


TOPIC_SCHEMA: dict[str, dict[str, str]] = {
    f"{NAMESPACE}/temp": {"direction": "device→edge", "payload": "SensorPayload"},
    f"{NAMESPACE}/humidity": {"direction": "device→edge", "payload": "SensorPayload"},
    f"{NAMESPACE}/light": {"direction": "device→edge", "payload": "SensorPayload"},
    f"{NAMESPACE}/motion": {"direction": "device→edge", "payload": "SensorPayload"},
    f"{NAMESPACE}/led": {"direction": "edge→device", "payload": "ActuatorCommand"},
    f"{NAMESPACE}/relay": {"direction": "edge→device", "payload": "ActuatorCommand"},
    f"{NAMESPACE}/buzzer": {"direction": "edge→device", "payload": "ActuatorCommand"},
    f"{NAMESPACE}/servo": {"direction": "edge→device", "payload": "ActuatorCommand"},
    f"{NAMESPACE}/door": {"direction": "edge→device", "payload": "ActuatorCommand"},
    f"{NAMESPACE}/sync": {"direction": "bidirectional", "payload": "SyncHeartbeat"},
}


ARCHITECTURE_LAYERS = [
    {
        "id": "L1",
        "name": "Percepção / Atuação",
        "components": ["Arduino/ESP32", "DHT22", "LDR", "PIR", "Relés", "Servos", "Portas"],
    },
    {
        "id": "L2",
        "name": "Comunicação",
        "components": ["Wi-Fi", "MQTT (QoS 0/1)", "WebSocket", "REST"],
    },
    {
        "id": "L3",
        "name": "Edge Coordination",
        "components": ["Raspberry Pi Agent", "Espelhamento de estado", "Heartbeat sync"],
    },
    {
        "id": "L4",
        "name": "Serviço / Persistência",
        "components": ["FastAPI", "SQLite", "Telemetria", "Auditoria"],
    },
    {
        "id": "L5",
        "name": "Apresentação / Experimentação",
        "components": ["Simulador visual", "Research Lab", "Java Dashboard", "Export CSV/JSON"],
    },
]


def wrap(source: str, payload: dict[str, Any], qos: QoSLevel = QoSLevel.AT_LEAST_ONCE) -> dict[str, Any]:
    return Envelope(source=source, payload=payload, qos=qos).model_dump(mode="json")
