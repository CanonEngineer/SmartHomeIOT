"""
SmartHome IoT Platform — servidor principal.

Inicie com:
    python app.py
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api import router as api_router
from config import settings
from database import SessionLocal, init_db
from mqtt_bridge import mqtt_bridge
from research_api import router as research_router
from simulator import simulator
from state import house_state
from protocol import PROTOCOL_VERSION

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("smarthome")

WEB_DIR = Path(__file__).resolve().parent.parent / "web"


def handle_mqtt_message(topic: str, payload: dict) -> None:
    """Atualiza estado a partir de mensagens MQTT reais (quando broker ativo)."""

    async def _apply() -> None:
        if topic == "house/temp" and "value" in payload:
            await house_state.update_sensors(temperature=float(payload["value"]))
        elif topic == "house/humidity" and "value" in payload:
            await house_state.update_sensors(humidity=float(payload["value"]))
        elif topic == "house/light" and "value" in payload:
            await house_state.update_sensors(light=float(payload["value"]))
        elif topic == "house/motion" and "value" in payload:
            await house_state.update_sensors(motion=bool(payload["value"]))
        elif topic == "house/sync":
            board = payload.get("board")
            if board in ("arduino", "raspberry"):
                await house_state.heartbeat(board)

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(_apply())
    except RuntimeError:
        pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    mqtt_bridge.configure(handle_mqtt_message)
    mqtt_bridge.start()
    await simulator.start(SessionLocal)
    logger.info("SmartHome online em http://%s:%s", settings.host, settings.port)
    yield
    await simulator.stop()
    mqtt_bridge.stop()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router)
app.include_router(research_router)

if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")


@app.get("/")
def index():
    index_path = WEB_DIR / "index.html"
    if not index_path.exists():
        return {"message": "Interface web não encontrada. Crie web/index.html"}
    return FileResponse(index_path)


@app.get("/health")
def health():
    return {"status": "ok", "app": settings.app_name, "protocol": PROTOCOL_VERSION}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host=settings.host, port=settings.port, reload=False)
