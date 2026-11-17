# PI13 — comprobación estructural del manifiesto (08/11/2026)

Base: main `f6258093f3b807bc93bdf04f9cbd20e3a0551c11`.
Ruta: `05_evidence/m4_sci_v3_source_review_2026-10-28/source_review_352_template.csv`.
Blob Git SHA: `8395d8d3991f1b4633e21caa6356bec5e4179f58`.

| Campo declarado | Resultado |
|---|---:|
| Filas | 352 |
| Clips ESC-50 | 240 (vacuum_cleaner, chainsaw, clock_alarm, wind, rain, siren; 40 cada una) |
| Grabaciones speech | 112 |
| Train / val / test EN EL CSV | 220 / 64 / 68 |
| source_group únicos | 209 |
| pcm_sha256 duplicados en CSV | 0 |
| Grupos fuente cruzando particiones | 0 |
| Revisión humana documentada | **0/352** |

Licencias declaradas: 240 CC-BY-NC-3.0 (requiere atribución por clip); 112 CC-BY-4.0. **No hay validación legal individual**.

## Alcance y límites

El análisis es estructural, sobre texto del CSV. NO se escucharon los 352 clips; no se verificó pureza, identidad física de fuentes, duplicados perceptuales ni permisos de uso. El grupo llamado `test` en este manifiesto **no sustituye el nuevo test independiente sellado** exigido por asesor. NO se recalcularon los resultados históricos ni se ejecutó benchmark streaming/offline nuevo.

## Gates pendientes antes de test PI13/PI14

1. Confirmación del asesor con fecha: OG/OE, papel de M2, margen de protección, criterio estadístico y tamaño efectivo.
2. Auditoría humana de 352 archivos, doble revisión de submuestra, Cohen κ, decisiones/exclusiones.
3. Construcción de nuevo test con fuentes y hablantes no vistos; revisión de fuga entre train/val/test y manifest SHA.
4. Freeze anterior a inferencia de métricas/umbral, test, checkpoint, versiones, código y semilla.
5. Ensayo real por escenas CNN/DSP/Oracle y perfilamiento offline por bloques de M4, con trazas.

Instrumentos locales de PI13/PI14 probados con datos artificiales: 12/12 tests; no equivalen a validación acústica.

**ESTADO: protocolo propuesto, sin aprobación académica ni resultados nuevos.**