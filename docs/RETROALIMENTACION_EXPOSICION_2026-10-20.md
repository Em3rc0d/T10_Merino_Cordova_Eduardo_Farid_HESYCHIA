# HESYCHIA — acta técnica de retroalimentación del parcial

**Exposición grabada:** 20 de octubre de 2026  
**Acta elaborada:** 22 de octubre de 2026  
**Origen:** transcripción automática suministrada por el tesista. **No es una transcripción certificada ni literal de la voz del docente.**  
**Alcance:** hallazgos de la presentación y preguntas, contrastados con el repositorio previo al acta. No sustituye una rúbrica oficial ni modifica el título.

## Dictamen y límites de la fuente

El docente manifestó que el planteamiento del problema, los objetivos reformulados y los criterios medibles estaban bien encaminados. Destacó explícitamente la honestidad al comunicar incumplimientos y la existencia de trazabilidad y pruebas. También cuestionó brechas de implementación, estado del arte y versionado. Algunos pasajes de sus preguntas están fuertemente degradados por reconocimiento de voz y se marcan como pendientes de confirmación.

## Observaciones convertidas en acciones verificables

| ID | Observación identificable | Evidencia anterior | Acción exigible | Estado a 2026-10-22 |
|---|---|---|---|---|
| OBS-01 | Aprendizaje profundo en el título sin red M4 entrenada | Máscara IRM oracle con stems; contrato de arquitectura M4 | Entrenar M4 real, guardar pesos, protocolo y predicciones; medir distancia a oracle | ABIERTO |
| OBS-02 | ¿Cómo seleccionar siguiente candidato sin volver a optimizar usando fold 10? | M2 SVM validado en fold 9; test fold 10 ya observado: 0.7257 | Seleccionar por desarrollo 1–8/9; congelar candidato antes de nueva prueba; informar explícitamente que fold 10 ya fue observado | ABIERTO |
| OBS-03 | Voz supera el límite de pérdida en un subconjunto del lote | Se escucha referencia a «47 de 100»; requiere cotejo con CSV crudo | Auditar por mezcla y por cap, no solo promedios; conservar casos fallidos | HERRAMIENTA AÑADIDA; DATOS PENDIENTES |
| OBS-04 | Latencia de clip 34.607 ms distinta de p95/hop y E2E | 80 mediciones Acer con scope whole_clip_processing_only | Presupuesto temporal por etapa + benchmark streaming real en laptop | ABIERTO |
| OBS-05 | Ventana STFT 512 a 16 kHz = 32 ms | N_FFT=512, HOP=160, SR=16000 | Formalizar ventana, hop, look-ahead efectivo, buffers y E2E; evitar equipararlos | DOCUMENTADO; MEDICIÓN PENDIENTE |
| OBS-06 | Atenuar sirenas implica conflicto de seguridad | M3b permite ALLOW a siren en escenario de laboratorio | Declarar simulación offline; política real conservadora para alertas críticas por diseñar/validar | ABIERTO |
| OBS-07 | Resultados O06/O07/O09 no versionados | No constan artefactos identificados por esos IDs en la revisión del árbol main | Localizar salidas reales, checksum, commit y manifiesto; nunca reconstruir cifras | ABIERTO |
| OBS-08 | Estado del arte breve / método de búsqueda insuficiente | Documentación histórica PI7/PI8 | Protocolo de búsqueda replicable, matriz de evidencia, estudios primarios vigentes | ABIERTO |
| OBS-09 | Evidenciar uso de IA en elaboración | Declaración oral del tesista | Declaración transparente de herramientas, tareas y verificación humana según norma institucional | ABIERTO |
| OBS-10 | Alineación OE1 / rol M2, M4 | Propuesta en docs/PROPUESTA_ALINEACION_OBJETIVOS_PI8.md | Solicitar validación del asesor; no modificar objetivos oficiales unilateralmente | PENDIENTE ASESOR |
| OBS-11 | Demo breve funcional | Demostración Docker PI8 | Video de 3–5 min desde ejecución reproducible, con límites explicitados | PENDIENTE EVIDENCIA |

## Resultados y corrección de atribución

- **M2 reconocimiento, prueba oficial congelada:** Macro-F1 = **0.7257** del SVM RBF en fold 10. El umbral RNF-03 es 0.85 y **no se cumple**. El valor 0.6623 referido en la presentación y el 0.72 aproximado **no deben fusionarse** con este resultado: revisar identificadores de ensayo.
- **M4:** se mencionaron alrededor de 10.9 dB de atenuación objetivo y 1.12 dB de degradación de voz. Estos valores se presentan aquí **como cifras orales reportadas, NO verificadas en los artefactos del repositorio**. La referencia a 47/100 incumplimientos también es **provisional**.
- **Acer Nitro 5:** p95 pooled **34.607 ms** en 80 muestras, scope **whole_clip_processing_only**; no equivale a p95/hop, E2E, inferencia CNN ni prueba Android. Evidencia documental previa: LATENCY_CAMPAIGN_ACER_NITRO5_2026-10-12.md.
- **M4 aprendido, streaming, TFLite y Honor X8c:** no demostrado en esta revisión.

## Decisiones éticas y metodológicas

1. Un resultado no conforme permanece no conforme. Una revisión **prospectiva y justificada** de criterios puede ser legítima, pero nunca debe aprobar retrospectivamente el mismo experimento.
2. El experimento de sirena en laboratorio no equivale a política de seguridad para uso en una vía pública.
3. Un clasificador M2 no separa por sí solo las fuentes de una mezcla; M4 requiere estimación de máscara aprendida.
4. No inventar promedios, conteos, firmas, clips, registros ni testimonios para satisfacer una observación.

## Próximos documentos contractuales

- PROTOCOLO_POST_PARCIAL_S9_S13.md
- LATENCY_BUDGET_S9.md
- M4_METRICS_AUDIT.md
- EVIDENCE_PROVENANCE_REGISTER.md
