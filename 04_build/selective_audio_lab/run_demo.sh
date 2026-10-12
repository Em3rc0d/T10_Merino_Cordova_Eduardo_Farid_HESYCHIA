#!/usr/bin/env bash
set -euo pipefail
python -m unittest discover -p "test*.py"
python src/run_demo.py --out outputs/demo_run
python src/latency_benchmark.py --out outputs/latency --runs 40
python src/validate_artifacts.py --run-dir outputs/demo_run
