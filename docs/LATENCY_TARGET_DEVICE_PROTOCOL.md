# Protocolo S8 — latencia en dispositivo objetivo

## Motivo

La rúbrica específica de T10 exige mostrar **latencia medida en el dispositivo objetivo**. La medición CI o en infraestructura ajena no satisface por sí sola esa evidencia.

Para S8 se usa una medición acotada y honesta en la laptop objetivo (Acer Nitro 5): tiempo de procesamiento del clip completo de 4 s dentro del contenedor/local runtime.

## Alcance de esta medición

Etiqueta obligatoria:

`whole_clip_processing_only`

Sí mide:
- tiempo de ejecución del pipeline controlado sobre un clip de 4 s;
- p50, p95 y media de N repeticiones;
- CPU visible al proceso/contenedor;
- versión de Python y etiqueta del dispositivo.

No mide:
- latencia por hop;
- captura de micrófono;
- salida de audio;
- E2E de streaming;
- inferencia TFLite Android;
- Honor X8c.

## Ejecución recomendada

```powershell
cd C:\Users\eduar\Desktop\Farid\T10_Merino_Cordova_Eduardo_Farid_HESYCHIA
git pull
$env:HESYCHIA_DEVICE_LABEL="Acer Nitro 5"
docker compose up --build
```

Abrir `http://localhost:8080` → **Edge readiness** → **Medir procesamiento local**.

Configuración recomendada para el parcial:
- runs = 40;
- seed = 42;
- device_label = Acer Nitro 5.

## Evidencia a congelar

El job genera:
- `latency_samples.csv`;
- `latency_summary.json`.

Registrar en la entrega:
- fecha/hora;
- commit Git;
- device_label;
- runs;
- p50;
- p95;
- mean;
- `measurement_scope`;
- nota explícita de que no es RNF-05 final.

## Criterio de presentación

No comparar el p95 de clip completo con el umbral `p95/hop ≤ 10 ms`, porque las unidades de trabajo son diferentes. El dato S8 sirve para demostrar ejecución y medición en el dispositivo objetivo; RNF-05 se evalúa posteriormente con streaming por bloques y E2E real.

## Resultado ejecutado — 2026-10-12

La medición se ejecutó desde la consola Docker en la **Acer Nitro 5**, con 40 runs y seed 42:

| Métrica | Valor |
|---|---:|
| p50 · clip completo | **19.976 ms** |
| p95 · clip completo | **26.205 ms** |
| media · clip completo | **20.725 ms** |

Alcance: `whole_clip_processing_only`.

Este dato ya puede usarse como evidencia S8 de medición en el dispositivo objetivo. **RNF-05 final sigue pendiente**, porque aún faltan p95/hop, E2E de captura/salida y streaming real.
