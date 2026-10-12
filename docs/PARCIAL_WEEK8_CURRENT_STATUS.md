# Estado actual para Examen Parcial — Semana 8

**Tesis:** T10 — HESYCHIA  
**Tesista:** Merino Córdova, Eduardo Farid  
**Fecha de corte:** 2026-10-12

## Regla de entrega

El parcial se defiende con la versión corregida y vigente del contrato técnico:

**PI5 requisitos → PI6 arquitectura corregida → PI7 v1.1 diseño detallado corregido → PI8 construcción incremental verificable.**

El documento maestro original de Tesis I queda como antecedente histórico cuando contradice las correcciones PI6/PI7.

## Estado ejecutivo

El repositorio ya contiene un incremento funcional Edge-local reproducible. No se afirma sistema final completo. El estado correcto para exposición es:

- arquitectura Edge-first: operativa a nivel local;
- M3b política target/protected: funcional;
- M4 baseline IRM oracle: funcional como línea base controlada;
- M6 evidencia: funcional con JSON, CSV, SQLite, checksums y validador;
- M2 benchmark semántico: **evidencia real medida** sobre UrbanSound8K oficial; SVM seleccionado en validación; test Macro-F1=0.7257; RNF-03=0.85 **no cumplido por la baseline**;
- latencia S8 en Acer Nitro 5: **medida y agregada** en 2 lotes/80 muestras; pooled p50=20.024 ms, pooled p95=34.607 ms, media=22.688 ms; p95 por lote=26.205–41.508 ms (`whole_clip_processing_only`); RNF-05 final sigue pendiente;
- TFLite/Honor X8c: pendiente;
- streaming real por bloques: pendiente;
- claims clínicos: prohibidos.

## Evidencia ya verificada

La verificación CI del incremento cubre instalación desde `requirements-lock.txt`, tests contractuales, demo PI8, validación de artefactos/SQLite, JavaScript, Docker Compose, build de imagen y health smoke test. Para el conteo exacto usar siempre el workflow verde más reciente; no conservar cifras históricas obsoletas.

## Estado local del tesista

El entorno local científico ya fue corregido y ejecutado con **Python 3.11.9**. UrbanSound8K y la campaña de latencia se obtuvieron con el entorno validado; no volver a usar el alias global de Windows como sustituto del `.venv`.

UrbanSound8K ya fue descargado, validado y ejecutado. La evidencia real observada fue:

```powershell
$DATASET = "C:\Users\eduar\Desktop\Farid\UrbanSound8K"
.\.venv\Scripts\python.exe src\validate_urbansound8k.py --dataset-root "$DATASET"
.\.venv\Scripts\python.exe src\semantic_benchmark.py --dataset-root "$DATASET" --out "outputs\m2_urbansound8k" --seed 42
```

## Mensaje de defensa

> Este parcial no presenta una tesis final terminada. Presenta un artefacto técnico que ya pasó de especificación a construcción verificable. El sistema actual demuestra la cadena DSP, la política de preservación, la reconstrucción, la trazabilidad y el expediente reproducible. M2 ya cuenta con benchmark real sobre UrbanSound8K: la baseline SVM obtuvo Macro-F1=0.7257 en fold 10 y **no alcanzó** RNF-03=0.85; el umbral se conserva y el siguiente candidato debe desarrollarse sin tuning sobre el test.

## Riesgo principal de exposición

No decir: “M2 ya cumple el requisito de desempeño”.  
Sí decir: “ejecuté la baseline real sobre UrbanSound8K; SVM fue el mejor candidato clásico, obtuvo Macro-F1=0.7257 en test y no alcanzó el umbral 0.85. El resultado queda congelado como línea base y justifica avanzar al candidato aprendido ya previsto”.
