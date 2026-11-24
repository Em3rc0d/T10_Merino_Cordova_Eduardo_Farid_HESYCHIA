"""Bounded web adapter for the existing offline scientific candidate.

This is inference on a user clip, never a confirmatory test or an acoustic score.
"""
from __future__ import annotations
import base64
import hashlib
import importlib.util
import io
import json
import math
import subprocess
from pathlib import Path
from datetime import datetime, timezone

LAB = Path(__file__).resolve().parents[1]
SELECTED = LAB / 'models/m4_sci_real_candidate_v1/selected'
EXPECTED_SHA = 'c0b34027fe1d4165b062f4145ca7173b3d547cedc39846e17298295e99fb1966'
TARGETS = ('vacuum_cleaner', 'chainsaw')
MAX_BYTES = 4 * 1024 * 1024


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def candidate_status():
    checkpoint = SELECTED / 'candidate.pt'
    summary = SELECTED / 'summary.json'
    manifest = SELECTED / 'training_manifest.json'
    result = {'release': 'Sustentación · noviembre 2026', 'targets': list(TARGETS),
              'ready': False, 'scientific_go': False, 'mode': 'offline_assisted_target',
              'limits': ['Auditoría humana y test confirmatorio pendientes.',
                         'La inferencia de un clip no mide A_target ni A_protected sin stems.',
                         'No acredita streaming ni protección automática de alertas.']}
    try:
        result['commit'] = subprocess.check_output(
            ['git', 'rev-parse', '--short=12', 'HEAD'], cwd=LAB,
            text=True, stderr=subprocess.DEVNULL, timeout=3).strip()
        dirty = subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=no'], cwd=LAB, text=True, stderr=subprocess.DEVNULL, timeout=3).strip()
        result['working_tree_modified'] = bool(dirty)
    except (OSError, subprocess.SubprocessError):
        result['commit'] = 'No disponible (copia sin Git)'
    try:
        s = json.loads(summary.read_text(encoding='utf-8'))
        m = json.loads(manifest.read_text(encoding='utf-8'))
        actual = digest(checkpoint)
        result.update(checkpoint_sha256=actual, checkpoint_verified=actual == EXPECTED_SHA,
                      parameters=s['parameter_count'], best_epoch=s['best_epoch'],
                      corpus_review=s['corpus_review'], frontend=m['frontend'],
                      manifest_sha256=digest(manifest), torch_installed=importlib.util.find_spec('torch') is not None)
        result['ready'] = result['checkpoint_verified'] and result['torch_installed']
        result['state'] = 'CANDIDATO EXPERIMENTAL' if result['ready'] else 'Checkpoint o Torch no disponible'
    except (OSError, ValueError, KeyError) as exc:
        result.update(state='Candidato no disponible', error=str(exc))
    return result


def decode_upload(payload):
    import numpy as np
    import soundfile as sf
    if payload.get('target') not in TARGETS:
        raise ValueError('Objetivo admitido: vacuum_cleaner o chainsaw')
    if not isinstance(payload.get('block_protected', False), bool):
        raise ValueError('block_protected debe ser booleano')
    encoded = payload.get('audio_base64')
    if not isinstance(encoded, str) or len(encoded) > (MAX_BYTES * 4 // 3 + 4):
        raise ValueError('Adjunta un WAV de hasta 4 MiB y 15 segundos')
    try:
        data = base64.b64decode(encoded, validate=True)
        info = sf.info(io.BytesIO(data))
    except Exception as exc:
        raise ValueError('WAV no válido') from exc
    if len(data) > MAX_BYTES or info.format not in ('WAV', 'WAVEX'):
        raise ValueError('Se requiere WAV de hasta 4 MiB')
    if not 1 <= info.channels <= 2 or not 8000 <= info.samplerate <= 96000 or not 0 < info.frames <= 15 * info.samplerate:
        raise ValueError('WAV: 1–2 canales, 8–96 kHz y duración máxima de 15 s')
    audio, rate = sf.read(io.BytesIO(data), dtype='float32', always_2d=True)
    if not np.isfinite(audio).all():
        raise ValueError('El WAV contiene muestras no finitas')
    return data, audio, rate


def run_candidate(output_root, run_id, payload, decoded):
    import numpy as np
    import scipy.signal
    import soundfile as sf
    from m4_scientific.inference import predict_file
    raw, audio, rate = decoded
    block = payload.get('block_protected', False)
    # BLOCK is allowed without weights; it must never invoke the estimator.
    if not block and not candidate_status()['ready']:
        raise ValueError('Checkpoint seleccionado no verificado o Torch no disponible; sin fallback Oracle')
    directory = Path(output_root) / run_id
    directory.mkdir(parents=True, exist_ok=False)
    source = directory / 'input_original.wav'
    source.write_bytes(raw)
    mono = audio.mean(axis=1)
    if rate != 16000:
        gcd = math.gcd(rate, 16000)
        mono = scipy.signal.resample_poly(mono, 16000 // gcd, rate // gcd).astype('float32')
    sf.write(directory / 'input_16k.wav', mono, 16000, subtype='FLOAT')
    meta = predict_file(SELECTED / 'candidate.pt', source, directory / 'output.wav',
                        payload['target'], block_protected=block)
    rendered, _ = sf.read(directory / 'output.wav', dtype='float32')
    # Same axes and no independent normalization for an honest visual comparison.
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 1, figsize=(9, 3.4), sharex=True, sharey=True)
    times = np.arange(len(mono)) / 16000
    for ax, wave, label in zip(axes, (mono, rendered), ('Entrada mono · 16 kHz', 'Salida del candidato / bypass')):
        ax.plot(times[::8], wave[::8], linewidth=.5, color='#087f83')
        ax.set_ylabel(label, fontsize=8)
    axes[-1].set_xlabel('Tiempo (s)'); fig.tight_layout()
    fig.savefig(directory / 'waveform.png', dpi=140); plt.close(fig)
    artifacts = [{'name': name, 'sha256': digest(directory / name),
                  'url': f'/artifacts/{run_id}/{name}'} for name in
                 ('input_original.wav', 'input_16k.wav', 'output.wav', 'output.json', 'waveform.png')]
    result = {'run_id': run_id, 'target': payload['target'], 'policy': meta,
              'engine': 'bypass' if not meta['model_called'] else 'cnn_scientific_candidate',
              'pcm_bypass_verified': bool(np.array_equal(mono, rendered)) if block else None,
              'metrics': None, 'scientific_go': False,
              'created_at': datetime.now(timezone.utc).isoformat(),
              'runtime': candidate_status(),
              'note': 'Escucha de inferencia offline. Sin referencias limpias no se calculan métricas de separación.',
              'artifacts': artifacts}
    (directory / 'scientific_run.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return result


def list_candidate_runs(root):
    rows = []
    for path in sorted(Path(root).glob('SCIENCE-*/scientific_run.json'), key=lambda p: p.stat().st_mtime, reverse=True)[:100]:
        try:
            row = json.loads(path.read_text(encoding='utf-8'))
            rows.append({'run_id': path.parent.name, 'target': row['target'], 'engine': row['engine'],
                         'created_at': row.get('created_at'), 'policy': row['policy']['decision'],
                         'url': f'/artifacts/{path.parent.name}/scientific_run.json'})
        except (OSError, ValueError, KeyError):
            continue
    return rows
