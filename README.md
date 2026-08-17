# RAIL-TWIN

AI-powered predictive train traffic management prototype centered on Vasai Road Junction.

This is a decision-support system. It does not control signals, replace interlocking or Kavach, or autonomously execute safety-critical commands. The track-level graph is a provenance-labeled simulation representation based on the approved project layout, not an engineering signalling plan.

## Run

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Backend: http://localhost:8000/docs  
Frontend: http://localhost:5173  
Health: http://localhost:8000/health

Validate the deterministic seed locally:

```powershell
cd backend
python -m app.data.seed
```

The seed is synthetic/demo data and is never presented as live railway operational data. External RTIS, COA, ARS/TMS, signalling, NTES, and RailRadar integrations are adapter interfaces only.

## Simulation and prediction

Start the background digital twin through the API or dashboard. The default run is a two-hour simulated horizon; controls support `1x`, `5x`, `10x`, and `20x`.

```powershell
curl -X POST http://localhost:8000/api/v1/simulation/start
curl -X POST http://localhost:8000/api/v1/predictions/train -H 'Content-Type: application/json' -d '{"episodes":20,"seed":2026}'
curl -X POST http://localhost:8000/api/v1/predictions/run
curl -X POST http://localhost:8000/api/v1/conflicts/detect
curl -X POST http://localhost:8000/api/v1/optimization/run
```

For the full deterministic training command:

```powershell
python -m app.prediction.train --episodes 1667 --seed 2026
```

The scenario is `data/scenarios/scenario_vasai_freight_bottleneck.json`. Its +480-second freight event is synthetic; downstream delays are calculated by the simulation and propagation engine.

## Validation evidence

Switch the dashboard to Validation mode or start a background evidence run through the API:

```powershell
$run = Invoke-RestMethod -Method Post http://localhost:8000/api/v1/validation/runs -ContentType application/json -Body '{}'
Invoke-RestMethod "http://localhost:8000/api/v1/validation/runs/$($run.run_id)/summary"
Invoke-WebRequest "http://localhost:8000/api/v1/validation/runs/$($run.run_id)/export?format=markdown" -OutFile validation-report.md
```

The default suite runs seven controlled scenarios with seeds 2026–2035 against no intervention, a priority-aware minimum-safe-hold rule, and Rail-Twin. Results include failures and unsafe/no-solution outcomes. Evidence demonstrates controlled simulation behavior only and is not a claim of real railway deployment readiness.

## Structure

- `backend/app`: FastAPI API, schemas, persistence, adapters, graph, validation, simulation lifecycle
- `frontend/src`: React dashboard, SVG operational schematic, REST/WebSocket behavior
- `data/seed`: approved-prototype Vasai Road topology and deterministic train/timetable data
- `docker`: service images and initial PostGIS schema
