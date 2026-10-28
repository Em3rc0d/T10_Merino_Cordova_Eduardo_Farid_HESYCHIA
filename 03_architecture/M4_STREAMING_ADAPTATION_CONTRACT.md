# M4-STREAM — contrato de adaptación a procesamiento incremental en laptop
Estado: BLOQUEADO; NO IMPLEMENTAR hasta GO escrito del protocolo M4_SCIENTIFIC_TRAINING_CONTRACT.md. Contrato de diseño, NO promesa de latencia ni prueba del sistema.

## Objetivo y exclusiones
Transformar el estimador CNN científicamente congelado de procesamiento causal offline a ejecución incremental sobre bloques PCM de un micrófono o fichero reproducido en laptop, preservando paridad y política M3b.
Quedan fuera de esta etapa ANC físico, Bluetooth, hardware especializado, Android/TFLite, servidor remoto, análisis clínico y garantía de seguridad personal. El bypass seguro no es sustituto de supervisión humana en situaciones reales.

## Dependencia del modelo
Si M4 de la fase científica entrenó con ventana centrada, normalización por clip o características que necesitan audio futuro, el gate P1 NO habilita streaming hasta corregir el frontend, RETRENAR y REPETIR validación independiente. No convertir el checkpoint histórico PI9/PI10 por simple cambio de función STFT.
Conservar exactitud del esquema de features, ventanas, padding, normalización, target embedding, ganancia y política tal como se congeló en P1.

## Modelo de procesamiento
- Cadencia candidata de entrada: 16 kHz mono; salto HOP=160 muestras (=10 ms) y ventana FFT=512 muestras (=32 ms); números provisionales sujetos a benchmark y RNF.
- Entrada incremental: callback de audio coloca bloques en ring buffer acotado con timestamp monotónico. El thread de audio nunca realiza lectura de archivos, logs en disco ni esperas activas.
- Framing causal: construir ventana de las últimas 512 muestras con historial previo; no incluir muestras de tiempos posteriores al bloque disponible.
- STFT por frame → normalizador causal/fijo del entrenamiento → inferencia M4 con cache de activaciones/frames de contexto → ganancia T-F → iSTFT/OLA con ventanas y normalización WOLA correctas; emitir exactamente HOP muestras por paso en estado estacionario.
- Definir explícitamente el retardo de startup, padding inicial, cola final, contexto histórico CNN y continuidad de fase/reconstrucción. Un modelo con convoluciones causales NO significa que el frontend, la iSTFT o salida sean causales.
- La política de protección M3b es de precedencia obligatoria. Mientras M2 esté sin soporte de mezclas/confianza se opera con target configurado y se etiqueta como modo asistido. Modo integrado sólo después de demostrar que M2 detecta eventos concurrentes; si protección es incierta, bypass sin atenuación.
- Los stems no entran al predictor. Oracle queda fuera del camino real de inferencia streaming.

## Estados y contratos observables
Estados: INIT → WARMUP → ACTIVE → BYPASS/FAULT → STOPPED. Eventos y transiciones auditables; la ausencia de checkpoint nunca debe cambiar silenciosamente a Oracle.
En fault (NaN/Inf, mask inválida, falta de recursos, buffer underrun), aplicar política fail-open digital con ganancia unitaria o bypass explícito cuando técnicamente pueda ejecutarse sin riesgo; documentar límites del comportamiento físico real.
Cada frame auditado con input_index, output_index, frame_id, target_id, policy_decision, elapsed DSP, elapsed inference, overrun/underrun, drops, clip_count, hashes de parámetros; logs desacoplados del callback.
No interpretar BLOCK por etiqueta como detector automático de sirena en audio mezclado.

## Pruebas antes de audio en vivo
1. Paridad offline-CAUSAL vs chunks: alimentar misma secuencia con fragmentación variable y comprobar equivalencia numérica con tolerancia congelada, sin recortes, duplicaciones ni cambios artificiales de energía.
2. Identity test: ganancia 1 conserva la señal salvo retardo y error numérico documentado; verificar impulse, sinusoides, silencio, ruido rosa y cambios de bloque.
3. Boundary test: exactamente 160 muestras de salida por hop sostenido; discontinuidades entre bloques y solapamiento STFT auditadas.
4. Fault tests: checkpoint missing/corrupt, NaN gain, target ausente, BLOCK, overrun, underrun, reset, cambio de política y parada/reinicio.
5. Benchmark laptop real: warm and cold start; por hop DSP, inferencia, render y callback; RAM/CPU; al menos tres sesiones y una prueba continua >=10 minutos en entorno identificado.
6. Reportar por separado: latencia algoritmo (ventana/lookahead/cola), inferencia, p50/p95 camino crítico por hop, E2E físico si hay dispositivo loopback/medición de entrada y salida. Jamás inferir E2E de tiempo de inferencia.
7. Prueba humana de escucha informal para QA técnico solamente; no tratarla como ensayo clínico ni demostración de inteligibilidad formal.

## Criterios de cierre
- Paridad incremental robusta al chunking, sin usar audio del futuro o valores globales por clip.
- Precisión acústica no degradada frente al modelo científico congelado más allá de tolerancias predeclaradas; si falla reentrenar y volver al gate científico.
- Estabilidad >=10 minutos documentada sin backlog creciente ni drops no justificados.
- En laptop p95 del camino crítico por hop <=10ms; E2E p95 <=60ms sólo si se mide físicamente con protocolo, tal como SOURCE_OF_TRUTH. Un frame FFT de 32ms no implica inferencia de 32ms, ni garantiza latencia <=20ms.
- M3b protegido, bypass y política de error probados.
- Evidencia versionada: HW/OS/driver/audio IO, SR, HOP, N_FFT, checkpoint SHA, histograma latencias, WAV entrada/salida de control, métricas, logs y tests.
- Si uno de los RNF no se consigue: marcar incumplido, no reescribir el criterio retroactivamente; cualquier cambio formal requiere justificación y revisión con asesor.

## Decisiones aún abiertas (se cierran tras P1)
- API/biblioteca local para audio I/O según sistema operativo de laptop.
- Tamaño de buffer físico y política de jitter/overrun.
- Si el M2 integrado funciona en streaming sin bloquear M4 y con protección conservadora.
- Sistema de snapshots y hash de streaming; formato del reporte y consentimiento para captura de voz local.
