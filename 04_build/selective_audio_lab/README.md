# T10 Selective Audio Lab — PI8+ Increment

Incremento funcional reproducible para la tesis T10, alineado con PI7 v1.1 y las correcciones PI6/PI7.

## Estado funcional actual

Este incremento ya ejecuta realmente:

- **M1 baseline:** audio sintético controlado, 16 kHz, STFT `n_fft=512`, `hop=160`.
- **M3a:** generación de stems y mezcla controlada.
- **M3b:** política `target/protected` con precedencia de protección `BLOCK → g=1`.
- **M4 baseline:** IRM oracle desde stems conocidos, ganancia acotada e iSTFT.
- **M6:** persistencia SQLite v1.2, Run ID, métricas, artefactos y checksums.
- validación automática de integridad del expediente.
- benchmark local del procesamiento del clip completo.

## Límite científico explícito

La IRM actual es una **baseline oracle** y no el estimador CNN final. Su función es demostrar que los contratos DSP, política, reconstrucción y evidencia son ejecutables antes de entrenar M4.

Todavía no se afirma:
- benchmark semántico M2 real;
- máscara aprendida;
- streaming E2E de captura/salida;
- exportación/paridad TFLite;
- perfil físico Honor X8c;
- eficacia clínica.

## Reproducción estricta

Requiere Python 3.11.

```bash
python -m venv .venv
source .venv/bin/activate              # Linux/macOS
# .venv\Scripts\Activate.ps1         # Windows PowerShell

pip install -r requirements-lock.txt
python -m unittest discover -p "test*.py"
python src/run_demo.py --out outputs/demo_run
python src/latency_benchmark.py --out outputs/latency --runs 40
python src/validate_artifacts.py --run-dir outputs/demo_run
```

O:

```bash
bash run_demo.sh
```

## Evidencias generadas

`outputs/demo_run/` incluye:

- `protected.wav`
- `target.wav`
- `background.wav`
- `mixture.wav`
- `output_selective.wav`
- `mask_irm.npy`
- `gain.npy`
- `demo_metrics.csv`
- `artifacts_manifest.csv`
- `demo_summary.json`
- `evidence.sqlite`

La validación vuelve a calcular SHA-256 y comprueba coherencia entre manifiesto, filesystem, Run ID y SQLite.

## Política protegida

La regla central puede probarse de forma independiente:

```bash
python src/run_demo.py \
  --target-label speech_like_synthetic \
  --protected speech_like_synthetic \
  --out outputs/protected_block
```

En ese caso la decisión es `BLOCK` y la ganancia se mantiene unitaria. Esto demuestra que la precedencia de señales protegidas no depende de una predicción automática de M2.

## Resultado CI

El workflow de reproducibilidad ejecuta instalación desde lockfile, tests contractuales, demo, benchmark, validación de artefactos y subida de evidencia. El incremento modular M3b + M6 fue verificado exitosamente en GitHub Actions.
