# Proceso M4-v1 de admisión de fuentes (engineering-only)

Esta carpeta contiene tests de fixtures y los comandos para revisar candidatos de fuentes acústicas. No incorpora material de terceros ni declara un dataset aprobado. Ejecutar desde `04_build/selective_audio_lab`:

```bash
python -m unittest discover -s experiments -p 'test_m4_*.py' -v
python src/m4_corpus_intake.py --action inspect --candidates m4_candidate_sources_v1.csv --out outputs/corpus_candidate_audit
python src/m4_corpus_intake.py --action promote --candidates m4_candidate_sources_v1.csv --out outputs/corpus_candidate_audit
```

**Esperado:** 16/16 tests PASS; `promote` devuelve código 2 BLOCKED con 0 fuentes admitidas hasta incorporar audios y revisiones humanas reales. Esto no es un fallo de CI. Para descarga de un preview con SHA conocido, usar `--action download-one --candidate-id FS_117120` en un equipo con acceso a Internet. La conexión a Freesound puede estar filtrada según entorno. Los datos de test deben permanecer sellados y todos los archivos se mantienen fuera de GitHub público.

ADRs, licencias, comentarios metodológicos: `docs/M4_CORPUS_V1_INTAKE_2026-10-22.md` y `docs/ADR_M4_LOSS_NUMERICAL_STABILITY_2026-10-22.md`.
