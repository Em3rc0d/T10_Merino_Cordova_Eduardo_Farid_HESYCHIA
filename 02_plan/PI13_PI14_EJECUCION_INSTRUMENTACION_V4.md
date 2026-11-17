# PI13–PI14 · Corte de instrumentación v4 (08/11/2026)

Base verificada: `main f625809`. Esta rama documenta propuestas y auditorías; no reemplaza ensayos ni aprobación académica.

## Evidencia histórica — reutilizable con restricciones

El recibo `05_evidence/m4_sci_v2_pilot_2026-10-28/aggregate_receipt.json` reporta validación de desarrollo con 160 escenas, 48 elegibles para la antigua regla `both_ok`. V1 seleccionado: media A_target=2.0496 dB y pérdida protegida=0.5801 dB; V2 seed71: 2.9184 dB y 0.5140 dB. Ambos 0/48. V2 seed71 fue seleccionado por validación; no constituye resultado confirmatorio sobre test nuevo. La comparación pareada por medias de grupos (10 fuentes, 4 hablantes) de V2 seed71 frente a V1 arroja +0.7900 dB objetivo y -0.2065 dB daño protegido; diferenciar este promedio agrupado de los promedios globales.

La campaña histórica de Acer Nitro 5 (2 lotes; 80 muestras) arroja p50 agrupado 20.024 ms, p95 34.607 ms y media 22.688 ms sobre **procesamiento de clip completo del pipeline controlado**, no p95 por hop de CNN ni E2E.

## Herramientas independientes para ejecutar localmente

Se generó paquete `HESYCHIA_PI13_PI14_Tools_v4.zip` fuera del repositorio con:

- `pi13_review_workbench.py`: UI HTTP local; 352 PCM restaurados, SHA256 por WAV verificado antes de guardar; revisión A y B ciegas por archivo, export CSV.
- `pi13_double_sample.py`: submuestra estratificada por clase/split y source_group; selección determinista según semilla.
- `pi14_m4_forward_benchmark.py`: checkpoint **real requerido**; p50/p95/p99 y RTF sólo de forward+gain M4; STFT precomputada fuera del cronómetro, no streaming E2E.
- Suites previas de congelación, corpus, κ, pareamiento CNN/DSP/Oracle y resumen por hops.

**QA local: 18/18 pruebas de software** con fixtures/PCM de prueba y checkpoint simulado, incluyendo un roundtrip HTTP. No se escucharon PCM reales en este entorno y no se ejecutó checkpoint real Acer.

## Gates pendientes

1. OG/OE, papel M2, criterio acústico, margen de preservación y N/aprobación con fecha del asesor.
2. Revisión auditiva humana de 352 clips originales; doble ciega y κ, exclusiones justificadas.
3. Nuevo test independiente no expuesto con grupos fuente y hablante disjuntos, preespecificación y hash previo a apertura.
4. Evaluación real CNN/DSP/Oracle emparejada por `mix_sha256`.
5. Benchmark de inferencia M4 *real* en Acer; registrar alcance y no confundir inferencia con E2E.

**No hay GO científico ni streaming validado.** Este documento sólo registra actividades y propone cómo obtener las evidencias faltantes; no desbloquea el test.
