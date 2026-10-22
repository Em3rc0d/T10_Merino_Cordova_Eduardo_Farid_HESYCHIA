# Contrato de tiempo y presupuesto de latencia — HESYCHIA S9

**Fecha:** 2026-10-22. Este documento especifica mediciones; no añade resultados no observados.

## Parámetros actuales

| Parámetro | Valor |
|---|---:|
| Frecuencia de muestreo | 16 000 muestras/s |
| Ventana STFT | 512 muestras = **32 ms de señal** |
| Hop | 160 muestras = **10 ms de avance** |
| Overlap | 352 muestras = **22 ms de solapamiento** |
| Duración del clip benchmark actual | 4 segundos |

Las expresiones anteriores son aritmética del diseño, **no mediciones de latencia E2E**. El hop de 10 ms no elimina la dependencia contextual de la ventana de 32 ms. El look-ahead efectivo varía con alineación, uso de ventanas causales o centradas, política de buffers, comportamiento del modelo y reconstrucción.

## Contratos que no deben confundirse

| Scope | Qué mide | Umbral/estado |
|---|---|---|
| whole_clip_processing_only | Tiempo de ejecución de procesar un clip completo ya disponible | Acer 2026-10-12, 80 muestras: p95 34.607 ms; no comparable al presupuesto hop |
| per_hop_processing | Tiempo de cómputo del procesamiento de un bloque/hop en runtime sostenido | Meta p95 ≤10 ms; no medido |
| algorithmic_delay | Retardo causal del algoritmo y sus buffers incluyendo contexto disponible | Pendiente de análisis/medición |
| E2E audio | Desde estímulo/captura hasta salida acústica reproducida, incluyendo I/O | Meta p95 ≤60 ms; no medido |
| TFLite_inference_android | Inferencia aislada exportada en Honor X8c | Meta p95 ≤20 ms; no medido |

Importante: una inferencia de 8 ms no garantiza E2E de 8 ms. Y un whole-clip de 34.607 ms **no demuestra** incumplimiento del p95/hop ≤10 ms: son cargas de trabajo distintas.

## Método bloqueante antes del experimento E2E

1. Definir y congelar hardware, sample rate, canal, driver, tamaño y cantidad de buffers, hop, ventana, modo del modelo, CPU/GPU, warmup y reloj.
2. Construir runtime que consuma bloques secuenciales a velocidad de audio; registrar timestamps monotónicos por etapa (ingesta, STFT, inferencia, política, iSTFT, salida) y sus colas.
3. Ejecutar un mínimo de 10 minutos por escenario, descartando solo el warmup **preespecificado**, nunca muestras lentas a conveniencia.
4. Calcular p50/p95, máximo, backlog, dropouts, underruns y factor de tiempo real; separar tiempos de cómputo de latencia observable.
5. Medir E2E con montaje de loopback/acústico justificado, que incluya buffers e I/O; registrar calibración e incertidumbre. No sumar percentiles de distintas distribuciones para fabricar un p95 E2E.
6. Reportar bloqueos técnicos (por ejemplo si la ventana y los buffers imposibilitan 60 ms) como limitaciones, sin cambiar silenciosamente metas.

## Interpretación del parcial

El valor **34.607 ms** es la campaña pooled de procesamiento de clip de 4 s en Acer Nitro 5 documentada en LATENCY_CAMPAIGN_ACER_NITRO5_2026-10-12.md. El proyecto aún no demuestra streaming, E2E ni inferencia móvil. La frase «el sistema ya cumple latencia» sigue prohibida.
