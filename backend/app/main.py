from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.data.seed import load_and_validate
from app.data.store import read_seed, network_payload
from app.db import database_health
from app.schemas import StatusResponse, SimulationCommand, EventCommand, RecommendationDecision
from app.services.simulation import SimulationService
from app.data.seed import seed_database

settings = get_settings(); simulation = SimulationService(); seed = load_and_validate()

@asynccontextmanager
async def lifespan(app):
    await seed_database()
    yield

app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.get("/health")
async def health(): return {"status":"ok", "service":"backend", "database": await database_health()}

@app.get("/api/v1/system/status", response_model=StatusResponse)
async def status(): return StatusResponse(status=simulation.state, environment=settings.environment, scenario_id=settings.demo_scenario_id, persistence="postgresql", event_transport="redis")
@app.get("/api/v1/network")
async def network(): return network_payload()
@app.get("/api/v1/trains")
async def trains(): return {"items": read_seed("trains.csv"), "source": "simulation-data", "is_synthetic": True}
@app.get("/api/v1/platforms")
async def platforms(): return {"items": read_seed("platforms.csv"), "source": "simulation-data", "is_synthetic": True}
@app.get("/api/v1/predictions")
async def predictions(): return {"items": [], "status":"empty", "message":"No prediction run has been executed."}
@app.get("/api/v1/conflicts")
async def conflicts(): return {"items": [], "status":"empty", "message":"No conflicts have been detected."}
@app.get("/api/v1/recommendations")
async def recommendations(): return {"items": [], "status":"empty", "message":"No recommendations have been generated."}
@app.get("/api/v1/metrics")
async def metrics(): return {"items": [], "status":"empty", "message":"Metrics will appear after a simulation run."}

@app.post("/api/v1/simulation/{action}")
async def simulation_command(action: str, command: SimulationCommand | None = None):
    if action not in {"start", "pause", "reset"}: raise HTTPException(404, "Unknown simulation action")
    event = simulation.command(action, command.simulation_id if command else None)
    return {"state": simulation.state, "event": event.model_dump(mode="json")}

@app.post("/api/v1/simulation/event")
async def simulation_event(command: EventCommand):
    return {"accepted": True, "event_type": command.event_type, "payload": command.payload, "timestamp": datetime.now(timezone.utc)}
@app.post("/api/v1/what-if/run")
async def what_if(payload: dict): return {"status":"accepted", "result": None, "message":"What-if execution interface is ready; simulation engine is not enabled in Phase 2."}
@app.post("/api/v1/recommendations/{recommendation_id}/{decision}")
async def recommendation_decision(recommendation_id: str, decision: str, body: RecommendationDecision):
    if decision not in {"accept", "modify", "reject"}: raise HTTPException(404, "Unknown decision")
    return {"recommendation_id": recommendation_id, "decision": decision, "reason": body.reason, "status":"recorded"}

@app.websocket("/ws/simulation")
async def simulation_socket(websocket: WebSocket):
    await websocket.accept()
    try:
        await websocket.send_json({"type":"connection.ready", "state":simulation.state})
        while True:
            message = await websocket.receive_json()
            if message.get("action") in {"start", "pause", "reset"}:
                event = simulation.command(message["action"]); await websocket.send_json(event.model_dump(mode="json"))
    except WebSocketDisconnect: pass
