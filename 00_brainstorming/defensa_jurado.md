# Defensa ante jurado - T10

## Narrativa en una frase
No se está construyendo un audífono médico ni ANC físico; se construye un prototipo técnico Edge AI que reconoce/monitorea eventos acústicos y aplica atenuación selectiva por máscara tiempo-frecuencia bajo criterios medibles de preservación, latencia y reproducibilidad.

## Preguntas probables y respuesta corta

### 1. ¿Cumple la latencia necesaria para tiempo real?
En PI8 se mide una latencia local preliminar sobre el entorno de desarrollo. La tesis separa inferencia, camino crítico por hop y E2E. El objetivo corregido es p95 <= 10 ms por hop en laptop, E2E p95 <= 60 ms y Android TFLite p95 <= 20 ms cuando se ejecute el perfil físico.

### 2. ¿Cómo decide qué sonidos atenuar y cuáles conservar?
En la versión corregida el target se fija por configuración experimental. M2 no gobierna automáticamente M4. La política M3b aplica precedencia de señales protegidas; si el target pertenece al conjunto protegido, se bloquea la atenuación y g=1.

### 3. ¿Cómo validará éticamente?
La validación base usa datasets públicos/licenciados y mezclas sintéticas con stems conocidos. No se recolecta audio de personas con TEA. Cualquier captura humana primaria requerirá consentimiento informado y autorización aplicable.

### 4. ¿Qué aporta frente a un clasificador de sonidos?
El clasificador solo indica probabilidad de clase. El aporte está en separar esa capa semántica de una máscara T-F condicionada por target y evaluar simultáneamente atenuación del objetivo y preservación de señal protegida.

### 5. ¿Qué parte funciona en PI8?
Funciona un incremento local reproducible: genera mezcla controlada, aplica máscara T-F de línea base basada en stems, reconstruye audio, calcula métricas acústicas y mide latencia local. Es una base ejecutable para reemplazar la máscara oracle por el estimador entrenado en PI9.
