from app.conflicts import ConflictDetector
from app.safety import SafetyValidator
from app.simulation.engine import RailwaySimulation

def test_simulation_moves_trains_and_records_occupancy():
    state = RailwaySimulation(horizon_seconds=7200, snapshot_interval=300).run()
    assert state.simulation_time == 7200
    assert state.occupancies
    assert any(t.status.value == "COMPLETED" for t in state.trains.values())

def test_freight_event_propagates_causal_delay():
    state = RailwaySimulation(horizon_seconds=7200, snapshot_interval=300).run()
    assert any(c.cause_type == "EVENT" and c.affected_train == "T012" for c in state.delay_causes)
    assert any(c.cause_type == "RESOURCE_OVERLAP" for c in state.delay_causes)

def test_conflict_detection_and_safety_contract():
    state = RailwaySimulation(horizon_seconds=1800, snapshot_interval=300).run()
    conflicts = ConflictDetector().detect(state)
    assert all(c.type in {"BLOCK_CONFLICT","PLATFORM_CONFLICT","HEADWAY_CONFLICT"} for c in conflicts)
    assert SafetyValidator().validate(state).status in {"SAFE","UNSAFE"}
