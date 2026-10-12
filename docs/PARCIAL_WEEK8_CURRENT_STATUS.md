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
- M2 benchmark semántico: pipeline implementado y probado con fixture; evidencia real de UrbanSound8K pendiente de descarga/ejecución completa;
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

UrbanSound8K está en descarga. La evidencia real de M2 solo se congela después de:

```powershell
$DATASET = "C:\Users\eduar\Desktop\Farid\UrbanSound8K"
.\.venv\Scripts\python.exe src\validate_urbansound8k.py --dataset-root "$DATASET"
.\.venv\Scripts\python.exe src\semantic_benchmark.py --dataset-root "$DATASET" --out "outputs\m2_urbansound8k" --seed 42
```

## Mensaje de defensa

> Este parcial no presenta una tesis final terminada. Presenta un artefacto técnico que ya pasó de especificación a construcción verificable. El sistema actual demuestra la cadena DSP, la política de preservación, la reconstrucción, la trazabilidad y el expediente reproducible. El reconocimiento semántico M2 ya tiene pipeline ejecutable, pero sus resultados científicos reales se congelarán únicamente cuando se ejecute UrbanSound8K completo.

## Riesgo principal de exposición

No decir: “ya entrené IA con UrbanSound8K”.  
Sí decir: “ya implementé el pipeline reproducible de benchmark; la ejecución real está preparada y depende de completar la descarga del dataset oficial”.
