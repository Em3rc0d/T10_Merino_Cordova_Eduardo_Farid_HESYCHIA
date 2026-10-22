# Registro de procedencia y pendientes de evidencia

**Corte:** 2026-10-22. La existencia de una descripción en PPT, acta o Markdown no equivale a tener el artefacto binario/CSV con hash.

| Identificador | Evidencia observable en main | Estado de verificación | Para cerrar |
|---|---|---|---|
| M2-US8K-BASELINE-001 | Documentado en M2_REAL_RESULT_2026-10-12.md; SHA modelo y metadata | Resultados documentados; outputs locales no incluidos en Git | Adjuntar/exportar paquete verificable, sin repetir selección con fold 10 |
| Acer latency campaign | LATENCY_CAMPAIGN_ACER_NITRO5_2026-10-12.md; ZIP local referenciado | Resumen documentado, ZIP fuera del árbol Git | Conservar ZIP/checksums y entorno |
| M4 Oracle real-mixture batch | Protocolo y código existentes, no se observa real_mixture_runs.csv versionado | DATOS CRUDOS PENDIENTES | Ejecutar/recuperar run y auditar por mezcla y por cap |
| O06 | ID citado verbalmente por docente, sin artefacto inequívoco identificado | PENDIENTE | Ubicar archivo original, ruta, sha256, run y commit |
| O07 | ID citado verbalmente por docente, sin artefacto inequívoco identificado | PENDIENTE | Ubicar archivo original, ruta, sha256, run y commit |
| O09 | ID citado verbalmente por docente, sin artefacto inequívoco identificado | PENDIENTE | Ubicar archivo original, ruta, sha256, run y commit |
| M4 aprendido | No se observa archivo de pesos/entrenamiento M4 terminado | NO IMPLEMENTADO / NO MEDIDO | Implementar, entrenar, auditar val/test y comparar con Oracle |
| Streaming por hops / E2E | No se observa ejecución física válida | NO MEDIDO | Ejecutar protocolo de LATENCY_BUDGET_S9.md |
| Honor X8c / TFLite | No existe evidencia de inferencia física en Honor | NO MEDIDO | Paridad, modelo exportado y pruebas reales con hashes |

## Convención de incorporación posterior

Un identificador pasa a VERIFICADO solo con: (1) ruta de artefactos; (2) run_id inequívoco; (3) fecha y device; (4) commit de código; (5) fuente dataset / partición; (6) configuración; (7) SHA-256; (8) output/reporte regenerable. No crear archivos simulados para completar este registro.

## Nota sobre la transcripción

Los tokens «O06», «O07» y «O09» aparecen de manera imperfecta en la transcripción. Deben cotejarse con la rúbrica, grabación o informe del docente antes de asignarles una correspondencia definitiva.
