# HESYCHIA M4 — V2: entrenamiento con audio real y comparación V1

**Fecha:** 2026-10-28. **Veredicto:** REWORK / scientific_GO=false / streaming BLOCKED.

**Fuente primaria:** [GitHub Actions #40778794063](https://github.com/Em3rc0d/T10_Merino_Cordova_Eduardo_Farid_HESYCHIA/actions/runs/40778794063), commit 69fff5feb8a0924e32a0df102e3aba271da476cb, workflow SUCCESS. Se ejecutó únicamente entrenamiento y VALIDACIÓN.

## Reproducción real completada

Se adquirieron las mismas 352 grabaciones del piloto anterior: 240 clips ESC-50 y 112 de Mini LibriSpeech. Se recuperaron los contenedores WAV históricos y se comprobó correspondencia byte a byte: PASS_BYTE_EXACT_RESTORATION. SHA de registry: ca9f983a0bc3c024ba10273f7698e696526d38ecdd80c1ef4af1c667826f799e. SHA del contrato de escenas V2: f5c3603f8593bd75720e9c497a011bc000a25ae63e37fdf1e4128ae0fbf71d4a.

Con una CNN profunda causal y pérdida supervisada selectiva se entrenaron tres semillas (71,72,73), 30 épocas cada una, usando 1.600 escenas TRAIN y 160 escenas VAL. En VAL se evaluaron las tres semillas y el checkpoint histórico V1 sobre las mismas mezclas. Las pruebas de ingeniería finalizaron 37 passed, 1 warning. Los archivos TEST anteriores están expuestos históricamente; este flujo no los usó para ajuste, selección ni evaluación V2.

## Resultados de VAL (no test independiente)

Medias reportadas por el evaluador sobre escenarios ALLOW. Conteos de aceptación conjunta sobre exactamente 48 escenas elegibles con objetivo y habla, sin alerta anotada.

| Modelo | Media A_target (dB) | Media A_voice_loss (dB) | Target >=6 (48) | Voice <=1 (48) | Ambos |
|---|---:|---:|---:|---:|---:|
| V1 selected | 2.050 | 0.580 | 0 | 33 | 0/48 |
| V2 seed71 | **2.918** | 0.514 | 0 | 36 | **0/48** |
| V2 seed72 | 2.579 | 0.533 | 0 | 37 | 0/48 |
| V2 seed73 | 2.563 | **0.512** | 0 | 38 | 0/48 |

La selección exclusivamente por validación favorece seed71. En las 48 escenas elegibles, sus medianas son A_target=2.842 dB y A_voice_loss=0.543 dB; el máximo A_target observado es 5.399 dB. **Ninguna de las 48 escenas alcanzó la atenuación >=6 dB**, aun cuando 36/48 conservan voz <=1 dB. Es evidencia de mejora parcial en validación, no de cumplimiento científico.

## Diferencia pareada frente a V1

Comparación sobre las mismas mezclas y orígenes, media con igual peso por grupo:

| Diferencia V2 - V1 | ΔA_target, 10 grupos de ruido (dB) | ΔPérdida de voz, 4 hablantes (dB) | Cambio en cumplimiento conjunto |
|---|---:|---:|---|
| seed71 | +0.790 | -0.207 | 0/48 a 0/48 |
| seed72 | +0.665 | -0.159 | 0/48 a 0/48 |
| seed73 | +0.442 | -0.264 | 0/48 a 0/48 |

Estas diferencias son **descriptivas y sujetas a sesgo de selección en validación**. No estiman el beneficio de generalización en un test externo. No existen aquí intervalos confirmatorios por grupos cruzados.

## Fallos restantes

- Target: ninguna de las 48 escenas elegibles superó 6 dB para ninguna semilla. La señal de progreso es una ganancia parcial, no el resultado requerido.
- No solicitado: seed71 atenúa la otra clase de ruido una mediana de 2.170 dB en escenas elegibles, frente a 2.842 dB del objetivo. No se demuestra todavía selectividad suficientemente robusta.
- Objetivo ausente con habla: seed71 supera 1 dB de pérdida de voz en 3 de 48 escenas ALLOW, frente a 5 de 48 en V1.
- No se realizó una ablación contrafactual sobre audio REAL con etiquetas intercambiadas durante validación; el contraste existe en entrenamiento, pero no es evidencia independiente de selectividad por etiqueta.
- No se volvió a evaluar M2; su alta tasa de falsos positivos de alerta sigue pendiente de corrección.

## Archivos, hashes y procedencia

- [Artefacto completo en GitHub](https://github.com/Em3rc0d/T10_Merino_Cordova_Eduardo_Farid_HESYCHIA/actions/runs/40778794063/artifacts/12857151259): tres checkpoints, tres historiales, manifiestos y CSV de 640 registros de VAL. Expira 2026-11-04 22:31 UTC; también puede descargarse desde la conversación.
- SHA-256 ZIP: b3964adc1a06b846b262126488f08fceb56a0580e3aa32fc79192658703401cb.
- [Recibo agregado versionado](../05_evidence/m4_sci_v2_pilot_2026-10-28/aggregate_receipt.json).
- Checkpoint seed71 SHA-256: 5a5752efd6bb4ccb8b3e564692d8118e1dfaf3f0be2aedd3ac55dfdf0a61832f (mejor época 27).
- Checkpoint seed72 SHA-256: a4de8b8ca60194ef84fdf00498ede652174e7773c82ee3aee6f914eb52c54e46 (época 24).
- Checkpoint seed73 SHA-256: 6c7f645773b1f44b790c8ec4c5ad3382ef9385f612917f26d6f2143681cd3788 (época 23).

## Gate de investigación

**REWORK P1.** Las 352 fuentes siguen con revisión humana de aislamiento pendiente; 160 mezclas VAL no equivalen a 160 fuentes independientes. Faltan duplicados perceptuales, grabaciones originales nuevas de un dominio de campo no expuesto, voz espontánea y español, revisión de alertas M2 y aceptación del asesor. No hay eficacia clínica TEA, prueba física de latencia ni streaming.

Priorizar la capacidad de separación de M4 con experimentos de CNN tiempo-frecuencia (sin sustituir aprendizaje profundo por DSP fijo), e incorporar evaluación de clase correcta versus intercambiada en VAL. Comparar contra el techo alcanzable de máscaras restringidas y auditar fuentes. No abrir otro TEST hasta congelar un modelo suficientemente convincente en validación. No alterar título ni umbrales sin aprobación.

Este piloto informa con transparencia un resultado mixto y fallos; NO declara cumplimiento del título completo.
