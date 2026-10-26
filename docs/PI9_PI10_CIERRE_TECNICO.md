# Cierre técnico experimental de PI9 y PI10

Corte 26 de octubre de 2026. Base S10-A `e8afd1a`. **Integración experimental verificada localmente**. El artefacto ahora ejecuta una CNN entrenada desde la UI, permite compararla con Oracle sobre la misma mezcla y conserva bypass y evidencia por run. No constituye validación científica final ni aceptación académica del asesor.

Antes, la acción principal de la consola ejecutaba exclusivamente IRM Oracle. Ahora el usuario elige Oracle o CNN experimental; la opción de modelo final validado permanece deshabilitada. El target sigue configurado explícitamente. M2 no modifica automáticamente el target ni se ha reformulado unilateralmente el objetivo oficial. El título y el Word adjunto permanecen intactos.

## Arquitectura congelada para esta demostración

M1 representa la mezcla a 16 kHz, STFT de 512 muestras y hop de 160. M3a genera las escenas offline. M3b aplica precedencia obligatoria de señales protegidas. ALLOW con CNN carga un checkpoint y recibe solo mezcla y target_id; ALLOW con Oracle obtiene la IRM de stems. BLOCK evita cargar y ejecutar cualquiera de los estimadores. La misma ganancia se aplica al audio y, solo en evaluación, a los stems para medir atenuaciones. M6 conserva configuración, política, métricas, audio, máscara y procedencia del modelo.

La CNN usa embedding 10×16, tres Conv1D causales de 128 canales y dilataciones 1/2/4, y salida sigmoid de 257 bins. Suma 236833 parámetros. Es una implementación PyTorch CPU de la arquitectura experimental, con **pesos nuevos**, no una conversión de los pesos Keras anteriores. Solo se entrenó drilling_synthetic. La existencia de embedding no demuestra aprendizaje multiclase.

El manifiesto, historial, seeds y checkpoint están en [models/m4_drilling_experimental_v1](../04_build/selective_audio_lab/models/m4_drilling_experimental_v1). La selección usa mínimo MSE de validación, con 24 escenas train y 8 val; no usa un test científico. La pérdida de smoke no sustituye la decisión metodológica pendiente sobre L0. Todos los datos pertenecen al mismo generador procedural y la señal protegida es tonal, no habla real. Distintas semillas no hacen independiente este corpus.

La STFT está centrada y la normalización usa el clip completo. La causalidad de las convoluciones no convierte el pipeline en streaming. wall_time_ms excluye carga de pesos y escritura; no es E2E ni p95/hop.

## Referencias de implementación

| Función | Archivo |
|---|---|
| Red, carga segura de pesos y verificación de manifiesto | [m4_experimental.py](../04_build/selective_audio_lab/src/m4_experimental.py) |
| Entrenamiento reproducible de ingeniería | [train_m4_demo.py](../04_build/selective_audio_lab/src/train_m4_demo.py) |
| Inferencia y bypass antes del estimador | [attenuation.py](../04_build/selective_audio_lab/src/attenuation.py), [run_demo.py](../04_build/selective_audio_lab/src/run_demo.py) |
| Comparación e integridad pareadas | [compare_demo.py](../04_build/selective_audio_lab/src/compare_demo.py) |
| Jobs API y estados reales | [web_server.py](../04_build/selective_audio_lab/src/web_server.py) |
| Sección M4 y comparación de máscaras y audio | [index.html](../04_build/selective_audio_lab/web/index.html) |
| Versionado de modelo en SQLite | [evidence_store.py](../04_build/selective_audio_lab/src/evidence_store.py), [schema_v13.sql](../03_architecture/schema_v13.sql) |
| Integridad, incluida alteración de checkpoint | [validate_artifacts.py](../04_build/selective_audio_lab/src/validate_artifacts.py), [test_m4_integration.py](../04_build/selective_audio_lab/test_m4_integration.py) |

No se modifican las bases históricas v1.2. Los runs nuevos usan v1.3 para admitir metadatos PyTorch; los históricos siguen verificándose con el lector común. Cada run CNN ejecutado incluye copia del checkpoint y sus manifiestos. El verificador compara esos hashes con SQLite y la configuración. Si CNN falla, no se hace fallback a Oracle. Ante BLOCK se registra bypass como motor realmente ejecutado y no se atribuye ejecución de pesos.

## Resultado observado y QA

Pasaron **85 pruebas, cero fallos y cero omisiones**, mediante unittest discover. Chromium ejecutó E1–E4 y comprobó ausencia de errores JS y overflow de página a 390 px. Los logs, capturas y resúmenes están en [evidencia congelada](../05_evidence/pi9_pi10_2026-10-26/qa_summary.json). La validación visual incluyó escritorio y móvil; no equivale a auditoría completa de accesibilidad.

El entorno fue Linux x86_64 con Python 3.12.14 y Torch 2.10.0+cpu. Las versiones completas observadas se registran junto al log. **No son mediciones de Acer Nitro 5 ni Honor X8c.** Docker/Compose se prepararon, pero no se ejecutó su build en este entorno, que no dispone de Docker. El runbook permite comprobarlo en un host con daemon.

La comparación seed 42 produjo aproximadamente:

| Motor | A_target dB | A_protected dB | SI-SDRi protected dB |
|---|---:|---:|---:|
| Oracle | 11.966 | 0.096 | 11.723 |
| CNN experimental | 11.922 | 0.000 al redondear | 11.784 |

Los valores completos, Run ID, hash de mezcla y modelo están en [paired_comparison.json](../05_evidence/pi9_pi10_2026-10-26/paired_comparison.json). El SHA de la mezcla es idéntico entre motores. La cifra protegida redondeada a cero no debe interpretarse como ausencia matemática de toda alteración.

Estas cifras describen **una escena sintética de la misma familia del entrenamiento**. No prueban superioridad general frente a Oracle, voz preservada ni RNF-04. La inspección visual de la máscara aprendida sugiere un posible atajo por bandas frecuenciales, coherente con un generador sencillo; no demuestra separación semántica. Target-absent, solapamiento y fuentes independientes deben evaluarse con el protocolo científico futuro, sin elegir nuevos pesos o umbrales a partir de un test final.

## Matriz de las siete observaciones

Las etiquetas O1–O7 se usan según el contexto remitido por el tesista. La rúbrica original completa y su evaluación posterior no están adjuntas a este sprint; no se simulan firmas, aprobación ni levantamientos del profesor.

| Observación | Cambio y evidencia | Estado defendible |
|---|---|---|
| O1 aprendizaje profundo y Oracle | E1 ejecuta pesos desde UI; E2 genera dos runs con misma escena y máscaras distintas; pruebas sin Oracle dentro de inferencia | Integración demostrada. Validación científica final pendiente |
| O2 preservación de voz | Conservado criterio; demo identificada como sustituto tonal; no se ajusta RNF-04 con estos resultados | Pendiente de corpus real y decisión prospectiva sobre pérdida/preservación |
| O3 declaración de IA | [Declaración acotada del incremento](PI9_PI10_DECLARACION_IA.md) | Uso en este sprint documentado; declaración histórica completa requiere revisión del tesista |
| O4 video narrado | Captura real automatizada y guion con narración sintética de apoyo; duración y capítulos reales en [video_timeline.json](../05_evidence/pi9_pi10_2026-10-26/video_timeline.json) | Revisión del tesista y aceptación del formato por asesor pendientes |
| O5 rol M2 y objetivo | UI separa reconocimiento semántico y estimación de máscara; M2 no gobierna automáticamente M4 | Decisión metodológica/formal del asesor pendiente |
| O6 sirenas | BLOCK obligatorio antes de carga; E3, tests API y muestras idénticas | Corrección técnica verificada; levantamiento académico pendiente del asesor |
| O7 resultados, estado del arte y latencia | Evidencia nueva versionada con ambiente, motor y hashes; M2 histórico distinguido de crudos montados | Parcial. Crudos históricos, método de revisión, p95/hop y E2E pendientes |

La referencia histórica de M2 sigue reportando Macro-F1 0.7257 y RNF-03 no cumplido. Cuando faltan los crudos locales, la consola muestra la fuente Markdown y su SHA como evidencia documental, sin inventar semantic_summary.json ni reportar una nueva ejecución. No se reabrió el fold 10 durante este sprint.

## Demostración y siguiente decisión

[Runbook](PI9_PI10_RUNBOOK.md) y [guion](../06_presentation/pi9_pi10/video_script.json) permiten repetir las cuatro escenas. El video de apoyo debe revisarse antes de entrega; no sustituye la capacidad del tesista de explicar el código, los datos, la política y las limitaciones. La narración sintética queda declarada.

Primero revisar y ejecutar este artefacto en el entorno de exposición. Luego resolver con el asesor O2 y O5. La actualización integral del Word debe reflejar esa decisión y este estado congelado, conservar el título y distinguir implementado, experimental y científicamente validado. No declarar finalizados streaming, TFLite, hardware ni eficacia clínica.

## Minutos del video de apoyo generado

Captura real automatizada con narración sintética identificada en pantalla y audio. Duración aproximada 07:09. Revisión del tesista pendiente. Estos minutos corresponden al video generado; no se atribuyen a una grabación previa.

| Inicio | Contenido |
|---|---|
| 00:00 | Estado y alcance |
| 00:45 | Arquitectura y entrenamiento |
| 01:38 | E1 Inferencia real de la CNN |
| 02:38 | E2 Comparación pareada con Oracle |
| 03:41 | E3 Sirena protegida |
| 04:31 | E4 Trazabilidad e integridad |
| 05:25 | M2 y observaciones abiertas |
| 06:13 | Cierre del incremento y límites |
