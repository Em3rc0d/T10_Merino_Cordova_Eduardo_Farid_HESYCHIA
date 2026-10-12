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

El código **no reordena ni remezcla** los folds oficiales. La verificación bloqueante se realiza a nivel de ocurrencia etiquetada `(fsID, classID, occurrenceID)`, que es la unidad formada por los slices de una misma ocurrencia. El cruce de un `fsID` entre folds se registra como diagnóstico, no como motivo automático para alterar los folds oficiales.

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
- integridad de folds a nivel de ocurrencia etiquetada `(fsID, classID, occurrenceID)`;
- diagnóstico de `fsID` reutilizados entre folds;
- extracción de features;
- entrenamiento SVM/RF;
- selección por validación;
- evaluación test;
- generación de evidencias.

**Ese fixture es una prueba de software, no evidencia experimental de UrbanSound8K.**  
La evidencia científica de M2 solo se considera producida cuando se ejecuta el mismo pipeline sobre la distribución completa oficial.


## Comparabilidad metodológica

La tesis congela un **holdout por folds oficiales**: 1–8 para entrenamiento, 9 para selección/validación y 10 para test final. Este protocolo evita fuga entre los conjuntos definidos para esta investigación y permite reservar un test que no participa en la selección.

No debe describirse como **validación cruzada de 10 folds**. Por tanto, un Macro-F1 obtenido aquí **no es directamente comparable** con publicaciones que promedian desempeño mediante otro protocolo de evaluación, aun cuando usen el mismo dataset. Cualquier comparación externa debe declarar explícitamente la diferencia de protocolo.

## Trazabilidad adicional del benchmark

Cada ejecución genera además:

- SHA-256 de `metadata/UrbanSound8K.csv`;
- conteo de clips por fold y por split;
- SHA-256 del modelo seleccionado;
- `benchmark_manifest.json` con hashes de los CSV/modelo generados;
- versión de Python/NumPy/Pandas observada en el run.

Esto identifica la evidencia producida sin convertir el fixture CI en evidencia científica del dataset real.


## Hallazgo de integridad en la distribución oficial

La copia descargada y verificada por checksum MD5 oficial `9AA69802BBF37FB986F71EC1483A196E` contiene 8,732 filas, 10 folds, 10 clases y cero audios faltantes.

Se observaron cinco `fsID` presentes en más de un fold:

```text
77751  -> folds 2, 7
106905 -> folds 1, 8
132016 -> folds 1, 4
176638 -> folds 1, 4
180937 -> folds 1, 9
```

En estos casos, el mismo Freesound ID participa con **clases objetivo distintas**. El archivo oficial no se modifica ni se reagrupa para “corregir” este comportamiento, ya que la recomendación del dataset es conservar los folds predefinidos.

La protección contra leakage del pipeline se define por la ocurrencia etiquetada:

```text
occurrence_key = (fsID, classID, occurrenceID)
```

Los distintos `sliceID` de una misma ocurrencia deben permanecer en un único fold. Si una misma `occurrence_key` aparece en dos particiones, el benchmark se bloquea.

El cruce de `fsID` entre clases diferentes se conserva como **diagnóstico de la distribución**, no como criterio para remezclar los datos.

## Nota sobre protocolo oficial y protocolo de tesis

La documentación oficial de UrbanSound8K recomienda 10-fold cross-validation sobre los folds predefinidos para comparabilidad con la literatura. El protocolo PI7 de esta tesis permanece, por ahora, como holdout 1–8/9/10 para selección/test interno. Por ello:

- no se llama “10-fold cross-validation” al resultado principal de PI7;
- no se reclama comparabilidad directa con publicaciones que reportan el promedio de los 10 folds;
- se recomienda incorporar posteriormente un benchmark secundario 10-fold para comparabilidad, sin alterar retrospectivamente RNF-03.

## Resultado real congelado — 2026-10-12

La distribución oficial completa fue validada y el benchmark se ejecutó con seed 42.

Selección en fold 9:

| Modelo | Macro-F1 | Macro-Recall | Macro-Precision | Accuracy |
|---|---:|---:|---:|---:|
| SVM RBF | **0.7146** | **0.7227** | 0.7163 | **0.6912** |
| Random Forest | 0.6795 | 0.6813 | **0.7065** | 0.6691 |

Modelo seleccionado: **SVM RBF**.

Test fold 10:

| Métrica | Valor |
|---|---:|
| Macro-F1 | **0.7257** |
| Macro-Recall | 0.7170 |
| Macro-Precision | 0.7426 |
| Accuracy | 0.7145 |

RNF-03: **NO CUMPLE** para esta baseline (`0.7257 < 0.85`).

Este resultado queda congelado como baseline real. El umbral no se cambia y el fold 10 no debe usarse para seleccionar cambios posteriores. Detalle: `docs/M2_REAL_RESULT_2026-10-12.md`.
