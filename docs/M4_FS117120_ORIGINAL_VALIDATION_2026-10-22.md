# M4 — FS_117120: WAV original verificado (22-10-2026)

**Decisión:** `ORIGINAL_BYTES_VERIFIED / AUDIO_QC_PASS / PREVIEW_CORRESPONDENCE_STRONG / FAVORABLE_TARGET_CANDIDATE / NOT_ADMITTED / D0_OPEN`. No se entrenó la CNN, no se modificaron título, objetivos ni arquitectura, y no se subió audio al repositorio. Este documento **actualiza** el estado histórico de `docs/M4_FS_117120_AUDIT_2026-10-22.md`, que se creó cuando aún no estaba disponible el WAV original.

## Procedencia y derechos

El tesista descargó `117120__unclesigmund__siren_med.wav` de [Freesound](https://freesound.org/people/UncleSigmund/sounds/117120/) (autor **UncleSigmund**; título **siren_med.wav**; categoría *Sound effects > Electronic / Design*). La ficha indica 44.1 kHz, 16 bits, estéreo, 11.24 s y licencia [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Se requiere atribución al autor, vínculo al origen/licencia e indicación de transformaciones; documentar estas obligaciones en el corpus final.

El WAV recibido tiene **1,982,780 bytes** y SHA-256 `E2CD9938F6B253CDDD1E5ADE5CD80EADBBC8A64A54606DB840181E83ED994362`. Coincide **exactamente** con el SHA-256 reportado por el tesista en Windows. Esto verifica los bytes transferidos, **no** un checksum firmado por Freesound (no disponible aquí). Los parámetros del archivo coinciden con su ficha pública.

## Conversión y calidad

- FFmpeg 7.1.5 (entorno de análisis): estéreo WAV/44,100 Hz/PCM16 → mono WAV/16,000 Hz/PCM16. SHA-256 derivado local `98E46DBE8AA07B8225F230D1C514CD70DA0EC0C9F1C396694F71417B8BE40450`.
- Conversión previa en Windows con FFmpeg 9.0.2 reportada por el tesista: SHA-256 `FF152606A8296F580FEBD0948E926BED6CB2F6330BF72890C096360624B180BB`. Los archivos derivados por entornos distintos **no coinciden byte a byte**; para hashes reproducibles congelar versión/opciones de FFmpeg. No sobreescribir los originales ni sustituir un hash por el otro.
- Calidades del derivado local: duración **11.240 s**, RMS **0.103463067**, pico **0.584228516**, cerca de clipping **0**, sin advertencias numéricas. Canales originales con correlación **0.999999759**.

## Comparación con vista previa previamente auditada

Se compararon los WAV mono/16 kHz del original y de la vista previa MP3 que antes aportó el tesista (SHA-256 de su derivado: `BDF08584D0DB2B8735861FBE08978026D107A36870044715FFC968162431F3FF`). Correlación cruzada FFT y ajuste escalar:

| Medida | Resultado |
|---|---:|
| Desfase temporal | 0 muestras = 0 ms |
| Pearson r | **0.999963367** |
| Ganancia original / vista previa | 1.031059 |
| Relación señal/error tras ajuste de ganancia | 41.35 dB |

Las señales corresponden prácticamente a **la misma grabación**, con pequeñas diferencias de amplitud/procesamiento. El cribado STFT sobre el derivado original (Hann, FFT 1024, hop 256) encontró **391/699** tramas activas, región de mayor actividad **1.04–7.44 s** y flatness mediana activa **0.004222**: patrón predominantemente tonal. Esto **no demuestra aislamiento perfecto** ni representa una métrica del desempeño del modelo.

El tesista declaró escuchar exclusivamente la sirena en la **vista previa**. No consta aún una escucha independiente/documentada del **original**. La gran semejanza entre ondas respalda que el contenido es esencialmente el mismo; la admisión científica sigue exigiendo revisión final documentada.

## Riesgos y puerta de admisión

La clasificación del publicador como efecto electrónico/de diseño es una **amenaza de validez externa**: no constituye prueba de generalización a sirenas de calle, claxones, pirotecnia u otras situaciones reales. El original, su vista previa y cualquier segmento/transformación son **una misma grabación independiente**: no distribuirlos entre train/validation/test. No completar automáticamente `reviewed_license=CONFIRMED`, `isolation_review=ACCEPT_ISOLATED` ni asignar split; faltan registro final de atribución, más sirenas independientes, voces protegidas y fondos. **D0 permanece abierto; no entrenamiento real todavía.**

Evidencia estructurada: `docs/evidence/M4_FS117120_ORIGINAL_VALIDATION_2026-10-22.json`.
