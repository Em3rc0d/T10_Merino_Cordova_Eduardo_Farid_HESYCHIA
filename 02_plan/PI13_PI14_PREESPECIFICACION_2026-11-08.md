# HESYCHIA · Protocolo confirmatorio final para PI15

Fecha de consolidación: 2026-11-17.  
Base: revisión académica del 10/11/2026 y revisión PI15 del 17/11/2026.  
**ESTADO: CRITERIOS METODOLÓGICOS PREESPECIFICADOS. TEST CONFIRMATORIO AÚN NO ABIERTO.**

## 1. Alcance experimental

- **OG:** diseñar, implementar y evaluar computacionalmente una arquitectura de atenuación digital selectiva mediante aprendizaje profundo, cuantificando atenuación del evento objetivo, preservación de señales protegidas y desempeño computacional frente a DSP y una referencia Oracle IRM.
- **OE1:** implementar frontend espectral, CNN de máscara y política M3b; M2 se mantiene como clasificador auxiliar y no se usa como evidencia de detección autónoma segura de alertas.
- **OE2:** comparar CNN y DSP sobre escenas nuevas pareadas; Oracle IRM se reporta como referencia experimental privilegiada.
- **OE3:** medir factibilidad de inferencia offline en laptop mediante latencia por bloque p50/p95/p99, RTF y recursos, separando explícitamente esta medición de streaming físico E2E.

## 2. Hipótesis y regla de decisión

Estimandos primarios pareados:

- `ΔA_target = A_target(CNN) - A_target(DSP)`. Valores mayores favorecen CNN.
- `ΔA_protected = A_protected(CNN) - A_protected(DSP)`. Valores menores indican menor daño adicional a la señal protegida.

La superioridad en atenuación de objetivo se establece cuando el límite inferior del IC unilateral 95 % de `ΔA_target` es mayor que 0 dB.

La no inferioridad de preservación se establece cuando el límite superior del IC unilateral 95 % de `ΔA_protected` es menor o igual que 1 dB.

Regla conjunta:

| Superioridad objetivo | No inferioridad protegida | Conclusión |
|---|---|---|
| Sí | Sí | Se rechaza H0 y se sostiene la ventaja selectiva de CNN frente a DSP. |
| Sí | No | Hay mayor atenuación del objetivo, pero a costa de la señal protegida; H1 no se sostiene como mejora selectiva. |
| No | Sí | No se demuestra ventaja de atenuación sobre DSP; la preservación sí es no inferior. |
| No | No | CNN no supera a DSP en ninguna de las dos condiciones principales. |

El criterio histórico `both_ok` (A_target >= 6 dB y A_protected <= 1 dB) se conserva únicamente como indicador secundario descriptivo.

## 3. Inferencia estadística

- Unidad primaria de remuestreo: **source_group**.
- Todas las mezclas pertenecientes a un grupo seleccionado permanecen juntas.
- Bootstrap: **10 000 réplicas** en el análisis confirmatorio.
- Reporte: IC percentil e IC BCa.
- Sensibilidad secundaria: remuestreo por `speaker_group`.
- Se reportan cantidad real de grupos fuente, hablantes y mezclas.

## 4. Diseño del test independiente

Antes de la primera inferencia confirmatoria:

- mínimo **20 source_group** nuevos e independientes del entrenamiento/validación/test V1;
- mínimo **4 hablantes nuevos**;
- separación por fuente/grabación/hablante antes de recorte, augmentación o mezcla;
- mismo `mix_sha256` para CNN, DSP y Oracle;
- congelación del manifiesto, checkpoint, baseline DSP, código de evaluación, protocolo de métricas y configuraciones mediante SHA-256;
- ningún ajuste de arquitectura, hiperparámetros o umbrales usando el test sellado.

Se mantiene un mínimo operativo de 30 escenas únicamente como cuota técnica conservadora; la independencia se juzga por grupos, no por número de recortes.

## 5. Baseline DSP

La referencia DSP es `DSP_CLASS_TEMPLATE_V1`:

- recibe `mixture_waveform` y `target_id`, igual que la rama CNN recibe mezcla y clase objetivo;
- no recibe stems limpios del test;
- usa STFT Hann, 16 kHz, n_fft=512, hop=160;
- estima plantillas espectrales exclusivamente con el conjunto de entrenamiento admisible;
- aplica una máscara espectral fija por clase y la misma política de ganancia/cap que la CNN;
- código, configuración, plantillas y manifiesto de entrenamiento deben congelarse antes de abrir el test.

Oracle IRM permanece separado: usa información privilegiada y no es la baseline DSP.

## 6. Auditoría perceptual del corpus

El universo registrado contiene 352 fuentes. Para cierre de OE1 se utiliza la **muestra estratificada preseleccionada de 93 registros**, revisada de forma independiente por dos evaluadores.

Se exige:

- decisión por registro según la escala definida por el workbench;
- segundo evaluador independiente del desarrollo;
- Cohen κ sobre los 93 pares;
- umbral interpretativo mínimo preespecificado κ >= 0,60;
- proporción estimada de contaminación con IC95 %;
- exclusiones documentadas antes de generar plantillas DSP y antes de congelar el test.

La selección de 93 registros tiene semilla 20261108 y SHA-256:
`f0266f300f1c3eb12ef6d3a20b49ed61f6b7ea79f739b8d1febc03a1cfa11abb`.

## 7. Casos de prueba confirmatorios

- **CP02:** en las mismas mezclas, comparar etiqueta correcta vs etiqueta permutada. El IC95 % de `A_target(correcta) - A_target(permutada)` debe quedar completamente por encima de 0 para evidenciar uso efectivo de la condición semántica.
- **CP10:** CNN, DSP y Oracle deben operar sobre `mix_sha256` idénticos.
- **M3b:** `BLOCK` implica bypass exacto y no invoca M4.
- **M2:** se reporta de manera auxiliar; no gobierna la inferencia confirmatoria de M4.

## 8. OE3

Benchmark oficial:

- checkpoint real seleccionado;
- Acer Nitro 5;
- al menos **1000 bloques medidos después del warm-up**;
- p50, p95, p99, media, RTF, CPU, RAM, SO, Python, PyTorch, número de threads, hash del checkpoint y hash del script;
- alcance: inferencia M4 + política de ganancia por bloque offline;
- no se presenta como latencia de captura/reproducción ni streaming E2E.

## 9. Integridad

Un resultado confirmatorio negativo es válido y debe reportarse. No se reutiliza el test V1 expuesto para selección de modelo ni se reconstruyen resultados inexistentes.
