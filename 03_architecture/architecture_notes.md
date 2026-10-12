# Arquitectura corregida PI6 -> PI7 -> PI8

El sistema mantiene un pipeline modular **Pipes and Filters**:

M1 Ingesta y representación -> M2 Reconocimiento semántico -> M3a Mezclas controladas offline -> M3b Política objetivo/protegido -> M4 Máscara T-F y reconstrucción -> M5 Runtime/perfilado -> M6 Evidencia y métricas.

## Correcciones estructurales
- M5 es orquestador del camino crítico, no una etapa posterior.
- M3a no participa en streaming real; solo M3b participa como política de runtime.
- M2 no cambia automáticamente el target en v1.1.
- El smartphone queda delimitado a perfilado TFLite con tensores exportados.
- La evaluación E2E del prototipo se realiza en laptop.
