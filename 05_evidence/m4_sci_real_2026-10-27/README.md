# Evidencias M4: candidato con audio real, REWORK

El candidato `seed61`, seleccionado exclusivamente en validación, cumple los
criterios simultáneos en 1/48 escenas de test. Medianas: 2.529 dB de atenuación
objetivo y 1.127 dB de pérdida de voz. No se acredita GO científico ni streaming.

- [Informe e interpretación](../../docs/M4_SCI_REAL_RESULTS_2026-10-27.md)
- [Freeze original anterior al test](freeze_test.json)
- [Resultados brutos reproducidos](test_replication/)
- [Procedencia y hashes de la reproducción](replication_receipt.json)
- [Regresión completa: 136 aprobadas, 2 omitidas](final_qa.log)
- [Pruebas científicas reconstruidas: 29 aprobadas](scientific_replication_tests.log)
- [Inferencia CLI y bypass antes de cargar pesos](cli_smoke.json)
- [Entorno de reproducción](replication_environment.json)
- [Registro y recetas de cobertura completa V2](v2/)
- [Comparación de candidatos en validación](validation/)
- [Pesos, manifiestos y selección](../../04_build/selective_audio_lab/models/m4_sci_real_candidate_v1/)

La sesión que ejecutó el test original perdió sus archivos temporales antes de
publicar los resultados. La carpeta `test_replication` contiene una reproducción
con pesos, datos y código verificados, identificada como test ya observado.
No se fabrican los CSV originales ni se interpreta esta repetición como nueva
evidencia independiente. Los recibos mantienen las fechas reales de cada ejecución.

Las fuentes ESC-50 son pseudo-stems pendientes de escucha. Los registros,
auditorías y hashes no certifican aislamiento, ausencia de duplicados perceptuales,
eficacia clínica, suficiencia de dominio ni rendimiento en hardware objetivo.
Los audios de terceros y las salidas WAV no se redistribuyen en Git.

Los archivos de corpus y validación de desarrollo V1 se conservan para trazabilidad;
`legacy_condition_gaps.json` documenta sus omisiones de cobertura. Los logs antiguos
retienen sus resultados originales; `final_qa.log` corresponde a la regresión nueva.
