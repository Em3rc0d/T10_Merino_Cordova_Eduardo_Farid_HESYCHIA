# HESYCHIA S10-A — Docker y QA local (Acer Nitro 5)

La imagen `hesychia:s10a` ejecuta la consola actual. **La rama S10-A no está en main**: es indispensable cambiar de rama antes de reconstruir.

## Actualizar repositorio en Windows PowerShell

Desde la carpeta del repositorio:

```powershell
git status --short
git fetch origin
git switch --track origin/feat/s10a-safe-demo-policy-20261025
```

Si la rama ya existe localmente:

```powershell
git switch feat/s10a-safe-demo-policy-20261025
git pull --ff-only
```

Si `git status --short` muestra cambios locales, resuélvelos antes de cambiar de rama; no uses `git reset --hard` para forzar.

## Reconstruir y ejecutar

```powershell
docker compose up --build --force-recreate -d hesychia
docker compose ps
curl.exe http://localhost:8080/api/health
```

La imagen **ejecuta `test_s10a_safety` durante su build**. Si la política falla, no se creará correctamente la imagen y deberá revisarse el error de build.

Consola: **http://localhost:8080**. En **Atenuación**, seleccionar:

- **Perforación sintética:** `ALLOW`, baseline IRM oracle, no M4 aprendido.
- **Sirena sintética:** `BLOCK` obligatorio, bypass digital sin modificar el audio calculado.
- **Perforación sintética + bloqueo manual:** `BLOCK` por configuración adicional.

### Prueba automatizada de la consola encendida

```powershell
docker compose exec -T hesychia python s10a_docker_smoke.py
```

Esta prueba crea runs reales vía HTTP (no invoca resultados falsos), verifica política, procedencia, integridad JSON/SQLite/SHA y compara los bytes WAV del escenario bloqueado. Debe terminar con `S10A DOCKER SMOKE: PASS`. Los runs quedan persistidos en `04_build/selective_audio_lab/outputs/web`.

### Suite de regresión de S10-A en contenedor

```powershell
docker compose --profile qa run --rm hesychia-qa
```

El perfil `qa` reutiliza la imagen construida por `hesychia`. Comprueba política S10-A, contratos anteriores, demo y API, sin correr GitHub Actions. No se declara `PASS` hasta ejecutar y observar el resultado.

### Ver logs o detener sin borrar evidencias

```powershell
docker compose logs --tail=120 hesychia
docker compose down
```

`docker compose down` no elimina los artefactos locales bind-mounted. **No uses `down -v` ni borres `outputs` si deseas conservar evidencia.**

### Puerto ocupado

```powershell
$env:HESYCHIA_PORT="8081"
docker compose up --build --force-recreate -d hesychia
curl.exe http://localhost:8081/api/health
```

El smoke corre dentro del contenedor y siempre apunta al puerto interno 8080.

### UrbanSound8K (opcional, solo M2)

No hace falta montar UrbanSound8K para S10-A. Para el benchmark M2, antes de iniciar Compose:

```powershell
$env:URBANSOUND8K_HOST_PATH="C:\Users\eduar\Desktop\Farid\UrbanSound8K"
docker compose up --build --force-recreate -d hesychia
```

La ruta debe contener `metadata/UrbanSound8K.csv` y los folds oficiales. La ruta se monta **read-only** dentro del contenedor.

## Límites de los resultados

Los dos objetivos y la referencia tonal son sintéticos. La demo usa IRM oracle calculada con stems privilegiados: **NO** representa entrenamiento ni evaluación del M4 aprendido. No demuestra RNF-04 con voz real, streaming en tiempo real, latencia E2E ni seguridad de alarmas no etiquetadas. No se ha ejecutado Docker en el entorno de ChatGPT; las instrucciones y configuración deben verificarse en tu máquina.
