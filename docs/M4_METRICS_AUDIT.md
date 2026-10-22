# Auditoría reproducible de M4 Oracle por mezcla

El docente cuestionó la preservación de voz: una media de 1.12 dB o la referencia oral a «47 de 100 mezclas» **no se puede verificar sin el CSV del experimento exacto**. No debe inferirse ese conteo del resumen ni suponerse que es el mismo run.

## Ejecución sobre el lote REAL ya generado localmente

Desde 04_build/selective_audio_lab:

~~~bash
python src/m4_oracle_audit.py \
  --input outputs/m4_real_mixture_oracle_batch/real_mixture_runs.csv \
  --out outputs/m4_oracle_audit \
  --min-target-db 6 --max-protected-db 1 \
  --primary-cap-db 12 --min-mixtures 100
~~~

Si no existe real_mixture_runs.csv, primero ejecutar el experimento documentado en M4_REAL_MIXTURE_ORACLE_PROTOCOL.md con UrbanSound8K y un corpus de voz real, **sin inventar los resultados**.

## Artefactos

- m4_oracle_per_mix_audit.csv: métricas y flags target_ok/protected_ok/both_ok por (mix_id, cap_db).
- m4_oracle_audit_summary.json: SHA-256 del CSV, resultados por cap, número de fallos individuales y conjuntos, media y mediana.
- El gate primario evalúa el cap de 12 dB, según protocolo anterior. El sweep 18/24/30 es sensibilidad, no una excusa para elegir a posteriori el que mejor salga.

La herramienta bloquea CSV incompleto, cap sin todos los mix_id, duplicados, NaN/Inf y lotes inferiores a 100 mezclas por defecto.

## Interpretación

Para cada mezcla i:

- target_ok(i) = A_target(i) ≥ 6 dB
- protected_ok(i) = A_protected(i) ≤ 1 dB
- both_ok(i) = target_ok(i) y protected_ok(i)

La tasa de cumplimiento conjunto es descriptiva para el lote; **un promedio válido no compensa una mezcla que incumple**. Los stems de referencia se usan para esta métrica aislada: no demuestra inteligibilidad, seguridad real ni beneficio clínico.

**Advertencia crítica:** este programa audita **la máscara Oracle**, no una red neuronal. Un futuro modelo M4 aprendido necesita su evaluación separada y una comparación pareada, nunca sustitución silenciosa.
