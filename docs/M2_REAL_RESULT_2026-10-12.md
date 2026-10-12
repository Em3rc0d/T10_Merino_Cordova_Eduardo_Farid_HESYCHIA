# M2 — resultado real UrbanSound8K — baseline clásica

**Fecha de ejecución:** 2026-10-12  
**Run ID:** `M2-US8K-BASELINE-001`  
**Dataset:** UrbanSound8K oficial completo  
**Estado:** EVIDENCIA REAL MEDIDA · RNF-03 NO CUMPLIDO POR LA BASELINE

## Integridad del dataset

| Evidencia | Resultado |
|---|---:|
| Filas | 8,732 |
| Folds | 1–10 |
| Clases | 10 |
| Audio faltante | 0 |
| Forma oficial | OK |
| Filename ↔ metadata | OK |
| Ocurrencias etiquetadas cruzando folds | 0 |
| `fsID` cross-fold diagnósticos | 5 |
| Cross-fold `fsID` solo entre clases distintas | Sí |
| MD5 del archivo oficial | `9AA69802BBF37FB986F71EC1483A196E` |
| SHA-256 de metadata | `b207f7a53f9e5eb02a5dd71d58fb8b66c88c24c0637b926dc72d9d400a6a2354` |

Los folds oficiales se preservaron sin reshuffle. El guard bloqueante de leakage se aplicó a la ocurrencia etiquetada `(fsID,classID,occurrenceID)`.

## Partición usada

| Split | Folds | Clips |
|---|---|---:|
| Train | 1–8 | 7,079 |
| Validation | 9 | 816 |
| Test | 10 | 837 |

## Selección en fold 9

| Modelo | Macro-F1 | Macro-Recall | Macro-Precision | Accuracy | Fit (s) |
|---|---:|---:|---:|---:|---:|
| SVM RBF | **0.7146** | **0.7227** | 0.7163 | **0.6912** | 1.1413 |
| Random Forest | 0.6795 | 0.6813 | **0.7065** | 0.6691 | 4.8791 |

Regla congelada: máximo Macro-F1 de validación y luego Macro-Recall. Se seleccionó **SVM RBF**.

## Test fold 10

| Métrica | Resultado |
|---|---:|
| Macro-F1 | **0.7257233296** |
| Macro-Recall | 0.7170204454 |
| Macro-Precision | 0.7425609153 |
| Accuracy | 0.7144563919 |

Hash del modelo seleccionado:

`32869707f34a803b79cdee9eb8d9ed982011f6462899783343650d49b18b5ccf`

## RNF-03

Objetivo preespecificado: `Macro-F1 test >= 0.85`.

Resultado observado: `0.7257 < 0.85`.

**Veredicto de la baseline: RNF-03 NO CUMPLIDO.**

El umbral no se modifica. Este resultado no invalida el proyecto: demuestra que la baseline clásica SVM/RF no es suficiente para el objetivo de ingeniería y justifica continuar con el candidato aprendido ya previsto en PI7.

## Regla anti-leakage después de observar fold 10

El fold 10 ya fue abierto para esta baseline y su resultado queda congelado. A partir de este punto:

1. no seleccionar hiperparámetros ni arquitectura usando el resultado de fold 10;
2. cualquier mejora debe justificarse y seleccionarse con train/validation o un protocolo de desarrollo separado;
3. registrar antes de una nueva evaluación test la configuración candidata que se va a probar;
4. reportar explícitamente que el fold 10 ya había sido observado en la baseline;
5. usar un benchmark secundario 10-fold, si se incorpora, para comparabilidad con literatura, sin reescribir retroactivamente RNF-03.

## Interpretación correcta

- Este resultado corresponde a **M2 reconocimiento semántico**.
- No localiza bins tiempo–frecuencia.
- No controla automáticamente M4.
- No es evidencia clínica.
- No es el modelo final de atenuación.
- Sí cumple la exigencia S8 de contar con un modelo base procesando audio real y primeras métricas reproducibles.

## Entorno observado

- Python 3.11.9
- NumPy 2.4.6
- Pandas 3.0.6

## Artefactos producidos localmente

- `semantic_summary.json`
- `validation_models.csv`
- `confusion_matrix_test_fold10.csv`
- `predictions_test_fold10.csv`
- `svm_rbf_selected.joblib`
- `benchmark_manifest.json`
- feature cache versionado

Para incorporar gráficos de clase/confusión a la PPT se debe usar `confusion_matrix_test_fold10.csv`; no inferir ni dibujar la matriz sin ese archivo.