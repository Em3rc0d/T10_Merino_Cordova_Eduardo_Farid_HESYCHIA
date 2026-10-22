# HESYCHIA M4 — expansión de fuentes reales (2026-10-22)

**Decisión:** SOURCES_VERIFIED / NEW_AUDIO_NOT_DOWNLOADED / REAL_CORPUS_NOT_ADMITTED / D0_BLOCKED.
Continúa la CNN M4 de atenuación selectiva de HESYCHIA. No modificar título, objetivos ni arquitectura, no importar clasificador ECHO.

## Fuentes contrastadas

| Rol | Fuente oficial | Condiciones y observación | Estado |
|---|---|---|---|
| sirena | [Freesound FS_117120](https://freesound.org/people/UncleSigmund/sounds/117120/) | CC BY 4.0, WAV original ya contrastado en el commit 69eb412; efecto electrónico | Candidato favorable, no admitido |
| sirena | [Freesound FS_371179](https://freesound.org/people/SamsterBirdies/sounds/371179/) | CC0; 6.548 s, WAV 44.1 kHz mono; sirena electrónica | Pendiente obtención original y escucha |
| alarma, no sirena certificada | [Freesound FS_777165](https://freesound.org/people/Erokia/sounds/777165/) | CC0; 19.195 s, WAV 48 kHz estéreo; 'Alarm (Loopable)' con reverberación | Clasificación semántica pendiente; posible distractor |
| voz protegida | [OpenSLR SLR31 Mini LibriSpeech](https://www.openslr.org/31/) | CC BY 4.0; train-clean-5 (332 MB) y dev-clean-2 (126 MB) | Piloto pequeño, todavía no descargado |
| voz test | [OpenSLR SLR12 test-clean](https://www.openslr.org/12/) | CC BY 4.0; 346 MB | **Test sellado**, no usar en desarrollo |
| fondo | [Microsoft MS-SNSD](https://github.com/microsoft/MS-SNSD) | Mezcla fuentes Freesound CC0 y DEMAND CC BY-SA 3.0; permisos varían por audio | No certificar licencias por etiqueta de colección |

OpenSLR SHA-256 no proporcionado por el publicador para los archivos seleccionados: controlar MD5 publicado y guardar SHA-256 de bytes locales:
- [SLR31 MD5 official](https://openslr.trmal.net/resources/31/md5sum.txt): train-clean-5 `5df7d4e78065366204ca6845bb08f490`, dev-clean-2 `6d7ab67ac6a1d2c993d050e16d61080d`.
- [SLR12 MD5 official](https://openslr.trmal.net/resources/12/md5sum.txt): test-clean `32fa31d27d2e1cad72775fee3f4849a9`.

## Artefacto de automatización elaborado y probado

Se preparó un paquete local `HESYCHIA_M4_CORPUS_BATCH_AUTOMATION_2026-10-22.zip` que contiene:
- `04_build/selective_audio_lab/src/m4_public_corpus_bootstrap.py`: plan sin descargar, descarga individual explícita de archivos OpenSLR con comprobación MD5 y SHA256, control de host/tamaño, extracción segura y catálogo por speaker de fuentes candidatas; indexación de backgrounds sin asignar licencias ficticias.
- `04_build/selective_audio_lab/test_m4_public_corpus_bootstrap.py`: **8/8 pruebas locales con fixtures PASS**. No son resultados de entrenamiento o audio real.
- `docs/M4_CORPUS_BATCH_EXPANSION_2026-10-22.md`: instrucciones y límites.

**Importante:** este paquete está preparado por separado y **no está aún integrado como código de este commit**. No ejecutar comandos que presuman esa ruta hasta instalarla o integrarla explícitamente.

## Gates y amenazas

No se descargaron nuevas grabaciones: el entorno de ejecución no resuelve los hosts de audio; Freesound pide sesión para descargar originales. No hay muestras nuevas de voz o fondos con revisiones humanas; la CNN no se entrenó con nuevo corpus. Mantener `D0 BLOCKED`, `D1 PARTIAL`, test sellado, pérdida bajo ADR, cero afirmaciones clínicas. LibriSpeech Mini deriva de SLR12, no es conjunto independiente respecto al LibriSpeech completo; exigir detección de solapamientos y disjunción de locutores. El entrenamiento con voces inglesas no prueba generalización a usuarios hispanohablantes.
