# Protocolo de Mensagens v1.0.0

Namespace: `house/*`

## Envelope

```json
{
  "protocol": "1.0.0",
  "message_id": "uuid",
  "correlation_id": null,
  "source": "arduino|raspberry|server|ui",
  "timestamp_utc": "ISO-8601",
  "qos": 1,
  "payload": {}
}
```

## Tópicos

| Tópico | Direção | Payload |
|--------|---------|---------|
| `house/temp` | device→edge | `{ "value": number }` |
| `house/humidity` | device→edge | `{ "value": number }` |
| `house/light` | device→edge | `{ "value": number }` |
| `house/motion` | device→edge | `{ "value": boolean }` |
| `house/led` | edge→device | `{ "on": boolean }` |
| `house/relay` | edge→device | `{ "channel": "1..4", "on": boolean }` |
| `house/buzzer` | edge→device | `{ "on": boolean }` |
| `house/servo` | edge→device | `{ "servo_id": "porta-1|porta-2|arm", "angle": 0..180 }` |
| `house/door` | edge→device | `{ "door_id": "main|garage", "open": boolean }` |
| `house/sync` | bidirecional | `{ "board": "arduino|raspberry", "ok": true }` |

## Semântica de sincronia

- Cada placa publica heartbeat em `house/sync`
- O edge calcula **pair skew** = |t_arduino − t_raspberry|
- Janela operacional de sync: skew < 2500 ms (configurável na telemetria)

## Versionamento

Breaking changes incrementam MAJOR em `PROTOCOL_VERSION` (`python_server/protocol.py`).
