#!/usr/bin/env bash
set -euo pipefail
python src/run_demo.py --out outputs/demo_run
python src/latency_benchmark.py --out outputs/latency
