# CONTRACT COMPLIANCE — HESYCHIA T10

Fecha de auditoría: 2026-10-12  
Referencia: `SOURCE_OF_TRUTH.md`

## Regla de interpretación

**Cumplimiento del contrato** no significa **tesis terminada**.  
En Semana 8, un elemento puede estar correctamente **PENDING** si el cronograma lo ubica en S9–S13. Una violación sería afirmar que está implementado/validado cuando no lo está, reintroducir una formulación descartada o cambiar un criterio después de observar el test.

## Auditoría actual

| Cláusula contractual | Estado | Evidencia / límite |
|---|---|---|
| No ANC físico; atenuación T-F | COMPLIANT | PI8 usa STFT → gain/mask → iSTFT |
| M2 ≠ M4 | COMPLIANT | diseño y trazabilidad los separan |
| Target fijo por configuración v1.1 | COMPLIANT | M2 no gobierna automáticamente M4 |
| M3a offline / M3b runtime | COMPLIANT | README y arquitectura distinguen ambos caminos |
| M5 orquestador | COMPLIANT | runtime documentado como orquestador |
| Edge-first sin nube obligatoria | COMPLIANT | build local y CI sin API de inferencia externa |
| No afirmaciones clínicas | COMPLIANT | manifest y documentación lo excluyen |
| Evidencia reproducible | COMPLIANT | Run ID, JSON, CSV, SQLite, hashes reales de inputs, manifiesto, validator de integridad cruzada, tests y CI |
| Demo reproducible Docker | COMPLIANT-S8 | imagen construida en CI, health smoke test OK, UI sin métricas científicas hard-codeadas |
| Dependencias congeladas | COMPLIANT | requirements-lock + CI usando lockfile |
| RF-01/02 DSP | PARTIAL / ON PLAN | demo sintética implementa 16 kHz/STFT; integración completa con datasets reales pendiente |
| RF-03 / M2 benchmark | IMPLEMENTED / REAL-EVIDENCE-MEASURED | UrbanSound8K oficial completo validado; SVM/RF ejecutados; SVM seleccionado en fold 9; test fold 10 medido; provenance manifest generado |
| RF-04 política | COMPLIANT | M3b ejecutable con ALLOW/BLOCK, precedencia protected y persistencia POLICY_DECISION |
| RF-05 mezclas | COMPLIANT-BASELINE | stems sintéticos controlados + manifiesto/checksums |
| RF-06 M4 máscara aprendida | PENDING / ON PLAN | PI8 usa IRM oracle explícitamente; estimador aprendido S9 |
| RF-07 reconstrucción | COMPLIANT-BASELINE | iSTFT funcional |
| RF-08 runtime/streaming | PARTIAL / ON PLAN | consola web Docker y procesamiento local operativos; streaming por bloques aún pendiente |
| RF-09 expediente | COMPLIANT | evidence.sqlite + Run ID + métricas + artefactos + SHA-256 + validación cruzada |
| RF-10 entrenamiento M4 | PENDING / ON PLAN | S9 |
| RF-11 TFLite/paridad | PENDING / ON PLAN | S9–S10 |
| RNF-03 Macro-F1 ≥0.85 | MEASURED / NOT MET BY BASELINE | SVM RBF test fold 10 Macro-F1=0.7257; el umbral 0.85 se conserva; siguiente candidato debe seleccionarse sin usar fold 10 para tuning |
| RNF-04 selectividad acústica | COMPLIANT-BASELINE | baseline supera criterios en run sintético; no se extrapola al modelo final |
| RNF-05 latencia final | PARTIAL / TARGET-DEVICE-S8-MEASURED | Acer Nitro 5 whole-clip: p50=19.976 ms, p95=26.205 ms, mean=20.725 ms; aún no equivale a p95/hop ni E2E |
| RNF-06 recursos Android | UNMEASURED / ON PLAN | Honor X8c no perfilado aún |
| RNF-07 estabilidad 10 min | PENDING / ON PLAN | aún no ejecutada |
| RNF-08 ética | COMPLIANT | datasets públicos/licenciados + síntesis; sin audio TEA primario |
| RNF-09 change traceability | COMPLIANT | SOURCE_OF_TRUTH + git history |
| RNF-10 paridad TFLite | PENDING / ON PLAN | aún no exportado |

## Resultado de auditoría

**No se detecta una desviación contractual activa en el estado PI8.**  
Los elementos faltantes están declarados como pendientes y corresponden a fases posteriores. La baseline IRM no se presenta como CNN final; las métricas locales no se presentan como Android ni como validación definitiva. Desde el incremento PI8+ la política M3b y el expediente M6 ya son ejecutables y están cubiertos por pruebas automáticas.

## Gates que NO pueden omitirse

1. Preservar la baseline M2 real y desarrollar el siguiente candidato sin tuning sobre fold 10.
2. M4 aprendido.
3. Integración con datasets reales y particiones congeladas.
4. Streaming por bloques en laptop.
5. Exportación/paridad TFLite.
6. Perfil físico Honor X8c.
7. Estabilidad ≥10 min.
8. Validación final sin cambios post hoc.
