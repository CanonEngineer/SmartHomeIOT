"""Configuração do agente Raspberry Pi."""

import os

MQTT_HOST = os.getenv("MQTT_HOST", "127.0.0.1")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_CLIENT_ID = os.getenv("MQTT_CLIENT_ID", "raspberry-hub")
API_BASE = os.getenv("API_BASE", "http://127.0.0.1:8000")

# GPIO (BCM). Em PC sem GPIO, o agente usa modo simulado.
PIN_LED = int(os.getenv("PIN_LED", "17"))
PIN_BUZZER = int(os.getenv("PIN_BUZZER", "27"))
PIN_RELAY1 = int(os.getenv("PIN_RELAY1", "22"))
PIN_RELAY2 = int(os.getenv("PIN_RELAY2", "23"))
USE_GPIO = os.getenv("USE_GPIO", "auto")  # auto | true | false
