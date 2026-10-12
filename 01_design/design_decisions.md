# Decisiones cerradas para PI8

## Formulación
La tesis se presenta como prototipo técnico Edge AI de atenuación selectiva de audio. El término institucional "cancelación" se operacionaliza como atenuación selectiva mediante máscara/gain tiempo-frecuencia, no como ANC físico.

## Decisiones congeladas
- Target elegido por configuración del investigador; M2 no cambia el target automáticamente.
- M3a genera mezclas solo offline; M3b aplica política target/protected en runtime.
- M4 aprende/aplica máscara T-F condicionada por target; no se asume que clasificar equivale a separar.
- M5 es el orquestador del runtime. El **objetivo final** es streaming E2E en laptop; en PI8+ solo están operativos la consola Docker y el procesamiento controlado de clip. Android se limita a futuro perfilado TFLite con tensores exportados.
- M6 registra Run ID, checksums, métricas, artefactos y trazabilidad.

## Criterio PI8
PI8 demuestra construcción inicial: flujo controlado de punta a punta con datos sintéticos reproducibles, métricas acústicas y benchmark local de latencia. No presenta resultados clínicos ni medición real en Honor X8c hasta ejecutarla físicamente.


## Decisión de UI PI8+

El prototipo histórico de PI7 era una maqueta navegable. Para S8 se adopta una consola **HTML/CSS/JavaScript servida por Python** y empaquetada con Docker, conectada al pipeline real. La decisión reduce dependencias de demo y conserva el contrato de jobs 202 + jobId.

Esto es una sustitución de implementación de interfaz, no un cambio del aporte científico ni de la arquitectura M1–M6. La UI no contiene métricas científicas hard-codeadas; consume runs y evidencia generados por el backend.
