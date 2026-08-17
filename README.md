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

## Structure

- `backend/app`: FastAPI API, schemas, persistence, adapters, graph, validation, simulation lifecycle
- `frontend/src`: React dashboard, SVG operational schematic, REST/WebSocket behavior
- `data/seed`: approved-prototype Vasai Road topology and deterministic train/timetable data
- `docker`: service images and initial PostGIS schema
