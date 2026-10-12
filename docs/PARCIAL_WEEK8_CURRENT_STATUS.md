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
- TFLite/Honor X8c: pendiente;
- streaming real por bloques: pendiente;
- claims clínicos: prohibidos.

## Evidencia ya verificada

La última verificación CI pasada incluyó:

1. instalación desde `requirements-lock.txt`;
2. seis tests automáticos;
3. ejecución de PI8 demo;
4. benchmark local del clip completo;
5. validación de artefactos mediante SHA-256;
6. persistencia y validación de SQLite;
7. generación de artifact de evidencia.

## Estado local del tesista

El equipo local ya tiene dependencias instaladas, pero se detectó que el `.venv` usado inicialmente quedó en Python 3.14.2. Como el contrato CI usa Python 3.11.x y el equipo también tiene Python 3.11.9 disponible, el entorno local debe recrearse con `py -3.11` antes de ejecutar la evidencia científica real.

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
