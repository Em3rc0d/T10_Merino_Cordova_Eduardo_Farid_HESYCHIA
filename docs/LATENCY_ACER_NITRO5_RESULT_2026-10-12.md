# S8 — latencia medida en dispositivo objetivo

**Fecha:** 2026-10-12  
**Dispositivo declarado:** Acer Nitro 5  
**Runs:** 40  
**Seed:** 42  
**Scope:** `whole_clip_processing_only`

## Resultado observado — lote congelado A

| Métrica | Valor |
|---|---:|
| p50 · clip completo | **19.976 ms** |
| p95 · clip completo | **26.205 ms** |
| media · clip completo | **20.725 ms** |

## Interpretación

Este lote satisface la necesidad de S8 de mostrar una medición ejecutada en el dispositivo objetivo, pero no debe tratarse como una estimación definitiva de rendimiento. Los lotes repetidos deben agregarse y reportar también su variabilidad; no se debe seleccionar retrospectivamente el p95 más bajo.

**Sí demuestra:**
- ejecución local del pipeline controlado en la Acer Nitro 5;
- 40 repeticiones con seed 42;
- p50/p95/media del procesamiento del clip completo;
- evidencia producida por la misma consola Docker del prototipo.

**No demuestra todavía:**
- p95 por hop de 10 ms;
- latencia E2E captura→procesamiento→salida;
- streaming por bloques;
- inferencia Android/TFLite;
- estabilidad de 10 minutos.

Por tanto, no debe compararse `26.205 ms` directamente con el requisito `p95/hop <= 10 ms`, porque la unidad de trabajo es distinta. Tampoco debe usarse para declarar RNF-05 final como cumplido.

## Mensaje para defensa

> En la laptop objetivo medí el procesamiento del clip completo durante 40 ejecuciones: p50=19.976 ms, p95=26.205 ms y media=20.725 ms. Esta medición corresponde al alcance `whole_clip_processing_only`; aún no equivale al p95 por hop ni a la latencia E2E del streaming final.

## Estado

- Evidencia de latencia en dispositivo objetivo para S8: **MEDIDA**.
- RNF-05 final: **PARCIAL / PENDIENTE**.

## Regla para lotes repetidos

Si existen varias ejecuciones con la misma Acer Nitro 5, seed y número de repeticiones, conservar cada lote y generar una campaña agregada. La presentación debe priorizar la distribución combinada y el rango de p95 entre lotes, evitando cherry-picking.

Utilidad: `src/freeze_latency_campaign.py`.
