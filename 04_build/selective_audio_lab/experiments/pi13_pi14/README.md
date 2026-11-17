# HESYCHIA — PI15, ejecución reproducible de cierre

**Estado científico actual:** la instrumentación está implementada; la campaña confirmatoria y el benchmark oficial de Acer sólo se consideran cerrados cuando existen sus artefactos reales.

## 1. Herramientas

| Archivo | Función |
|---|---|
| `scripts/pi13_review_workbench.py` | Revisión perceptual local con SHA-256 de cada audio |
| `scripts/pi13_double_sample.py` | Reproduce la muestra estratificada de 93 registros |
| `scripts/pi13_agreement.py` | Cohen κ entre los dos evaluadores |
| `scripts/pi13_corpus_gate.py` | Gate estructural de la revisión |
| `scripts/pi13_freeze_preflight.py` | Preflight fail-closed previo al test |
| `scripts/pi14_analysis_v2.py` | CNN−DSP pareado, bootstrap por grupo, percentil + BCa y decisión conjunta |
| `scripts/pi14_m4_forward_benchmark.py` | Benchmark M4 real con >=1000 bloques |
| `src/dsp_class_template.py` | Baseline DSP condicionada por clase |

## 2. Preparación local

```bash
REPO="$HOME/T10_Merino_Cordova_Eduardo_Farid_HESYCHIA"
LAB="$REPO/04_build/selective_audio_lab"
MANIFEST="$REPO/05_evidence/m4_sci_v3_source_review_2026-10-28/source_review_352_template.csv"
AUDIO_ROOT="$LAB/data/m4_sci_v2_pilot/pcm"
OUT="$LAB/experiments/pi13_pi14/outputs"
mkdir -p "$OUT/reviews"
python -m pip install -r "$LAB/requirements-scientific.txt"
python -m pytest -q "$LAB/experiments/pi13_pi14/tests"
```

Si los PCM no están restaurados, usar únicamente el procedimiento de reproducción del corpus ya versionado. No crear audios de relleno.

## 3. Auditoría OE1: 93 registros, dos evaluadores

Recrear la selección congelada:

```bash
cd "$LAB/experiments/pi13_pi14"
python scripts/pi13_double_sample.py \
  --manifest "$MANIFEST" \
  --out "$OUT/reviews/audit_93.csv" \
  --report "$OUT/reviews/audit_93_selection.json" \
  --rate 0.20 --min-groups-per-stratum 2 --seed 20261108
sha256sum "$OUT/reviews/audit_93.csv"
```

El SHA esperado para la selección preespecificada es:
`f0266f300f1c3eb12ef6d3a20b49ed61f6b7ea79f739b8d1febc03a1cfa11abb`.

Evaluador A:

```bash
python scripts/pi13_review_workbench.py serve \
  --manifest "$MANIFEST" --sample-manifest "$OUT/reviews/audit_93.csv" \
  --audio-root "$AUDIO_ROOT" --out-dir "$OUT/reviews" \
  --reviewer reviewer_A --port 8765
```

Evaluador B independiente:

```bash
python scripts/pi13_review_workbench.py serve \
  --manifest "$MANIFEST" --sample-manifest "$OUT/reviews/audit_93.csv" \
  --audio-root "$AUDIO_ROOT" --out-dir "$OUT/reviews" \
  --reviewer reviewer_B --port 8766
```

Exportar y calcular concordancia:

```bash
python scripts/pi13_review_workbench.py export-double \
  --first "$OUT/reviews/reviewer_A.csv" \
  --second "$OUT/reviews/reviewer_B.csv" \
  --out "$OUT/reviews/double_review_93.csv"

python scripts/pi13_agreement.py \
  --reviews "$OUT/reviews/double_review_93.csv" \
  --out "$OUT/reviews/kappa_93.json"
```

Registrar además proporción de contaminación e IC95 %. Si κ < 0,60 o existe contaminación relevante, documentar adjudicación/exclusiones antes del freeze.

## 4. Baseline DSP

La definición está congelada en:

- `src/dsp_class_template.py`
- `configs/dsp_class_template_v1.json`
- `docs/DSP_BASELINE_CONTRACT_2026-11-17.md`

Las plantillas finales sólo se generan después de aplicar exclusiones del corpus. Registrar SHA-256 del artefacto resultante antes del test.

## 5. Benchmark OE3 en Acer Nitro 5

```bash
cd "$LAB"
python experiments/pi13_pi14/scripts/pi14_m4_forward_benchmark.py \
  --checkpoint models/m4_sci_real_candidate_v1/selected/candidate.pt \
  --model-src src \
  --out experiments/pi13_pi14/outputs/m4_forward_acer \
  --runs 100 --warmup 8 --hops 16 --seconds 2 \
  --device cpu --threads 4 --min-samples 1000
```

El JSON debe contener >=1000 muestras y reportar p50/p95/p99, RTF y recursos. Esta medición es M4-forward offline; no es streaming físico E2E.

## 6. Freeze del test

Completar una copia de `fixtures/PI13_FREEZE_CONFIG_TEMPLATE.json` con rutas reales a:

- test_scenes;
- reporte de auditoría;
- checkpoint;
- código de evaluación;
- protocolo;
- reporte de fuga fuente/hablante;
- concordancia interevaluador.

```bash
python scripts/pi13_freeze_preflight.py \
  --config outputs/PI15_FREEZE_CONFIG.json \
  --out outputs/freeze_preflight.json
```

No ejecutar el test hasta que el preflight no tenga bloqueadores y se hayan registrado los SHA-256.

## 7. OE2 y análisis final

CNN, DSP y Oracle deben producir una fila por método sobre la misma escena y el mismo `mix_sha256`.

```bash
python scripts/pi14_analysis_v2.py \
  --by-scene outputs/confirmatory_by_scene.csv \
  --out outputs/confirmatory_analysis.json \
  --boot 10000 --voice-margin-db 1.0
```

La decisión final usa los límites unilaterales BCa y la regla conjunta de cuatro casos. CP02 y CP10 se ejecutan antes de redactar la conclusión de OE2.

## 8. Cierre de versión

Sólo después de completar y auditar la evidencia:

1. fusionar PR #7 a `main`;
2. citar el SHA de `main` evaluado;
3. crear tag `v1.0-tesis`;
4. actualizar tesis, PI15 y video con exactamente esa versión.
