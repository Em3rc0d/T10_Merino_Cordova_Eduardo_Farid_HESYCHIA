# Guion de exposición — Examen Parcial PI8 — T10 Grupo B

**Duración objetivo:** 12 minutos. La exposición sigue el orden oficial de 12 diapositivas y vuelve siempre a la cadena **Problema → OE → requisito → componente → diseño → construcción → validación**.

## 1. Carátula
Presentar el título institucional exacto, T10, Grupo B, tesista y asesor. Aclarar solo si preguntan que “cancelación” se operacionaliza como atenuación selectiva T-F y no como ANC físico.

## 2. Problema y objetivos — 1 min
Explicar que una supresión general puede afectar tanto eventos molestos como señales que deben preservarse. Mencionar el dato de Tesis I sobre hiperacusia y resumir OG/OE1–OE3. Indicar que PI7 v1.1 operacionalizó los objetivos para separar reconocimiento, separación y viabilidad Edge.

## 3. S5 Requisitos — 1.5 min
Resaltar RF-02, RF-03, RF-04, RF-06/07, RF-08, RF-09 y los RNF cuantificados. Indicar MoSCoW y vínculo a OE. Protected tiene precedencia sobre target.

## 4. S6 Arquitectura — 1.5 min
Explicar los caminos offline y runtime. M3a solo offline; M5 orquesta el runtime; M2 no gobierna automáticamente M4. Mencionar stack y que los componentes futuros están rotulados como previstos.

## 5. S6 Decisiones — 1 min
Explicar tres decisiones con alternativa descartada: Edge-first vs cloud obligatorio; M2 ≠ M4; política explícita vs target automático. Añadir separación M3a/M3b.

## 6. S7 Diseño detallado 1 — 1.5 min
Mostrar modelo de datos y secuencia. RUN_ASSET resuelve N:M; POLICY_DECISION persiste ALLOW/BLOCK. Secuencia: config → M5 → M1 → M3b → M4 → M6. Si target está protegido, g=1.

## 7. S7 Diseño detallado 2 — 1 min
Mostrar la consola web funcional empaquetada con Docker. No hay métricas científicas hard-codeadas: aparecen después de un run. Los jobs funcionales responden 202 + jobId y se consultan por estado; la evidencia puede verificarse contra JSON/SQLite/manifiesto/SHA-256. Las rutas de streaming/TFLite aún responden 501.

## 8. S8 Construcción — 1 min
No usar porcentajes estimados. Mostrar estados categóricos verificables: IMPLEMENTADO, BASELINE, PARCIAL y EVIDENCIA REAL PENDIENTE. Funciona la consola Docker, baseline PI8+, M3b, M6 y M2 real. UrbanSound8K completo ya fue ejecutado: SVM RBF fue seleccionado y obtuvo Macro-F1=0.7257 en test. RNF-03=0.85 no fue cumplido por esta baseline. Pendiente siguiente candidato, M4 aprendido, streaming, TFLite y Honor X8c. Mostrar QR del repo.

## 9. S8 Demostración — 2 min
Ejecutar o mostrar desde la UI: ALLOW → métricas/audio/figuras → Evidencias → Verificar integridad. Reportar A_target≈11.99 dB, A_protected≈0.007 dB y SI-SDRi≈11.52 dB solo para el run ALLOW de referencia. Si el tiempo permite, ejecutar BLOCK y mostrar target_is_protected / g=1; sus métricas de atenuación no se comparan contra el criterio ALLOW. Aclarar que en la Acer Nitro 5 se ejecutaron 2 lotes de 40 runs, 80 muestras en total: pooled p50=20.024 ms, pooled p95=34.607 ms y media=22.688 ms; el p95 por lote varió 26.205–41.508 ms. Se reporta la campaña completa, no el mejor lote. El alcance es `whole_clip_processing_only`, no p95/hop, E2E ni Android. La IRM es oracle baseline, no CNN final.

## 10. Trazabilidad — 0.5 min
Recorrer un ejemplo: OE2 → RF-04/06/07 → M3b/M4 → A4/A5/A6 → policy + mask + WAV. Indicar que TFLite aparece como pendiente, no como evidencia falsa.

## 11. Plan de validación — 1 min
Semántica: UrbanSound8K; baseline real Macro-F1=0.7257 frente a RNF-03=0.85, por lo que no cumple. Explicar que el umbral no se cambia y que el siguiente candidato ya estaba previsto en PI7. Acústica: A_target, A_protected, SI-SDRi. Compute: p95/hop, E2E, TFLite, RAM y tamaño. Como Grupo B, incluir pruebas funcionales e ISO/IEC 25010; SUS/TAM queda como aplicabilidad por confirmar con el asesor. Cronograma S9–S15 hasta cierre. Si un umbral no se alcanza, se reporta; no se mueve post hoc.

## 12. Riesgos y próximos pasos — 0.5 min
Riesgos: sobreclaim, latencia ambigua y no alcanzar umbrales. Mitigaciones: SOURCE_OF_TRUTH, mediciones separadas y criterios congelados. Observaciones ya levantadas: M2/M4 separados, M3a/M3b, Android acotado, API jobs, trazabilidad de datos, UI honesta y no claims clínicos. Siguiente gate: candidato aprendido preespecificado, sin tuning sobre fold 10, y luego streaming/RNF-05 final.

## Reglas de defensa
- Decir “incremento funcional reproducible”, no “sistema final terminado”.
- Sí afirmar el Macro-F1 real de la baseline: 0.7257. No afirmar que RNF-03 esté cumplido.
- No equiparar latencia de clip completo con p95/hop, E2E o Android.
- No afirmar eficacia clínica.
- Si preguntan por el título: continuidad administrativa; implementación técnica = atenuación selectiva T-F.
