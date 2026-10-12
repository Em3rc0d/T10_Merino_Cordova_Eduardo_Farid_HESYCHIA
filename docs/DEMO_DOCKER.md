# Demo reproducible con Docker — HESYCHIA T10

## Objetivo

Evitar la dependencia de un entorno local específico durante la defensa. La demo web y el pipeline PI8+ se ejecutan dentro de una imagen con Python 3.11.17 y dependencias congeladas.

El contenedor **no convierte módulos pendientes en implementados**. La consola habilita únicamente capacidades realmente disponibles y devuelve 501 para entrenamiento M4, TFLite y streaming mientras sigan pendientes.

## Requisitos

- Docker Desktop o Docker Engine con Compose v2.
- Repositorio clonado.
- UrbanSound8K solo es necesario para el benchmark M2 real. La baseline de atenuación funciona sin el dataset.

## Arranque mínimo

Desde la raíz del repositorio:

```powershell
docker compose up --build
```

Abrir:

```text
http://localhost:8080
```

Comprobar salud:

```powershell
curl.exe http://localhost:8080/api/health
```

Respuesta esperada:

```json
{
  "status": "ok",
  "service": "hesychia-web"
}
```

## Montar UrbanSound8K en Windows

Si el dataset está en:

```text
C:\Users\eduar\Desktop\Farid\UrbanSound8K
```

ejecutar antes de Compose:

```powershell
$env:URBANSOUND8K_HOST_PATH="C:\Users\eduar\Desktop\Farid\UrbanSound8K"
docker compose up --build
```

Dentro del contenedor el dataset se monta read-only en:

```text
/data/UrbanSound8K
```

La UI comprobará `metadata/UrbanSound8K.csv`, `audio/fold1` y `audio/fold10` antes de habilitar la validación y el benchmark real.

## Flujo recomendado para la defensa

1. `docker compose up --build` antes de la exposición.
2. Abrir `http://localhost:8080`.
3. Verificar el indicador **Servicio operativo**.
4. Abrir **Atenuación** y ejecutar primero ALLOW.
5. Mostrar los tres valores medidos producidos por ese run, no valores escritos a mano.
6. Cambiar el escenario a BLOCK y demostrar la precedencia de protección (`target_is_protected`).
7. Reproducir `mixture.wav` y `output_selective.wav` desde la UI.
8. Mostrar waveform y espectrograma generados a partir del mismo run.
9. Abrir **Evidencias** y pulsar **Verificar** para comprobar JSON/SQLite/manifiesto/SHA-256.
10. Si UrbanSound8K ya está montado y validado, abrir **Benchmark M2** y ejecutar/mostrar el resultado real.
11. En **Edge readiness**, mostrar que streaming/TFLite/Honor X8c siguen pendientes si aún no fueron medidos.

## Persistencia

`docker-compose.yml` monta:

```text
./04_build/selective_audio_lab/outputs
```

en el contenedor. Por ello los runs generados por la demo permanecen disponibles aunque el contenedor se reinicie.

## Reproducción sin UI

```powershell
docker compose run --rm hesychia python src/run_demo.py --out outputs/demo_cli
```

Tests:

```powershell
docker compose run --rm hesychia python -m unittest discover -p "test*.py"
```

## Alcance de la UI

| Sección | Estado | Fuente de datos |
|---|---|---|
| Estado | funcional | contrato + estado del software |
| Atenuación | funcional baseline | run real generado al pulsar ejecutar |
| Audio / figuras | funcional | WAV y PNG del mismo run |
| Evidencias | funcional | JSON/CSV/SQLite/SHA-256 |
| Benchmark M2 | funcional cuando UrbanSound8K oficial está montado | resultados del benchmark real |
| Streaming Edge | pendiente | no se muestran métricas inventadas |
| Exportación TFLite | pendiente | endpoint responde 501 |
| Honor X8c | pendiente | solo aparecerá tras perfilado físico |

## Por qué Docker ayuda al parcial

El ejecutable ya no depende de que el jurado replique la configuración de Python del tesista: Python, dependencias y servidor quedan dentro de la imagen. El host aporta únicamente Docker, el dataset opcional y el puerto 8080.

Esto reduce el problema de «en mi PC funcionaba», pero no elimina factores externos como arquitectura de CPU, recursos del host o permisos de Docker. Las métricas de rendimiento final deben seguir midiéndose en el dispositivo objetivo especificado.