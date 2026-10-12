# Readiness de rúbrica S8 — T10 / Grupo B

Fecha: 2026-10-12

Este archivo separa **capacidad implementada** de **evidencia todavía pendiente**. No sustituye la rúbrica oficial.

## Requisitos específicos de T10

| Evidencia exigida | Estado actual | Evidencia disponible | Acción pendiente antes del parcial |
|---|---|---|---|
| Dataset de audio y clases de estímulos | VALIDADO / BENCHMARK PENDIENTE | UrbanSound8K oficial descargado; MD5 oficial, 8,732 filas, 10 folds, 10 clases y 0 audios faltantes; guard de ocurrencia corregido | ejecutar benchmark real y congelar resultados |
| Modelo base de clasificación/separación procesando audio | CUMPLE COMO BASELINE S8 | M2 SVM/RF ejecutable; M4 IRM oracle procesa mezcla y genera salida/audio/métricas | no presentar oracle como modelo aprendido final |
| Latencia medida en dispositivo objetivo | PENDIENTE DE EVIDENCIA LOCAL | job de medición `whole_clip_processing_only` y UI/Docker ya implementados | ejecutar 40 runs en Acer Nitro 5 y congelar `latency_summary.json` |

## Requisitos comunes de Grupo B

| Elemento | Estado |
|---|---|
| 1–2 módulos Must operando E2E | CUMPLE: M3b + M6, con baseline M4 integrada |
| Repositorio con commits | CUMPLE |
| Ambiente de ejecución local | CUMPLE: Docker Compose |
| Demo funcional | CUMPLE para baseline controlada |
| Evidencia reproducible | CUMPLE: JSON/CSV/SQLite/SHA-256/integrity |
| UI / artefacto demostrable | CUMPLE: consola web evidence-first |
| Pruebas funcionales | CUMPLE a nivel automatizado del incremento |
| ISO/IEC 25010 | PLAN / especificación; no declarar evaluación final ejecutada |
| SUS/TAM | POR CONFIRMAR CON ASESOR; no inventar usuarios/encuesta |

## Estado de defensa

### Puede demostrarse ahora

- ALLOW: atenuación baseline y métricas reales del run.
- BLOCK: precedencia de señal protegida y `g=1`.
- reproducción de mezcla/salida.
- waveform y espectrograma del mismo run.
- integridad del expediente.
- Docker health y ejecución reproducible.
- M2 software y contrato experimental.

### No puede afirmarse todavía

- Macro-F1 real de UrbanSound8K.
- cumplimiento RNF-03.
- streaming real por bloques.
- p95/hop o E2E final.
- latencia de Acer Nitro 5 hasta ejecutar el job local.
- modelo M4 aprendido.
- TFLite/paridad/Honor X8c.
- eficacia clínica.

## Gates previos al parcial

1. volver a ejecutar el validador actualizado y confirmar `occurrence_fold_consistency_ok=true`.
2. Ejecutar M2 real y congelar resultados.
3. Ejecutar medición whole-clip en Acer Nitro 5.
4. Grabar video de respaldo usando exactamente la misma imagen Docker.
5. Actualizar NotebookLM/PPT únicamente con los números producidos por esos dos runs reales.