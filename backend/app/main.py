from contextlib import asynccontextmanager
import asyncio
from datetime import datetime, timezone
from dataclasses import asdict
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.data.seed import load_and_validate
from app.data.store import read_seed, network_payload, active_scenario
from app.db import database_health
from app.schemas import StatusResponse, SimulationCommand, EventCommand, RecommendationDecision
from app.services.simulation import SimulationService
from app.data.seed import seed_database
from app.simulation.state import DelayEvent
from app.conflicts import ConflictDetector
from app.optimization import Action, WhatIfEngine, OptimizationEngine
from app.prediction.service import PredictionService
from app.simulation.engine import RailwaySimulation
from app.services.orchestrator import SimulationOrchestrator

settings = get_settings(); simulation = SimulationService(); seed = load_and_validate(); conflict_detector = ConflictDetector(); prediction_service = PredictionService(); optimization = OptimizationEngine(WhatIfEngine(lambda: RailwaySimulation())); orchestrator = SimulationOrchestrator(simulation, prediction_service, optimization)

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
@app.get("/api/v1/simulation/state")
async def simulation_state():
    twin = simulation.twin
    return {"status": simulation.state, "speed": simulation.speed_multiplier, "state": asdict(twin) if twin else None}
@app.get("/api/v1/simulation/snapshots")
async def simulation_snapshots(): return {"items":[asdict(s) for s in simulation.snapshots]}
@app.get("/api/v1/network")
async def network(): return network_payload()
@app.get("/api/v1/scenarios/active")
async def scenario(): return active_scenario()
@app.get("/api/v1/trains")
async def trains(): return {"items": read_seed("trains.csv"), "source": "simulation-data", "is_synthetic": True}
@app.get("/api/v1/trains/{train_id}/history")
async def train_history(train_id: str):
    if not any(row["train_id"] == train_id for row in seed["trains"]) and (simulation.twin is None or train_id not in simulation.twin.trains): raise HTTPException(404, "Train not found")
    return {"train_id":train_id,"items":[asdict(snapshot.trains[train_id]) for snapshot in simulation.snapshots if train_id in snapshot.trains]}
@app.get("/api/v1/platforms")
async def platforms(): return {"items": read_seed("platforms.csv"), "source": "simulation-data", "is_synthetic": True}
@app.get("/api/v1/junctions")
async def junctions(): return {"items": read_seed("junctions.csv"), "source":"simulation-data", "is_synthetic":True}
@app.get("/api/v1/predictions")
async def predictions(): return {"items": simulation.twin.predictions if simulation.twin else [], "status":"ok" if simulation.twin and simulation.twin.predictions else "empty"}
@app.get("/api/v1/predictions/models")
async def prediction_models(): return {"items": prediction_service.registry.list()}
@app.get("/api/v1/conflicts")
async def conflicts(): return {"items":[asdict(c) for c in (simulation.twin.active_conflicts if simulation.twin else [])], "status":"ok" if simulation.twin and simulation.twin.active_conflicts else "empty"}
@app.get("/api/v1/conflicts/{conflict_id}")
async def conflict(conflict_id: str):
    found = next((c for c in (simulation.twin.active_conflicts if simulation.twin else []) if c.conflict_id == conflict_id), None)
    if not found: raise HTTPException(404, "Conflict not found")
    return asdict(found)
@app.post("/api/v1/conflicts/detect")
async def detect_conflicts():
    if not simulation.twin: return {"items":[],"status":"empty"}
    return {"items":[asdict(c) for c in orchestrator.detect_conflicts()]}
@app.get("/api/v1/recommendations")
async def recommendations(): return {"items": simulation.twin.recommendations if simulation.twin else [], "status":"ok" if simulation.twin and simulation.twin.recommendations else "empty"}
@app.get("/api/v1/metrics")
async def metrics():
    items = [asdict(s.metrics) for s in simulation.snapshots]
    return {"items": items, "status":"ok" if items else "empty"}

@app.post("/api/v1/simulation/start")
async def simulation_start(command: SimulationCommand | None = None):
    simulation_id = orchestrator.start_simulation(command.simulation_id if command else None); return {"state":simulation.state,"simulation_id":simulation_id}
@app.post("/api/v1/simulation/pause")
async def simulation_pause(): orchestrator.pause_simulation(); return {"state":simulation.state}
@app.post("/api/v1/simulation/resume")
async def simulation_resume(): orchestrator.resume_simulation(); return {"state":simulation.state}
@app.post("/api/v1/simulation/reset")
async def simulation_reset(): orchestrator.reset_simulation(); return {"state":simulation.state}
@app.post("/api/v1/simulation/speed")
async def simulation_speed(payload: dict):
    try: simulation.set_speed(int(payload.get("speed",1)))
    except ValueError as exc: raise HTTPException(422, str(exc))
    return {"speed":simulation.speed_multiplier}

@app.post("/api/v1/simulation/event")
async def simulation_event(command: EventCommand):
    payload = command.payload; event = DelayEvent(timestamp=float(payload.get("timestamp", simulation.twin.simulation_time if simulation.twin else 0)), target_type=str(payload.get("target_type","train")), target_id=str(payload.get("target_id","")), delay_seconds=float(payload.get("delay_seconds",0)), reason=str(payload.get("reason",command.event_type)), severity=str(payload.get("severity","MEDIUM")), scenario_id=str(payload.get("scenario_id",settings.demo_scenario_id)))
    orchestrator.inject_event(event); return {"accepted":True,"event":asdict(event)}
@app.post("/api/v1/what-if/run")
async def what_if(payload: dict):
    if not simulation.twin: raise HTTPException(409, "Start a simulation first")
    action = Action(str(payload.get("action_type","HOLD_TRAIN")), str(payload.get("train_id")), int(payload.get("duration_seconds",60)), payload.get("target"), str(payload.get("reason","controller what-if")))
    result = optimization.what_if.run(simulation.twin, action, int(payload.get("horizon_seconds",1200)))
    return {"status":"ok","result":asdict(result)}
@app.post("/api/v1/optimization/run")
async def optimize(payload: dict | None = None):
    if not simulation.twin: raise HTTPException(409, "Start a simulation first")
    return orchestrator.generate_recommendations(int((payload or {}).get("horizon_seconds",1200))) or {"status":"empty","message":"No safe recommendation found"}
@app.get("/api/v1/optimization/results")
async def optimization_results(): return {"items":[asdict(r) for r in optimization.last_results]}
@app.post("/api/v1/predictions/train")
async def train_models(payload: dict | None = None):
    data = payload or {}; return prediction_service.train(int(data.get("episodes",20)), int(data.get("seed",settings.random_seed)))
@app.post("/api/v1/predictions/run")
async def run_predictions():
    if not simulation.twin: raise HTTPException(409,"Start a simulation first")
    return {"items":orchestrator.process_predictions()}
@app.post("/api/v1/recommendations/{recommendation_id}/{decision}")
async def recommendation_decision(recommendation_id: str, decision: str, body: RecommendationDecision):
    if decision not in {"accept", "modify", "reject"}: raise HTTPException(404, "Unknown decision")
    recommendation = next((r for r in (simulation.twin.recommendations if simulation.twin else []) if r.get("recommendation_id") == recommendation_id), None)
    if not recommendation: raise HTTPException(404,"Recommendation not found")
    try: orchestrator.apply_controller_action(recommendation_id, decision, body.modified_action)
    except ValueError as exc: raise HTTPException(409, str(exc))
    return {"recommendation_id": recommendation_id, "decision": decision, "reason": body.reason, "status":"recorded"}

@app.websocket("/ws/simulation")
async def simulation_socket(websocket: WebSocket):
    await websocket.accept()
    try:
        await websocket.send_json({"type":"connection.ready", "state":simulation.state})
        while True:
            try: message = await asyncio.wait_for(websocket.receive_json(), timeout=.5)
            except asyncio.TimeoutError: message = {}
            action = message.get("action")
            if action == "start": orchestrator.start_simulation()
            elif action == "pause": orchestrator.pause_simulation()
            elif action == "resume": orchestrator.resume_simulation()
            elif action == "reset": orchestrator.reset_simulation()
            await websocket.send_json({"type":"simulation.tick","simulation_id":str(simulation.simulation_id) if simulation.simulation_id else None,"simulation_time":simulation.twin.simulation_time if simulation.twin else 0,"state":simulation.state,"trains":{k:{"status":v.status,"node":v.current_node,"delay_seconds":v.delay_seconds} for k,v in (simulation.twin.trains.items() if simulation.twin else [])}})
    except WebSocketDisconnect: pass
