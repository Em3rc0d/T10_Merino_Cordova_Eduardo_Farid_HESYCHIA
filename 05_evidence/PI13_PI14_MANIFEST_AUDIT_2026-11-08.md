# HESYCHIA — auditoría documental PI13/PI14 (2026-11-08)
Base: dictamen PI11/PI12 de 2026-11-02; commit main f625809. Estado: observación estructural, no auditiva.

## Manifiesto de 352
Fuente: `05_evidence/m4_sci_v3_source_review_2026-10-28/source_review_352_template.csv`.
- 352 registros: **240 ESC-50** (vacuum_cleaner, chainsaw, clock_alarm, wind, rain, siren; **40 por categoría**) y **112 speech**.
- Split declarado: train **220**, val **64**, test **68**.
- **209 source_group** únicos, **0** SHA-256 PCM repetidos y **0** source_group cruzando splits **dentro de los metadatos CSV**. Esto **no demuestra** ausencia de near-duplicates ni independencia acústica.
- **0/352** registros contienen revisión humana completada (`reviewer_id`, `review_date_utc`, `review_decision` vacíos).
- Licencia **declarada**: ESC-50, CC-BY-NC-3.0 en 240 filas; speech, CC-BY-4.0 en 112 filas. Verificación de atribución/permiso por clip: pendiente.

## Diferenciar corpus histórico vs test nuevo
`05_evidence/m4_sci_real_2026-10-27/freeze_test.json` documenta un freeze histórico: NO sellar encima, NO abrir un test 'nuevo' basándose en él y NO reusar archivos de un test expuesto para seleccionar el modelo.
El nuevo test independiente **no** está congelado ni evaluado en PI13/PI14. La cuota **48 escenas / 12 grupos fuente / 12 hablantes** es **propuesta operativa sujeta al asesor y a precisión estadística**.

## Regla propuesta (sin autoridad de aprobación todavía)
Estimandos CNN−DSP pareados en A_target (más alto mejor) y A_protected como pérdida (más bajo mejor). IC95% con remuestreo por grupos originales y sensibilidad por hablante. SI-SDRi, target ausente y both_ok 6/1 dB secundarios. Oracle IRM: referencia privilegiada, **no** límite matemático universal.
El margen de preservación, regla global GO y OG/OE requieren fecha y conformidad del asesor **antes de abrir** un nuevo test.

## Qué se ha probado / no probado
- Verificado: consistencia estructural del manifiesto en lectura del repositorio.
- Herramientas externas de QA local: scripts Python para manifest, κ y bootstrap; 5 tests fixture PASS (prueban el software, no la CNN).
- No verificado: escucha de los 352; acuerdo humano κ; derechos por asset; independencia perceptual; test científico nuevo; streaming real; E2E físico; beneficio clínico.

## Fuentes para revisión del manuscrito
- Williams et al. (2021), DST vs hiperacusia DOI 10.1016/j.neubiorev.2020.11.030.
- Williams, Suzman & Woynaroski (2021), metaanálisis DOI 10.1097/AUD.0000000000001005.
- Zhang & Wang (2021), Deep ANC físico DOI 10.1016/j.neunet.2021.03.037.
- Le Roux et al. (2019), SI-SDR DOI 10.1109/ICASSP.2019.8683855.
- Piczak (2015), ESC-50 DOI 10.1145/2733373.2806390.
