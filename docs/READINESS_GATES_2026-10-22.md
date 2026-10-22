# M4 gates después de implementación causal — 2026-10-22

**No modificar objetivos ni arquitectura de la tesis.** Los artefactos nuevos se limitan a entrenamiento supervisado de M4 y pruebas de integridad existentes.

| Gate | Estado | Motivo |
|---|---|---|
| D0 Fuentes aisladas/licencia | BLOCKED | No existen en el entorno audios reales de sirena y voz separados, inspeccionados y con derechos certificados. ECHO provee etiquetas y rutas de audios ambientales, **no stems puros**; no usar como ground truth automáticamente. |
| D1 Integridad de fuentes | PARTIAL | Importador y gate funcionan con registro CSV y SHA, muestras independientes por fuente/locutor; falta manifiesto real. |
| D2 STFT+CNN causal | PARTIAL | Implementación causal/OLA y paridad modelo batch-vs-stream con fixtures PASS; falta perfil p95 real por hop, estabilidad 10 min, I/O y E2E. |
| D3 Pérdida | PROPOSAL | Variante con estabilización del denominador cuando target ausente. No es la pérdida L0 literal, exige ADR y consenso antes del protocolo científico final. |
| D4 Test sellado | PARTIAL | El código de entrenamiento no genera mezclas de test ni selecciona con ellas; falta población externa independiente verdaderamente blindada. |
| D5 TFLite/hardware | BLOCKED | Modelo nuevo entrenado PyTorch, falta exportación/validación de paridad TFLite y medición Acer/Honor. |

Resultado local de smoke: 12 tests PASS + CNN entrenada por 6 épocas **exclusivamente en 9 archivos WAV artificiales**, 3 roles x 3 splits (el entrenador consume audio train+val). Esto no es prueba real ni resultado de RNF científicos.

**Próximo GO verificable:** generar un manifiesto de referencias aisladas de sirenas y voz con SHA reales y derechos claros; validación de licencias por archivo y aislamiento mediante escucha/auditoría; aceptar ADR prospectiva; entrenar M4 de cero en frontend causal; congelar pesos y evaluar una vez en test externo. El archivo m4_sources_template.csv está intencionalmente vacío salvo cabecera, no hay audio fingido.
