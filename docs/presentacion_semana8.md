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

Stack PI8+ implementado: Python 3.11, NumPy/SciPy/librosa, scikit-learn, SQLite, HTML/CSS/JavaScript, servidor HTTP Python, Docker/Docker Compose y Git. TensorFlow/Keras y Kotlin/TFLite se muestran como previstos para las fases siguientes.

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
Grupo B: UI funcional + contratos API.

UI PI8+: consola web responsive servida por el mismo contenedor Docker. Lee métricas y artefactos desde runs reales; no contiene valores científicos hard-codeados.

Rutas actualmente funcionales:
- POST /api/jobs/attenuate → 202 {jobId}
- POST /api/dataset/validate → 202 {jobId}
- POST /api/jobs/benchmark → 202 {jobId}
- GET /api/jobs/{id} → status/resultRef
- GET /api/runs y /api/runs/{id} → evidencia
- GET /api/runs/{id}/integrity → coherencia JSON/SQLite/manifiesto/SHA-256

Contratos aún pendientes:
- /api/jobs/train-mask
- /api/jobs/export-tflite
- /api/streaming/session

Estos responden 501 hasta tener implementación probada. Android seguirá usando TFLite local cuando esa fase exista.

## 8. S8 — Construcción
Mostrar una **tabla categórica de estado**, no porcentajes estimados.

| Módulo | Estado verificable |
|---|---|
| M1 | PARCIAL |
| M2 | SOFTWARE LISTO / EVIDENCIA REAL PENDIENTE |
| M3a | BASELINE |
| M3b | IMPLEMENTADO |
| M4 | BASELINE |
| M5 | PARCIAL |
| M6 | IMPLEMENTADO |

Funciona: consola web Docker, baseline PI8+, M3b, M6, M2 software/fixture y CI.  
Falta: M2 real, M4 aprendido, streaming, TFLite y Honor X8c.

Repositorio mediante QR/enlace.

## 9. S8 — Demostración
Flujo reproducido: stems → mezcla → STFT → IRM oracle → gain → iSTFT → métricas → SQLite.

Run ALLOW de referencia:
- A_target ≈ 11.99 dB
- A_protected ≈ 0.007 dB
- SI-SDRi(protected) ≈ 11.52 dB

Caso BLOCK disponible en la UI: al marcar el target como protegido, M3b fuerza g=1 y la atenuación objetivo se trata como no aplicable por diseño.

CI final del incremento PI8+: **22 tests OK** (workflow 38209597684); checksums, SQLite, integridad cruzada, Docker Compose, build y health check validados.  
Latencia de CI del clip completo es evidencia de reproducibilidad, no del dispositivo objetivo. **Acer Nitro 5: valor pendiente de ejecución local antes del parcial** mediante Edge readiness → Medir procesamiento local. Ese dato se rotula `whole_clip_processing_only` y no equivale a p95/hop, E2E ni Android.

## 10. Matriz de trazabilidad
OE → Requisito → Componente → Diseño → Evidencia construida.

La matriz diferencia explícitamente evidencia ya construida de contratos todavía pendientes, por ejemplo TFLite.

## 11. Plan de validación
Semántica: UrbanSound8K + Macro-F1 ≥ 0.85.  
Acústica: A_target ≥ 6 dB, A_protected ≤ 1 dB, SI-SDRi > 0.  
Compute: laptop p95/hop ≤ 10 ms, E2E p95 ≤ 60 ms, TFLite p95 ≤ 20 ms.

Calidad Grupo B: pruebas funcionales + ISO/IEC 25010. SUS/TAM se deja como aplicabilidad por confirmar con el asesor; no se declara validación de usuarios inexistente.

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
