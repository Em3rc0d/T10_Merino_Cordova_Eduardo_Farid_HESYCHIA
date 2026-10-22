# HESYCHIA M4 — integración de fuentes verificadas con CNN causal (2026-10-22)

**Estado:** implementación y pruebas de ingeniería **PASS**; **NO es un entrenamiento científico con fuentes reales**. No modifica el título de tesis, los RF/RNF, la arquitectura v1.1, los resultados anteriores ni la versión congelada del experimento Oracle. Las variantes de pérdida y el checkpoint de prueba son **prospectivos**.

## Alcance y evidencia ejecutada

- Nuevo `src/m4_causal_bridge.py`: un frontend de STFT causal de 512 muestras y hop=160 a 16 kHz; ventana sqrt-Hann igual a `m4_causal_frontend.py`, 257 bins, log1p(20*|STFT|), sin normalización por máximos del clip ni look-ahead. `reconstruct_stream` aplica la ganancia por bloque usando WOLA existente y toma una función de inferencia causal. La política BLOCK fuerza ganancia 1, sin ejecutar el modelo.
- `StreamingTorchGain`: adaptador de un solo objetivo `siren` que mantiene 15 frames de historia (campo receptivo exacto del contrato PI7 de dilataciones 1/2/4 y kernel3), produce una ganancia limitada a cap=12 dB. Su paridad con CNN evaluada sobre toda la secuencia fue validada localmente. Es una **baseline de exactitud**, no una implementación optimizada de streaming. Recalcula el contexto en cada hop y necesita benchmark de p95 por hop/tiempo E2E y administración real de audio I/O.
- `src/m4_real_corpus.py`: verifica el registro mediante `m4_data_gate`, chequea bytes/sha256, derechos declarados, speakers y grabaciones divididas por origen antes de generar mezclas. Lee fuentes locales WAV/FLAC soportadas por soundfile, remuestrea a 16 kHz con scipy.resample_poly, compone escenas con stems conocidos de voz / target / background en train o val. **Bloquea solicitar split `test` a la función de escenas de entrenamiento**.
- `src/train_m4_real.py`: nueva implementación PyTorch de la **misma arquitectura funcional PI7** (embedding 16; Conv1D causales de 128 canales dilataciones 1/2/4; Dense(257)+sigmoid). Su pesos **no se importaron** de Keras: tensor layout y representación STFT difieren; requiere entrenamiento desde cero sobre fuentes aprobadas. Entrena y selecciona solo con train/val; registra losses, versiones, hashes de entrada y checkpoint. Ningún test se usa para tuning.
- Para `target_absent`, se implementó una **estabilización prospectiva** de la pérdida L0 mediante piso de denominador `max(mean(|target|), 0.01*mean(|mix|), 1e-4)`; es una variante de ingeniería que **requiere ADR/aprobación** antes de usarla como la función científica contractual. Penalización adicional de voz configurable, valor por defecto 0.0, no declarada resultado final.
- 12 pruebas locales (fuentes artificiales y formatos WAV). Pruebas de ganancia unitaria con diversa longitud, política BLOCK, silencio, rechazo de ganancia inválida, no anticipación de muestras futuras, equivalencia de características por frame, ausencia target, grupos de manifest, gradientes finitos y equivalencia salida causal CNN batch-vs-frame.
- Smoke adicional sobre un manifiesto de **9 audios artificiales** (3 roles × 3 splits) creado solo para pruebas. Entrenamiento 6 épocas en CPU, checkpoint verificable y WAV artificial de salida. No representa generalización ni desempeño acústico real.

## Integridad y limitaciones científicas

- El uso de material de ECHO fue **metodológico**: provenance, agrupación, falsos positivos, hard negatives y controles de experimento. No se copió su clasificación como objetivo de la tesis. M4 sigue estimando máscara espectral, M2 sigue siendo benchmark/monitor y la política M3b permanece.
- Audios de ECHO son grabaciones de campo etiquetadas (no stems necesariamente aislados); su manifold puede contener ambiente. Se requieren pistas aisladas de sirena examinadas y con derechos compatibles. El rótulo `isolated` de un manifest **no certifica** pureza ni licencias verdaderas; exige revisión humana documentada. FUSS tiene pistas individuales pero sus sources estándar no incluyen etiquetas por clase. DESED Synthetic tiene foreground aislados pero está centrado en sonidos domésticos; siren no queda verificado. UrbanSound8K no satisface automáticamente separación pura.
- La etapa experimental real mantiene D0 **BLOCKED** hasta auditar stems aislados; D1 **PARTIAL** hasta disponer de un manifest real; D2 **PARTIAL** hasta verificar streaming real y captura→reproducción; D3 **OPEN** hasta decisión ADR sobre estabilización de pérdida y regularizador; D4 **PARTIAL** hasta test sellado verdaderamente independiente; D5 **OPEN** hasta conversión/paridad TFLite, hardware Acer/Honor y benchmark físico.
- Verificar licencias **por activo** y los derechos de entrenamiento/redistribución. Ningún fichero de audio de terceros se versiona en GitHub.

## Contrato de manifiesto fuente

Archivo CSV a preparar por propietario del corpus:

`source_id,role,split,recording_id,speaker_id,path,sha256,license,reference_grade`

`role`: `target`, `protected`, `background`. `split`: `train`, `val`, `test`. `reference_grade`: `isolated` solo para fuente target auditada; `pseudo_stem` para fuentes con mezcla original; `speech` y `background` para los demás roles.

Grupos `recording_id` y `speaker_id` independientes por split; no reutilizar clips originales aun con semillas o SNR distintos. El registro tiene que aportar rutas locales existentes y SHA-256 verificados. No escribir licencias ficticias. Evitar subir datos privados, audios de voz o licencias restringidas al repositorio público.

## Instrucciones de ejecución (fuentes reales verificadas)

Desde `04_build/selective_audio_lab`, con entorno aislado Python 3.11 y dependencias Numpy/Scipy/SoundFile/Torch instaladas:

```bash
python -m unittest discover -s experiments -p 'm4_*checks.py'
python src/m4_data_gate.py --registry /ruta/audio/m4_sources.csv --out outputs/m4_source_audit.json
python src/train_m4_real.py --registry /ruta/audio/m4_sources.csv --out outputs/m4_real_provisional --epochs 10 --train-steps 60 --val-steps 12 --batch-size 4 --duration 4
```

La última invocación solo procede para **fuentes aisladas verificadas** y después de aprobar la pérdida prospectiva. El entrenador no lee el split test para entrenar ni para seleccionar checkpoints. El script comprueba hashes de todos los archivos durante el gate inicial; este chequeo de integridad no equivale a usar los test como datos del modelo.

Para repetir **el fixture artificial** sin corpus externo (desde la carpeta del paquete):

```bash
python -m unittest discover -s experiments -p "m4_*checks.py" -v
python experiments/run_m4_causal_fixture_smoke.py
```

El fixture crea WAV de senos matemáticos y los etiqueta explícitamente `FIXTURE_TEST_ONLY`. No contiene grabaciones humanas ni sirenas reales. Los umbrales A_target≥6dB/A_protected≤1dB, test independiente, Oracle pareado, 10 min de continuidad, p95/hop y E2E no se consideran cerrados por estas pruebas.

## Decisión GO / NO GO

**GO ingeniería:** frontend y trainer causal compatibles, controles de manifest, pruebas y baseline instrumental. **NO GO científico:** aún faltan corpus aislado con fuentes reales, diversidad, validación de licencias, protocolo loss congelado y test verdaderamente independiente. No forzar un `GO` para cumplir una fecha.
