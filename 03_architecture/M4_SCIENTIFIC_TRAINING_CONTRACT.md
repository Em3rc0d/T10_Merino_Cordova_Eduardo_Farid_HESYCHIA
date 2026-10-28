# M4-SCI — protocolo de dataset, entrenamiento y evaluación científica
Estado: DRAFT 2026-10-27. Autoridad: SOURCE_OF_TRUTH.md, PI7 vigente y decisiones posteriores documentadas. No modifica RNF/OE. No resultados todavía.

## Pregunta contrastable
¿Puede un estimador CNN condicionado por un evento objetivo, al procesar una mezcla desconocida sin stems limpios, atenuar el evento objetivo conservando habla humana real bajo límites predeclarados de degradación, con generalización a fuentes no vistas?
La clasificación de M2 es tarea separada. El estimador debe medirse en modo ORACLE LABEL (target correcto configurado) y luego en modo INTEGRATED LABEL (etiqueta estimada por M2) sin confundir esas condiciones.

## Artefactos y particiones obligatorios
- manifest_raw.csv: asset_id, sha256, dataset_version, url_or_origin, license_id, license_evidence, speaker_id, recording_session_id, source_id, domain, class_labels, purity_qc, duration_s, sr, channels, split_group, split y split_reason.
- dataset_contract.json: clases, condiciones de exclusión, lista de licencias admitidas, reglas de inclusión, seeds, conversión a 16 kHz mono, versiones y SHA de generador.
- stems_manifest.csv: protected_asset_id, target_asset_id, background_asset_id, target_present, SNR/SIR, overlap_fraction, reverb_id, mix_seed, mix_sha256, stem_hashes y split.
- leakage_report.json: checks de SHA idéntico, near-duplicate fingerprint, speaker/source/session, fragmentos y material aumentado; FALLA si una fuente cruza splits.
- manifests por corrida: model_cfg, optimizer, lr schedule, batch, seed, frontend_cfg, preprocessing stats learned on train only, checkpoint_hash, train/val loss history, validation metrics.
- freeze_test.json: SHA de dataset final, checksum de splits, versión de métricas, política de protección, umbrales oficiales, fecha del freeze y aprobación; ninguna edición posterior silenciosa.

## Datos y licencias (candidatos, NO aprobados hasta QC)
- Habla: corpus con voces reales y hablantes separados entre train/test (p. ej. LibriSpeech, sujeto a licencia y compatibilidad).
- Target: sonidos mecánicos reales con fuentes identificables, candidatos perforación y aspiradora. FSD50K contiene sonidos polifónicos; no considerar sus grabaciones stems limpios por defecto. Elegir grabaciones aisladas con QC o fuentes individualmente grabadas/licenciadas.
- Fondos: grabaciones de contexto disjuntas. Distinguir 'real recording mixed synthetically' de 'real in situ mixture with unknown stems'.
- Alertas: usar sonidos reales de seguridad en pruebas de BLOCK/target-absent; nunca etiquetarlos automáticamente como atenuables. La asignación de clase no equivale a indicación clínica sobre TEA.
- No ingresar descargas privadas ni audio de terceros sin permiso; preservar atribución y licencias. Tests finales no deben generarse de fuentes usadas antes.

## Diseño de particiones
1. Inventariar originales y agrupar por hablante, fuente física, grabación, sesión y derivados; deduplicar.
2. Particionar por grupos antes de resample/recorte/augmentación/mezclas. Propuesta inicial 70/15/15 por grupos sujetos a cobertura; la fracción se ajusta antes de test por suficiencia de clases, nunca después de ver resultados.
3. Generar mezclas distintas sólo dentro de su split; mantener mismo mixture/stem hashes para todos los modelos de comparación.
4. 30 escenas NUEVAS son mínimo docente, no necesariamente potencia estadística suficiente. Proponer además test suficiente por clase/condición y fuentes independientes verificadas; dejar explicitado tamaño efectivo por grupo.
5. Añadir prueba de dominio diferente (grabación de campo de una fuente real, desconocida), sin interpretarla como stem ground truth si no lo tiene.

## Contrato de entrada y modelo candidato
- Formato audio: float32 mono 16 kHz; SNR y clipping reportados, sin cambios basados en test.
- N_FFT = 512 y hop = 160 como punto de partida, NO especificación irrevocable; Hann con ventanas de análisis ancladas al pasado y padding exclusivamente izquierdo/futuro cero.
- Feature: magnitud logarítmica STFT; aplicar normalizador fijo calculado SOLO de train o estadísticos causales. PROHIBIDO máximo/amplitud por clip completo en inferencia.
- Salida: 257 ganancias por frame [0,1] mediante sigmoid; máscara usada en camino reconstrucción con STFT original. Definir cap de atenuación por política.
- Arquitectura candidata: embedding por clase + temporal Conv1D causal + cabeza espectral. Comparar contra CNN sin etiqueta/etiqueta permutada para probar efecto real de condicionamiento.
- Lookahead del modelo = 0 frames; computar contexto histórico/receptive field; la ventana FFT sigue teniendo duración y retardo que se miden separadamente.
- Guardar todo el contrato de frontend junto al checkpoint. Cambio de frontend invalida paridad de pesos anteriores.

## Protocolo de aprendizaje
- Baselines: M4 histórico (dominio sintético, fuera de comparación de eficiencia del nuevo dominio si no soporta las clases); método DSP clásico; modelo CNN inicial; oracle IRM privilegiado.
- Pre-entrenamiento opcional si la tarea lo requiere; registrarlo y controlar licencia/partición. No presentarlo como CNN propia entrenada desde cero si hubo pesos preentrenados.
- Inicialmente comparar pérdida MSE máscara ideal vs compuesta: pérdida de reconstrucción de mezcla-objetivo restada y penalización de degradación en voz. Los pesos se seleccionan exclusivamente en validation.
- Early stopping y selección por una métrica de validación predefinida que contemple simultáneamente A_target y A_protected; tres semillas mínimas; gradientes y finitud chequeados.
- Las augmentaciones se aplican SOLO en train; validar robustez en gain/phase, nivel, reverberación, target ausente, hard negatives, overlap, fuentes espectralmente próximas.
- No afirmar mejora por aumentar números de escenas del mismo generador. Diferenciar ejemplos de entrenamiento de diversidad de grabaciones.
- Guardar modelo immutable y tabla por run, no reescribir checkpoint histórico.

## Métricas y método estadístico
- Objetivo: A_target dB sobre stem objetivo conocido; reducción debe cotejarse con degradación protegida.
- Voz: A_protected dB, SI-SDRi respecto a voz objetivo deseada, STOI cuando su uso sea compatible con corpus/protocolo. Reportar artefactos subjetivos auditivos mediante muestras, sin sustituir ensayos formales.
- Error del sistema: FALSE ATTENUATION con target ausente, FAIL BLOCK de alarmas/sirenas, salida silenciosa, clipping/NaN, errores de etiquetado M2.
- Semántica: M2 multi-label/SED evaluada por separado sobre mezclas, Macro-F1/recall por clase, calibración/confianza.
- Reportes: distribución por condición y por fuente, media/mediana, p5/p95 pertinentes, intervalos bootstrap AGRUPADOS por fuente original; no contar recortes de una misma grabación como muestras independientes.
- Comparar con y sin acondicionamiento de clase, entrenamiento semillas, máscaras pareadas sobre mezcla SHA igual; nunca comparar una CNN con stems informados por Oracle como si tuvieran inputs equivalentes.

## Criterios de salida: GO / REWORK / STOP
GO si: fuentes reales/licencias válidas, leakage gate PASS, 30+ escenas nuevas + prueba de fuente real; modelo entrenado y reproducido; pérdida y métricas documentadas; límites oficiales de protección/atenuación cumplidos; control class conditioning y target-absent superados; ausencia de fallback silencioso; freeze de checkpoint/test y reporte de incertidumbre. Si M2 falla, no afirmar integración final.
REWORK: caso aislado de insuficiencia o error con explicación y PLAN de nueva validación (no reutilizar test quemado para tuning).
STOP/PIVOT: no existe fuente viable/permiso, el clasificador no generaliza, o atenuación útil incompatible con preservación; reportar resultado negativo y replantear con asesor.
