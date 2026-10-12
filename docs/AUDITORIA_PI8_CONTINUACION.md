# Auditoría PI8+ — continuación y cierre técnico del parcial

Fecha: 2026-10-12  
Tesis: T10 / HESYCHIA  
Alcance: repositorio, demo, evidencia y documentación S5–S8.

## Resultado ejecutivo

La revisión detectó inconsistencias entre la maqueta histórica PI7, la arquitectura corregida y la evidencia realmente construida. Se corrigieron sin ampliar artificialmente el alcance de la tesis.

El incremento PI8+ queda como **demo técnica reproducible y verificable**, no como sistema final de tesis.

## Brechas cerradas

| Brecha | Corrección | Estado |
|---|---|---|
| UI histórica con valores ilustrativos | sustituida por consola conectada al backend real | CERRADA |
| identificadores genéricos en AUDIO_ASSET | AUDIO_ASSET queda ligado al SHA-256 real de protected/target/background | CERRADA |
| validator solo verificaba archivos/conteos | verifica manifiesto ↔ filesystem ↔ JSON ↔ SQLite ↔ política ↔ métricas ↔ config ↔ inputs | CERRADA |
| configuración compartida entre runs | cada run conserva EXP-{run_id} y su config | CERRADA |
| no había demo visual de precedencia protected | UI ejecuta escenarios ALLOW y BLOCK | CERRADA |
| parámetros API demasiado permisivos | seed/cap_db/alpha/protect_target validados antes del job | CERRADA |
| M2 con provenance limitada | metadata SHA-256, split/fold counts, model hash y benchmark_manifest | CERRADA |
| arquitectura descrita como cadena lineal | separados camino offline y runtime con M5 como orquestador | CERRADA |
| streaming redactado como hecho | documentación distingue target final vs PI8 actual | CERRADA |
| porcentajes de avance sin método formal | sustituidos por estados categóricos verificables | CERRADA |
| overflow móvil básico | añadidas reglas responsive/overflow | CERRADA |
| Docker sin contrato de demo explícito | Dockerfile + Compose + health check + runbook | CERRADA |

## Verificación automatizada actual

Workflow final de código exitoso: **38209597684** (job **114680574511**).

Evidencia observada en ese workflow:

- Python 3.11.17;
- **22 tests → OK**;
- sintaxis JavaScript → OK;
- reproducción PI8 → OK;
- validator de integridad → OK;
- 9 artefactos registrados;
- 3 input assets ligados a SHA-256 real;
- `docker compose config` → OK;
- build de imagen Docker → OK;
- health smoke test → `{"status":"ok","service":"hesychia-web"}`;
- job de latencia local etiquetado `whole_clip_processing_only` probado por CI.

## Qué demuestra hoy la demo

### ALLOW

Ejecuta un run real de la baseline controlada:

`stems → mezcla → STFT → IRM oracle → gain → iSTFT → métricas → evidencia`

Produce WAV, NPY, PNG, CSV/JSON, SQLite y hashes.

### BLOCK

Permite añadir el target al conjunto protegido. M3b aplica:

`target ∈ protected_set → BLOCK → g=1`

Este caso demuestra la regla de preservación. No se evalúa contra el objetivo de atenuación ALLOW porque su propósito es precisamente impedir la atenuación.

### Integridad

Cada run puede verificarse desde la UI. El validator detecta modificaciones en archivos, métricas SQLite o hashes de input.

### M2

El software de benchmark está implementado y probado con fixture. El benchmark científico real permanece bloqueado hasta disponer de UrbanSound8K oficial completo.

## Decisión metodológica M2

La tesis usa:

- folds 1–8 → train;
- fold 9 → validation;
- fold 10 → test.

Es un **holdout basado en folds oficiales**, no validación cruzada de diez folds. Los resultados no deben presentarse como directamente comparables a publicaciones que usen otro protocolo.

## Elementos todavía pendientes

1. UrbanSound8K completo y evidencia real de M2.
2. M4 aprendido target-conditioned.
3. integración con mezclas reales / LibriSpeech.
4. streaming por bloques en laptop.
5. p95 por hop y E2E final.
6. exportación y paridad TFLite.
7. perfil físico Honor X8c.
8. RAM/tamaño de modelo móvil.
9. estabilidad de 10 minutos.
10. validación final congelada.

Además, la **latencia en el dispositivo objetivo Acer Nitro 5** sigue pendiente de ejecución por el tesista. El mecanismo ya existe en la UI/Docker, pero el valor de CI no debe presentarse como medición de la Acer.

## Regla de defensa

Nunca afirmar:

- que IRM oracle es la CNN final;
- que M2 real ya cumple Macro-F1 ≥ 0.85;
- que la latencia de clip es p95/hop o E2E;
- que Android ya fue medido;
- que existe streaming final;
- que existe eficacia clínica.

## Siguiente gate

**Validar UrbanSound8K completo → ejecutar M2 real → congelar evidencia → recién después avanzar al M4 aprendido.**