# Presentación — Examen Parcial Semana 8

## Diapositiva 1 — Carátula
**UNMSM · FISI · Proyecto de Tesis II**  
**EXAMEN PARCIAL · SEMANA 8**

**Tesis:** Sistema inteligente de cancelación selectiva de ruido mediante aprendizaje profundo para la atenuación de estímulos acústicos asociados a la hiperacusia en personas con TEA.

**Tesista:** Merino Córdova, Eduardo Farid · T10 · Grupo B  
**Asesor:** Daniel Alfonso Quinto Pazce

Trazabilidad: **S5 requisitos → S6 arquitectura → S7 diseño → S8 construcción inicial**.

> Idea central: no se promete eficacia clínica ni ANC físico; se demuestra un prototipo técnico de atenuación selectiva por máscara tiempo-frecuencia.

## Diapositiva 2 — Problema y objetivos
**Problema.** Los sistemas de supresión ciega reducen sonido sin conciencia semántica: pueden atenuar estímulos molestos, pero también señales que deben preservarse.

**Objetivo general.** Diseñar, implementar y evaluar computacionalmente un prototipo Edge AI de procesamiento selectivo de audio, con métricas semánticas, acústicas y computacionales.

**OE1.** Comparar representaciones y modelos para reconocimiento semántico.  
**OE2.** Implementar/evaluar atenuación selectiva por máscara T-F preservando señal protegida.  
**OE3.** Caracterizar ejecución local/Edge: latencia, recursos, estabilidad y trazabilidad.

Alcance ético: no es dispositivo médico; no realiza ensayos clínicos; validación base con datasets públicos/licenciados y mezclas sintéticas.

## Diapositiva 3 — S5: requisitos medibles
**RF:** RF-01/02 audio + STFT/log-Mel/MFCC; RF-03 benchmark; RF-04/05 política + mezclas; RF-06/07 máscara T-F + reconstrucción; RF-08/09 runtime + evidencias; RF-10/11 entrenamiento + TFLite.

**RNF principales**
- RNF-03: Macro-F1 ≥ 0.85 en test predefinido.
- RNF-04: A_target ≥ 6 dB; A_protected ≤ 1 dB; SI-SDRi > 0 dB.
- RNF-05: laptop p95 camino crítico ≤ 10 ms/hop; E2E p95 ≤ 60 ms; Android TFLite p95 ≤ 20 ms.

Los umbrales son criterios de ingeniería del prototipo, no clínicos.

## Diapositiva 4 — S6: arquitectura corregida
Pipeline: **M1 Ingesta → M2 Reconocimiento → M3b Política → M4 Máscara T-F/reconstrucción**, orquestado por **M5 Runtime**, con **M6 Evidencia**.

M3a genera mezclas únicamente offline. M2 no gobierna automáticamente M4. Laptop ejecuta el pipeline E2E; smartphone se limita a perfilado TFLite hasta contar con app real.

## Diapositiva 5 — S6: decisiones arquitectónicas
**D1 · Edge-local.** Sin nube obligatoria para reducir dependencia, favorecer privacidad y reproducibilidad.  
**D2 · Semántica ≠ separación.** La etiqueta no localiza bins; M2 y M4 están desacoplados.  
**D3 · Evidencia trazable.** Run ID + checksum + SQLite + filesystem.

Alternativas descartadas: cloud como dependencia central; script monolítico; app móvil completa prematura.

## Diapositiva 6 — S7: procesos y datos
Proceso crítico: **stems test + target + policy → mezcla → M3b → M4 → audio/máscara/métricas**.

Modelo de datos: DATASET, AUDIO_ASSET, RUN_ASSET, RUN, POLICY_DECISION, METRIC y ARTIFACT. RUN_ASSET resuelve la N:M y POLICY_DECISION conserva la decisión aplicada.

## Diapositiva 7 — S7: API, UI y contratos
Trabajos largos: **202 Accepted + jobId**; consulta con **GET /jobs/{id}**. Android no depende de la API.

UI: configuración, benchmark, atenuación, streaming y evidencias. Los valores de los mockups son ilustrativos, no resultados finales.

Regla de seguridad: si `target ∈ protected_set`, se bloquea atenuación y `g=1`.

## Diapositiva 8 — S8: construcción
Incremento funcional local reproducible:
- mezcla controlada;
- máscara T-F baseline/oracle;
- iSTFT;
- métricas acústicas;
- benchmark local de ejecución;
- JSON/CSV/checksums.

Pendiente: estimador A5 aprendido, exportación TFLite y perfilado físico en Honor X8c.

## Diapositiva 9 — S8: demostración y evidencia
Resultados del run sintético controlado:
- A_target = 11.99 dB
- A_protected = 0.007 dB
- SI-SDRi protected = 11.52 dB
- latencia local p95 = 15.70 ms para el procesamiento del audio completo de 4 s en el entorno de desarrollo.

Comandos:
```bash
cd 04_build/selective_audio_lab
python src/run_demo.py --out outputs/demo_run
python src/latency_benchmark.py --out outputs/latency
```

**No interpretar esta latencia como perfil Android ni como E2E del sistema final.**

## Diapositiva 10 — Trazabilidad
- OE1 → RF-01/02/03 → M1/M2 → A1/A2 → benchmark.
- OE2 → RF-04/05/06/07 → M3/M4 → A3/A4/A5/A6 → audio + métricas.
- OE3 → RF-08/09/11 → M5/M6 → A7/A8/A9 → perfil + evidencias.

Ejemplo: RF-06 → M4 → A5 → `mask_irm.npy`, `output_selective.wav`, `demo_metrics.csv`.

## Diapositiva 11 — Plan de validación
S9 M4 real → S10 integración → S11 plan formal → S12 línea base → S13 validación final.

Dimensiones:
- semántica: Macro-F1/Recall/Precision;
- acústica: A_target, A_protected, SI-SDRi;
- computacional: p50/p95, RAM, tamaño, drops;
- reproducibilidad: seeds, folds y checksums.

## Diapositiva 12 — Riesgos y próximos pasos
**R1 Latencia:** optimizar o reportar incumplimiento.  
**R2 Preservación:** RN-01, cap_dB, A_protected ≤ 1 dB, SI-SDRi.  
**R3 Android:** perfilar TFLite físicamente; no inventar mediciones.

Siguiente hito: reemplazar baseline oracle por estimador M4 entrenado y ejecutar perfil TFLite real.
