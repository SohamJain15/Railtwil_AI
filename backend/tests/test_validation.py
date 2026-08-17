from app.simulation.engine import RailwaySimulation
from app.simulation.metrics import calculate_metrics
from app.validation.models import ValidationStrategy
from app.validation.runner import ValidationRunner

def test_metrics_are_derived_from_occupancy_history():
    state=RailwaySimulation(seed=2026,horizon_seconds=1800,snapshot_interval=300,scenario_events=[]).run()
    metrics=calculate_metrics(state,1800)
    assert metrics["track_utilization"] > 0
    assert metrics["track_utilization"] <= 1
    assert metrics["platform_utilization"] <= 1
    assert metrics["junction_utilization"] <= 1
    assert metrics["throughput_trains_per_hour"] >= 0
    assert metrics["headway_violations"] >= 0

def test_validation_episode_is_reproducible_and_exportable():
    runner=ValidationRunner(); scenario=runner.suite["scenarios"][0]
    first=runner._episode(scenario,2026,ValidationStrategy.NO_INTERVENTION)
    second=runner._episode(scenario,2026,ValidationStrategy.NO_INTERVENTION)
    assert first.metrics == second.metrics
    run=runner.start(seeds=[2026],scenario_ids=[scenario["scenario_id"]])
    import time
    deadline=time.time()+20
    while runner.get(run.run_id).status.value not in {"COMPLETED","FAILED"} and time.time()<deadline: time.sleep(.05)
    assert len(runner.get(run.run_id).results)==3
    content,_=runner.export(run.run_id,"json")
    assert scenario["scenario_id"] in content

def test_rule_baseline_is_distinct_from_no_intervention():
    runner=ValidationRunner(); scenario=runner.suite["scenarios"][1]
    base=runner._episode(scenario,2026,ValidationStrategy.NO_INTERVENTION)
    rule=runner._episode(scenario,2026,ValidationStrategy.RULE_BASED)
    assert base.metrics["total_delay_minutes"] != rule.metrics["total_delay_minutes"]
