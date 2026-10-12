# Readiness de rúbrica S8 — T10 / Grupo B

Fecha: 2026-10-12

Este archivo separa **capacidad implementada** de **evidencia todavía pendiente**. No sustituye la rúbrica oficial.

## Requisitos específicos de T10

| Evidencia exigida | Estado actual | Evidencia disponible | Acción pendiente antes del parcial |
|---|---|---|---|
| Dataset de audio y clases de estímulos | CUMPLE S8 | UrbanSound8K oficial validado: 8,732 clips, 10 folds, 10 clases, 0 faltantes, integridad de ocurrencias OK | evidencia real congelada |
| Modelo base de clasificación/separación procesando audio | CUMPLE S8 | M2 real: SVM/RF sobre UrbanSound8K; SVM seleccionado; test Macro-F1=0.7257. M4 IRM oracle procesa mezcla y genera salida/audio/métricas | RNF-03 no cumplido por baseline; continuar candidato aprendido previsto |
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

- cumplimiento RNF-03 por el modelo final; la baseline real quedó en Macro-F1=0.7257 y **NO CUMPLE**.
- streaming real por bloques.
- p95/hop o E2E final.
- latencia de Acer Nitro 5 hasta ejecutar el job local.
- modelo M4 aprendido.
- TFLite/paridad/Honor X8c.
- eficacia clínica.

## Gates previos al parcial

1. Congelar/custodiar los artefactos locales del run M2 real.
2. Ejecutar medición whole-clip en Acer Nitro 5.
3. Grabar video de respaldo usando exactamente la misma imagen Docker.
4. Actualizar la PPT con Macro-F1=0.7257 como baseline real y RNF-03 no cumplido, sin ocultarlo.
5. No usar fold 10 para elegir cambios del siguiente candidato.