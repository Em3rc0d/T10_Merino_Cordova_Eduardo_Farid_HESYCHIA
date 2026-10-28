# Contrato de integración PI9 y PI10

Fecha 2026-10-26. Base e8afd1a S10-A. Alcance autorizado: integración experimental, comparación pareada, seguridad y trazabilidad. El Word institucional y los objetivos oficiales permanecen pendientes de revisión posterior.

## Decisiones de ingeniería

Se reutiliza la arquitectura experimental de 236833 parámetros (embedding 16, tres Conv1D causales 128 con dilataciones 1,2,4, salida sigmoid 257). Se implementa en PyTorch CPU con longitud temporal variable; no se atribuyen pesos de experimentos anteriores. Se genera un NUEVO checkpoint para drilling_synthetic con señales originales procedurales del generador S10-A. Entrenamiento y validación usan semillas disjuntas del mismo generador: esto prueba ingeniería, no independencia de corpus ni generalización científica. MSE de máscara es una pérdida de smoke, no L0 definitiva. Datos reales, RNF-04 y gates D0-D5 siguen abiertos.

La inferencia recibe únicamente mezcla y target_id configurado. Los stems se utilizan para etiquetas de entrenamiento, Oracle y métricas posteriores. La comparación usa exactamente los mismos parámetros y verifica el hash de mixture.wav; no permite comparar escenas distintas. No se modifica el frontend offline centrado ni se afirma streaming.

M3b se ejecuta antes de cargar pesos. BLOCK evita ambos estimadores y conserva identidad digital incluso sin checkpoint o sin PyTorch. ALLOW CNN exige checkpoint + manifiesto coherentes; un error produce fallo explícito, nunca fallback a Oracle. El modelo final validado sigue deshabilitado.

M6 registra motor solicitado y ejecutado, modelo/checkpoint y hashes, historia de entrenamiento, máscara, audio, configuración, métricas y política en JSON/SQLite. Una copia del checkpoint acompaña cada run CNN ejecutado para evitar dependencias mutables. Los runs históricos Oracle mantienen compatibilidad.

La consola debe mostrar arquitectura, checkpoint, historia train/val, límites y pendientes; permitir inferencia y comparación; mostrar máscaras y audios de ambos motores. Se incluyen pruebas de stems ausentes en inferencia, checkpoint corrupto, BLOCK con predictor que falla si se invoca, igualdad de escena, integridad/tamper y API real. Se verifica UI en navegador si el entorno dispone de navegador automatizable.

## Criterio de entrega

E1 inferencia CNN real; E2 comparación pareada Oracle/CNN; E3 sirena BLOCK; E4 verificación SHA/SQLite. Registrar resultados observados sin convertirlos en validación científica. Docker se verificará solo si hay daemon disponible; registrar cualquier limitación. El video y la aprobación del asesor se reportan con su estado real.
