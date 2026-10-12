# Guion final de exposición — Semana 8 / Examen Parcial

Duración objetivo: 10–12 minutos.  
Regla: no vender resultados no medidos; defender trazabilidad, construcción y próximos gates.

## 1. Apertura

Buenos días, docente. Presento el avance consolidado de la tesis T10, correspondiente al examen parcial de Proyecto de Tesis II. El proyecto se denomina HESYCHIA y mantiene el título institucional registrado sobre cancelación selectiva de ruido mediante aprendizaje profundo para atenuar estímulos acústicos asociados a hiperacusia en personas con TEA.

La precisión técnica principal es que, dentro del alcance de ingeniería, la palabra “cancelación” se operacionaliza como **atenuación selectiva mediante máscara tiempo–frecuencia**, no como ANC físico ni como tratamiento clínico.

## 2. Problema y alcance

El problema abordado no es eliminar todo el sonido ambiental. El problema es que un sistema de supresión general puede reducir señales molestas, pero también puede afectar señales importantes. Por eso el artefacto busca distinguir el contexto acústico, aplicar una política explícita de preservación y atenuar selectivamente el evento objetivo.

El alcance de esta tesis es técnico-computacional. No se afirma eficacia clínica, diagnóstico, tratamiento ni uso médico.

## 3. Continuidad PI5–PI8

El avance sigue una cadena de trazabilidad:

- PI5: requisitos, escenarios y criterios de aceptación;
- PI6: arquitectura modular Edge-first;
- PI7: diseño detallado corregido e integrado;
- PI8: construcción incremental reproducible.

No se está improvisando código fuera del diseño. El PI8 implementa partes trazables de los módulos definidos previamente.

## 4. Arquitectura vigente

La arquitectura vigente tiene seis módulos principales:

- M1: ingesta y representación;
- M2: reconocimiento semántico;
- M3a: mezclas controladas offline;
- M3b: política target/protected;
- M4: máscara tiempo–frecuencia y reconstrucción;
- M5: runtime/perfilado;
- M6: evidencia y métricas.

Una corrección clave es que M2 no equivale a M4. Clasificar un sonido no significa saber qué bins tiempo–frecuencia atenuar. Por eso M2 reconoce/monitorea, mientras M4 aplica o aprende una máscara.

## 5. Construcción PI8 ya funcional

El incremento funcional actual ejecuta:

1. generación de stems sintéticos controlados;
2. mezcla de señal protegida, objetivo y fondo;
3. STFT;
4. máscara IRM oracle como baseline;
5. política de atenuación;
6. iSTFT;
7. métricas acústicas;
8. persistencia de evidencia.

Esta baseline IRM no es el modelo final. Es una línea base controlada para verificar que el contrato DSP, la política, la reconstrucción y la trazabilidad funcionan.

## 6. Política M3b

La política target/protected ya es ejecutable. Si el evento objetivo pertenece al conjunto protegido, se bloquea la atenuación y la ganancia queda en uno. Eso evita que el sistema elimine una señal que debe preservarse.

Esta regla está probada automáticamente y se persiste en SQLite como `POLICY_DECISION`.

## 7. Evidencia M6

El módulo M6 ya no es solo documentación. El sistema genera:

- `demo_summary.json`;
- `demo_metrics.csv`;
- `artifacts_manifest.csv`;
- audios de entrada/salida;
- máscara y ganancia;
- `evidence.sqlite`;
- hashes SHA-256;
- validación cruzada entre manifiesto, filesystem, Run ID y SQLite.

Esto permite reproducibilidad y auditoría del avance.

## 8. M2 semántico

El módulo M2 ya fue ejecutado sobre UrbanSound8K oficial completo. Se validaron 8,732 clips, 10 clases y 10 folds, sin audios faltantes ni ocurrencias etiquetadas cruzando particiones. Se compararon SVM RBF y Random Forest usando fold 9 para selección. SVM obtuvo Macro-F1 de validación 0.7146 y fue seleccionado. En fold 10 obtuvo Macro-F1 0.7257, Macro-Recall 0.7170, Macro-Precision 0.7426 y Accuracy 0.7145. El RNF-03 fijado en 0.85 **no fue alcanzado por esta baseline**.

## 9. Estado del dataset

UrbanSound8K fue descargado desde la distribución oficial y el archivo comprimido coincidió con el MD5 oficial. El validador confirmó 8,732 filas, folds 1–10, 10 clases y cero audios faltantes. Se detectaron cinco `fsID` presentes en más de un fold para clases distintas; se conservaron los folds oficiales y se bloqueó leakage a nivel de ocurrencia etiquetada `(fsID,classID,occurrenceID)`, con cero cruces de ocurrencia.

## 10. Resultados que sí puedo afirmar

Además, la medición local S8 en la Acer Nitro 5 se repitió en dos lotes de 40 runs, 80 muestras en total. La campaña agregada obtuvo p50=20.024 ms, p95=34.607 ms y media=22.688 ms; el p95 por lote varió entre 26.205 y 41.508 ms. Se reporta la campaña completa para evitar cherry-picking. El alcance es `whole_clip_processing_only`: no equivale a p95/hop, E2E ni Android.

Puedo afirmar que:

- el incremento PI8 es reproducible;
- CI pasa correctamente;
- M3b funciona;
- M6 funciona;
- M2 fue ejecutado sobre UrbanSound8K oficial y su baseline real quedó en Macro-F1=0.7257;
- RNF-03 no fue cumplido por la baseline y no se movió el umbral;
- no se han inventado mediciones Android;
- no se han hecho claims clínicos.

## 11. Pendientes controlados

Los siguientes gates no pueden omitirse:

1. desarrollar el siguiente candidato M2/M4 sin tuning sobre fold 10 y manteniendo congeladas la baseline M2 y la evidencia de latencia Acer;
2. entrenar M4 aprendido;
3. integrar datasets reales en la evaluación de atenuación;
4. implementar streaming por bloques;
5. exportar TFLite y verificar paridad;
6. perfilar Honor X8c físicamente;
7. ejecutar estabilidad de 10 minutos;
8. congelar validación final.

## 12. Cierre

En conclusión, la tesis ya no está solo en diseño. Existe una implementación funcional y auditada del primer incremento, alineada con las correcciones de PI6 y PI7. Lo que falta está claramente declarado como gate posterior. La fortaleza del avance es que no se sobredeclara: cada afirmación tiene evidencia, y lo pendiente queda explícitamente separado.
