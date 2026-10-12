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
| Evidencia reproducible | COMPLIANT | Run ID, JSON, CSV, checksums, tests y CI |
| Dependencias congeladas | COMPLIANT | requirements-lock + CI usando lockfile |
| RF-01/02 DSP | PARTIAL / ON PLAN | demo sintética implementa 16 kHz/STFT; integración completa con datasets reales pendiente |
| RF-03 / M2 benchmark real | PENDING / ON PLAN | S9 |
| RF-04/05 política + mezclas | COMPLIANT-BASELINE | demo controlada |
| RF-06 M4 máscara aprendida | PENDING / ON PLAN | PI8 usa IRM oracle explícitamente; estimador aprendido S9 |
| RF-07 reconstrucción | COMPLIANT-BASELINE | iSTFT funcional |
| RF-08 runtime/streaming | PARTIAL / ON PLAN | procesamiento local medido; streaming por bloques aún pendiente |
| RF-09 expediente | COMPLIANT | evidencia versionada |
| RF-10 entrenamiento M4 | PENDING / ON PLAN | S9 |
| RF-11 TFLite/paridad | PENDING / ON PLAN | S9–S10 |
| RNF-03 Macro-F1 ≥0.85 | UNMEASURED / ON PLAN | no se inventa resultado antes del benchmark real |
| RNF-04 selectividad acústica | COMPLIANT-BASELINE | baseline supera criterios en run sintético; no se extrapola al modelo final |
| RNF-05 latencia final | PARTIAL / ON PLAN | CI/local mide procesamiento de clip; no se confunde con p95/hop, E2E o Android |
| RNF-06 recursos Android | UNMEASURED / ON PLAN | Honor X8c no perfilado aún |
| RNF-07 estabilidad 10 min | PENDING / ON PLAN | aún no ejecutada |
| RNF-08 ética | COMPLIANT | datasets públicos/licenciados + síntesis; sin audio TEA primario |
| RNF-09 change traceability | COMPLIANT | SOURCE_OF_TRUTH + git history |
| RNF-10 paridad TFLite | PENDING / ON PLAN | aún no exportado |

## Resultado de auditoría

**No se detecta una desviación contractual activa en el estado PI8.**  
Los elementos faltantes están declarados como pendientes y corresponden a fases posteriores. La baseline IRM no se presenta como CNN final; las métricas locales no se presentan como Android ni como validación definitiva.

## Gates que NO pueden omitirse

1. Benchmark semántico real.
2. M4 aprendido.
3. Integración con datasets reales y particiones congeladas.
4. Streaming por bloques en laptop.
5. Exportación/paridad TFLite.
6. Perfil físico Honor X8c.
7. Estabilidad ≥10 min.
8. Validación final sin cambios post hoc.
