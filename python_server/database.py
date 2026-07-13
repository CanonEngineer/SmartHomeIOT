"""Camada de banco de dados."""

from datetime import datetime

import bcrypt
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from config import settings
from models import ActionLog, Base, Device, SensorReading, User

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


DEFAULT_DEVICES = [
    {"device_id": "arduino-sala", "name": "Arduino Sala", "kind": "arduino", "status": "online"},
    {"device_id": "raspberry-hub", "name": "Raspberry Pi Hub", "kind": "raspberry", "status": "online"},
    {"device_id": "servo-porta-1", "name": "Servo Porta Principal", "kind": "servo", "status": "online"},
    {"device_id": "servo-porta-2", "name": "Servo Porta Garagem", "kind": "servo", "status": "online"},
    {"device_id": "door-main", "name": "Porta Principal", "kind": "door", "status": "closed"},
    {"device_id": "door-garage", "name": "Porta Garagem", "kind": "door", "status": "closed"},
    {"device_id": "relay-1", "name": "Relé Luz Sala", "kind": "relay", "status": "off"},
    {"device_id": "relay-2", "name": "Relé Luz Cozinha", "kind": "relay", "status": "off"},
    {"device_id": "led-status", "name": "LED Status", "kind": "led", "status": "off"},
    {"device_id": "buzzer-alarm", "name": "Buzzer Alarme", "kind": "buzzer", "status": "off"},
]


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if not db.query(User).filter(User.username == settings.admin_user).first():
            db.add(
                User(
                    username=settings.admin_user,
                    password_hash=hash_password(settings.admin_password),
                    role="admin",
                )
            )

        for item in DEFAULT_DEVICES:
            existing = db.query(Device).filter(Device.device_id == item["device_id"]).first()
            if not existing:
                db.add(Device(**item, last_seen=datetime.utcnow()))

        if db.query(SensorReading).count() == 0:
            db.add(
                SensorReading(
                    temperature=24.5,
                    humidity=55.0,
                    light=62.0,
                    motion=False,
                )
            )

        db.commit()
    finally:
        db.close()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def log_action(db: Session, device: str, action: str, detail: str = "") -> ActionLog:
    entry = ActionLog(device=device, action=action, detail=detail, timestamp=datetime.utcnow())
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def touch_device(db: Session, device_id: str, status: str | None = None) -> Device | None:
    device = db.query(Device).filter(Device.device_id == device_id).first()
    if not device:
        return None
    device.last_seen = datetime.utcnow()
    if status is not None:
        device.status = status
    db.commit()
    db.refresh(device)
    return device
