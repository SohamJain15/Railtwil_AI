from dataclasses import dataclass
import random
import pandas as pd
from app.simulation.engine import RailwaySimulation

FEATURES = ["current_delay_seconds","distance_remaining_m","current_speed_kmph","scheduled_remaining_seconds","priority_class","current_block_occupancy","platform_occupancy","downstream_train_count","headway_seconds","junction_congestion","time_of_day"]

@dataclass
class TrainingDataset:
    frame: pd.DataFrame; episode_ids: list[int]

def generate_dataset(episodes: int = 20, seed: int = 2026) -> TrainingDataset:
    rng = random.Random(seed); rows = []
    for episode in range(episodes):
        sim = RailwaySimulation(seed + episode, horizon_seconds=900, snapshot_interval=900)
        for train in sim.state.trains.values():
            distance = float(sum((sim._edge(a,b) or {"length_m":0})["length_m"] for a,b in zip(train.route_nodes, train.route_nodes[1:])))
            delay = rng.randint(0, 480); congestion = rng.random(); occupancy = rng.random()
            rows.append({"episode_id":episode,"train_id":train.train_id,"current_delay_seconds":delay,"distance_remaining_m":distance,"current_speed_kmph":train.speed_kmph,"scheduled_remaining_seconds":max(0,train.predicted_time),"priority_class":train.priority,"current_block_occupancy":occupancy,"platform_occupancy":rng.random(),"downstream_train_count":rng.randint(0,8),"headway_seconds":rng.randint(60,300),"junction_congestion":congestion,"time_of_day":8.0,"eta_target":max(30,distance/max(train.speed_kmph,1)*3.6+delay),"delay_target":delay+int(congestion*180),"conflict_target":int(occupancy+congestion>1.15)})
    return TrainingDataset(pd.DataFrame(rows), list(range(episodes)))
