import argparse, json, time, hashlib
from pathlib import Path
import numpy as np
import pandas as pd
import soundfile as sf
from scipy.signal import stft, istft, chirp

SR = 16000
DURATION = 4.0
N_FFT = 512
HOP = 160
EPS = 1e-9

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()

def normalize(x, peak=0.9):
    m = np.max(np.abs(x)) + EPS
    return (x / m) * peak

def synthesize(seed=42):
    rng = np.random.default_rng(seed)
    t = np.arange(int(SR * DURATION)) / SR
    envelope = 0.45 + 0.35 * np.sin(2 * np.pi * 2.2 * t) ** 2
    protected = envelope * (
        0.30 * np.sin(2 * np.pi * 180 * t)
        + 0.15 * np.sin(2 * np.pi * 360 * t)
        + 0.07 * np.sin(2 * np.pi * 720 * t)
    )
    target = 0.35 * chirp(t, f0=650, f1=1450, t1=0.8, method='linear') * (0.5 + 0.5 * np.sin(2 * np.pi * 1.25 * t))
    noise = rng.normal(0, 0.04, len(t))
    background = np.convolve(noise, np.ones(9) / 9, mode='same')
    return protected.astype(np.float32), target.astype(np.float32), background.astype(np.float32)

def stft_complex(x):
    _, _, Z = stft(x, fs=SR, window='hann', nperseg=N_FFT, noverlap=N_FFT - HOP, nfft=N_FFT, boundary='zeros')
    return Z

def istft_complex(Z, length):
    _, y = istft(Z, fs=SR, window='hann', nperseg=N_FFT, noverlap=N_FFT - HOP, nfft=N_FFT, input_onesided=True, boundary=True)
    if len(y) < length:
        y = np.pad(y, (0, length - len(y)))
    return y[:length].astype(np.float32)

def si_sdr(est, ref):
    est = est - np.mean(est)
    ref = ref - np.mean(ref)
    scale = np.dot(est, ref) / (np.dot(ref, ref) + EPS)
    s_target = scale * ref
    e_noise = est - s_target
    return 10 * np.log10((np.sum(s_target ** 2) + EPS) / (np.sum(e_noise ** 2) + EPS))

def process(protected, target, background, cap_db=12, alpha=1.0):
    raw_mix = protected + target + background
    scale = (np.max(np.abs(raw_mix)) + EPS) / 0.95
    p = protected / scale
    tg = target / scale
    bg = background / scale
    mixture = p + tg + bg
    X = stft_complex(mixture)
    S_t = stft_complex(tg)
    S_rest = stft_complex(p + bg)
    irm = np.abs(S_t) / (np.abs(S_t) + np.abs(S_rest) + EPS)
    g_min = 10 ** (-cap_db / 20)
    gain = np.maximum(1.0 - alpha * irm, g_min)
    Y = gain * X
    output = istft_complex(Y, len(mixture))
    p_out = istft_complex(gain * stft_complex(p), len(p))
    tg_out = istft_complex(gain * stft_complex(tg), len(tg))
    metrics = {
        'A_target_db': float(10 * np.log10((np.sum(tg ** 2) + EPS) / (np.sum(tg_out ** 2) + EPS))),
        'A_protected_db': float(10 * np.log10((np.sum(p ** 2) + EPS) / (np.sum(p_out ** 2) + EPS))),
        'SI_SDRi_protected_db': float(si_sdr(output, p) - si_sdr(mixture, p)),
        'mask_mean': float(np.mean(irm)),
        'mask_max': float(np.max(irm)),
        'duration_s': float(len(mixture) / SR),
        'sr': SR,
        'n_fft': N_FFT,
        'hop': HOP,
        'target_label': 'siren_synthetic',
        'protected_label': 'speech_like_synthetic',
        'baseline_type': 'oracle_IRM_stem_demo'
    }
    return mixture.astype(np.float32), output.astype(np.float32), p.astype(np.float32), tg.astype(np.float32), bg.astype(np.float32), irm.astype(np.float32), metrics

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='outputs/demo_run')
    ap.add_argument('--seed', type=int, default=42)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()
    protected, target, background = synthesize(args.seed)
    mixture, output, p, tg, bg, mask, metrics = process(protected, target, background)
    metrics['wall_time_ms'] = float((time.perf_counter() - start) * 1000)
    audio_paths = {
        'protected.wav': p,
        'target.wav': tg,
        'background.wav': bg,
        'mixture.wav': mixture,
        'output_selective.wav': output,
    }
    artifact_rows = []
    for name, data in audio_paths.items():
        path = out / name
        sf.write(path, data, SR)
        artifact_rows.append({'artifact': name, 'path': str(path.name), 'sha256': sha256(path)})
    np.save(out / 'mask_irm.npy', mask)
    artifact_rows.append({'artifact': 'mask_irm.npy', 'path': 'mask_irm.npy', 'sha256': sha256(out / 'mask_irm.npy')})
    pd.DataFrame([metrics]).to_csv(out / 'demo_metrics.csv', index=False)
    pd.DataFrame(artifact_rows).to_csv(out / 'artifacts_manifest.csv', index=False)
    summary = {
        'run_id': 'PI8-DEMO-RUN-001',
        'scope': 'incremento_funcional_local_reproducible',
        'warning': 'No clinical claim. Synthetic/stem-controlled demo only.',
        'metrics': metrics,
        'artifacts': artifact_rows,
    }
    with open(out / 'demo_summary.json', 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(json.dumps(summary, indent=2, ensure_ascii=False))

if __name__ == '__main__':
    main()
