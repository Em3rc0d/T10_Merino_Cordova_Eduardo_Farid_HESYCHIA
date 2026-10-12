# Guía rápida para el docente / revisor automatizado

## Fuente de verdad y precedencia

Ante cualquier contradicción con formulaciones históricas del documento original de Tesis I, usar **[SOURCE_OF_TRUTH.md](SOURCE_OF_TRUTH.md)**. La versión vigente es PI7 v1.1 corregida e integrada con las observaciones de PI6 y PI7.

## Qué debe verificarse primero

Este repositorio está organizado para que la revisión del parcial pueda seguir exactamente la cadena solicitada:

**Problema → Objetivos → Requisitos → Componente → Diseño → Construcción → Evidencia → Validación.**

### Evidencia por semana
- **S5 / Requisitos:** `docs/informe_consolidado_S5_S8.md#2-requisitos-consolidados`
- **S6 / Arquitectura:** `03_architecture/` y sección 3 del informe.
- **S7 / Diseño detallado:** `01_design/`, `03_architecture/schema_v12.sql` y sección 4 del informe.
- **S8 / Construcción:** `04_build/selective_audio_lab/`.
- **Evidencia:** `05_evidence/`.
- **Exposición:** `docs/presentacion_semana8.md` y `docs/guion_exposicion.md`.

## M2 — estado verificable

El módulo de benchmark semántico valida UrbanSound8K, conserva folds 1–8/9/10, bloquea leakage a nivel de ocurrencia etiquetada `(fsID,classID,occurrenceID)`, extrae MFCC/log-Mel, entrena SVM y Random Forest, selecciona únicamente con validación y genera Macro-F1/Recall/Precision, matriz de confusión, predicciones y modelo serializado.

El CI valida el software con fixture, y además la distribución oficial completa ya fue ejecutada localmente. SVM RBF fue seleccionado en fold 9 y obtuvo Macro-F1=0.7257 en fold 10. RNF-03=0.85 **no fue cumplido por la baseline**. El resultado está documentado en `docs/M2_REAL_RESULT_2026-10-12.md`.

Protocolo: `docs/M2_URBANSOUND8K_PROTOCOL.md`.

## Afirmaciones soportadas

1. Existe un incremento funcional local reproducible.
2. La demo genera stems sintéticos, mezcla, máscara IRM baseline, audio procesado y métricas.
3. En el run de referencia se observaron A_target≈11.99 dB, A_protected≈0.007 dB y SI-SDRi≈11.52 dB.
4. La medición S8 en la Acer Nitro 5, 40 runs, obtuvo p50=19.976 ms, p95=26.205 ms y media=20.725 ms para `whole_clip_processing_only`; no equivale a p95/hop ni E2E.
5. Existe trazabilidad mediante JSON/CSV/SQLite/manifiesto/checksum y un validador de **integridad cruzada** que exige coherencia entre filesystem, Run ID, política, métricas, configuración, artefactos SQLite y SHA-256 reales de los WAV de entrada.
6. M3b ya ejecuta la regla de precedencia protected: si target ∈ protected_set, la decisión es BLOCK y g=1.

## Afirmaciones que NO hace el proyecto

- No se afirma eficacia clínica sobre hiperacusia o TEA.
- No se afirma que la máscara PI8 sea el modelo CNN final.
- No se afirma streaming Android completo.
- No se afirma haber medido todavía el Honor X8c.
- La latencia local de PI8 no equivale al E2E final ni al p95 por hop requerido para la implementación final.
- Los criterios Macro-F1/latencia/acústica son metas de ingeniería preespecificadas, no umbrales clínicos.

## Correcciones PI6/PI7 incorporadas

- RF-10 entrenamiento del estimador de máscara.
- RF-11 exportación/paridad TFLite.
- RNF cuantificados.
- M3a (offline) separado de M3b (runtime).
- M5 definido como orquestador.
- Target fijo por configuración; M2 no gobierna M4.
- RUN_ASSET y POLICY_DECISION en el modelo de datos.
- UrbanSound8K con folds oficiales; LibriSpeech como señal protegida.
- A5-train/A5-infer especificado con IRM, embedding, pérdida y fórmula de ganancia.
- Android delimitado a perfilado TFLite hasta implementación real.

## Reproducción

```bash
cd 04_build/selective_audio_lab
pip install -r requirements-lock.txt
python -m unittest discover -p "test*.py"
python src/run_demo.py --out outputs/demo_run
python src/latency_benchmark.py --out outputs/latency --runs 40
python src/validate_artifacts.py --run-dir outputs/demo_run
```

Los tests contractuales verifican finitud, rango de máscara/ganancia, reproducibilidad, criterios acústicos, precedencia de política y round-trip de evidencia SQLite.


## Demo web / Docker

La demo actual se levanta con `docker compose up --build` y sirve una consola en `http://localhost:8080`. La UI consume resultados reales de jobs/runs: no conserva los números ilustrativos del prototipo PI7. Las funciones aún pendientes (streaming, train-mask, export-tflite) responden 501 o permanecen deshabilitadas en lugar de simularse.

La verificación CI del incremento web/Docker cubre tests contractuales, sintaxis JavaScript, reproducción PI8, build de la imagen y health smoke test. Consultar el workflow verde más reciente para el conteo exacto, evitando conservar cifras históricas obsoletas.


## Nota metodológica M2

El protocolo de tesis usa holdout 1–8/9/10 (train/validation/test) sobre los folds oficiales. No se describe como validación cruzada de diez folds y sus resultados no deben compararse directamente con publicaciones que usen otro protocolo de agregación. `benchmark_manifest.json` conserva metadata SHA-256, conteos y hashes de artefactos del benchmark.
