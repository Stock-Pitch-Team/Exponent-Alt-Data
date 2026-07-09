"""CLI entry point: python scripts/run_pipeline.py <p1..p6> [--step NAME] [--no-cache]"""
import argparse
import importlib
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(PROJECT_ROOT / "logs" / "pipelines.log", encoding="utf-8"),
    ],
)

PIPELINES = {
    "p1": "src.p1_headcount.build",
    "p2": "src.p2_litigation.build",
    "p3": "src.p3_reactive.build",
    "p4": "src.p4_moat.build",
    "p5": "src.p5_gov.build",
    "p6": "src.p6_clients.build",
    "p7": "src.p7_utilization.build",
    "p8": "src.p8_peers.build",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pipeline", choices=sorted(PIPELINES))
    ap.add_argument("--step", default=None, help="run a single named step")
    ap.add_argument("--no-cache", action="store_true", help="bypass HTTP cache")
    args = ap.parse_args()

    module = importlib.import_module(PIPELINES[args.pipeline])
    module.run(step=args.step, use_cache=not args.no_cache)


if __name__ == "__main__":
    main()
