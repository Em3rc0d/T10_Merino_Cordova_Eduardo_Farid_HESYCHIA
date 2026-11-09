# HESYCHIA · PI13/PI14 — preespecificación para revisión académica
Fecha: 2026-11-08. Base documental: dictamen PI11+PI12 del 2026-11-02, commit f625809.
**ESTADO: PROPUESTA; NO APROBADA / TEST NUEVO NO ABIERTO.**

## Alcance OG/OE propuesto
- OG: evaluar cuantitativamente atenuación de evento objetivo, preservación de señal protegida y factibilidad computacional del pipeline M4 frente a DSP y Oracle.
- OE1: implementar frontend espectral, CNN de máscara y política M3b; M2 es auxiliar, no demuestra separación ni detección autónoma segura de alarma.
- OE2: comparar CNN−DSP en las mismas mezclas; Oracle usa stems privilegiados sólo para entrenamiento/evaluación.
- OE3: medir offline en laptop p50/p95/p99 por bloque, RTF y recursos. Sin afirmar streaming o E2E físico.

## Contrato de métricas
- Primarias (pareadas, por mezcla idéntica): delta A_target = A_target(CNN)-A_target(DSP); delta A_protected = A_protected(CNN)-A_protected(DSP), con A_protected como daño (más bajo favorece CNN).
- IC 95 % bootstrap de **grupos independientes de fuente**, preservando bloques completos; reportar cantidad de grupos y de hablantes independientes. Una escena/recorte no equivale a grupo.
- Secundarias: SI-SDRi, both_ok (A_target>=6 dB y A_protected<=1 dB), target ausente, tasa de Oracle y fracción (CNN-DSP)/(Oracle-DSP) sólo si el denominador está definido y suficientemente alejado de cero.
- Posibilidad de resultados negativos: imprescindible. No cambiar reglas tras inspeccionar test.
- Margen máximo de deterioro protegido, nivel alfa, criterio final GO/REWORK/STOP: **PENDIENTES DE APROBACIÓN DEL ASESOR**.

## Contrato de datos
- Auditoría humana de 352 pseudo-stems: una decisión por archivo, segunda lectura ciega de submuestra estratificada, kappa interevaluador y reporte de exclusiones.
- Candidato operativo **no congelado**: 48 escenas nuevas / >=12 grupos fuente objetivo / >=12 hablantes; tamaño definitivo según cobertura, precisión del IC y aprobación.
- Dividir originales por fuente/grabación/hablante ANTES de recorte, augmentación y mezcla. Congelar manifest/hash/checkpoint/versiones/config/criterios y fecha ANTES de abrir test.
- Ningún ajuste de hiperparámetros, arquitectura ni umbrales basado en el test expuesto o futuro.

## Pruebas
- CP02: etiquetado correcto contra permutado con mismos audios y control; candidato para evidencia: IC95% de A_target(correcta - permutada) completamente >0, con daño protegido reportado.
- CP10: misma comparación primaria, DSP y Oracle pareados con misma semilla/mezcla/hash.
- M3b: BLOCK => ganancia 1 y model_called=false; no inferir seguridad autónoma de M2 del bypass.
- M2: reportar taxonomía, matriz de confusión, FP/FN y 96 falsos positivos de alerta V1 como antecedente; metas no fijadas retrospectivamente.

## Evidencia requerida / estados
| Gate | Estado |
|---|---|
| OG/OE y rol de M2 aprobados | PENDIENTE |
| Margen protegido/regla de aceptación final aprobados | PENDIENTE |
| Revisión 352 clips y kappa | PENDIENTE |
| N y grupos independientes justificados | PENDIENTE |
| freeze_test.json / SHA256 / timestamp | PENDIENTE |
| Test CNN/DSP/Oracle sellado | NO EJECUTADO |
| Benchmark offline laptop | NO EJECUTADO |
| E2E streaming físico | FUERA DE EVIDENCIA ACTUAL |

La creación de este documento **no modifica los contratos RNF preexistentes**, ni certifica resultados, ni reemplaza la necesidad de aprobación formal o fuentes de audio reales. Tesis provisional y PI13/PI14 preparados como artefactos separados para evaluación.
