# HESYCHIA — T10 · Tesis II · UNMSM

**Tesista:** Merino Córdova, Eduardo Farid  
**Tema institucional:** Diseño de un sistema inteligente de cancelación selectiva de ruido mediante aprendizaje profundo para la atenuación de estímulos acústicos asociados a la hiperacusia en personas con TEA.  
**Grupo:** B — aporte práctico / software  
**Asesor:** Daniel Alfonso Quinto Pazce

## Estado académico

Este repositorio consolida la trazabilidad **PI5 → PI6 → PI7 corregido → PI8 / Examen Parcial**.

La implementación se delimita como un **prototipo técnico Edge AI de atenuación selectiva de audio**. El término institucional “cancelación” se operacionaliza como atenuación mediante ganancias/máscaras tiempo–frecuencia; no se implementa ANC físico por antirruido ni se realizan afirmaciones clínicas.

## Estructura del repositorio

| Ruta | Propósito |
|---|---|
| `00_brainstorming/` | narrativa de defensa, preguntas del jurado y límites del alcance |
| `01_design/` | decisiones de diseño congeladas y correcciones integradas |
| `02_plan/` | checklist, demo, validación y próximos pasos |
| `03_architecture/` | arquitectura corregida y esquema SQLite |
| `04_build/` | incremento funcional reproducible de PI8 |
| `05_evidence/` | métricas, manifiestos y evidencia reproducible generada por el build |
| `06_presentation/` | material y fuentes de la exposición |
| `07_submission/` | fuentes documentales de la entrega consolidada |
| `08_existing_context/` | contexto académico previo y referencias de revisión |
| `docs/` | documentación consolidada legible desde GitHub |

## Trazabilidad principal

```text
Problema
  ↓
Objetivos específicos
  ↓
RF / RNF de PI5
  ↓
Arquitectura modular Edge-local
  ↓
Diseño detallado PI7 v1.1
  ↓
Incremento funcional PI8
  ↓
Evidencia reproducible
  ↓
Plan de validación
```

## Pipeline técnico v1.1

La arquitectura corregida distingue **dos caminos diferentes** para evitar interpretar los módulos como una única secuencia lineal.

### Camino experimental/offline

```text
Datasets/corpus
     ↓
M1 Ingesta y representación
     ├──────────────→ M2 Reconocimiento semántico / benchmark
     │
     └→ M3a Generación de mezclas controladas
              ↓
        M3b Política target/protected
              ↓
        M4 Máscara T-F + reconstrucción
              ↓
        M6 Evidencia y métricas
```

### Camino runtime / streaming en laptop

```text
Audio / bloques
     ↓
M5 Runtime/orquestador
     ├→ M1 representación
     ├→ M3b política
     ├→ M4 máscara + iSTFT
     └→ M6 métricas / trazabilidad
```

**M3a no participa en streaming.** **M2 no modifica automáticamente el target** en v1.1; puede operar como benchmark o monitor asíncrono. Esta separación sigue la corrección consolidada PI6 → PI7.

## M2 — benchmark semántico ejecutable

El repositorio ya contiene un pipeline funcional para **UrbanSound8K**:

- valida metadata, clases, folds y presencia de audio;
- congela folds 1–8 para train, 9 para validación y 10 para test;
- bloquea leakage de la misma ocurrencia etiquetada `(fsID,classID,occurrenceID)` entre particiones y conserva como diagnóstico los `fsID` oficiales reutilizados entre clases;
- extrae MFCC + log-Mel;
- entrena baselines SVM RBF y Random Forest;
- selecciona candidato solo con validación;
- evalúa test una vez;
- genera Macro-F1, Macro-Recall, Macro-Precision, Accuracy, matriz de confusión, predicciones y modelo serializado.

El CI verifica el pipeline con un fixture controlado y la distribución oficial completa ya fue ejecutada localmente. La baseline SVM RBF obtuvo Macro-F1=0.7257 en fold 10; RNF-03=0.85 no fue cumplido por esta baseline.

Ver: `docs/M2_URBANSOUND8K_PROTOCOL.md`.

## PI8 — incremento funcional

El incremento inicial permite:

- generar una mezcla controlada con stems conocidos;
- aplicar una máscara tiempo–frecuencia de línea base;
- reconstruir audio;
- medir atenuación del target y preservación de señal protegida;
- ejecutar benchmark local de latencia;
- generar JSON, CSV, manifiestos y checksums reproducibles.

La máscara de la demo PI8 es una **línea base controlada/oracle basada en stems**. No debe presentarse como el estimador CNN final; el entrenamiento del estimador condicionado corresponde al siguiente incremento.

## Ejecución

```bash
cd 04_build/selective_audio_lab
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1

pip install -r requirements.txt
# Para reproduccción exacta del entorno CI validado:
# pip install -r requirements-lock.txt
python src/run_demo.py --out outputs/demo_run
python src/latency_benchmark.py --out outputs/latency
```

## Reproducibilidad

El entorno verificado en CI usa **Python 3.11.17**. `requirements.txt` fija las dependencias directas validadas y `requirements-lock.txt` conserva el conjunto completo observado en la ejecución exitosa del workflow.

## Alcance Edge

- **Laptop Acer Nitro 5:** entorno objetivo para entrenamiento, benchmark, mezclas, atenuación controlada y, en la fase final, streaming E2E. **En PI8+ el streaming por bloques todavía está pendiente.**
- **Honor X8c:** perfilado TFLite con tensores exportados.
- No se promete todavía streaming completo de audio en Android.
- El perfil físico del Honor X8c debe ejecutarse en el dispositivo; ningún valor Android se considera medido hasta esa ejecución.

## Ética

La validación base usa datasets públicos/licenciados y mezclas sintéticas. No se requiere audio primario de personas con TEA. Cualquier captura humana posterior exige consentimiento informado y la autorización que corresponda.

## Entrega Semana 8

La estructura de la exposición sigue las 12 diapositivas definidas por el asesor y demuestra la cadena S5–S8. Los documentos de `docs/`, `06_presentation/` y `07_submission/` constituyen la fuente de verdad académica para el parcial.

---
**HESYCHIA / T10 — 2026-II**


## Demo web reproducible con Docker

La demo PI8+ dispone de una consola web conectada al pipeline real y empaquetada con Docker. La UI no contiene métricas hard-codeadas: los resultados de atenuación aparecen después de ejecutar un run; M2 muestra resultados solo después de ejecutar UrbanSound8K completo; streaming/TFLite permanecen bloqueados mientras estén pendientes.

```powershell
docker compose up --build
```

Abrir `http://localhost:8080`.

Para montar UrbanSound8K use una variable de entorno con una ruta local absoluta o relativa:

```bash
export URBANSOUND8K_HOST_PATH="/ruta/al/UrbanSound8K"
export HESYCHIA_DEVICE_LABEL="laptop_objetivo"
docker compose up --build
```

En PowerShell el equivalente es `$env:URBANSOUND8K_HOST_PATH="C:\ruta\UrbanSound8K"`. En WSL use una ruta Linux, por ejemplo `/mnt/c/.../UrbanSound8K`.

La distribución no se incluye en Git. Debe descargarse desde la fuente oficial de UrbanSound8K y conservar sus folds predefinidos.

Guía completa: `docs/DEMO_DOCKER.md`.


### Resultado real M2 — 2026-10-12

UrbanSound8K oficial completo fue validado y ejecutado con el protocolo 1–8/9/10. La baseline clásica seleccionó SVM RBF en fold 9 y obtuvo en fold 10 Macro-F1 **0.7257**, Macro-Recall **0.7170**, Macro-Precision **0.7426** y Accuracy **0.7145**. RNF-03 (`Macro-F1 >= 0.85`) **no fue cumplido por esta baseline**. El umbral se mantiene. Ver `docs/M2_REAL_RESULT_2026-10-12.md`.

La Acer Nitro 5 fue medida en **2 lotes / 80 muestras**. La campaña agregada obtuvo pooled p50 **20.024 ms**, pooled p95 **34.607 ms** y media **22.688 ms**; el p95 por lote varió entre **26.205 y 41.508 ms**. Scope `whole_clip_processing_only`: no equivale a p95/hop ni E2E final. Ver `docs/LATENCY_CAMPAIGN_ACER_NITRO5_2026-10-12.md`.

## Evidencia adicional solicitada por revisión parcial

Se incorporaron dos protocolos reproducibles para cerrar observaciones metodológicas:

### M2 — benchmark secundario oficial de 10 folds

```bash
python src/semantic_benchmark_10fold.py \
  --dataset-root /ruta/al/UrbanSound8K \
  --out outputs/m2_10fold \
  --cache-dir outputs/m2_urbansound8k/feature_cache_v2_sr16000_soxr_hq \
  --seed 42
```

Reporta Macro-F1, Macro-Recall, Macro-Precision y Accuracy por fold, además de media, desviación estándar e IC95. Este benchmark es **secundario y de comparabilidad**; no sustituye retrospectivamente el resultado RNF-03 ya congelado con 1–8/9/10.

### M4 — lote real de mezclas para techo oracle

Requiere UrbanSound8K y un corpus de voz real, recomendado LibriSpeech:

```bash
python src/real_mixture_oracle_batch.py \
  --dataset-root /ruta/al/UrbanSound8K \
  --speech-root /ruta/a/LibriSpeech \
  --out outputs/m4_real_mixture_oracle_batch \
  --n 100 \
  --target-snrs=-5,0,5,10 \
  --caps=12,18,24,30 \
  --seed 42
```

Este experimento usa sirenas reales, voz real y fondos reales, y produce media, desviación estándar e IC95. Continúa siendo un **techo oracle basado en stems**, no desempeño del M4 aprendido.


## Continuación posterior a la exposición del 20 de octubre de 2026

Se registra la retroalimentación y se mantiene intacto el test M2 0.7257 y el benchmark whole-clip de Acer 34.607 ms. El lote acústico Oracle dispone ahora de una auditoría por mezcla (solo si existe el CSV real; no se generan números ficticios). **M4 aprendido, streaming, E2E, TFLite y pruebas físicas Honor siguen abiertos.**

- [Acta de retroalimentación](docs/RETROALIMENTACION_EXPOSICION_2026-10-20.md)
- [Protocolo experimental S9–S13](docs/PROTOCOLO_POST_PARCIAL_S9_S13.md)
- [Auditoría acústica por mezcla](docs/M4_METRICS_AUDIT.md)
- [Contrato de latencia](docs/LATENCY_BUDGET_S9.md)
- [Registro de procedencia de evidencia](docs/EVIDENCE_PROVENANCE_REGISTER.md)

Ejemplo, desde `04_build/selective_audio_lab` y **solo con los artefactos reales disponibles**:

```bash
python src/m4_oracle_audit.py --input outputs/m4_real_mixture_oracle_batch/real_mixture_runs.csv --out outputs/m4_oracle_audit
```
