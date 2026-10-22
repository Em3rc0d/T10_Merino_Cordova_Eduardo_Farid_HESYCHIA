# Gate de diseño M4 — tareas para cierre antes de entrenar

**Fecha:** 2026-10-22; estado inicial **NO BUILD_READY**.
Diseño completo: [01_design/M4_LEARNING_DESIGN_2026-10-22.md](../01_design/M4_LEARNING_DESIGN_2026-10-22.md)

| Gate | Evidencia para cerrar | Estado actual |
|---|---|---|
| D0 | Source audit sirena aislada vs pseudo-stem, atribución/licencia comprobada | OPEN |
| D1 | Train/val/test manifests, hashes, independencia fsID + speaker + clips origen | OPEN |
| D2 | Framing/STFT/iSTFT causal, normalización causal, tests offline-vs-stream | OPEN |
| D3 | Pérdida L0 estable con target-absent y ADR prospectiva opcional L1 | OPEN |
| D4 | Selección val-only, prueba independiente sellada, métricas por mezcla | OPEN |
| D5 | Prueba de compatibilidad runtime TFLite, memoria/CPU disponibles, equipo objetivo | OPEN |

La implementación posterior es secuencial: generar corpus/controladores -> test causal frontend -> entrenamiento M4-L0 -> comparación val y eventual L1 preregistrado -> evaluación test UNA vez -> Oracle pareado -> TFLite/paridad -> Edge laptop -> Honor.

No se entrenó ningún modelo ni se produjo un nuevo benchmark con este commit. Mantener intocados los resultados previos y no consumir commits por cada ajuste.