# Protocolo S8+ — lote de mezclas reales para techo oracle

## Objetivo

Cerrar la observación de evidencia acústica insuficiente causada por un único run sintético.

## Datos

- target: clips reales de clase **siren** de UrbanSound8K;
- protected: voz real de LibriSpeech;
- background: clips UrbanSound8K de `air_conditioner`, `engine_idling` o `street_music`;
- frecuencia de trabajo: 16 kHz;
- duración: 4 s;
- mínimo: 100 mezclas.

## Condiciones

- seed congelada: 42;
- SNR target/protected: -5, 0, +5 y +10 dB;
- background relativo a protected: -10 dB;
- cap sweep: 12, 18, 24 y 30 dB.

## Métricas

- A_target;
- A_protected;
- SI-SDRi protected;
- SI-SDRi target;
- media;
- desviación estándar;
- IC95.

## Interpretación

El experimento sigue usando stems separados para producir la IRM. Por ello mide un **techo oracle** bajo condiciones más realistas de contenido, no el desempeño final de la red aprendida.

El cap de 12 dB no se presenta como umbral clínico. Es un límite de ingeniería preespecificado para la baseline y se somete a análisis de sensibilidad mediante el sweep. No se cambiará retrospectivamente solo porque una configuración suene mejor.

## Ejecución

```bash
python src/real_mixture_oracle_batch.py \
  --dataset-root /ruta/al/UrbanSound8K \
  --speech-root /ruta/a/LibriSpeech \
  --out outputs/m4_real_mixture_oracle_batch \
  --n 100 \
  --target-snrs=-5,0,5,10 \
  --caps=12,18,24,30 \
  --seed 42
```

## Artefactos

- `real_mixture_runs.csv`;
- `real_mixture_aggregate.csv`;
- `real_mixture_summary.json`.

Ninguna cifra debe copiarse a PPT/informe hasta que estos archivos existan tras una ejecución real.