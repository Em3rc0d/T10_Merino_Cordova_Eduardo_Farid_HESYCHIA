# HESYCHIA — secuencia vinculante: CNN científica antes que streaming
Fecha: 2026-10-27. Base: main integrado con PR #1 y PR #2. Estado: PROTOCOLO PROPUESTO, pendiente de revisión académica; NO es certificación de resultados.

## Orden obligatorio y no intercambiable
P1 / M4-SCI: curación de datos reales → congelación de diseño experimental → entrenamiento CNN causal-compatible → validación independiente con voz real → comparación con baselines y Oracle → checkpoint candidato congelado → decisión GO/REWORK/STOP.
P2 / M4-STREAM: únicamente después de GO en P1, reusar el candidato y convertir frontend/inferencia en procesamiento incremental de audio de laptop → medir continuidad y latencia → ejecutar QA → decidir GO/REWORK/STOP.
No se adelanta streaming, Android ni TFLite para encubrir un modelo sin generalización. No se modifica el título de tesis, los objetivos ni los RNF mediante este documento.

## Hechos que se preservan
- M4 PI9/PI10 es una demostración offline con Conv1D causal, STFT centrada, normalización de clip completo y target drilling_synthetic único.
- Entrenamiento 24 escenas + validación 8 escenas del mismo generador; protección tonal, no voz grabada; no test científico independiente.
- M2 histórico Macro-F1 0.7257 y RNF-03 no satisfecho; no se considera validado ni está conectado para seleccionar automáticamente el target de M4.
- Referencia Oracle IRM usa stems limpios solo en entrenamiento/evaluación; no puede usarlos para inferencia CNN.
- M3b BLOCK precede cualquier inferencia y jamás se degrada. Las señales protegidas no equivalen a gatillos atenuables universales.
- Los 85 tests previos prueban ingeniería en PI9/PI10, no generalización ni streaming.

## Fase P1 / CNN científica — entregables y gates
1. D0 datos: manifiestos por grabación de audio original (hash, fuente, licencia, origen, clase, dispositivo si aplica, hablante, grupo de fuga, revisión manual); fuentes reales de ruido y voz; uso legal trazable.
2. D1 split: separación ANTES de augmentación o mezcla por fuente/grabación/hablante cuando corresponda; train/validation/test disjuntos, deduplicación; por lo menos 30 escenas de prueba nuevas, además de una fuente real del dominio acústico; ninguna selección de modelos o hiperparámetros basada en test.
3. D2 corpus: fijar clases atenuables candidatas (primera iteración: perforación y aspiradora, sujetas a suficiencia de audio aislado); voces y alertas como eventos protegidos. Mezclar stems conocidos para preservar ground truth; registrar SNR, solapamiento, seeds y fuentes. Incluir target ausente y distractores con contenido espectral compartido.
4. D3 arquitectura: conservar CNN causal pequeña como baseline; definir un frontend que sea válido para procesamiento causal futuro (frames alineados al pasado, normalización independiente del audio futuro, ningún lookahead). Si cambia la representación, entrenar checkpoint nuevo; NO reclamar equivalencia con PI9/PI10.
5. D4 entrenamiento: configs versionadas, curva train/val, early stopping, al menos tres semillas, experimentos de ablation (clase condicionante real vs clase permutada/retirada; pérdida MSE vs pérdida acústica/protección), control de NaN y leakage. Seleccionar checkpoint SOLO por validation.
6. D5 evaluación: congelar hash de checkpoint + test + política + plan antes de abrir test; comparar sin proceso, baseline DSP, CNN anterior, CNN candidata y Oracle privilegiado. Reportar A_target, A_protected, SI-SDRi protección, medidas de inteligibilidad de habla si aplican (p. ej. STOI en corpus adecuado), Macro-F1/recall para M2 en su propia tarea, intervalos por fuente, fallos y variabilidad entre seeds.
7. D6 integración: modo objetivo conocido para aislar M4; luego modo sistema integrado M2→M3b→M4 para medir error de M2 vs error M4. Si M2 no satisface condiciones de mezcla, declarar pendiente y no simular control automático. Política BLOCK verificada tanto con modelo presente como ausente.
8. D7 aceptación: documentar contra umbrales oficiales previamente fijados (RNF-04 y demás); no inventar números ni moverlos tras el test. Si no pasa, REWORK con datos de validación nuevos y test futuro independiente; si tampoco, conclusión negativa legítima.

## Gate P1 → P2 (todos requeridos)
- Entrenamiento reproducible desde cero con audio real y checkpoint verificable.
- Datos, licencias, particiones, hashes y protocolo de auditoría completos.
- Test independiente de al menos 30 escenas desconocidas; informe completo, también fallos.
- Evaluación explícita de conservación de voz real y de target ausente.
- Comparación pareada con baselines y Oracle, sin stems en inferencia.
- Condicionamiento por clase demostrado experimentalmente o alcance de una sola clase formalmente declarado.
- Arquitectura y política seguras verificadas; métricas contractuales e intervalos de incertidumbre documentados.
- Confirmación del asesor para cualquier decisión que modifique OE1/OE2; uso de IA declarado.
Sólo después de constatar este gate se inicia desarrollo incremental streaming.

## Fase P2 / streaming laptop — entregables y gates
S1 contrato DSP causal y de buffering; S2 inferencia estado-a-estado con el checkpoint congelado; S3 paridad offline causal vs chunks; S4 prueba 10 minutos sin huecos, duplicados, clipping excesivo ni deriva; S5 perfil CPU, RAM, p50/p95 del camino crítico por hop y extremo a extremo; S6 pruebas de audio protegido, desconexiones y fallback seguro. El frontend streaming tendrá explícito el mismo contrato usado para entrenar M4. Si exige nueva representación, se vuelve a D3-D7: NO se adapta el modelo sin nueva evaluación.
Los RNF vigentes en SOURCE_OF_TRUTH son: laptop p95 camino crítico por hop <= 10 ms y E2E p95 <= 60 ms; Android TFLite p95 <= 20 ms es fase posterior, no requisito de esta transición. Ser causal no demuestra p95 ni E2E.

## Reglas de evidencia
- Preservar baselines históricos y no modificar sus hashes, audios o métricas.
- Evitar guardar datasets de terceros en Git; sí almacenar manifiestos, scripts, configuraciones, runs, hashes y licencias.
- Identificar para cada afirmación: planeado, implementado, ejecutado, test independiente o validado académicamente.
- El Word académico se actualiza DESPUÉS del checkpoint y de la evaluación, conservando título hasta decisión formal.
- NO fusionar un modelo nuevo a main como científico hasta el gate P1; experimentos en ramas y PR dedicados.

## Estado inicial
P1 = NOT STARTED como entrenamiento científico; P2 = BLOCKED BY P1. El entorno PI9/PI10 es baseline de ingeniería ya integrado en main.
