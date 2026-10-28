# Evidencia técnica PI9 y PI10 al 26 de octubre de 2026

85 pruebas locales aprobadas; sin skips. Chromium ejecutó E1 CNN, E2 comparación pareada, E3 sirena BLOCK y E4 integridad; sin errores JS y sin overflow de página a 390 px. Las capturas se tomaron del sistema real.

qa_summary.json registra alcance, entorno y límites. paired_comparison.json conserva Run ID, modelo, hashes y valores completos. code_under_test_sha256.json permite verificar la identidad de las fuentes probadas. environment_observed.txt es un inventario del entorno real, no un nuevo requirements portable. unittest_85.log conserva el resultado completo.

Los WAV, máscaras, SQLite y snapshots de pesos se archivan como paquete de evidencia independiente, sin introducirlos todos en Git. Las capturas y resúmenes no sustituyen ese paquete. El video de apoyo identifica su narración sintética y conserva el guion en 06_presentation/pi9_pi10.

No hubo corpus real, test científico independiente, validación de RNF-04, streaming, TFLite, medición Acer/Android ni build Docker en este entorno.
