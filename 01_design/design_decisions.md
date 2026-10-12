# Decisiones cerradas para PI8

## Formulación
La tesis se presenta como prototipo técnico Edge AI de atenuación selectiva de audio. El término institucional "cancelación" se operacionaliza como atenuación selectiva mediante máscara/gain tiempo-frecuencia, no como ANC físico.

## Decisiones congeladas
- Target elegido por configuración del investigador; M2 no cambia el target automáticamente.
- M3a genera mezclas solo offline; M3b aplica política target/protected en runtime.
- M4 aprende/aplica máscara T-F condicionada por target; no se asume que clasificar equivale a separar.
- M5 ejecuta streaming E2E en laptop; Android se limita a perfilado TFLite con tensores exportados.
- M6 registra Run ID, checksums, métricas, artefactos y trazabilidad.

## Criterio PI8
PI8 demuestra construcción inicial: flujo controlado de punta a punta con datos sintéticos reproducibles, métricas acústicas y benchmark local de latencia. No presenta resultados clínicos ni medición real en Honor X8c hasta ejecutarla físicamente.
