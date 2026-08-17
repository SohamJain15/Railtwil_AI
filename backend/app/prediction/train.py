import argparse
from app.prediction.service import PredictionService

if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--episodes", type=int, default=1667); parser.add_argument("--seed", type=int, default=2026); args = parser.parse_args(); print(PredictionService().train(args.episodes, args.seed))
