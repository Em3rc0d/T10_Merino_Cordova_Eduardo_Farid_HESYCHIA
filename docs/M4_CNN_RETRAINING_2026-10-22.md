# HESYCHIA M4 — reentrenamiento y comparación sintética (2026-10-22)

**Clasificación:** experimento de ingeniería de señales *sintéticas*; NO evidencia científica con sirenas/voz real, NO eficacia clínica, NO sistema streaming.

## Protocolo y datos

Se continuó desde el checkpoint synthetic CNN original del 22-oct (Keras 3.13.2/PyTorch 2.10.0+cpu), sin cambiar la arquitectura de 236,833 parámetros (target Embedding 16, Conv1D causal 128 kernel3 dilataciones 1/2/4 y 257 bins sigmoid). Se reentrenó con **4,000 escenas sintéticas** y **1,000 de validación**, en **25 épocas** (batch 32, Adam 5e-4, seed=42). Cinco regímenes balanceados: familiar, interferencia, frecuencias altas, solapamiento espectral con protegida, objetivo ausente. Cada escena dura ~0.31 s y procede de seno/chirp/ruido; **NO hay audios de voz ni sirenas reales**.

Pérdida para esta ablación: MSE(máscara estimada, IRM) + 0.08 × energía espectral de señal protegida retirada por la máscara. **Distinta de L0 contractual PI7**; no trasladar su descenso a cifras científicas de la tesis.

La selección ocurrió únicamente con validación, usando early stopping patience=5 (no activado: se completaron 25 épocas). Loss val con este objetivo: 0.034263 → 0.004163. Tiempo entrenamiento del entorno compartido CPU ~83.24 s, **no Acer ni latencia streaming**.

## Comparación pareada

Tras congelar pesos, se evaluó el checkpoint original y el nuevo sobre **las mismas 600 escenas recién generadas con semillas diferentes**: 100 por cada caso (familiar, interferencia, frecuencia alta, solapamiento, ausente, y nueva sirena FM). La familia FM no figuró en entrenamiento. Los otros tres casos difíciles **ya se conocían de una prueba anterior**; desde este reentrenamiento son *in-distribution* por familia, aunque las escenas concretas sean nuevas.

Criterio por mezcla: A_target ≥6 dB y A_protected ≤1 dB, simultáneamente, con cap=12 dB.

| Caso | Antes: éxitos | Después: éxitos | A_protected antes media | Después media |
|---|---:|---:|---:|---:|
| Familiar | 100/100 | 100/100 | 0.073 dB | 0.057 dB |
| Interferencia | 30/100 | 97/100 | 0.054 dB | 0.035 dB |
| Alta frecuencia (ya añadida a train) | 0/100 | 95/100 | 0.158 dB | 0.012 dB |
| Solapamiento | 1/100 | 62/100 | 3.308 dB | 0.170 dB |
| FM sintética no entrenada | 0/100 | **0/100** | 0.614 dB | 0.166 dB |
| Objetivo ausente | n/a | n/a | ~0.001 dB | ~0.002 dB |

Total escenas target-presente: **131/500 (26.2 %) → 354/500 (70.8 %)**. Errores conjuntos **73.8 % → 29.2 %**; diferencia descriptiva **−44.6 puntos porcentuales**. Cambios pareados: 224 pasaron fallo→éxito, uno éxito→fallo y 275 conservaron el estado. Considerando solo las cuatro familias ya conocidas para el segundo modelo: 131/400 → 354/400.

**Resultado negativo indispensable:** FM sin entrenar 0/100. Este patrón ahora también fue observado en test y no será test ciego si se usa para diseñar otra versión.

## Trazabilidad y limitaciones

- El nuevo checkpoint tiene SHA-256: `20e11a860a8953300b98e232054fb21cf7c7eb6705008d6d49ce9618e8de0c10`.
- El anterior tiene SHA-256: `760d6eedb2531cd4b5663f4e418bd03d3ba931d6dfed4a00974e13e1965a6beb`.
- Auditoría ejecutada de las 600 filas del CSV pareado + SHA-256: PASS.
- Artefactos completos (código exacto, pesos previos/nuevos, CSV por mezcla, WAV, gráficos, logs y manifest SHA-256) están en el paquete local `HESYCHIA_M4_CNN_retraining_2026-10-22.zip`, entregado al usuario en esta conversación. **El binario del modelo NO fue versionado en GitHub**.
- No interpretar el descenso de error como robustez ante sirenas reales ni capacidad de cancelar físicamente ruido. No se verificó inteligibilidad de voz, uso clínico, seguridad, causalidad STFT end-to-end, TFLite, consumo ni latencia p95 por hop.

## Decisión

**PASS del experimento de aprendizaje aumentado dentro de las familias sintéticas abordadas; FAIL de extrapolación FM desconocida.** No aumentar épocas para maquillar el FAIL. Próximo paso: cerrar D0-D5, referencias acústicas limpias/licenciadas, partición por fuentes, entrenamiento L0 o ADR justificada, evaluación independiente real y frontend causal verificado. Se mantienen resultados M2 y Oracle históricos.
