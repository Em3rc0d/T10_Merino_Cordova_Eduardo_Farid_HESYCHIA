# M2 — Protocolo UrbanSound8K

## Propósito

M2 evalúa **reconocimiento semántico de eventos acústicos**. Su salida no localiza bins tiempo–frecuencia y no modifica automáticamente el target de M4.

## Dataset contractual

**UrbanSound8K** es el benchmark principal de M2.

Contrato esperado de la distribución oficial:

- 8,732 clips etiquetados;
- duración de hasta 4 s;
- 10 clases;
- folds oficiales 1–10;
- metadata en `metadata/UrbanSound8K.csv`;
- audio en `audio/fold1` … `audio/fold10`.

Clases:

0 air_conditioner  
1 car_horn  
2 children_playing  
3 dog_bark  
4 drilling  
5 engine_idling  
6 gun_shot  
7 jackhammer  
8 siren  
9 street_music

Fuente primaria: Urban Sound Datasets / NYU.  
Referencia: Salamon, Jacoby & Bello (2014), *A Dataset and Taxonomy for Urban Sound Research*.

## Partición congelada de tesis

No se usa `random_split`.

```text
folds 1–8 → entrenamiento
fold 9     → validación / selección de candidato
fold 10    → test final
```

El código verifica además que `fsID` no cruce train/validation/test.

## Representación baseline

Para el primer benchmark clásico:

- mono;
- 16 kHz;
- hasta 4 s, zero-pad si es más corto;
- STFT: `n_fft=512`, `hop=160`;
- MFCC: 20 coeficientes;
- log-Mel: 64 bandas;
- vector fijo: media + desviación estándar de MFCC y log-Mel.

Esta representación sirve a los baselines clásicos. No sustituye el diseño del candidato CNN posterior.

## Baselines ejecutables

### SVM RBF

- escalado estándar;
- `C=10`;
- `gamma=scale`;
- kernel RBF.

### Random Forest

- 300 árboles;
- `max_features=sqrt`;
- `class_weight=balanced_subsample`;
- seed congelada.

La selección se realiza **solo con fold 9** mediante Macro-F1 y, en empate, Macro-Recall. El fold 10 se evalúa una vez después de seleccionar el candidato.

## Métricas

- Macro-F1;
- Macro-Recall;
- Macro-Precision;
- Accuracy;
- matriz de confusión.

RNF-03 mantiene como objetivo de ingeniería:

```text
Macro-F1 test >= 0.85
```

Si el benchmark real no lo alcanza, se registra como incumplimiento. No se reajusta el umbral después de observar el test.

## Ejecución con el dataset real

Estructura:

```text
/path/UrbanSound8K/
├── metadata/
│   └── UrbanSound8K.csv
└── audio/
    ├── fold1/
    ├── ...
    └── fold10/
```

Validación:

```bash
cd 04_build/selective_audio_lab
python src/validate_urbansound8k.py --dataset-root /path/UrbanSound8K
```

Benchmark:

```bash
python src/semantic_benchmark.py \
  --dataset-root /path/UrbanSound8K \
  --out outputs/m2_urbansound8k \
  --seed 42
```

## Evidencias generadas

- `semantic_summary.json`
- `validation_models.csv`
- `confusion_matrix_test_fold10.csv`
- `predictions_test_fold10.csv`
- modelo seleccionado `.joblib`
- cache de features versionable por configuración

## Estado de verificación

El pipeline M2 se prueba automáticamente con un fixture de audio que conserva el contrato de folds y clases oficiales para verificar:

- lectura de metadata;
- construcción de paths;
- no leakage por `fsID`;
- extracción de features;
- entrenamiento SVM/RF;
- selección por validación;
- evaluación test;
- generación de evidencias.

**Ese fixture es una prueba de software, no evidencia experimental de UrbanSound8K.**  
La evidencia científica de M2 solo se considera producida cuando se ejecuta el mismo pipeline sobre la distribución completa oficial.
