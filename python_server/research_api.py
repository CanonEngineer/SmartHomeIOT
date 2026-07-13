"""API de pesquisa / doutorado: telemetria, protocolo e experimentos."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from experiments import experiment_runner
from protocol import ARCHITECTURE_LAYERS, PROTOCOL_VERSION, TOPIC_SCHEMA
from telemetry import telemetry

router = APIRouter(prefix="/api/research", tags=["research"])


class ExperimentBody(BaseModel):
    name: str
    params: dict[str, Any] = Field(default_factory=dict)


@router.get("/overview")
def overview():
    return {
        "title": "SmartHome IoT — Research Lab",
        "protocol_version": PROTOCOL_VERSION,
        "architecture_layers": ARCHITECTURE_LAYERS,
        "topics": TOPIC_SCHEMA,
        "experiments": experiment_runner.CATALOG,
        "telemetry": telemetry.summary(),
    }


@router.get("/telemetry")
def get_telemetry():
    return telemetry.summary()


@router.get("/protocol")
def get_protocol():
    return {
        "version": PROTOCOL_VERSION,
        "layers": ARCHITECTURE_LAYERS,
        "topics": TOPIC_SCHEMA,
    }


@router.get("/experiments")
def list_experiments():
    return {
        "catalog": experiment_runner.CATALOG,
        "history": [
            {
                "experiment_id": e.experiment_id,
                "name": e.name,
                "started_at": e.started_at,
                "finished_at": e.finished_at,
                "sqi": e.metrics.get("sync_quality_index"),
                "sample_count": e.metrics.get("sample_count"),
            }
            for e in experiment_runner.history[-30:]
        ],
    }


@router.post("/experiments/run")
async def run_experiment(body: ExperimentBody, db: Session = Depends(get_db)):
    try:
        result = await experiment_runner.run(body.name, db, body.params)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "result": result.to_dict()}


@router.get("/experiments/{experiment_id}")
def get_experiment(experiment_id: str):
    try:
        return experiment_runner.export_bundle(experiment_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/experiments/{experiment_id}/export.csv")
def export_csv(experiment_id: str):
    try:
        bundle = experiment_runner.export_bundle(experiment_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    path = bundle["csv_path"]
    return FileResponse(path, media_type="text/csv", filename=f"{experiment_id}.csv")


@router.get("/experiments/{experiment_id}/export.json")
def export_json(experiment_id: str):
    try:
        bundle = experiment_runner.export_bundle(experiment_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    path = bundle["json_path"]
    return FileResponse(path, media_type="application/json", filename=f"{experiment_id}.json")


@router.get("/thesis-brief.md", response_class=PlainTextResponse)
def thesis_brief():
    """Resumo técnico pronto para colar em slides/relatório."""
    t = telemetry.summary()
    return (
        "# SmartHome IoT — Brief Técnico\n\n"
        f"- Protocolo: {PROTOCOL_VERSION}\n"
        f"- Sync Quality Index (SQI): {t['sync_quality_index']}\n"
        f"- Latência média de comando (ms): {t['command_latency_ms']['mean']}\n"
        f"- P95 latência (ms): {t['command_latency_ms']['p95']}\n"
        f"- Eventos de sync: {t['protocol_metrics']['total_sync_events']}\n"
        f"- Desyncs: {t['protocol_metrics']['desync_events']}\n"
        f"- Skew Arduino↔Raspberry (ms): {t['protocol_metrics']['last_pair_skew_ms']}\n\n"
        "Camadas: L1 Percepção/Atuação → L2 Comunicação → L3 Edge → L4 Serviço → L5 Experimentação.\n"
    )
