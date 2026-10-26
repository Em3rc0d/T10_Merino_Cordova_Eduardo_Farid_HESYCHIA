# S10-A — Observación 6: evidencia y estado

**Fecha:** 2026-10-25. **Observación:** la demo atenuaba sirenas, potencialmente señales de emergencia. **Estado académico:** EN PROCESO — corrección de software preparada en rama, falta QA completo del checkout y entrega de video.

## Rutas verificables en la rama S10-A

| Elemento | Archivo (relativo al repositorio) | Cambio |
|---|---|---|
| Política | `04_build/selective_audio_lab/src/policy.py` | Precedencia obligatoria, catálogo y motivos auditables |
| Señales | `04_build/selective_audio_lab/src/audio_core.py` | Nuevo generador `synthesize_drilling` |
| DSP | `04_build/selective_audio_lab/src/attenuation.py` | BLOCK hace bypass digital sin máscara IRM |
| Run | `04_build/selective_audio_lab/src/run_demo.py` | Carpeta/ID S10-A, procedencia, nueva escena por defecto |
| API | `04_build/selective_audio_lab/src/web_server.py` | Validación de target, sin anulación crítica |
| UI | `04_build/selective_audio_lab/web/index.html` | Dos targets sintéticos y advertencia oracle |
| Tests | `04_build/selective_audio_lab/test_s10a_safety.py`, `test_contract_v12.py`, `test_demo.py`, `test_web_server.py` | Contratos funcionales y regresión |
| Diseño | `docs/S10A_SAFETY_POLICY_DESIGN.md` | Alcance y límites científicos |
| Runbook | `docs/DEMO_DOCKER.md` y `02_plan/plan_demo_video.md` | Demostración planificada, no grabada |

## QA que sí se ejecutó durante el desarrollo

- **12/12 pruebas PASS** en entorno Python local de un **espejo instrumental del núcleo** (política/DSP/generadores), no en checkout completo del repositorio. Se evaluaron bloqueo obligatorio, fallos de catálogo, protección manual, generación determinista, caso ALLOW oracle y bypass digital exacto.
- Fixture mecánico procedural seed=42, cap=12 dB, alpha=1: `A_target≈11.97 dB`, `A_protected≈0.10 dB`, `SI-SDRi_protected≈+11.72 dB`. Son resultados de este fixture, **no de habla real ni del modelo M4 aprendido**; tampoco validan RNF-04 ni permiten reescribir resultados anteriores.
- Sirena sintética explícita: `BLOCK`, output igual a mezcla digital, atenuaciones nominales 0 dB.

**NO ejecutado en el repositorio real de esta rama durante esta revisión:** suite completa, Docker/UI/API end-to-end, artefactos SQLite+SHA emitidos por el nuevo checkout y video narrado. Hasta ejecutarlos, no asignar `PASS` global ni declarar O6 levantada.

## Matriz para PI9 + PI10

| N.º | Observación | Estado | Dónde se verifica |
|---|---|---|---|
| 6 | Declarar alarmas/sirenas protegidas y cambiar target de demo | EN PROCESO | Archivos de código y pruebas citados; diseño S10-A; video y QA de integración aún pendientes |

## Integridad y atribución

El desarrollo recibió asistencia de ChatGPT en diseño, código y pruebas instrumentales. El tesista es responsable de auditar el funcionamiento, comprender el código y declarar el uso de IA en la versión académica según la normativa aplicable. Los commits agrupados reflejan incrementos funcionales: no se alteraron marcas temporales ni se simuló autoría humana.

Los resultados Oracle previos, RNF-03, RNF-04 y demás experimentos permanecen congelados.
