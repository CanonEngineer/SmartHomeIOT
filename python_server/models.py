"""Modelos SQLAlchemy."""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(32), default="admin")
    created_at = Column(DateTime, default=datetime.utcnow)


class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(128), nullable=False)
    kind = Column(String(32), nullable=False)  # arduino | raspberry | relay | servo | door
    status = Column(String(32), default="offline")
    last_seen = Column(DateTime, default=datetime.utcnow)
    meta = Column(Text, default="{}")


class SensorReading(Base):
    __tablename__ = "sensors"

    id = Column(Integer, primary_key=True, index=True)
    temperature = Column(Float, default=0.0)
    humidity = Column(Float, default=0.0)
    light = Column(Float, default=0.0)
    motion = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class ActionLog(Base):
    __tablename__ = "logs"

    id = Column(Integer, primary_key=True, index=True)
    device = Column(String(64), nullable=False)
    action = Column(String(128), nullable=False)
    detail = Column(Text, default="")
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
