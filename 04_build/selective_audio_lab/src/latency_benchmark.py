import argparse, json, time
from pathlib import Path
import numpy as np
import pandas as pd
from run_demo import synthesize, process

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='outputs/latency')
    ap.add_argument('--runs', type=int, default=40)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    latencies = []
    for i in range(args.runs):
        p, t, b = synthesize(seed=42 + i)
        t0 = time.perf_counter()
        process(p, t, b)
        latencies.append((time.perf_counter() - t0) * 1000)
    arr = np.array(latencies)
    summary = {
        'runs': args.runs,
        'environment': 'local_python_runtime_container_reference',
        'audio_duration_s': 4.0,
        'processing_p50_ms': float(np.percentile(arr, 50)),
        'processing_p95_ms': float(np.percentile(arr, 95)),
        'processing_mean_ms': float(np.mean(arr)),
        'realtime_factor_mean': float(np.mean(arr) / (4.0 * 1000)),
        'note': 'Esta medición es del entorno local de desarrollo; el perfil Android debe ejecutarse en el Honor X8c.'
    }
    pd.DataFrame({'run': list(range(args.runs)), 'elapsed_ms': latencies}).to_csv(out / 'latency_samples.csv', index=False)
    with open(out / 'latency_summary.json', 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(json.dumps(summary, indent=2, ensure_ascii=False))

if __name__ == '__main__':
    main()
