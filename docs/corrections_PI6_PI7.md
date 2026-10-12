# Registro de levantamiento — PI6 + PI7 → versión ejecutable para PI8

| Observación del asesor | Acción integrada | Evidencia |
|---|---|---|
| Título “cancelación” vs artefacto de atenuación | Se conserva título institucional y se define operacionalmente “cancelación” como atenuación T-F, no ANC físico | README, informe, presentación |
| RNF no medibles | Se fijan tolerancias de reproducibilidad, métricas acústicas, latencia y recursos | informe §2 |
| RF huérfanos | RF-10 entrenamiento de máscara; RF-11 exportación/paridad TFLite | informe §2 |
| M3 mezclaba dos responsabilidades | M3a mezclas offline / M3b política runtime | arquitectura |
| M5 aparecía como etapa final | M5 pasa a orquestador/runtime del camino crítico | arquitectura |
| Rol de M2 ambiguo | Target se fija por configuración; M2 no cambia M4 automáticamente | design_decisions |
| Android sin stack/alcance real | Android se limita a perfilado TFLite; streaming E2E en laptop | README / arquitectura |
| Latencia <20 ms ambigua | Se separan p95 por hop, E2E y Android; el PI8 local se reporta aparte | informe / reviewer guide |
| Relación N:M sin resolver | RUN_ASSET | schema_v11.sql |
| Política no persistida | POLICY_DECISION | schema_v11.sql |
| Particiones aleatorias / fuga | UrbanSound8K usa folds oficiales; LibriSpeech conserva splits públicos | diseño |
| A5 subespecificado | A5-train/A5-infer: IRM, embedding, arquitectura causal, pérdida y gain | informe |
| Métricas acústicas vagas | A_target, A_protected, SI-SDRi | demo_metrics.csv / informe |
| API síncrona para jobs largos | Diseño 202 Accepted + jobId + GET /jobs/{id} | diseño |
| UI podía aparentar resultados | HTML corregido elimina métricas prellenadas no ejecutadas | PI7_T10_Prototipo_UI.html |
| Falta de evidencia construida | Incremento funcional reproducible + tests + CSV/JSON/checksums | 04_build / 05_evidence |

## Gate de construcción

El PI8 no reabre arquitectura. El incremento demuestra el contrato del pipeline con baseline controlada. El siguiente gate exige:

1. entrenar el estimador de máscara con datos reales y particiones congeladas;
2. sustituir la IRM oracle por el modelo aprendido;
3. comparar contra baseline DSP;
4. exportar TFLite y ejecutar paridad;
5. perfilar físicamente el Honor X8c;
6. ejecutar validación definitiva sin cambios post hoc.
