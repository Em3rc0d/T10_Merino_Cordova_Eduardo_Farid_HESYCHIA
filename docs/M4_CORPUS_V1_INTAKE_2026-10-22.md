# Corpus M4-v1 — diligencia real de fuentes y gate de admisión

**Fecha:** 2026-10-22. **Ámbito:** ingeniería del entrenamiento supervisado M4 ya previsto; sin modificar título, objetivos, arquitectura o resultados de la tesis.

**Estado documental verificado:** CANDIDATES_DISCOVERED / INGESTION_GATE_BLOCKED / NO_REAL_AUDIO_TRAINED. Esta iteración no descarga ni inspecciona audios externos porque el entorno de ejecución no resuelve los dominios de descarga. Los sitios de las fuentes se consultaron mediante navegador de investigación. La certificación completa requiere ejecutar en un equipo con conectividad y escuchar los candidatos.

## Decisión científica crítica

M4 necesita stems conocidos para producir una IRM de referencia. Etiquetas débiles de un clasificador y snippets de campo no prueban aislamiento. No tratar clips clasificados como `SIREN` como fuentes puras. D0 solo se cierra mediante **revisión de la propia señal** y anotación explícita de aislamiento, uso permitido, diversidad de orígenes, trazabilidad y ausencia de contaminantes relevantes. Los potenciales silencios, clipping y duración se auditan con código; una prueba numérica no sustituye escucha humana.

## Fuentes iniciales con licencia observada en el publicador

| ID del registro | Origen oficial | Evidencia | Estado de audio |
|---|---|---|---|
| FS_117120 | https://freesound.org/people/UncleSigmund/sounds/117120/ | CC BY 4.0 publicado, efecto de sirena electrónica, 11.24s. El catálogo técnico conserva preview MP3 y SHA-256 esperado `3acc27af9d2d2533e60c466b311630e9e7aabf27b36eaea43a7b5aa2dbcf0e83`. | Candidato; no descargado, no inspeccionado. Debe preferirse WAV original si está permitido y disponible, porque el preview es comprimido. |
| FS_371179 | https://freesound.org/people/SamsterBirdies/sounds/371179/ | CC0 en ficha de autor, 6.548s, WAV original. | Candidato, no certificado. |
| FS_777165 | https://freesound.org/people/Erokia/sounds/777165/ | CC0 en ficha; 19.195s, WAV original; reverb indicado por autor. | Candidato; puede ser atenuación del efecto electrónico, no una sirena física de calle. |
| SLR12_TRAIN/DEV/TEST | https://openslr.elda.org/12/ | Corpus LibriSpeech SLR12 CC BY 4.0; train-clean-100, dev-clean, test-clean. | Candidatos de colección: NO son registros de audio individuales. Usar scanner para crear entradas por FLAC y speaker ID. |

La evidencia de licencia de una ficha original no es un derecho probado para otro archivo re-subido: preservar productor/ID, versión, ruta, fecha de verificación, SHA-256 del original y del PCM derivado. Solo la persona que verifique la escucha y los derechos marcará `reviewed_license=CONFIRMED` y `isolation_review=ACCEPT_ISOLATED` / `ACCEPT_SPEECH` / `ACCEPT_BACKGROUND`, con reviewer y nota. **Esas celdas están vacías en el registro versionado.**

### Catálogo suplementario de descubrimiento

`m4_unreviewed_media_candidates_2026-10-22.csv` indexa candidatos *etiquetados* de un catálogo técnico previamente construido para otro proyecto. Sus etiquetas pueden ser débiles, los enlaces a previews pueden ser comprimidos y las licencias no se transfieren automáticamente. Los elementos llegan con `reviewed_license`, `isolation_review` y `split` vacíos. No se añaden a la narrativa de la tesis ni implican usar su clasificador.

## Herramientas de ingesta

Desde `04_build/selective_audio_lab`:

```bash
python src/m4_corpus_intake.py --candidates m4_candidate_sources_v1.csv --out outputs/m4_corpus_v1 --action inspect
python src/m4_corpus_intake.py --candidates m4_candidate_sources_v1.csv --out outputs/m4_corpus_v1 --action download-one --candidate-id FS_117120
```

La segunda operación **solo** descarga el preview MP3 de la ficha `FS_117120` si el SHA original esperado coincide y el host es permitido. No acepta redirecciones a hosts fuera de lista ni archivos mayores de 25 MiB. Si el archivo descargado tiene un hash distinto, la descarga se descarta; no altera el hash esperado para lograr PASS. No se admite automáticamente el audio en el corpus.

Tras descargar, convertir y preservar original por separado (ejemplo de API interna): `convert_approved_original(original_path, pcm_path)`. Registra hash de bytes originales, hash de PCM mono 16 kHz y chequeos de duración/RMS/clipping. La conversión **no convierte** un clip con fondo en sirena aislada y el límite de calidad no sustituye revisión perceptual.

Para LibriSpeech, descargar los archives oficiales en un equipo con conexión, verificar `md5sum.txt` del publicador, extraer de forma segura y crear entradas individuales:

```bash
python src/m4_librispeech_catalog.py --root /ruta/librispeech_extraido --out outputs/m4_librispeech_candidates.csv --max-per-subset 24
```

El catálogo extraído queda *no revisado*, sin split asignado. El objetivo del piloto es cubrir múltiples speakers independientes; una sola voz generando cientos de escenas no cuenta como cientos de observaciones independientes. En el corpus principal usar agrupación por speaker y grabación, no dividir ventanas del mismo original entre splits. Las particiones de LibriSpeech son un buen punto de partida, sujetas a revisión de identidad y licencias.

### Promoción conservadora

Una vez inspeccionados los archivos y completadas las columnas de derechos, ruta de WAV/FLAC, split y revisión auditada, ejecutar:

```bash
python src/m4_corpus_intake.py --candidates m4_candidate_sources_v1.csv --out outputs/m4_corpus_v1 --action promote
python src/m4_data_gate.py --registry outputs/m4_corpus_v1/m4_sources.csv --out outputs/m4_corpus_v1/source_integrity.json
```

El primer comando rechaza silencio, duración menor de 4 segundos, clipping significativo, faltantes, condiciones de uso incompletas, grupos de grabación repetidos y speakers cruzados. Emite `m4_sources.csv` **solo si existe al menos una fuente distinta por rol y split y todo PASS**. Ese mínimo técnico no significa suficiencia científica: para una evaluación útil se necesita una cantidad y diversidad de grabaciones independientes que será especificada al congelar el corpus final. Los splits deben asignarse **a la grabación/origen antes de aumentar**. Un audio comprimido y su WAV derivado comparten la misma identidad de fuente.

**Prueba cerrada:** el protocolo final debe reservar fuente externa y locutores disjuntos del entrenamiento; las fuentes cuyos resultados se observaron anteriormente quedan en desarrollo, no deben volver a presentarse como test ciego. Mientras no exista test verdaderamente independiente, no se reporta desempeño final.

## Evidencia de esta ejecución

- Registro inicial verificado: **6 candidatos documentados**, 3 roles `target`, 3 colecciones `protected`, **0 `background`**.
- **1** candidato con URL de preview y hash remoto esperado. Licencias observadas en los publicadores de los 3 targets y en LibriSpeech, pero `reviewed_license` permanece vacío, por lo que no hay admisión automática.
- Ejecución `--action inspect`: `CANDIDATES_NOT_CERTIFIED`, 0 aceptados.
- Ejecución `--action promote`: `BLOCKED` con nueve celdas rol/split sin fuentes admitidas. Archivo de auditoría reproducible en `docs/evidence/M4_CORPUS_INTAKE_BLOCKED_2026-10-22.json`.
- **16 tests unitarios locales PASS**, con audio fixture artificial exclusivamente; cubren URLs seguras, checksums, auditoría técnica, revisión humana, licencias, speaker/group leakage, condiciones target ausente y gradientes de pérdida estabilizada.
- No se realizó un entrenamiento nuevo con datos reales, ni se extrapoló un resultado sintético.

## D0–D5

| Gate | Estado | Condición de cierre |
|---|---|---|
| D0 fuentes aisladas/licencias | BLOCKED | Descargas verificadas, escucha, derechos, orígenes independientes |
| D1 split/manifest | PARTIAL | Código de validación ejecutable; faltan manifests reales, backgrounds y diversidad |
| D2 CNN/STFT causal | PARTIAL | Tests de fixtures; falta medición física p95/hop/E2E |
| D3 pérdida L0 | PROSPECTIVE ADR | Ver ADR de estabilidad; necesita conformidad científica del asesor antes del experimento definitivo |
| D4 test nuevo | BLOCKED | Corpus externo reservado y sellado, sin uso para ajuste |
| D5 TFLite/dispositivo | OPEN | Paridad, exportación, Acer y Honor físicos |

Referencias primarias: Freesound (fichas indicadas), OpenSLR SLR12 https://openslr.elda.org/12/ , documentación de previews Freesound https://freesound.org/docs/api/overview.html .
