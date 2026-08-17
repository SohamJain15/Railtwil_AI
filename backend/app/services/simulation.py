import threading
import time
from uuid import UUID, uuid4
from app.simulation.engine import RailwaySimulation
from app.simulation.state import DigitalTwinState, SimulationSnapshot

class SimulationService:
    def __init__(self):
        self.state = "idle"; self.simulation_id: UUID | None = None; self.engine: RailwaySimulation | None = None
        self.speed_multiplier = 1; self._paused = threading.Event(); self._stop = threading.Event(); self._thread: threading.Thread | None = None
        self.snapshots: list[SimulationSnapshot] = []; self.lock = threading.RLock()
    @property
    def twin(self) -> DigitalTwinState | None: return self.engine.state if self.engine else None
    def start(self, simulation_id: UUID | None = None, speed: int = 1):
        with self.lock:
            if self.state == "running": return self.simulation_id
            self.simulation_id = simulation_id or self.simulation_id or uuid4(); self.engine = RailwaySimulation(); self.engine.state.simulation_id = self.simulation_id; self.set_speed(speed); self.state = "running"; self._paused.clear(); self._stop.clear()
            self._thread = threading.Thread(target=self._run, daemon=True); self._thread.start(); return self.simulation_id
    def _run(self):
        while self.engine and not self._stop.is_set() and self.engine.env.now < self.engine.horizon_seconds:
            if self._paused.is_set(): time.sleep(.05); continue
            target = min(self.engine.env.now + 60, self.engine.horizon_seconds); self.engine.run(target); self.snapshots = self.engine.state.snapshots[-100:]; time.sleep(max(.001, .25/self.speed_multiplier))
        if not self._stop.is_set(): self.state = "completed"
    def pause(self): self._paused.set(); self.state = "paused"
    def resume(self): self._paused.clear(); self.state = "running"
    def reset(self): self._stop.set(); self._paused.clear(); self.state = "idle"; self.simulation_id = None; self.engine = None; self.snapshots = []
    def set_speed(self, speed: int):
        if speed not in {1,5,10,20}: raise ValueError("speed must be 1, 5, 10, or 20")
        self.speed_multiplier = speed
    def add_event(self, event):
        if self.engine: self.engine.apply_delay_event(event)
