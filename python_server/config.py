"""Configurações do SmartHome IoT Platform."""

from pathlib import Path
from pydantic_settings import BaseSettings


BASE_DIR = Path(__file__).resolve().parent.parent
DB_DIR = BASE_DIR / "database"
DB_DIR.mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    app_name: str = "SmartHome IoT Platform"
    host: str = "127.0.0.1"
    port: int = 8000
    database_url: str = f"sqlite:///{DB_DIR / 'smarthome.db'}"

    mqtt_enabled: bool = False
    mqtt_host: str = "127.0.0.1"
    mqtt_port: int = 1883
    mqtt_username: str = ""
    mqtt_password: str = ""
    mqtt_client_id: str = "smarthome-server"

    jwt_secret: str = "smarthome-dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 12

    admin_user: str = "admin"
    admin_password: str = "admin123"

    simulation_mode: bool = True
    sensor_interval_seconds: float = 2.0


settings = Settings()
