# HESYCHIA · Iteración de robustez de CNN M4

**Fecha:** 2026-10-22. **Naturaleza:** prueba exploratoria de ingeniería sobre señales procedurales; NO resultado científico de tesis ni validación clínica. **No modifica la tesis, M2, su arquitectura M4 congelada ni los umbrales.**

## Motivación y técnicas aprovechadas

Se adaptaron prácticas generales de ingeniería acústica: negativos difíciles explícitos, control por familia, semillas disjuntas, preservación del test, auditoría pareada y trazabilidad de checkpoints. No se copió ni integró código de modelos clasificadores externos, ni se incorporaron funcionalidades de detección y clasificación de otro proyecto. El propósito exclusivo sigue siendo M4: estimar la máscara tiempo-frecuencia de atenuación y preservar una señal protegida.

## Diseño

CNN **sin alterar arquitectura**: 236833 parámetros, entrada magnitud espectral 257 bins/32 frames, embedding 16, tres Conv1D causales 128 canales con dilataciones 1/2/4, máscara sigmoid. Inicializada desde pesos anteriores (SHA-256 `20e11a860a8953300b98e232054fb21cf7c7eb6705008d6d49ce9618e8de0c10`). Entrenamiento adicional CPU con 1650 escenas de train, 330 de validación, 12 épocas, Adam lr=0.0004, batch=32, semilla=42. Todas las señales son artificiales (tonos, chirps, ruido) y duran unos 0.31 segundos. Ninguna pista de voz, alarma ni sirena procede de grabación del mundo real.

Las familias de entrenamiento incluyeron barridos familiares, alta frecuencia, interferencia, solapamiento, FM, sirenas pulsantes, objetivo ausente, alarma de automóvil, beeper de marcha atrás, silbatos y música sintética. Los negativos se etiquetan con **target=0**. La etiqueta IRM usa fuentes separadas solo para entrenamiento/referencia, jamás como entrada al modelo. La función de pérdida es MSE(máscara, IRM) + 0.08 × penalización espectral sobre la señal protegida, variante experimental y **no** la L0 del protocolo PI7. El frontend conserva STFT centrada **offline**: no se ha integrado todavía causalidad de streaming extremo a extremo.

## Evaluación pareada

Se emplearon exactamente las mismas 275 escenas procedurales para el checkpoint anterior y el nuevo, con semilla diferente de entrenamiento/validación. Hay 175 escenas con target y 100 sin target; las familias nuevas OOD están predefinidas en código y no se usan para selección ni entrenamiento. Los casos FM y otras familias problemáticas ya se conocían por experimentos anteriores; por tanto, la prueba no es ciega en el sentido científico. Éxito por escena presente: A_target >= 6 dB **y** A_protected <= 1 dB con cap=12 dB.

| Familia (25 escenas cada una) | Antes | Después | Observación |
|---|---:|---:|---|
| Familiar | 25 | 25 | Sin cambios |
| Interferencia | 23 | 22 | 1 regresión neta |
| Solapamiento | 21 | 21 | Igual éxito, atenuación protegida media empeoró |
| FM (conocida e incorporada a train) | 1 | 11 | Mejora dentro de familia ahora conocida |
| Objetivo pulsante | 1 | 13 | Mejora dentro de familia ahora conocida |
| Sirena dual OOD | 0 | **0** | Falla no resuelta |
| Sirena pulsante irregular OOD | 0 | 15 | Señal alentadora en este generador |

**Total positivo:** 71/175 = 40.57% → 107/175 = 61.14%. Error conjunto: 59.43% → 38.86%, reducción descriptiva **20.57 puntos porcentuales**. Transiciones: 40 fallos que pasan a éxito, 4 éxitos que pasan a fallo, 67 aciertos estables y 64 fallos estables. NO extrapolar porcentajes a sirenas reales, personas con TEA ni escenarios clínicos.

**100 escenas sin target:** máscara media anterior = 0.10549, nueva = 0.02299. Se contabilizaron 0 casos con A_protected > 1dB en esos 100 negativos para ambos modelos, pero una máscara menor es solamente una aproximación instrumental de menor supresión indebida; no demuestra false-positive rate de eventos ni seguridad de escucha. Son familias de alarma de automóvil, beeper, silbato y un confusor agrupado OOD.

### Limitaciones graves

- Las fuentes/etiquetas son generadores simples, NO audio de voz/sirena real, ni información clínica.
- Los splits usan seeds distintos, pero siguen compartiendo generador matemático; eso no da independencia acústica por origen.
- La máscara IRM Oracle es privilegiada y no equivale a una cota matemática universal.
- La CNN tiene convolución causal pero la STFT aquí es **centrada** y se evalúan ventanas de 32 frames, no streaming real por hop; no se midió latencia E2E, ni Android, ni TFLite.
- La loss no es L0 del protocolo PI7, por lo que este checkpoint es **experimental, no modelo final de tesis**.
- La sirena dual falló en 25/25 casos. Tampoco mejoró el solapamiento por cantidad de aciertos y ocurrió una regresión en interferencia. No se deben ocultar estos fallos.
- Ya se inspeccionaron los resultados de esta evaluación: no usar sus escenas como test final ciego en entrenamientos posteriores.

## Evidencia

- SHA-256 nuevo checkpoint: `290f9b50b6c718238abc22860ed96e04841a9458cac0cbcfe7c2eee2a413edb6`.
- Auditor `audit_m4_robustness.py`: **PASS**; 275 filas, 175 positivas, 100 negativas, 71/107 éxitos, hashes correctos y flags verificadas contra umbrales.
- **8 tests unitarios** PASS: shapes, finitud, negativos target=0, seeds, familias OOD excluidas, loss target-absent, auditor real y detección de datos manipulados.
- Artefactos: `results.json`, `paired.csv`, `learning_curve.csv`, checkpoint H5, WAV sintéticos de muestra, scripts de generación/entrenamiento/test y SHA-256 manifest.
- El paquete de la conversación `HESYCHIA_M4_HARD_NEGATIVE_2026-10-22.zip` contiene exactamente el código ejecutable adaptado y los resultados; NO se redistribuyeron grabaciones con licencias de terceros.

## Reproducción

```bash
cd experiments
export KERAS_BACKEND=torch
python -m unittest discover -p 'test_m4_robustness*.py'
python m4_robustness_iteration.py \
  --previous-weights ../previous/m4_augmented.weights.h5 \
  --out ../results_repeated --train 1650 --val 330 --epochs 12 \
  --test-per-family 25 --seed 42 --threads 2
python audit_m4_robustness.py --folder ../results_repeated
```

En Windows PowerShell, reemplazar `export` con `$env:KERAS_BACKEND='torch'`, y adaptar rutas. Los pesos previos están incluidos en el ZIP entregado. Las versiones verificadas en este entorno: Python3.13, keras3.13.2, torch2.10.0+cpu, numpy2.3.5, scipy1.17.0, soundfile0.13.1, h5py3.15.1; el entrenamiento en otro equipo puede producir variaciones numéricas.

**Próximo gate verdadero:** datos de fuentes aisladas con licencias/procedencia verificadas + manifiestos agrupados sin leakage, frontend STFT/OLA causal compartido entrenamiento/inferencia, loss L0 estabilizada o ADR previa, test real sellado, comparación pareada Oracle, TFLite/paridad y benchmarks por hop y E2E.
