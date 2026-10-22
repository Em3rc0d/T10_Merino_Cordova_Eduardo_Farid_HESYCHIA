# HESYCHIA M4 — Stress test CNN sintético (2026-10-22)

**Evidencia de ingeniería solamente: no es evaluación científica con sirenas/voz reales, ni prueba de streaming o beneficio clínico.**

## Configuración

Se entrenó exactamente la arquitectura causal CNN del smoke anterior (236,833 parámetros): Keras 3.13.2 con backend PyTorch 2.10.0+cpu; Conv1D 128 filtros y dilataciones 1/2/4, embedding 16, salida 257 bins. Train=768 escenas, val=192, test-ID=160 y test-OOD=160; seeds 42/1042/2042/3042, escenas generadas como tonos, chirps y ruido de 0.31 s (no fuentes acústicas reales). Adam LR=0.001; batch=16; 30 épocas; MSE de máscara. **MSE no es la función L0 acordada en PI7.** Tiempo de entrenamiento medido en CPU sandbox: 23.894 segundos; no Acer Nitro 5.

Train MSE antes 0.230633, después 0.002471; val MSE 0.002611. Estos valores por sí solos no demuestran generalización. Test OOD predefinido: banda nueva de frecuencia, interferencia intensa, solapamiento espectral con voz protegida y ausencia de target. Test observado y no reutilizable como nueva prueba ciega.

## Umbrales para cumplimiento conjunto por mezcla

A_target >= 6 dB y A_protected <= 1 dB simultáneamente con cap=12 dB. El Oracle usa stems privilegiados para formar una IRM, pero la CNN recibe solo magnitud mezclada y target_id.

| Condición | Target presente | CNN cumple ambos | Media A_target CNN | Media A_protected CNN | Oracle cumple ambos |
|---|---:|---:|---:|---:|---:|
| ID conocida | 120 | 120/120 (100%) | 11.934 dB | 0.066 dB | 120/120 |
| OOD interferencia | 40 | 4/40 (10%) | 3.716 dB | 0.040 dB | 40/40 |
| OOD nueva frecuencia | 40 | 0/40 (0%) | 0.040 dB | 0.185 dB | 40/40 |
| OOD solapamiento | 40 | 1/40 (2.5%) | 5.041 dB | **3.101 dB** | 39/40 |
| OOD total | 120 | **5/120 (4.17%)** | 2.932 dB | Heterogénea | 119/120 |

80 escenas adicionales sin target (40 ID/40 OOD) dieron A_protected media ~0.0005 dB; para estas no se calcula A_target. El Oracle no es máximo matemático universal. Todas las tasas se refieren solo a escenas artificiales del generador.

## Causalidad de la red y tiempos

Prueba de invariancia prefijo: al cambiar completamente frames 25–31, la predicción en frames 0–24 no varió (delta máximo 0). Esto prueba causalidad interna de Conv1D para este fixture, **no** de STFT/iSTFT ni del sistema físico.

500 inferencias CPU por ventana de 32 frames (~0.31 s), Keras model.predict y overhead incluidos: p50=4.557 ms, p95=5.627 ms, p99=7.235 ms; pico=250.009 ms; 4 llamadas superaron 10ms. **Estos tiempos no son p95 por hop ni E2E**. No hubo dispositivo móvil ni TFLite.

SHA-256 del checkpoint sintético: 760d6eedb2531cd4b5663f4e418bd03d3ba931d6dfed4a00974e13e1965a6beb.

## Veredicto

**PASS: aprendizaje de máscaras en una distribución sintética familiar. FAIL: robustez OOD.** Solapamiento degrada la protegida más de 1 dB; frecuencia novedosa casi no se atenúa. Entrenar durante más épocas en el mismo generador no corrige ese fallo científicamente. Se necesita fuente aislada/licenciada, partición por origen, loss PI7 estabilizada con target ausente, regularizador voz registrado prospectivamente, test nuevo y frontend causal extremo a extremo. Gates D0–D5 no cerrados.

Los scripts exactos de stress y diagnósticos, checkpoint, CSV por mezcla, curva, JSON y WAV se conservan como paquete de evidencia local HESYCHIA_M4_CNN_stress_2026-10-22.zip; no se subió ese binario a GitHub. Resumen verificable también guardado en docs/evidence/.
