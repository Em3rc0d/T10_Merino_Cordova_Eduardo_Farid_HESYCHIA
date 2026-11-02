# M4 con audio real — candidatos de investigación

Estos pesos se entrenaron sobre grabaciones reales, mezcladas digitalmente con
referencias conocidas. No sustituyen los checkpoints históricos PI9/PI10.
La condición de candidato no equivale a aprobación científica de selectividad.

**Resultado: REWORK.** El candidato seleccionado por validación (`seed61`)
cumple ambos criterios en 1/48 escenas elegibles de test. Medianas: 2.529 dB
de atenuación objetivo y 1.127 dB de pérdida de voz. Ver el informe
`docs/M4_SCI_REAL_RESULTS_2026-10-27.md` en la raíz del repositorio.

## Candidatos de cobertura completa

`seed61`, `seed62` y `seed63` repiten el entrenamiento con las 32 combinaciones
acústicas. `mask_mse61` y `no_class61` son sus controles. `selection.json` fija
el candidato elegido por validación; `selected/` conserva exactamente esos pesos.
El detector corregido y su calibración están en `events_v2`.

## Desarrollo anterior conservado

- `seed41`, `seed42`, `seed43`: CNN temporal causal, pérdida compuesta y etiqueta
  condicionante; tres inicializaciones y órdenes de minibatches independientes.
- `mask_mse`: control de pérdida MSE, seed 41.
- `no_class`: control sin información de clase; el predictor fuerza etiqueta 0.
- `spectral*_development`: variante con convoluciones separables en frecuencia/tiempo;
  contextos de entrenamiento con calentamiento causal y tres semillas.
- `events141`: detector multietiqueta experimental offline y calibración exclusiva
  en validación. No es un detector streaming ni una garantía de protección.

Cada carpeta conserva los pesos y los archivos originales de su entrenamiento.
Las corridas nuevas que incluyen `source_snapshot` preservan sus módulos exactos.
Los hashes y las métricas distinguen desarrollo, validación y test congelado.
La variante espectral se propuso tras observar los fallos de validación de la
temporal; el test reservado no intervino en esa decisión.

## Corpus y alcance

Se usaron candidatos ESC-50 de aspiradora/motosierra y habla Mini LibriSpeech.
Los sonidos ambientales son pseudo-stems pendientes de escucha y aislamiento;
no se atribuye calidad de fuentes puras a sus etiquetas. La evaluación tiene
alcance de benchmark experimental y no demuestra eficacia clínica en TEA.

ESC-50: colección CC BY-NC 3.0, con atribuciones por clip preservadas en el
registro. Mini LibriSpeech: CC BY 4.0, Panayotov, Chen, Povey y Khudanpur (2015).
El uso previsto de estos candidatos es investigación académica. No se incluyen
audios de terceros en Git; reconstruir los datos mediante el runbook.

## Ejecutar

Desde `04_build/selective_audio_lab`, con `requirements-scientific.txt`:

```bash
python src/m4_science.py predict --checkpoint models/m4_sci_real_candidate_v1/selected/candidate.pt --input /ruta/mezcla.wav --target vacuum_cleaner --out outputs/prueba.wav
```

El objetivo se configura explícitamente. Para probar el gate M2, añadir
`--event-checkpoint models/m4_sci_real_candidate_v1/events_v2/events.pt` y
`--event-calibration models/m4_sci_real_candidate_v1/events_v2/calibration.json`.
`--block-protected` fuerza bypass antes de cargar los pesos M4.

Protocolo y comandos completos: `docs/M4_SCIENTIFIC_CANDIDATE_RUNBOOK.md` desde
la raíz del repositorio. La salida es procesamiento offline de referencia;
no constituye captura/reproducción en vivo ni prueba de latencia física.

Dos variantes espectrales se detuvieron al detectarse el hueco de cobertura V1. Sus resúmenes y estados distinguen esa interrupción de un entrenamiento completado. Los controles antiguos se evalúan en el mismo test V2, registrando su contrato de entrenamiento distinto.
