# M4 aprendido — Diseño experimental D0 de HESYCHIA

**Fecha:** 2026-10-22. **Estado: propuesta, NO BUILD_READY.**
Este documento no modifica el título registrado, los RNF, los resultados congelados ni el contrato PI7 v1.1. La adopción de cambios requiere decisión prospectiva registrada antes de cualquier test. Documentos prevalentes: SOURCE_OF_TRUTH.md, docs/TARGET_SELECTION_AND_DEEP_M4.md, docs/PROTOCOLO_POST_PARCIAL_S9_S13.md.

## 1. Qué y cómo aprende M4

Tarea: aprender una máscara tiempo-frecuencia que reduzca una fuente objetivo dentro de una mezcla sin degradar excesivamente la voz protegida. No es ANC físico, tratamiento ni validación clínica. M2 clasifica eventos; M4 estima una máscara. Entrenar M4 no hace cumplir automáticamente el Macro-F1 de M2 (objetivo 0.85, baseline 0.7257).

Mezcla x(t) = voz(t) + target(t) + ambiente(t). Solo en entrenamiento/evaluación se conocen los stems individuales. Entrada de inferencia: mezcla y target_id configurado por M3b; nunca stems limpios.

Se conserva arquitectura de PI7: magnitud STFT [B,T,257]; target_id -> Embedding(16); concatenación por frame; tres Conv1D causales de 128 filtros, kernel 3, dilataciones 1/2/4, ReLU; Dense(257,sigmoid) -> máscara estimada Mhat. Las tres capas cubren 15 frames presentes/pasados (14 previos), no futuros. Atención: causalidad de convolución no demuestra causalidad de STFT+iSTFT.

M3b: BLOCK -> ganancia unitaria. ALLOW -> g=max(1-alpha*Mhat,10^(-cap_db/20)). Experimento primario: alpha=1 y cap_db=12; 18/24/30 dB solo sensibilidad preespecificada. Reconstrucción Y=g*STFT(x), seguida de iSTFT. Se evaluarán artefactos; conservar fase de mezcla no garantiza audio perfecto.

Primera etapa siren-only: el embedding queda en la interfaz, pero UNA clase NO demuestra que se aprendió condicionamiento multiclase. Una ampliación a varias clases exige nuevos stems limpios y otra evaluación explícita.

## 2. Integridad de datos — bloqueo científico principal

UrbanSound8K tiene anotaciones débiles y grabaciones de campo: una grabación etiquetada siren puede contener ambiente propio. Tratarla como stem puro hace que Oracle aprenda/suprima también ese ambiente. **Nunca afirmar extracción de sirena pura usando automáticamente esos archivos.** Procedimiento: verificar candidatos por procedencia/escucha y usar referencias suficientemente aisladas bajo licencias verificadas; alternativamente presentar el experimento honestamente como atenuación del pseudo-stem de grabación etiquetada.

La mezcla sintética permite usar referencia IRM = |STFT(target)|/(|STFT(target)|+|STFT(voz+ambiente)|+eps) **solo como etiqueta privilegiada**, nunca como entrada del modelo desplegable.

Fuente de voz candidata: LibriSpeech train-clean-100 / dev-clean / test-clean, verificando speakers disjuntos. Este corpus es habla leída en inglés, no valida conversación espontánea en español. UrbanSound8K conserva folds oficiales para M2; M4 requiere **otro manifiesto independiente** por grabación original (fsID) y speaker. No reusar segmentos de una misma grabación entre train/val/test aunque cambie semilla, ganancia, desplazamiento o SNR. Registrar dataset, licencia, archivo/sha256, fsID, slice, speaker, clase, offset, split, mezcla, semilla, resampler, gain y config.

Propuesta de escenas (congelar antes de entrenar): 4 s/16kHz; sirena/voz -5,0,+5,+10 dB; ambiente -10 dB relativo a voz; clases de ausencia de sirena con etiqueta de máscara cero para medir falsas atenuaciones. Propuesta target-absent 25% en cada split (a preespecificar, sin usar test para elegirlo). Construir train/val/test con fuentes disjuntas, no partir aleatoriamente mezclas ya construidas. No afirmar independencia estadística si 100 mezclas reusan un mismo clip.

**Gate D0-D1:** si no se obtiene evidencia de procedencia, permiso/licencia y separación real de fuentes, se bloquea el entrenamiento científico o se reduce explícitamente la interpretación a pseudo-stems.

## 3. Frontend causal — diseño antes de entrenar

El código anterior utiliza STFT SciPy con boundary=zeros en modo offline y normalización por máximo de TODO el clip. Esta última mira audio futuro y no sirve sin cambios para streaming causal.

Crear nuevo contrato de STFT/OLA incremental por hops de 160 muestras con ventana 512, buffers y estados explícitos; al entrenar usar la misma representación disponible en inferencia. Normalización con parámetros fijos derivados SOLO de train o estadística de estado causal; jamás máximo futuro de clip. Tests obligatorios: ganancia 1 -> reproducción fiel dentro de tolerancias, equivalencia offline incremental vs streaming, bordes, ausencia de lookahead, transición BLOCK/ALLOW sin artefactos inaceptables.

Ventana: 512/16000 = 32 ms. Hop: 160/16000 = 10 ms. El retardo algorítmico real y el tiempo E2E dependen de buffering/OLA/I-O. No inventarlos. Mantener pipeline PI8 anterior intacto como evidencia histórica; si cambia framing, correr nuevo Oracle sobre el mismo frontend M4 para comparación justa y registrar nuevo run ID.

## 4. Pérdida, entrenamiento y riesgos

Loss L0 PI7 vigente: 0.5*MAE(Mhat,IRM)+0.5*MAE(Mhat*|X|,|S_target|)/(mean(|S_target|)+eps).
**Riesgo**: denominador casi cero para escenas target-absent; requiere definición prospectiva de estabilización y tests de NaN/gradientes. No modificar fórmula silenciosamente.

Propuesta de ablation L1, sujeta a ADR prospectivo: Lspeech=sum((1-g)*|S_speech|)/(sum(|S_speech|)+eps); L1=L0+lambda*Lspeech. Es un surrogate de preservación espectral; no sustituye medición acústica/perceptual real. La elección de lambda ocurre SOLO en validación con presupuesto de variantes registrado, nunca mirando test. Primera baseline aprendida debe reportar L0 separado; L1 será candidato comparativo solo si el contrato se aprueba antes del experimento.

Hiperparámetros iniciales **propuestos, no medidos**: TensorFlow/Keras, Adam 1e-3, batch 16, máximo 50 épocas, early stopping patience=8 monitorizando validación, seed principal 42; semillas 43/44 como replicación si los recursos lo permiten. Sanidad: prueba de overfit sobre 1–4 escenas SOLO train, comprobación de shapes, gradientes, finite loss, backprop y cambios de pesos. Esto no es evidencia científica.

El embedding de clase siren no prueba generalidad; validar separadamente target presente vs ausente. Una máscara cero siempre preserva voz pero no atenúa sirena. Una máscara uno siempre atenúa sirena pero destruye voz. Ninguna satisface el problema.

## 5. Protocolo de evaluación congelable

Comparar sobre las **mismas mezclas fuente-disjuntas**: bypass (g=1), Oracle de stems, M4-L0 entrenado y M4-L1 solo si se preregistra. Ninguna máscara Oracle se presenta como máximo matemático universal ni como red aprendida.

Por mezcla: A_target>=6 dB; A_protected<=1 dB; flags target_ok, protected_ok y both_ok; proporción, conteo fallido, distribuciones, media/mediana/intervalos con unidad estadística declarada; SI-SDRi(protected) y SI-SDRi(target) con interpretación correcta; casos target ausente y BLOCK; pareo M4 vs Oracle. Una media aprobada no implica que todas las mezclas cumplan.

**Test sellado**: seleccionar candidato y parámetros solo con train/val; registrar checkpoint, modelo, datos, loss y cap antes de abrir test. Fold 10 M2 ya observado no es nuevo test ciego; para M4 idealmente preservar un corpus/origen externo nuevo. Nunca usar resultados de test para ajustar política, SNR, lambda o arquitectura.

## 6. Compatibilidad y Edge

Exportar Keras -> TFLite con operadores estándar tras smoke test de conversión. Registrar paridad máscara/ganancia/audio, y comparar FP32/cuantización solo como experimento prospectivo. Medir p50/p95 por hop <=10ms como objetivo de laptop, E2E captura-salida p95<=60ms separado, RAM, fallas/underruns durante >=10 min. Los 34.607ms de Acer son **whole-clip**, no per-hop. Honor X8c solo perfil TFLite p95<=20ms, sin prometer streaming Android.

Sirena = alerta crítica potencial. Atenuación de sirena en laboratorio no autoriza uso público sin nueva política de seguridad conservadora y validación.

## 7. Bloqueantes para implementar

D0 Fuentes originales/aisladas y licencias; D1 split manifest por fsID/speaker; D2 frontend causal y equivalencia OLA; D3 loss estable target-absent y ADR L1; D4 test independiente y selección preespecificada; D5 viabilidad TensorFlow/TFLite y perfil del equipo. No declarar BUILD_READY hasta cerrar D0-D5. Guardar artefactos M6: run_id, config, SHA, split, modelo, logs, métricas, errores y tiempo.

### Referencias principales (sujetas a matriz de estado del arte)
- TSIE review, Acoustical Science and Technology, 2025: https://doi.org/10.1250/ast.e24.124
- DCASE UrbanSound8K: https://dcase-repo.github.io/dcase_datalist/datasets/sounds/urbansound8k.html
- LibriSpeech oficial: https://openslr.elda.org/12/
- Conversión TensorFlow Lite: https://github.com/tensorflow/tensorflow/blob/master/tensorflow/lite/g3doc/models/convert/convert_models.md
