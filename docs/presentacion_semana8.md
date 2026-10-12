# Presentación — Examen Parcial Semana 8 — estructura oficial de 12 diapositivas

Esta versión reemplaza la organización anterior para la exposición. Sigue literalmente el esqueleto común exigido y adapta la evidencia a **Grupo B — aporte práctico**.

## 1. Carátula
Título institucional exacto: **Diseño de un sistema inteligente de cancelación selectiva de ruido mediante aprendizaje profundo para la atenuación de estímulos acústicos asociados a la hiperacusia en personas con TEA**.

Tesista: Eduardo Farid Merino Córdova · T10 · Grupo B.  
Asesor: Daniel Alfonso Quinto Pazce.

## 2. Problema y objetivos
Problema: ausencia de una solución computacional selectiva que atenúe eventos acústicos molestos sin suprimir señales relevantes.

Dato de continuidad desde Tesis I: la revisión consignó hiperacusia en 50–70 % de personas con TEA.

Objetivo general: diseñar, implementar y evaluar computacionalmente el sistema.

- OE1: representar/caracterizar audio con STFT, log-Mel y MFCC.
- OE2: reconocer eventos y aplicar atenuación selectiva mediante máscara T-F condicionada.
- OE3: evaluar desempeño semántico, acústico y viabilidad Edge.

## 3. S5 — Requisitos
Tabla compacta con RF/RNF, prioridad MoSCoW y vínculo a OE.

Must destacados:
- RF-02 representación;
- RF-03 benchmark semántico;
- RF-04 target/protected/cap_dB;
- RF-06/07 máscara + reconstrucción;
- RF-08 runtime;
- RF-09 evidencia;
- RNF: Macro-F1 ≥ 0.85; A_target ≥ 6 dB; A_protected ≤ 1 dB; latencias preespecificadas.

## 4. S6 — Arquitectura
Diagrama equivalente a C4 nivel 2 con dos caminos:

OFFLINE: M1 → M2 / M3a → M3b → M4 → M6.  
RUNTIME laptop: M5 orquesta M1 → M3b → M4 → M6.

Stack objetivo: Python 3.11, NumPy/SciPy/librosa, scikit-learn, TensorFlow/Keras, SQLite, FastAPI/Streamlit, Kotlin/TFLite y Git. Los elementos aún no implementados se rotulan como previstos.

## 5. S6 — Decisiones arquitectónicas
1. Edge-first vs cloud obligatorio: latencia, privacidad, reproducibilidad, offline.
2. M2 separado de M4: clasificación y separación no son el mismo problema.
3. Política explícita target/protected vs decisión automática de M2: seguridad y trazabilidad.
4. M3a offline; M3b sí participa en runtime.

## 6. S7 — Diseño detallado 1
Grupo B: modelo de datos + secuencia.

Entidades clave: EXPERIMENT, RUN, MODEL_VERSION, AUDIO_ASSET, RUN_ASSET, POLICY_DECISION, METRIC, ARTIFACT.

Secuencia crítica: config → M5 → M1 → M3b → M4 → M6.  
Regla: si target ∈ protected_set → BLOCK → g=1.

## 7. S7 — Diseño detallado 2
Grupo B: prototipo UI + contratos API.

UI: configuración de target/protected/run, sin métricas ficticias.

API:
- POST /jobs/benchmark → 202 {jobId}
- POST /jobs/train-mask → 202 {jobId}
- POST /jobs/attenuate → 202 {jobId}
- POST /jobs/export-tflite → 202 {jobId}
- GET /jobs/{id} → status/progress/resultRef
- POST /streaming/session → 201 {sessionId}

Android no depende de API: TFLite local + profile.json importado por M6.

## 8. S8 — Construcción
Mostrar qué funciona, qué falta y porcentaje de avance por módulo. Los porcentajes son **avance de construcción por checklist**, no resultados científicos.

Estado aproximado documentado:
- M1 50 %
- M2 70 %
- M3a 60 %
- M3b 100 %
- M4 45 %
- M5 30 %
- M6 85 %

Funciona: baseline PI8+ E2E, M3b, M6, M2 software/fixture y CI.  
Falta: M2 real, M4 aprendido, streaming, TFLite y Honor X8c.

Repositorio mediante QR/enlace.

## 9. S8 — Demostración
Flujo reproducido: stems → mezcla → STFT → IRM oracle → gain → iSTFT → métricas → SQLite.

Run de referencia:
- A_target ≈ 11.99 dB
- A_protected ≈ 0.007 dB
- SI-SDRi(protected) ≈ 11.52 dB

CI: 6 tests contractuales OK; checksums y SQLite validados.  
Latencia CI del clip completo 4 s: p50≈12.52 ms, p95≈13.23 ms. No equivale a p95/hop, E2E ni Android.

## 10. Matriz de trazabilidad
OE → Requisito → Componente → Diseño → Evidencia construida.

La matriz diferencia explícitamente evidencia ya construida de contratos todavía pendientes, por ejemplo TFLite.

## 11. Plan de validación
Semántica: UrbanSound8K + Macro-F1 ≥ 0.85.  
Acústica: A_target ≥ 6 dB, A_protected ≤ 1 dB, SI-SDRi > 0.  
Compute: laptop p95/hop ≤ 10 ms, E2E p95 ≤ 60 ms, TFLite p95 ≤ 20 ms.

Cronograma:
- S9: UrbanSound8K real + congelar RNF-03.
- S10: M4 aprendido + mezclas reales.
- S11: métricas acústicas + TFLite/paridad.
- S12: streaming laptop + p95/E2E.
- S13: Honor X8c + RAM/tamaño.
- S14: estabilidad 10 min + integración.
- S15: validación final + cierre.

## 12. Riesgos y próximos pasos
Riesgos:
1. confundir baseline con final;
2. confundir alcances de latencia;
3. no alcanzar umbrales experimentales.

Mitigación: SOURCE_OF_TRUTH, mediciones separadas y criterios congelados.

Observaciones del asesor levantadas: M2 no gobierna M4; M3a/M3b separados; Android limitado a TFLite; jobs 202+jobId; RUN_ASSET/POLICY_DECISION; UI sin fake metrics; no claims clínicos.

Siguiente gate inmediato: validar UrbanSound8K completo y ejecutar benchmark real M2.
