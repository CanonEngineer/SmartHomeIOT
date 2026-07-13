"""Rotas da API REST."""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth import authenticate_user, create_access_token, get_current_user
from database import SessionLocal, get_db, log_action, touch_device
from models import ActionLog, Device, SensorReading, User
from mqtt_bridge import mqtt_bridge
from simulator import simulator
from state import house_state
from telemetry import telemetry
from protocol import PROTOCOL_VERSION

router = APIRouter(prefix="/api")


class LedBody(BaseModel):
    on: bool


class BuzzerBody(BaseModel):
    on: bool


class RelayBody(BaseModel):
    channel: str = Field(..., pattern=r"^[1-4]$")
    on: bool


class ServoBody(BaseModel):
    servo_id: str
    angle: int = Field(..., ge=0, le=180)


class DoorBody(BaseModel):
    door_id: str
    open: bool


class SimulateBody(BaseModel):
    scenario: str = "welcome"


class HeartbeatBody(BaseModel):
    board: str


@router.post("/auth/login")
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = authenticate_user(db, form.username, form.password)
    if not user:
        raise HTTPException(status_code=401, detail="Credenciais inválidas")
    return {"access_token": create_access_token(user.username), "token_type": "bearer"}


@router.get("/me")
def me(user: User | None = Depends(get_current_user)):
    if not user:
        return {"authenticated": False}
    return {"authenticated": True, "username": user.username, "role": user.role}


@router.get("/status")
async def status():
    return {
        "ok": True,
        "protocol_version": PROTOCOL_VERSION,
        "mqtt_connected": mqtt_bridge.connected,
        "simulation_mode": True,
        "state": house_state.snapshot(),
        "telemetry": telemetry.summary(),
    }


@router.get("/sensors")
def sensors(db: Session = Depends(get_db), limit: int = 50):
    rows = (
        db.query(SensorReading)
        .order_by(SensorReading.created_at.desc())
        .limit(min(limit, 500))
        .all()
    )
    return [
        {
            "id": r.id,
            "temperature": r.temperature,
            "humidity": r.humidity,
            "light": r.light,
            "motion": r.motion,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@router.get("/devices")
def devices(db: Session = Depends(get_db)):
    rows = db.query(Device).order_by(Device.id.asc()).all()
    return [
        {
            "id": d.id,
            "device_id": d.device_id,
            "name": d.name,
            "kind": d.kind,
            "status": d.status,
            "last_seen": d.last_seen.isoformat() if d.last_seen else None,
        }
        for d in rows
    ]


@router.get("/logs")
def logs(db: Session = Depends(get_db), limit: int = 100):
    rows = db.query(ActionLog).order_by(ActionLog.timestamp.desc()).limit(min(limit, 500)).all()
    return [
        {
            "id": r.id,
            "device": r.device,
            "action": r.action,
            "detail": r.detail,
            "timestamp": r.timestamp.isoformat() if r.timestamp else None,
        }
        for r in rows
    ]


@router.post("/led")
async def led(body: LedBody, db: Session = Depends(get_db)):
    state = await house_state.set_led(body.on)
    touch_device(db, "led-status", "on" if body.on else "off")
    log_action(db, "led-status", "led", "on" if body.on else "off")
    mqtt_bridge.publish("house/led", {"on": body.on})
    return {"ok": True, "state": state}


@router.post("/buzzer")
async def buzzer(body: BuzzerBody, db: Session = Depends(get_db)):
    state = await house_state.set_buzzer(body.on)
    touch_device(db, "buzzer-alarm", "on" if body.on else "off")
    log_action(db, "buzzer-alarm", "buzzer", "on" if body.on else "off")
    mqtt_bridge.publish("house/buzzer", {"on": body.on})
    return {"ok": True, "state": state}


@router.post("/relay")
async def relay(body: RelayBody, db: Session = Depends(get_db)):
    try:
        state = await house_state.set_relay(body.channel, body.on)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    device_id = f"relay-{body.channel}"
    touch_device(db, device_id, "on" if body.on else "off")
    log_action(db, device_id, "relay", f"channel={body.channel} on={body.on}")
    mqtt_bridge.publish("house/relay", {"channel": body.channel, "on": body.on})
    return {"ok": True, "state": state}


@router.post("/servo")
async def servo(body: ServoBody, db: Session = Depends(get_db)):
    try:
        state = await house_state.set_servo(body.servo_id, body.angle)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    log_action(db, f"servo-{body.servo_id}", "servo", f"angle={body.angle}")
    mqtt_bridge.publish("house/servo", {"servo_id": body.servo_id, "angle": body.angle})
    return {"ok": True, "state": state}


@router.post("/door")
async def door(body: DoorBody, db: Session = Depends(get_db)):
    try:
        state = await house_state.set_door(body.door_id, body.open)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    mapped = {"main": "door-main", "garage": "door-garage"}.get(body.door_id, f"door-{body.door_id}")
    touch_device(db, mapped, "open" if body.open else "closed")
    log_action(db, mapped, "door", "open" if body.open else "close")
    mqtt_bridge.publish("house/door", {"door_id": body.door_id, "open": body.open})
    return {"ok": True, "state": state}


@router.post("/simulate")
async def simulate(body: SimulateBody, db: Session = Depends(get_db)):
    try:
        result = await simulator.run_scenario(body.scenario, db)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result


@router.post("/heartbeat")
async def heartbeat(body: HeartbeatBody, db: Session = Depends(get_db)):
    try:
        state = await house_state.heartbeat(body.board)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    board_map = {"arduino": "arduino-sala", "raspberry": "raspberry-hub"}
    touch_device(db, board_map.get(body.board, body.board), "online")
    return {"ok": True, "state": state}


class ConnectionManager:
    def __init__(self) -> None:
        self.active: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active:
            self.active.remove(websocket)

    async def broadcast_json(self, message: dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        for ws in self.active:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


ws_manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    await websocket.send_json({"type": "state", "data": house_state.snapshot()})

    async def forward(payload: dict[str, Any]) -> None:
        await websocket.send_json(payload)

    house_state.add_listener(forward)
    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action")
            if action == "ping":
                await websocket.send_json({"type": "pong", "ts": datetime.utcnow().isoformat()})
            elif action == "led":
                await house_state.set_led(bool(data.get("on")))
            elif action == "buzzer":
                await house_state.set_buzzer(bool(data.get("on")))
            elif action == "relay":
                await house_state.set_relay(str(data.get("channel", "1")), bool(data.get("on")))
            elif action == "servo":
                await house_state.set_servo(str(data.get("servo_id", "porta-1")), int(data.get("angle", 0)))
            elif action == "door":
                await house_state.set_door(str(data.get("door_id", "main")), bool(data.get("open")))
            elif action == "simulate":
                db = SessionLocal()
                try:
                    await simulator.run_scenario(str(data.get("scenario", "welcome")), db)
                finally:
                    db.close()
    except WebSocketDisconnect:
        pass
    finally:
        house_state.remove_listener(forward)
        ws_manager.disconnect(websocket)
