# M4 V3 — Auditoría humana de pureza acústica y nueva cohorte independiente

Estado: **PENDIENTE**. Este protocolo NO certifica la pureza de ESC-50 ni Mini LibriSpeech; la inspección auditiva requiere escuchar las grabaciones originales con permiso aplicable.

## Propósito

Las fuentes ESC-50 son **pseudo-stems de grabaciones reales**: cada clip tiene una etiqueta ambiental, pero puede contener simultáneamente voz, motores, reverberación, otras clases o alarmas. Una máscara aprendida de estas fuentes no necesariamente puede identificar lo que la anotación pretende aislar. El piloto V2 validó mejor voz (36/48) pero tuvo cero escenas con target >=6 dB. No atribuir el fallo exclusivamente a la arquitectura antes de auditar las fuentes.

## Procedimiento preregistrado antes de un nuevo test

1. Usar el registro de activos congelado y su atribución original. No copiar el audio a GitHub; reconstruirlo legalmente a partir de las fuentes originales fijadas y validar SHA. Documentar ID, clase, source_group, split, duración, clipping y licencia.
2. Inspección auditiva por clip (auriculares en volumen seguro; una persona y, cuando sea viable, segunda persona sin conocer el split). Clasificar pureza de evento principal; presencia de otros eventos objetivos, voz, alarmas u otros sonidos significativos; artefactos/clipping; inicio/fin. No reinterpretar un sonido mezclado como fuente aislada.
3. Guardar por cada revisión: asset_id, reviewer_id pseudónimo, fecha, versión del protocolo, fuente original, rango temporal escuchado, etiqueta principal, clase audible secundaria, presencia de voz, presencia de alarma, pureza (aislado / contaminación leve / mixto / indeterminado), causa de duda, veredicto (eligible / restricted / reject), evidencia de autorización/licencia y notas. Firmar el CSV+SHA sin modificar datos históricos.
4. Diferencias entre revisores: registrar ambos juicios y resolución de discrepancias; calcular acuerdo entre categorías si hay dos revisores. No forzar consenso ni eliminar desacuerdos del registro.
5. Anotar fragmentos de voz según hablante y contexto (lectura en inglés), sin inferir que generalizan a conversación espontánea en español.
6. Excluir de un set de referencia limpio los clips cuya interferencia impide determinar qué fuente causa la energía atenuada. Si se excluyen clips, crear **nueva versión** de corpus y recetas con nueva justificación/sha; no reescribir resultados V1/V2.
7. Una cohorte final nueva debe incluir grabaciones **originales nunca vistas** en entrenamiento, validación o test V1. Evitar duplicados exactos y perceptuales, repeticiones de Freesound y hablantes repetidos. Congelar identidades, metas acústicas y evaluador ANTES de ejecutar test.
8. No prometer relevancia clínica para hiperacusia o TEA por el solo hecho de incluir clases sonoras molestas. Documentar la selección por fuentes revisadas científicamente y evitar pruebas con personas sin protocolo/ética autorizados.

## Registro mínimo de revisión

Campos recomendados para CSV: asset_id,source_group,split,class,reviewer_id,date_utc,source_reference,license_verified,listen_start_s,listen_end_s,primary_audible,secondary_events,speech_present,alert_present,source_purity,clipping_audible,review_decision,reason,protocol_version.

Los artefactos de revisión son **datos de evidencia**, no parámetros de entrenamiento hasta que se autorice una nueva versión de corpus; jamás ajustar la cohorte TEST externa usando sus resultados de modelo.

## Gate

- Hasta completar este registro, la prueba spectral/CNN contrafactual sigue siendo un **piloto de desarrollo con fuentes no auditadas**.
- Una ablación donde la CNN espectral supere V2 en VAL justificaría replicación con múltiples semillas, no aprobación del título.
- Sin mejora de selectividad, hacer análisis de representabilidad/Pareto con Oracle restringido y mejorar datos antes de aumentar complejidad o emprender streaming.
