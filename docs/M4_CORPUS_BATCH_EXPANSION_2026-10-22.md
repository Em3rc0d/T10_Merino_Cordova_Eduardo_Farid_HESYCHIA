# HESYCHIA M4 — expansión verificable del corpus (22-10-2026)

**Alcance:** continuación técnica de la CNN M4 de HESYCHIA; no se modifica el título ni objetivos. No se reutiliza el clasificador ECHO. **Resultado:** investigación de fuentes y pipeline local probado con fixtures. **D0=BLOCKED**, **D1=PARTIAL**, entrenamiento CNN real **NO EJECUTADO**.

| Rol | Fuente | Datos verificados y derechos | Decisión |
|---|---|---|---|
| Objetivo | [UncleSigmund 117120](https://freesound.org/people/UncleSigmund/sounds/117120/) | WAV original y SHA-256 verificados en expediente anterior; licencia CC BY 4.0 | Candidato favorable no admitido. Una sola grabación independiente |
| Objetivo | [SamsterBirdies 371179](https://freesound.org/people/SamsterBirdies/sounds/371179/) | Freesound publica CC0; WAV 6.548 s, 44.1 kHz, mono, sirena electrónica | No descargado; revisión acústica pendiente |
| Ambiguo | [Erokia 777165](https://freesound.org/people/Erokia/sounds/777165/) | Freesound publica CC0; efecto *Alarm (Loopable)* de 19.195 s, reverberación | No declarar sirena de emergencia automáticamente; podría ser negativo/distractor |
| Voz | [OpenSLR SLR31](https://www.openslr.org/31/) | Mini LibriSpeech, CC BY 4.0; train-clean-5 aprox. 332 MB, dev-clean-2 aprox. 126 MB | Candidato piloto; no disponible en el entorno actual por DNS |
| Voz test | [OpenSLR SLR12](https://www.openslr.org/12/) | LibriSpeech test-clean, CC BY 4.0, aprox. 346 MB | TEST SELLADO; no abrir para desarrollo |
| Fondo | [Microsoft MS-SNSD](https://github.com/microsoft/MS-SNSD) | Audios de Freesound CC0 y DEMAND CC BY-SA 3.0, condiciones por archivo | Catálogo local con licencia pendiente; ninguna admisión automática |

**Checksums del publicador:** [SLR31 md5sum.txt](https://openslr.trmal.net/resources/31/md5sum.txt): train-clean-5 `5df7d4e78065366204ca6845bb08f490`, dev-clean-2 `6d7ab67ac6a1d2c993d050e16d61080d`. [SLR12 md5sum.txt](https://openslr.trmal.net/resources/12/md5sum.txt): test-clean `32fa31d27d2e1cad72775fee3f4849a9`.

**No confundir SLR31 con una fuente independiente de SLR12:** Mini LibriSpeech es subconjunto del mismo corpus; el contenido solapado no puede distribuirse entre train/val/test. Las particiones deben auditarse por locutor/grabación original. La voz inglesa no prueba aplicabilidad a voces del español peruano.

## Código implementado

`04_build/selective_audio_lab/src/m4_public_corpus_bootstrap.py` ofrece `status`, `download`, `extract`, `index-speech` e `index-background`. Descarga únicamente por selección explícita, con MD5 oficial fijado, SHA-256 local, límite de tamaño y hosts permitidos. Extrae TAR sin symlinks ni rutas transversales. Indexa un FLAC por speaker por subconjunto sin asignar split, revisar licencia o marcar aislamiento; test no se inspecciona por defecto. Fondos MS-SNSD quedan sin licencia asignada porque los términos difieren por archivo. Código evaluado con 8 pruebas offline sobre fixtures, no sobre audio real.

Ejecutar desde `04_build/selective_audio_lab`:

```powershell
python src\m4_public_corpus_bootstrap.py --action status
python -m unittest discover -p test_m4_public_corpus_bootstrap.py -v

# Opt-in; descarga ~458 MB más espacio de extracción:
python src\m4_public_corpus_bootstrap.py --action download --dataset mini-train
python src\m4_public_corpus_bootstrap.py --action download --dataset mini-dev
python src\m4_public_corpus_bootstrap.py --action extract --dataset mini-train
python src\m4_public_corpus_bootstrap.py --action extract --dataset mini-dev
python src\m4_public_corpus_bootstrap.py --action index-speech --out outputs\m4_corpus_v1\mini_speech_candidates.csv

# Sólo si ya existe una carpeta local de ruido obtenida con permiso:
python src\m4_public_corpus_bootstrap.py --action index-background --root data\m4_external\ms_snsd_noise --out outputs\m4_corpus_v1\background_candidates.csv
```

`--dataset standard-test` exige selección explícita y no debe emplearse mientras se ajustan parámetros. Cambiar `--mirror openslr.elda.org` es posible sin cambiar el MD5 esperado.

## Bloqueos reales

- Entorno actual sin resolución DNS hacia anfitriones de audio: no se han descargado los archivos de voz/ruido ni originales de 371179/777165. Freesound original requiere sesión del usuario.
- No existe corpus con los 3 roles en train/val/test admitidos. NO entrenar ni presentar métricas como validación de tesis; no falsear la cobertura.
- Antes de admitir cualquier muestra: atribución/licencia por archivo, revisión auditiva de aislamiento y su papel semántico, SHA, identificación de origen, exclusión de duplicados y asignación de split grupal.
- Variabilidad entre sirenas de efectos electrónicos y sirenas reales debe tratarse como amenaza de validez externa y requerirá test externo verdaderamente independiente.
