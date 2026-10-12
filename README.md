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
- verifica ausencia de fuga por `fsID`;
- extrae MFCC + log-Mel;
- entrena baselines SVM RBF y Random Forest;
- selecciona candidato solo con validación;
- evalúa test una vez;
- genera Macro-F1, Macro-Recall, Macro-Precision, Accuracy, matriz de confusión, predicciones y modelo serializado.

El CI verifica el pipeline con un fixture controlado. **La evidencia científica real de M2 sigue pendiente de ejecutar la distribución completa oficial de UrbanSound8K**; no se sustituye por el fixture.

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

Para UrbanSound8K en Windows:

```powershell
$env:URBANSOUND8K_HOST_PATH="C:\Users\eduar\Desktop\Farid\UrbanSound8K"
docker compose up --build
```

Guía completa: `docs/DEMO_DOCKER.md`.
