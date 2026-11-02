# M4 científico: adquisición, entrenamiento y evaluación reproducible

Estado: candidato experimental con audio real. La aprobación de ingeniería y la
evaluación acústica son decisiones distintas. Los pesos PI9/PI10 se conservan.
P2 streaming sigue dependiendo de un GO científico documentado.

## Qué se implementó

- Corpus de grabaciones reales con SHA-256 original/PCM, procedencia, licencia,
  atribución por clip y partición por grabación/hablante antes de mezclar.
- Aspiradora y motosierra como clases candidatas de esta corrida. La propuesta de
  perforación no se presenta como entrenada: requiere fuentes aisladas suficientes.
- Voz humana de Mini LibriSpeech SLR31. Su partición experimental es por identidad
  de hablante; no se atribuye al corpus una evaluación en español ni clínica.
- Mezclas reproducibles con clases concurrentes, objetivo ausente, voz ausente,
  fondos, alertas y solapamiento parcial. Las escenas de test no se usan en fit.
- CNN temporal causal condicionada por clase y candidato espectral separable.
  STFT anclada al pasado, 16 kHz, NFFT=512, hop=160, sqrt-Hann y compresión fija;
  no máximos de clip ni normalización temporal global.
- AdamW, selección por validación fija, early stopping, gradientes finitos,
  checkpoints y manifiestos independientes por semilla. No sobrescribir corridas.
- Pérdida MSE como ablation frente a reconstrucción compleja + protección del habla.
- Detector M2 experimental multietiqueta: aspiradora, motosierra, habla y alerta.
  Sus umbrales usan únicamente validación. El pooling es de clip completo:
  **este M2 no constituye reconocimiento streaming**.
- Dos modos: objetivo configurado con alertas anotadas y objetivo solicitado con
  gate estimado M2 → política → M4. El segundo mide errores del detector.
- Política M3b candidata versionada, que incorpora las etiquetas protegidas de
  S10-A y mantiene las clases nuevas en un catálogo de investigación separado.
  No se altera el catálogo de la demo histórica para declarar aprobación formal.
- Inferencia CLI sobre WAV/FLAC sin stems limpios; BLOCK precede la carga de M4.
- Freeze inmutable y test de un solo intento, comparación pareada con DSP,
  entrada sin procesar y Oracle informado por stems. El CNN histórico solo conoce
  `drilling_synthetic`: no se inventa una equivalencia con las clases nuevas.

## Fuentes y revisión del corpus

ESC-50 se fija al commit `33c8ce9eb2cf0b1c2f8bcf322eb349b6be34dbb6`.
Se respetan sus folds por `src_file`: 1–3 train, 4 val, 5 test. Su licencia de
colección es CC BY-NC 3.0; `LICENSE` conserva atribuciones y condiciones por clip.
El material se utiliza en investigación académica y no se redistribuye en Git.

Las clases de ESC-50 proceden de grabaciones de campo etiquetadas. **Una etiqueta
no prueba aislamiento de fuente**: estos clips son `pseudo_stem` candidatos y
requieren revisión auditiva. No se cambian a `isolated` para obtener un PASS.
El gate automático comprueba bytes, PCM normalizado exacto y grupos declarados;
la búsqueda de duplicados recortados/perceptuales sigue requiriendo revisión.

SLR31 se descarga del publicador OpenSLR y se verifica contra su MD5 publicado;
además se archiva SHA-256. La licencia declarada por el publicador es CC BY 4.0.
Se seleccionan hasta cuatro clips por hablante, tras separar las identidades.
El test reservado dentro de estos corpus no sustituye una prueba de campo de
dominio independiente.

Referencias primarias:

- https://github.com/karolpiczak/ESC-50
- https://github.com/karolpiczak/ESC-50/blob/33c8ce9eb2cf0b1c2f8bcf322eb349b6be34dbb6/LICENSE
- https://www.openslr.org/31/
- https://www.openslr.org/resources/31/md5sum.txt

## Preparar entorno y datos

Desde `04_build/selective_audio_lab`, Python 3.12 en entorno aislado:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-scientific.txt
python -m pytest -q test_m4_scientific.py
python src/m4_science.py prepare --root data/m4_sci --counts 1600 160 160 --seconds 2
```

La regresión completa de la demo histórica requiere las dependencias opcionales
`requirements-scientific-qa.txt`; ejecutar `python -m pytest -q` con backend Keras
Torch. Dos pruebas históricas dependen de un `paired.csv` local no versionado;
sus omisiones deben informarse, sin presentarlas como pruebas ejecutadas.

`prepare` descarga 240 clips ESC-50 de seis categorías y el archive SLR31
train-clean-5. Conserva originales y evidencias. Produce registro, auditoría,
recetas y plantilla `human_review.csv`. La conversión a PCM no certifica pureza.
Si el directorio ya contiene un registro, se debe crear una nueva versión;
el pipeline no sustituye silenciosamente un corpus congelado.

La primera corrida preservada utilizó FLOAT-WAV de libsndfile, cuyo chunk PEAK
incluye fecha de creación: una reconstrucción puede cambiar el hash del contenedor
sin cambiar ninguna muestra. Se verificaron por separado audio y recetas; el
reporte `corpus_reproduction.json` distingue esa igualdad de la identidad de bytes
del contenedor. El conversor actual usa FLOAT-WAV determinista de scipy. Esto
produce una revisión nueva del registro, sin reescribir registros o checkpoints
anteriores. Para repetir el entrenamiento, preparar un corpus nuevo y conservar
sus propios hashes; no sustituir el registro de una evaluación ya congelada.

## Entrenar y comparar en validación

El flag siguiente permite ejecutar un **piloto declarado con revisión pendiente**;
no transforma los pseudo-stems en fuentes aisladas aprobadas.

```bash
python src/m4_science.py train --out outputs/m4_sci/seed61 --seed 61 --pilot-unreviewed
python src/m4_science.py train --out outputs/m4_sci/seed62 --seed 62 --pilot-unreviewed
python src/m4_science.py train --out outputs/m4_sci/seed63 --seed 63 --pilot-unreviewed
python src/m4_science.py train --out outputs/m4_sci/mask_mse61 --seed 61 --loss mask_mse --pilot-unreviewed
python src/m4_science.py train --out outputs/m4_sci/no_class61 --seed 61 --conditioning none --pilot-unreviewed
python src/m4_science.py train --config configs/m4_sci_spectral.json --out outputs/m4_sci/spectral51 --pilot-unreviewed
python src/m4_science.py train-events --out outputs/m4_sci/events_v2 --pilot-unreviewed
```

Ejecutar secuencialmente en máquinas de RAM limitada. La caché de tensores está
respaldada por archivos y puede compartirse; las corridas no comparten pesos.
Cada seed inicializa pesos y orden de minibatches. Los manifests conservan el
contrato y hashes; los nuevos runs conservan copia del código de entrenamiento.

Para comparar funciones de pérdida se usan las mismas métricas acústicas,
**no se comparan numéricamente escalas de pérdida distintas**:

```bash
python src/m4_science.py validate --checkpoints outputs/m4_sci/seed61/candidate.pt outputs/m4_sci/seed62/candidate.pt outputs/m4_sci/seed63/candidate.pt --out outputs/m4_sci/validation
```

La selección usa cumplimiento conjunto por escena en validación, luego menor
violación del límite de habla y mayor atenuación. No utiliza test. Las variantes
añadidas después de observar validación son exploración declarada.

## Congelar y evaluar una sola vez

```bash
python src/m4_science.py freeze --checkpoints outputs/m4_sci/seed61/candidate.pt outputs/m4_sci/seed62/candidate.pt outputs/m4_sci/seed63/candidate.pt --event-checkpoint outputs/m4_sci/events_v2/events.pt --event-calibration outputs/m4_sci/events_v2/calibration.json --out outputs/m4_sci/freeze_test.json
python src/m4_science.py evaluate --freeze outputs/m4_sci/freeze_test.json --out outputs/m4_sci/test
```

La congelación fija pesos, recetas, corpus, código de evaluación, política y los
umbrales vigentes A_target≥6 dB y A_protected≤1 dB. La marca de intento se crea
antes de decodificar test. Un intento fallido no autoriza ajustar y reutilizar ese
test; cualquier corrección debe explicar la exposición y reservar otro test.

El reporte conserva CSV por escena y semilla, fallos, resultados por clase,
intervalos bootstrap por fuente/hablante, controles sin target, audio comparativo,
clasificación M2, errores sobre alertas y efectos de intercambiar la clase.

Las ganancias se estiman una vez sobre la mezcla. Para A_target y A_protected se
aplican esas mismas ganancias a las referencias: **no se reinfiere sobre cada
stem**. SI-SDRi y STOI se calculan además sobre la salida mezclada real respecto
al habla. SI-SDR es invariante a escala y no sustituye la atenuación en dB.
Los intervalos no resuelven completamente la dependencia cruzada entre hablantes
y fuentes; se informa ese límite y el número efectivo de grupos.

## Probar un audio propio

```bash
python src/m4_science.py predict --checkpoint outputs/m4_sci/seed62/candidate.pt --input /ruta/mezcla.wav --target vacuum_cleaner --out outputs/prueba.wav
```

Para el gate M2 estimado añadir `--event-checkpoint .../events.pt` y
`--event-calibration .../calibration.json`. Para protección explícita,
`--block-protected` devuelve el PCM mono/remuestreado sin llamar a M4.
No hay fallback a Oracle cuando faltan pesos. El detector experimental puede
equivocarse; sus errores y bloqueos conservadores se deben medir.

## Alcance del cierre

Una CNN entrenada y pruebas de software exitosas no bastan para GO. Faltan cerrar
la revisión humana, independencia de campo, suficiencia de fuentes por clase,
criterios acústicos, reconocimiento y protección integrados y conformidad
académica con clases/arquitectura/pérdida propuestas. Las salidas actuales se
identifican como candidatos; el reporte no emite GO automático.

No se ha implementado P2 en este incremento. El framing causal de entrenamiento
y el WOLA offline no prueban p95/hop, latencia física, captura en vivo ni Android.

## Revisión de cobertura V2 y conservación del desarrollo

La cohorte inicial se conserva como desarrollo: su diseño omitía voz sin ambos
ruidos y alertas con objetivo ausente. La auditoría `legacy_condition_gaps.json`
registra esas ausencias. Dos corridas espectrales se detuvieron por esa revisión
de datos; sus resúmenes lo declaran y no se presentan como repeticiones completas.

La cohorte V2 utiliza un diseño factorial de 32 combinaciones por partición
(clase solicitada × presencia de objetivo × otro ruido × habla × alerta).
Incluye voz limpia y silencio. Cada test de 160 escenas contiene 8 controles de
silencio; el reporte diferencia esas escenas de las mezclas de grabaciones reales.
Las semillas 61, 62 y 63 son los candidatos elegibles del entrenamiento corregido;
los otros modelos y las ablaciones permanecen en la comparación como controles.
La selección se hace antes del test, exclusivamente con validación.

Para reproducir exactamente los contenedores del corpus archivado, preparar los
audios en una carpeta física nueva y ejecutar:

```bash
python src/m4_science.py restore-frozen-corpus --root data/m4_sci --registry ../../05_evidence/m4_sci_real_2026-10-27/v2/registry.json --containers ../../05_evidence/m4_sci_real_2026-10-27/pcm_containers.json
```

Se preservan los registros previos, se verifican las muestras reconstruidas contra
los SHA-256 originales y se restauran las recetas archivadas. El recibo conserva
la fecha real de reproducción; los encabezados retienen únicamente los metadatos
del contenedor original. El archivo de encabezados no contiene muestras de audio.
