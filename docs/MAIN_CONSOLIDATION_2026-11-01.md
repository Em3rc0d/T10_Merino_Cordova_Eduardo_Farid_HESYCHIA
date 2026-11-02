# Consolidación del trabajo de HESYCHIA en `main`

Fecha de verificación: **2026-11-01**. Se fusionaron todos los PR pendientes de las ramas M4 sin atribuir aprobación científica al artefacto.

## Integraciones confirmadas

| PR | Base final | Commit de merge | Alcance | Estado científico |
|---|---|---|---|---|
| #4 | main | `ffab9f6b771fb327364d61469a1945273c112b3d` | M4 CNN con audio real; congelación, checkpoints, fuentes y test V1 | REWORK (1/48 escenas elegibles) |
| #5 | main | `c1f6259891a1f313b21d06294d1a79f2632ed64f` | Pérdida selectiva, entrenamiento de tres semillas, comparación de validación V1/V2 | REWORK (0/48 para cada modelo V2 en VAL) |
| #6 | main | `4296b3447888007d91faac40a8ff54872121449b` | Ablación CNN espectral, prueba contrafactual, protocolo y registro de 352 fuentes | PILOTO; entrenamiento V3 cancelado sin resultados acústicos concluidos |

Los PR #1, #2 y #3 ya estaban fusionados previamente en `main`.

## Verificación de contenido

Se comparó cada rama existente con `main` después de fusionar #4, #5 y #6. Todas presentaron `ahead_by=0`, `files.length=0`, incluyendo:

- `feat/m4-scientific-training-20261027`
- `feat/m4-v2-selective-objective-20261028`
- `feat/m4-v3-time-frequency-counterfactual-20261028`
- `plan/m4-scientific-cnn-then-streaming-20261027`

Por tanto **no existe contenido exclusivo pendiente de integrar en `main`**. Las referencias de ramas históricas pueden permanecer en GitHub; conservarlas no significa tener modificaciones sin fusionar. Su eliminación requiere una acción específica de GitHub distinta de un merge.

## Evidencia y lectura correcta

- V1: `docs/M4_SCI_REAL_RESULTS_2026-10-27.md`. La CNN se entrenó con 352 grabaciones reales originales mezcladas digitalmente y tuvo 1/48 aprobaciones conjuntas en test V1.
- V2: `docs/M4_SCI_V2_REAL_AUDIO_VALIDATION_2026-10-28.md`. Tres semillas entrenadas; en validación las 48 escenas elegibles tuvieron **0/48** aprobaciones conjuntas en las tres variantes. No es un test nuevo.
- V3: `src/m4_scientific/counterfactual.py`, `experiments/m4_v3_spectral_pilot.py` y `docs/M4_V3_SOURCE_REVIEW_PROTOCOL_2026-10-28.md`. El workflow #40782713180 terminó **CANCELLED**: 39 pruebas de código aprobadas, cuatro épocas entrenadas (aprox. 13 min cada una), sin validación acústica V3 completada ni checkpoint final aprobado. No reinterpretar como PASS.
- Auditoría humana: `05_evidence/m4_sci_v3_source_review_2026-10-28/source_review_352_template.csv` es **una plantilla sin revisiones humanas aprobadas**.
- OE1/M2: pendiente de decisión formal con el asesor y de validación integrada, pese a que existe candidato M2 neuronal offline. Mantener explícitos los falsos positivos de alertas.
- V3, V2 y V1 no acreditan eficacia clínica para TEA, ni cancelación física activa, ni streaming. El título se conserva sin modificar unilateralmente objetivos/RNF.

**Veredicto:** integración de ingeniería completa a `main`; `scientific_GO=false`, `streaming_GO=false`. No ejecutar ni declarar streaming como validado.
