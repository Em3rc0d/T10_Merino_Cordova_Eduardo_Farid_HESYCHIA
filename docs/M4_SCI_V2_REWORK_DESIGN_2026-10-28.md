# M4-SCI V2 — REWORK del estimador de aprendizaje profundo

Fecha: 2026-10-28. Estado: IMPLEMENTACIÓN EXPERIMENTAL DE ENTRENAMIENTO; NO SCIENTIFIC GO.
Dependencia: PR #4 (M4-SCI V1) sigue en borrador; V2 propone integrarse primero a esa rama. P2 streaming permanece BLOCKED.

## Hipótesis contrastable
En test V1 el modelo seleccionado alcanzó 2.529 dB de reducción del objetivo, 1.127 dB de pérdida de voz y 1/48 escenas elegibles con ambos límites cumplidos. Una pérdida con restricciones conjuntas, supervisión del objetivo ausente y contraste de clase podría mejorar la selectividad. No se afirma mejora antes de entrenar ni validar.

## Implementación V2
- M4 es una CNN profunda PyTorch entrenada por retropropagación. Los filtros clásicos y Oracle son baselines, NO reemplazan el estimador aprendido.
- Modalidad selective_v2 conectada al entrenador y CLI, utilizable con CNN temporal/espectral. La primera configuración usa la misma arquitectura CNN temporal causal V1 para aislar el efecto de la nueva función de pérdida; la CNN espectral queda como ablación posterior. Configuración inicial: configs/m4_sci_v2_selective.json.
- Nuevo cache explícito: mezcla, fuente objetivo, habla protegida y fuente de ruido no solicitada. Los stems SOLO entran en entrenamiento/validación, jamás en inferencia.
- Pérdida de entrenamiento con proxies diferenciables de A_target, A_protected y A_nontarget; identidad cuando falta el objetivo; contraste de clase correcta vs intercambiada sobre la misma mezcla; error de máscara auxiliar.
- Los ejemplos con alerta etiquetada quedan fuera de la pérdida de M4 porque M3b aplica BLOCK y bypass antes de cargar el modelo. La política debe verificarse por separado.
- Los dB calculados sobre espectrogramas son aproximaciones de entrenamiento; SOLO las métricas waveform/WOLA del evaluador existente determinan cumplimiento RNF.
- Pruebas nuevas: gradientes CNN, etiquetas contrafactuales, voz sola/objetivo ausente, silencio, seguridad BLOCK.

## Hiperparámetros iniciales, pendientes de tuning SOLO en validación
Límites académicos en evaluación: A_target >= 6 dB y A_protected <= 1 dB por escena elegible. Criterio auxiliar para otra fuente <= 1 dB, margen de clase 1 dB; son hipótesis técnicas y no nuevos RNF. Pesos V2: mask=.1, target=1, speech=2, other=1, absent=2, class=1. No han sido optimizados.

## Ruta de ejecución prevista, NO EJECUTADA sobre corpus real en esta rama
Directorio de trabajo: 04_build/selective_audio_lab

    python -m pytest -q test_m4_scientific.py
    python src/m4_science.py prepare --root data/m4_sci_v2 --conditions full-factorial-v2
    # ATENCIÓN: el corpus descargado es la misma población original que V1.
    # Es útil para desarrollo, NO proporciona un nuevo test independiente.
    # Antes de entrenar: completar revisión humana, procedencia y licencia.
    python src/m4_science.py train --root data/m4_sci_v2 --config configs/m4_sci_v2_selective.json --out runs/v2-seed71

La bandera --pilot-unreviewed permite exclusivamente entrenamiento piloto etiquetado; no transforma pseudo-stems sin revisar en evidencia científica. Ejecutar tres semillas y comparar variantes temporal/espectral usando VALIDACIÓN.

## Gates antes de abrir otro test
1. Revisar aislamientos reales, duplicados perceptuales, licencias e identidades; ampliar fuentes independientes.
2. Predeclarar evaluación simultánea por escena, calibración y métodos estadísticos; aprobación del asesor para cualquier cambio de objetivos.
3. Comparar pérdidas, arquitecturas y semillas exclusivamente en VALIDACIÓN, incluyendo target ausente, voz sola, otras clases y alertas.
4. Congelar código, checkpoint, fuentes nuevas, recetas, política, umbrales y evaluador antes del siguiente test.
5. Test nuevo genuinamente reservado: no reutilizar las 160 escenas ya observadas de PR #4 para entrenar, seleccionar o confirmar V2.
6. Exigir cumplimiento simultáneo de ambos RNF por escena elegible y reportar intervalos de incertidumbre y fallas. Sin GO, P2 streaming continúa bloqueado.

## Restricción crucial del test final
La orden prepare reutiliza exactamente la población ESC-50/SLR31 fijada en V1. Cambiar carpeta o semillas NO genera fuentes independientes. El sistema aún NO cuenta con un importador de una cohorte adicional de evaluación externa. El siguiente gate científico exige adquirir y registrar grabaciones realmente nuevas, separadas por fuente/hablante y nunca usadas en el test publicado. Hasta entonces, no ejecutar evaluate presentándolo como confirmación V2.

## Limitaciones no resueltas
Todavía no se ha entrenado V2 con un nuevo corpus. ESC-50 aporta pseudo-stems pendientes de escucha; la voz previa es lectura en inglés; M2 genera falsos positivos de alerta; no hay validación en campo, streaming, hardware ni eficacia clínica TEA. No se modifican título ni objetivos oficiales.
