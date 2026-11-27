# HESYCHIA · runbook final de cierre científico

Este runbook no abre el test confirmatorio. El orden es obligatorio.

## Gate A — OE1

1. Restaurar/verificar PCM del corpus.
2. Reproducir la muestra audit_93 y comprobar identidad canónica.
3. Revisor A y Revisor B (personas distintas) completan los 93 audios de forma independiente.
4. Calcular Cohen κ antes de adjudicar.
5. Adjudicar discrepancias, generar final_review_93.csv y contamination_93.json.
6. No continuar si κ < 0.60 sin resolver/documentar el gate.

## Gate B — targets externos

Después de cerrar OE1:

1. preparar el reserve pool externo preseleccionado;
2. escuchar cada target externo y marcar pureza sin consultar ninguna salida del modelo;
3. conservar todos los ELIGIBLE;
4. exigir >=20 source_group independientes y ambas clases;
5. preparar >=4 hablantes LibriSpeech externos al desarrollo.

## Gate C — OE3 físico

En la Acer Nitro 5 ejecutar:

```bash
python experiments/pi13_pi14/scripts/pi15_local_closure.py benchmark-acer \
  --out experiments/pi13_pi14/outputs/m4_forward_acer \
  --runs 100 --warmup 8 --threads 4
```

Debe producir >=1000 bloques y p50/p95/p99 + RTF con device_label Acer Nitro 5.
No equivale a streaming físico E2E.

## Gate D — freeze

Generar plantillas DSP solo con corpus ya auditado. Crear el freeze externo
incluyendo el protocolo `docs/PI15_SIGNAL_METRICS_PROTOCOL_2026-11-27.md`.
Ejecutar preflight fail-closed. No abrir el test si existe cualquier blocker.

## Gate E — campaña one-shot OE2

Solo con Gate D en PASS:

```bash
python experiments/pi13_pi14/scripts/pi15_confirmatory_campaign.py \
  --freeze <PI15_EXTERNAL_FREEZE.json> \
  --out experiments/pi13_pi14/outputs/confirmatory_final
```

La primera ejecución crea TEST_OPENED_DO_NOT_TUNE. No se repite para ajustar
modelo, baseline, umbrales o datos. Resultados negativos son resultados finales
válidos.

## Gate F — readiness

Ejecutar `pi15_jury_readiness.py` con audit_93, kappa, contaminación, freeze,
confirmatory_analysis, CP02 y benchmark Acer. READY significa cierre estructural
de evidencia; nunca eficacia clínica.

## Entregables finales

- CSV por escena CNN/DSP/Oracle;
- confirmatory_analysis.json con bootstrap 10 000;
- CP02 y CP10;
- tabla A_target/A_protected/SI-SDRi/SNR/STOI/PESQ;
- benchmark Acer p50/p95/p99/RTF;
- gráficos con IC95%;
- Word de tesis actualizado;
- PPT y video liviano;
- commit final + tag v1.0-tesis.
