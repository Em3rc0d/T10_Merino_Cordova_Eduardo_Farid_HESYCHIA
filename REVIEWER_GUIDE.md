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

El módulo de benchmark semántico ya posee una implementación ejecutable: valida el contrato de UrbanSound8K, congela folds 1–8/9/10, verifica ausencia de leakage por fsID, extrae MFCC/log-Mel, entrena SVM y Random Forest, selecciona únicamente con validación y genera Macro-F1/Recall/Precision, matriz de confusión, predicciones y modelo serializado.

El CI valida este pipeline con un fixture de audio que conserva el contrato de folds. **El fixture prueba software, no constituye resultado científico de UrbanSound8K.** El Macro-F1 real permanece pendiente hasta ejecutar la distribución completa.

Protocolo: `docs/M2_URBANSOUND8K_PROTOCOL.md`.

## Afirmaciones soportadas

1. Existe un incremento funcional local reproducible.
2. La demo genera stems sintéticos, mezcla, máscara IRM baseline, audio procesado y métricas.
3. En el run de referencia se observaron A_target≈11.99 dB, A_protected≈0.007 dB y SI-SDRi≈11.52 dB.
4. El benchmark local del clip completo tuvo p50≈14.03 ms y p95≈15.70 ms en el entorno de desarrollo.
5. Existe trazabilidad mediante JSON/CSV/SQLite/manifiesto/checksum y un validador que cruza filesystem, Run ID y base de evidencias.
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
