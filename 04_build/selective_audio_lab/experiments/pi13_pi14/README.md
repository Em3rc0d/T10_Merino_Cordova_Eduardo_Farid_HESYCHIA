# HESYCHIA — PI13/PI14, instrumentación reproducible v4 (08/11/2026)

**Estado científico: BLOQUEADO.** No se abrieron los tests nuevos, no se escucharon audios reales en este entorno y no se ejecutó el checkpoint real M4 en la laptop Acer. Estas herramientas permiten realizar y registrar esas actividades **localmente**, sin APIs de pago. Las 18 pruebas automatizadas realizadas con datos/PCMs de control NO son resultados académicos de la CNN.

## 1. Contenido

| Archivo | Función | Alcance |
|---|---|---|
| `scripts/pi13_review_workbench.py` | Servidor local para escuchar y revisar los 352 audios con SHA-256 obligatorio; registra una revisión por asset y por persona | Humano; no automatiza elegibilidad ni pureza |
| `scripts/pi13_double_sample.py` | Submuestra reproducible para doble revisión, estratificada por clase/split y agrupada por origen | Selección propuesta, no modifica train/val/test |
| `scripts/pi13_agreement.py` | Concordancia Cohen κ entre dos revisores fijos | No certifica independencia de personas |
| `scripts/pi13_corpus_gate.py` | Validación de CSV de revisión y particiones | PASS estructural no sustituye escuchar |
| `scripts/pi13_freeze_preflight.py` | Preflight fail-closed antes de sellar test | READY no autoriza unseal sin asesor |
| `scripts/pi14_analysis.py` | Comparación pareada CNN/DSP/Oracle usando `mix_sha256` idéntico | Requiere resultados verdaderos, nunca extrapola sobre ejemplos sintéticos |
| `scripts/pi14_benchmark_summary.py` | Resume trazas por bloque aportadas | Requiere trazas verdaderas, no simula E2E |
| `scripts/pi14_m4_forward_benchmark.py` | **Nuevo:** p50/p95/p99 y RTF de forward/gain de M4 con un checkpoint real explícito | No mide STFT, iSTFT, captura ni streaming físico |

## 2. Instalar y verificar

Extraer el ZIP, abrir una consola dentro de `hesychia_pi13_pi14/`:

```bash
python -m pip install numpy scipy soundfile torch pytest
python -m pytest -q tests/
# Validado en este entorno: 18 passed (fixtures, software, HTTP local, checkpoint sintético)
```

Para los siguientes pasos se requiere un clon local de [HESYCHIA](https://github.com/Em3rc0d/T10_Merino_Cordova_Eduardo_Farid_HESYCHIA), su checkpoint real `04_build/selective_audio_lab/models/m4_sci_real_candidate_v1/selected/candidate.pt` y el corpus PCM restaurado. Ningún audio comercial/ajeno se distribuye en este paquete.

Variables de ejemplo (ajustar rutas):

```bash
REPO="$HOME/T10_Merino_Cordova_Eduardo_Farid_HESYCHIA"
LAB="$REPO/04_build/selective_audio_lab"
MANIFEST="$REPO/05_evidence/m4_sci_v3_source_review_2026-10-28/source_review_352_template.csv"
AUDIO_ROOT="$LAB/data/m4_sci_v2_pilot/pcm"  # confirmar que existe y sus WAV coinciden con SHA
mkdir -p outputs/reviews
```

Si faltan los PCM, restaurarlos con el procedimiento de corpus **ya existente** en `m4_scientific.corpus.prepare` y `m4_scientific.reproduction.restore` dentro del repo (se requiere Internet y verificar licencias, hash y versión antes de hacer evaluaciones). **No se deben fabricar WAVs de relleno ni cambiar el CSV para pasar el gate.**

## 3. Auditar realmente los 352 PCM

Servidor HTTP local para el evaluador A (abrir `http://127.0.0.1:8765`):

```bash
python scripts/pi13_review_workbench.py serve \
  --manifest "$MANIFEST" --audio-root "$AUDIO_ROOT" \
  --out-dir outputs/reviews --reviewer reviewer_A --port 8765
```

El servidor sólo se enlaza a `127.0.0.1`. Cada audio se sirve y cada decisión se guarda **sólo si coincide el SHA-256 original**. Las decisiones permitidas son `eligible`, `restricted`, `reject`. `eligible` requiere `isolated` y evento principal audible. Revisiones de evaluadores distintos se guardan en archivos separados y no son visibles entre sí en la UI.

Submuestra doble ciega preseleccionada; registrar SHA/semilla y congelarla **antes** de revisar diferencias:

```bash
python scripts/pi13_double_sample.py --manifest "$MANIFEST" \
  --out outputs/reviews/second_review_sample.csv \
  --report outputs/reviews/second_review_selection.json \
  --rate 0.20 --min-groups-per-stratum 2 --seed 20261108

python scripts/pi13_review_workbench.py serve \
  --manifest "$MANIFEST" \
  --sample-manifest outputs/reviews/second_review_sample.csv \
  --audio-root "$AUDIO_ROOT" --out-dir outputs/reviews \
  --reviewer reviewer_B --port 8766
```

Al acabar la revisión A, crear **un nuevo CSV**, sin sobrescribir el manifiesto del repositorio:

```bash
python scripts/pi13_review_workbench.py export-primary \
  --manifest "$MANIFEST" \
  --review-csv outputs/reviews/reviewer_A.csv \
  --reviewer reviewer_A --out outputs/reviews/manifest_reviewed.csv

python scripts/pi13_corpus_gate.py \
  --manifest outputs/reviews/manifest_reviewed.csv \
  --out outputs/reviews/corpus_gate.json

python scripts/pi13_review_workbench.py export-double \
  --first outputs/reviews/reviewer_A.csv \
  --second outputs/reviews/reviewer_B.csv \
  --out outputs/reviews/double_review.csv

python scripts/pi13_agreement.py \
  --reviews outputs/reviews/double_review.csv \
  --out outputs/reviews/kappa.json
```

Si hay decisiones discrepantes, documentar adjudicación **en un registro separado**. No cambiar silenciosamente la opinión inicial de los revisores ni inferir κ cuando faltan pares.

## 4. Benchmark real de la inferencia CNN M4 (solo forward)

```bash
python scripts/pi14_m4_forward_benchmark.py \
  --checkpoint "$LAB/models/m4_sci_real_candidate_v1/selected/candidate.pt" \
  --model-src "$LAB/src" \
  --out outputs/m4_forward_laptop \
  --runs 40 --warmup 5 --hops 16 --seconds 2 --device cpu --threads 4
```

**Interpretar correctamente:** la señal es un fixture reproducible de tonos+ruido, y las features STFT son precomputadas **fuera** del cronómetro. Se mide exclusivamente inferencia CNN de M4 + política de ganancia sobre bloques offline con contexto histórico. Se guarda el hash del **checkpoint real**. El resultado no equivale a latencia E2E, al streaming continuo ni al p95 por hop del sistema completo. Repetir en Acer Nitro 5 y guardar hardware/OS para evidencias oficiales. No reportar las métricas de checkpoint simulado en los tests como rendimiento científico.

## 5. Test independiente/PI14

El procedimiento de congelación sigue **bloqueado** mientras falten OG/OE, criterio primario, revisión humana, grupos independientes, test nuevo y aprobación académica. La herramienta `pi14_analysis.py` exige un CSV verdadero por escena/metodología en la **misma mezcla `mix_sha256`**, y sólo genera estadísticas después de verificar el pareamiento.

```bash
python scripts/pi13_freeze_preflight.py \
  --config fixtures/PI13_FREEZE_CONFIG_TEMPLATE.json \
  --out outputs/freeze_preflight.json
# esperado hoy: BLOCKED, código 2
```

**No reutilizar el test V1 expuesto** para optimizar o declarar confirmación del V2/V3. El histórico V2 publicado es sólo *validación de desarrollo* y el benchmark S8 de 80 mediciones es de *procesamiento completo del clip con pipeline controlado*, NO de M4 per-hop.
