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

El módulo M2 ya tiene pipeline ejecutable para UrbanSound8K. El pipeline valida metadata, folds, clases, no leakage por `fsID`, extrae MFCC y log-Mel, entrena SVM/RF y genera Macro-F1, Macro-Recall, Macro-Precision, Accuracy, matriz de confusión y predicciones.

Sin embargo, todavía no afirmo un resultado científico real de UrbanSound8K porque la distribución completa está en descarga. El fixture del CI valida el software, no sustituye el experimento real.

## 9. Estado del dataset

UrbanSound8K pesa aproximadamente 5.6 GB y se está descargando en la laptop local. Una vez descomprimido, primero se ejecutará el validador oficial del contrato:

- 8732 filas;
- folds 1 al 10;
- metadata completa;
- audio en `fold1` a `fold10`;
- cero archivos faltantes.

Solo después de esa validación se ejecuta el benchmark real.

## 10. Resultados que sí puedo afirmar

Puedo afirmar que:

- el incremento PI8 es reproducible;
- CI pasa correctamente;
- M3b funciona;
- M6 funciona;
- el pipeline M2 está implementado;
- no se ha inventado evidencia de UrbanSound8K;
- no se han inventado mediciones Android;
- no se han hecho claims clínicos.

## 11. Pendientes controlados

Los siguientes gates no pueden omitirse:

1. ejecutar UrbanSound8K completo;
2. entrenar M4 aprendido;
3. integrar datasets reales en la evaluación de atenuación;
4. implementar streaming por bloques;
5. exportar TFLite y verificar paridad;
6. perfilar Honor X8c físicamente;
7. ejecutar estabilidad de 10 minutos;
8. congelar validación final.

## 12. Cierre

En conclusión, la tesis ya no está solo en diseño. Existe una implementación funcional y auditada del primer incremento, alineada con las correcciones de PI6 y PI7. Lo que falta está claramente declarado como gate posterior. La fortaleza del avance es que no se sobredeclara: cada afirmación tiene evidencia, y lo pendiente queda explícitamente separado.
