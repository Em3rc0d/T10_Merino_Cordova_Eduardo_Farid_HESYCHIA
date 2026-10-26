# Ejecutar y demostrar PI9 y PI10

## Inicio local

Desde la raíz del repositorio, usar Python 3.11 y un entorno virtual nuevo. No ejecutar GitHub Actions para este cierre.

```powershell
cd 04_build/selective_audio_lab
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-lock.txt
python -m pip install -r requirements-m4.txt
python src/web_server.py --host 127.0.0.1 --port 8080
```

Abrir http://localhost:8080. El checkpoint experimental está incluido en `models/m4_drilling_experimental_v1`; no hace falta entrenar para probar la UI. Si faltan pesos o Torch, Oracle sigue disponible y CNN informa indisponibilidad. La opción final validada permanece deshabilitada.

Alternativa Docker preparada, pendiente de comprobar en un host con Docker:

```powershell
docker compose up --build
# Segunda terminal
docker compose --profile qa run --rm hesychia-qa
```

La imagen incluye Torch CPU por defecto. Para imagen Oracle sin DL: `docker build --build-arg WITH_M4=0 -t hesychia:oracle .`. No afirmar que esa imagen ejecuta CNN. Las dependencias base conservan su lock histórico; requirements-m4 fija Torch, no un lock transitivo universal. El entorno exacto usado aquí queda en la evidencia de QA.

## Cuatro escenarios de demostración

| Escenario | Acción en consola | Referencia verificable |
|---|---|---|
| E1 inferencia profunda | M4 Deep Learning → revisar checkpoint e historia; Atenuación → drilling_synthetic, CNN experimental, seed 42 → Ejecutar | Config requested/executed engine, checkpoint SHA, mask_predicted.npy, audio y métricas |
| E2 comparación | Mismos parámetros → Comparar CNN vs Oracle → Verificar comparación | comparison_id, mismo SHA de mezcla, dos Run ID, máscaras y audios separados |
| E3 protección | Target siren_synthetic, motor CNN u Oracle → Ejecutar | BLOCK, mandatory_protected_signal, executed_engine=bypass, audio idéntico |
| E4 trazabilidad | Evidencias → Verificar → Abrir y descargar artefactos | SHA de audio/pesos/manifiesto; SQLite enlaza run, modelo, configuración y métricas |

M2 muestra los artefactos reales si están montados. Si solo está el documento histórico versionado, informa Macro-F1 0.7257 como **resultado documentado**, con fuente/SHA y ausencia de crudos. No lo presenta como benchmark recién ejecutado ni lo mezcla con los resultados de M4. La política funciona con etiquetas configuradas: no detecta automáticamente todas las señales protegidas en una mezcla.

## QA y regeneración

```powershell
python -m unittest discover -p 'test*.py' -v
# Opcional, para el recorrido real en Chromium
python -m pip install playwright==1.55.0
python -m playwright install chromium
python verify_pi9_pi10_browser.py
```

Las pruebas M4 se omiten explícitamente si Torch no está instalado; para verificar este sprint debe estarlo y no debe haber skips de M4. El script de navegador ejecuta E1–E4, comprueba errores JS y overflow a 390 px y guarda evidencia. No sustituye una auditoría completa de accesibilidad ni pruebas físicas.

Para regenerar pesos, usar otro directorio; no sobrescribir el checkpoint congelado:

```powershell
python src/train_m4_demo.py --out outputs/m4_retrained_engineering --epochs 8
```

El nuevo entrenamiento usa la misma configuración y no cambia retrospectivamente los resultados. El archivo de pesos puede tener otro hash según plataforma/versión. Es una prueba con señales procedurales; semillas distintas no hacen independiente un corpus de voz real.

## Persistencia y versiones

Cada run conserva una copia de pesos y manifiestos; el verificador no depende del checkpoint instalado después. Se usa `schema_v13.sql` para bases nuevas por run (adición del formato pytorch). Las bases históricas v1.2 se siguen leyendo; no se migran ni reescriben. No reutilizar un directorio de run histórico para crear uno nuevo.

`wall_time_ms` abarca DSP e inferencia del clip, excluye carga del modelo y escritura de artefactos; no mide captura/salida ni p95 por hop. La normalización por clip y STFT centrada hacen que esta demo siga siendo offline.

## Pendientes académicos

El cierre técnico permite demostrar aprendizaje profundo ejecutable y comparación con Oracle. O1 sigue abierta en su parte científica. O2 exige habla real y protocolo prospectivo. O5 exige decisión del asesor sobre M2 y objetivos. TFLite, E2E, estabilidad y hardware permanecen pendientes. Grabar y revisar el video narrado, enlazar sus minutos reales en la matriz de observaciones y obtener la evaluación del asesor antes de declarar PI9/PI10 entregado o una observación levantada.
