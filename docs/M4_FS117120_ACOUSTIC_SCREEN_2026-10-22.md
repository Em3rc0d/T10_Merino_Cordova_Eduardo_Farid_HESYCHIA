# HESYCHIA M4 — revisión auditiva y espectral de FS_117120 (22 octubre 2026)

## Evidencia de entrada

- El usuario declara haber escuchado solamente la sirena. Es **revisión perceptual favorable autorreportada**, no una certificación independiente de ausencia absoluta de otros sonidos.
- Se inspeccionó el WAV enviado por el usuario; SHA-256 `bdf08584d0db2b8735861fbe08978026d107a36870044715ffc968162431f3ff`, que coincide exactamente con su informe de Windows. Mono 16 kHz, PCM16, duración 11.24 s, RMS 0.100342779 y pico 0.566467285 sin clipping cercano.
- STFT exploratoria Hann nfft 1024 / hop 256; active_frames 391/700 con umbral de 3 % de energía máxima, región de mayor actividad 1.04 a 7.44 segundos, mediana de flatness en frames activos 0.0042335. El espectrograma muestra un barrido tonal armónico dominante; no revela componentes evidentes de voz/tráfico/música, pero **la inspección visual no demuestra aislamiento perfecto**.
- El candidato procede de https://freesound.org/people/UncleSigmund/sounds/117120/ y de una vista previa MP3, con SHA publicado en el catálogo técnico `3acc27af9d2d2533e60c466b311630e9e7aabf27b36eaea43a7b5aa2dbcf0e83`. Su WAV convertido no es el original sin pérdida. Licencia de catálogo CC BY 4.0; verificar derechos y conservar atribución al admitir.

## Decisión

**LISTENING_FAVORABLE + SPECTRAL_SCREEN_DOCUMENTED.** Fuente **candidata para piloto exploratorio**; **NO ADMITIDA** aún como stem científico validado. No cambiar silenciosamente su split ni marcar ACCEPT_ISOLATED / reviewed_license=CONFIRMED en m4_candidate_sources_v1.csv. El test de M4 permanece sellado.

Antes de D0 GO: descarga original si es factible, evidencia manual de derechos y atribución, mayor número y diversidad de fuentes objetivo por split, voces y fondos independientes; revisión adicional de procedencia por grabación. D1 permanece parcial; D3/D4/D5 no cambian. No se sube el audio a GitHub.

## Reproducibilidad

Desde 04_build/selective_audio_lab tras sincronizar main:

    python src/m4_tonal_screen.py --wav outputs/m4_corpus_v1/FS_117120_16k_mono.wav --expected-sha256 BDF08584D0DB2B8735861FBE08978026D107A36870044715FFC968162431F3FF --out outputs/m4_corpus_v1/FS_117120_tonal_screen.json
    python -m unittest discover -p test_m4_tonal_screen.py -v

El script no clasifica semánticamente ni admite por sí solo una fuente. Ver docs/evidence/M4_FS117120_TONAL_SCREEN_2026-10-22.json. Pruebas locales del módulo: 6/6 PASS.
