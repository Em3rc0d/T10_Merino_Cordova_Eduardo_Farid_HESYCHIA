# S8 — campaña agregada de latencia · Acer Nitro 5

**Fecha:** 2026-10-12  
**Dispositivo:** Acer Nitro 5  
**Seed:** 42  
**Runs por lote:** 40  
**Lotes:** 2  
**Muestras totales:** 80  
**Scope:** `whole_clip_processing_only`

## Resultado agregado

| Métrica | Valor |
|---|---:|
| p50 pooled · clip completo | **20.024 ms** |
| p95 pooled · clip completo | **34.607 ms** |
| media pooled · clip completo | **22.688 ms** |
| p95 mínimo entre lotes | **26.205 ms** |
| p95 máximo entre lotes | **41.508 ms** |
| rango de p95 entre lotes | **15.303 ms** |

Los valores anteriores provienen de la campaña congelada generada por `freeze_latency_campaign.py`; no se selecciona retrospectivamente el lote con menor p95.

## Lectura correcta

La campaña muestra que existe variabilidad entre ejecuciones aun usando el mismo dispositivo, seed y número de repeticiones. Por ello la presentación del parcial debe priorizar los valores pooled y declarar el rango de p95 observado entre lotes.

Esta evidencia **sí** demuestra:
- procesamiento local repetido en la laptop objetivo;
- 80 mediciones acumuladas en dos lotes independientes;
- distribución agregada de tiempos de procesamiento del clip completo;
- variabilidad inter-lote visible y conservada.

Esta evidencia **no** demuestra:
- p95 por hop;
- latencia E2E de captura→procesamiento→salida;
- streaming estable por bloques;
- inferencia Android/TFLite;
- cumplimiento final de RNF-05.

## Mensaje recomendado para defensa

> En la Acer Nitro 5 ejecuté dos lotes de 40 mediciones, 80 muestras en total. Para el procesamiento del clip completo, la distribución agregada obtuvo p50=20.024 ms, p95=34.607 ms y media=22.688 ms. El p95 por lote varió entre 26.205 y 41.508 ms. Reporto la campaña completa para evitar cherry-picking. Este alcance sigue siendo `whole_clip_processing_only`, por lo que no equivale al p95 por hop ni al E2E final.

## Estado contractual

- Evidencia S8 de latencia en dispositivo objetivo: **MEDIDA Y AGREGADA**.
- Variabilidad inter-lote: **MEDIDA**.
- RNF-05 final: **PARCIAL / PENDIENTE**.

## Artefacto congelado

`outputs/latency_campaigns/LATENCY-CAMPAIGN-Acer_Nitro_5_20261012T133744Z.zip`

El ZIP contiene resumen de campaña, muestras agregadas, métricas por lote y manifiesto de congelamiento.