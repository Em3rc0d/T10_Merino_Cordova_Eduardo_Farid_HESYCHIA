# HESYCHIA · Auditoría perceptual OE1 — instrucciones para revisores

## Objetivo
Revisar de manera independiente la muestra estratificada congelada de **93 registros**. Esta actividad evalúa la pureza/aptitud de las fuentes del corpus; no evalúa eficacia clínica ni permite modificar el modelo con base en el test confirmatorio.

## Independencia
- Revisor A y Revisor B deben ser personas distintas.
- Cada revisor escucha los 93 audios sin consultar las respuestas del otro.
- No discutir discrepancias hasta finalizar ambas revisiones.
- Los archivos `reviewer_A.csv` y `reviewer_B.csv` son evidencia original y no se sobrescriben durante la adjudicación.

## Criterios que muestra la interfaz
Para cada audio:
1. ¿se escucha el evento principal?;
2. pureza acústica: `isolated`, `minor_contamination`, `mixed` o `undetermined`;
3. voz presente;
4. alarma/sirena presente;
5. eventos secundarios audibles;
6. decisión: `eligible`, `restricted` o `reject`;
7. observaciones.

La interfaz verifica el SHA-256 del WAV antes de permitir guardar.

## Ejecución
Con los PCM restaurados y verificados:

Revisor A:
```bash
python scripts/pi13_review_workbench.py serve \
  --manifest "$MANIFEST" --sample-manifest "$OUT/reviews/audit_93.csv" \
  --audio-root "$AUDIO_ROOT" --out-dir "$OUT/reviews" \
  --reviewer reviewer_A --port 8765
```

Revisor B:
```bash
python scripts/pi13_review_workbench.py serve \
  --manifest "$MANIFEST" --sample-manifest "$OUT/reviews/audit_93.csv" \
  --audio-root "$AUDIO_ROOT" --out-dir "$OUT/reviews" \
  --reviewer reviewer_B --port 8766
```

## Cierre estadístico
Después de completar ambas revisiones:

```bash
python scripts/pi13_review_workbench.py export-double \
  --first "$OUT/reviews/reviewer_A.csv" \
  --second "$OUT/reviews/reviewer_B.csv" \
  --out "$OUT/reviews/double_review_93.csv"

python scripts/pi13_agreement.py \
  --reviews "$OUT/reviews/double_review_93.csv" \
  --out "$OUT/reviews/kappa_93.json"

python scripts/pi13_adjudication_template.py \
  --first "$OUT/reviews/reviewer_A.csv" \
  --second "$OUT/reviews/reviewer_B.csv" \
  --out "$OUT/reviews/adjudication_disagreements.csv"
```

El κ se calcula **antes** de cualquier adjudicación. Se utiliza κ >= 0,60 como umbral interpretativo preespecificado; valores inferiores requieren explicación/adjudicación y no se ocultan.

Una vez adjudicadas las discrepancias y construido el CSV final de 93 decisiones:

```bash
python scripts/pi13_contamination_ci.py \
  --reviewed-csv "$OUT/reviews/final_review_93.csv" \
  --expected-n 93 \
  --out "$OUT/reviews/contamination_93.json"
```

La proporción reportada corresponde a registros no aislados/no elegibles y se acompaña con IC95 % de Wilson.
