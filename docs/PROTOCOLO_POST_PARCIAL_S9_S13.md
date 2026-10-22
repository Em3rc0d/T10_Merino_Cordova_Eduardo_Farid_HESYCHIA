# Plan de cierre experimental después del parcial — HESYCHIA

**Estado:** plan prospectivo para revisión con asesor; conserva el título registrado y no altera resultados congelados.  
**Fecha:** 22 de octubre de 2026.

## Pregunta operacional

¿Hasta qué punto un estimador M4 aprendido puede atenuar una fuente acústica objetivo en mezclas controladas, preservando habla y cumpliendo presupuestos medibles de tiempo y recursos en hardware local?

La aplicación a baja tolerancia sonora/hiperacusia motiva el problema, **pero no es una validación clínica**. M2 (clasificación) y M4 (separación/atenuación) son tareas distintas; la ejecución M2 no constituye evidencia del desempeño M4.

## Gate G0 — contratos e integridad de datos (bloqueante)

1. Congelar clases de target y protegidas, versiones de corpus, licencias y hashes originales. Empezar con **siren** como experimento acotado; no afirmar generalidad multiclase con ese experimento.
2. UrbanSound8K: mantener folds oficiales. M2 baseline fija: train 1–8, validación 9, test 10. El fold 10 **ya fue observado** y no puede volver a gobernar elecciones.
3. Para M4, las fuentes de audio de train/val/test deben estar **disjuntas por origen**. Controlar al menos: (a) ocurrencia etiquetada de UrbanSound8K, (b) speaker ID de LibriSpeech, (c) fragmentos y reusos de la misma grabación. No reutilizar el mismo clip original con distinto SNR o semilla entre splits.
4. Si no es posible construir corpus M4 con train/val/test disjuntos, el resultado es **BLOCKED**; no simularlo con archivos del mismo origen.
5. Registrar semilla, normalización, configuración STFT, versionado de resampler y composición de mezcla. Mezclas con stems privilegiados se usan solo como ground truth de entrenamiento/evaluación, **no como entrada del modelo desplegable**.

## Gate G1 — reconocimiento semántico M2

- Conservar SVM 0.7257 como baseline congelada y RNF-03 Macro-F1 ≥0.85.
- Especificar CNN candidata y máximo presupuesto de exploración de hiperparámetros **antes** de evaluar nuevos tests.
- Elegir arquitectura, early stopping y thresholds con train/validation; test no participa de ninguna decisión.
- Documentar explícitamente que fold 10 se observó con una baseline anterior: una reevaluación del mismo fold no constituye un nuevo test ciego.
- Si el asesor exige prueba verdaderamente independiente tras haber visto fold 10, definir corpus/fuentes externas nuevas y dejar su partición sellada antes de ejecutar.

## Gate G2 — M4 profundo y comparación oracle

- Implementar la red causal y su condicionamiento por clase descritos en TARGET_SELECTION_AND_DEEP_M4.md. No llamar «M4 aprendido» a una IRM de stems.
- Artefactos mínimos: código de entrenamiento, requisitos y semilla, split manifest, pesos/modelo, métricas de val/test, checkpoints y SHA-256.
- Regla de selección: mínimo de loss preespecificada en validación; test evaluado únicamente tras congelar pesos e hiperparámetros.
- Evaluar **la misma mezcla** con M4 aprendido y con oracle para obtener distancia interpretable a una referencia con información privilegiada; Oracle no garantiza un techo matemático universal de cada métrica.
- Evitar seleccionar el cap o regla de ganancia mirando resultados test. Analizar 12/18/24/30 dB como sensibilidad preespecificada; cap primario 12 dB conservado hasta decisión prospectiva del asesor.

## Gate G3 — selectividad por mezcla, no solo media

Criterios vigentes: A_target ≥6 dB y A_protected ≤1 dB en experimento ALLOW. Reportar para cada mezcla los dos valores, sus banderas individuales y el cumplimiento conjunto. Reportar la distribución y los casos fallidos; **una media favorable no implica 100 % de cumplimiento**.

Medir además SI-SDRi(protected), SI-SDRi(target), artefactos y fuga de interferencia. SI-SDRi(target) se interpreta con el objetivo de atenuación, no como si el propósito fuera realzar la fuente perturbadora.

El script m4_oracle_audit.py audita lotes Oracle existentes, pero **NO certifica M4 aprendido**. El pipeline aprendido necesitará producir CSV y expediente propios.

## Gate G4 — seguridad de política

En uso experimental offline es posible simular atenuación de sirenas. Para un uso real, alertas críticas no deben tratarse automáticamente como ruido reducible; se requiere política conservadora de preservación, límites, incertidumbre, fallo seguro y evaluación específica. No prometer seguridad situacional antes de validarla.

## Gate G5 — latencia laptop y perfil Android

- Laptop: procesamiento real por hop con distribución p50/p95, buffers, warmup y duración de sesión; E2E captura→reproducción medido por método físico/loopback justificado. Distinguir latencia algorítmica, tiempo CPU por bloque y E2E.
- Contrato: p95 del procesamiento por hop ≤10 ms y E2E p95 ≤60 ms **como metas separadas**; reportar no cumplimiento de cada una.
- No comparar los 34.607 ms de un clip completo de 4 s con 10 ms por hop.
- Android: exportación TFLite, paridad numérica, tamaño del modelo, RAM e inferencia p95 ≤20 ms. Probar físicamente en Honor X8c; no presentar números de laptop como móviles.
- Estabilidad: sesión ≥10 min y conteo explícito de underruns, drops y fallos.

## Gate G6 — expediente y defensa

Por run: commit SHA, ID, config, split manifest, dataset checksum, pesos del modelo, métricas, logs, archivos y hashes. Incorporar O06/O07/O09 **solo** cuando sus outputs verificables estén disponibles. Cerrar estado del arte con ecuación de búsqueda, bases, inclusión/exclusión, tabla y fuentes primarias. Declarar asistencia de IA de forma fiel a la normativa aplicable.

## Criterio GO para defensa experimental

GO solo si hay M4 entrenado verificable, medición honesta de desempeño con datos separados, trazabilidad por run y resultados negativos conservados. Alcanzar todos los umbrales es una hipótesis a evaluar, **no un requisito para fabricar un resultado ni para reescribir la evidencia**. La suficiencia académica final corresponde al asesor y al jurado.

## Estado de ejecución al redactar

G0 parcial; G1 baseline congelada; G2 pendiente; G3 auditor implementado sin lote nuevo; G4 política laboratory-only; G5 solo whole clip; G6 documentación y CI previos, evidencia O06/O07/O09 pendiente. No declarar BUILD_READY final.
