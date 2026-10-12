# Guion de exposición — Examen Parcial S8 — T10

**Duración objetivo:** 12 minutos. Volver siempre a la trazabilidad **OE → requisito → módulo → diseño → evidencia**.

## 1. Carátula
“Presento el avance consolidado de la tesis T10. El artefacto es un prototipo técnico Edge AI de atenuación selectiva de audio; no es dispositivo médico ni ANC físico.”

## 2. Problema y objetivos
“El problema es la falta de herramientas computacionales que distingan entre sonidos potencialmente desencadenantes y señales que deben preservarse. El objetivo es diseñar, implementar y evaluar un prototipo técnico bajo métricas semánticas, acústicas y computacionales.”

## 3. S5 — Requisitos
“Los requisitos se agrupan en ingesta, representación, benchmark, política, mezcla, máscara, reconstrucción, runtime y evidencia. Las métricas ya están operacionalizadas.”

## 4. S6 — Arquitectura
“La arquitectura es Pipes and Filters: M1–M6, con M3 separado en M3a y M3b. La decisión clave es separar reconocimiento semántico y máscara T-F.”

## 5. S6 — Decisiones
“Tres decisiones: procesamiento local sin nube obligatoria; M2 no controla automáticamente M4; y Android queda limitado a perfilado TFLite hasta tener app real.”

## 6. S7 — Diseño detallado 1
“Muestro el flujo de atenuación: stems → mezcla → política → máscara → reconstrucción → métricas.”

## 7. S7 — Diseño detallado 2
“API, UI y modelo de datos quedan listos para reproducibilidad: Run ID, checksums, RUN_ASSET, POLICY_DECISION y artefactos.”

## 8. S8 — Construcción
“Se construyó un incremento funcional local: demo que genera mezcla, aplica una máscara baseline, reconstruye audio y guarda métricas/evidencias.”

## 9. S8 — Demostración
Ejecutar `run_demo.py`, mostrar artefactos y métricas. Aclarar que la máscara actual es baseline/oracle y que Android físico está pendiente.

## 10. Trazabilidad
“RF-06/RNF-04 → M4 → A5/A6 → output_selective.wav + demo_metrics.csv.”

## 11. Validación
“S9 modelo real de máscara; S10 integración/latencia; S11 plan; S12 línea base; S13 validación final.”

## 12. Riesgos
“Riesgos principales: latencia, degradación de señal protegida y Android. Mitigación: métricas separadas, política de preservación y perfilado honesto.”
