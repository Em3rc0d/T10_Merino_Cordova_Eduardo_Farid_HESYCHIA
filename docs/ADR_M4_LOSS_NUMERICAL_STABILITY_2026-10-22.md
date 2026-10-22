# ADR D3 · Estabilización numérica de L0 para ausencia del target

**Fecha:** 2026-10-22. **Estado:** ENGINEERING-CANDIDATE — *NO APROBADO FORMALMENTE PARA TESIS*.

## Problema observado

El contrato PI7 establece una loss supervisada:

`L0 = 0.5*MAE(Mhat,IRM) + 0.5*MAE(Mhat*|X|, |S_target|)/(mean(|S_target|)+eps)`

Con ausencia de target o energía residual casi cero, `mean(|S_target|)` es aproximadamente 0. Esto puede desestabilizar gradientes y provoca dependencia sensible al epsilon. La arquitectura, target condicionable, función de máscara y política de ganancia **no cambian**.

## Candidato prospectivo L0-stable-v1

Para cada escena `i`:

- `mu_t(i) = mean(|S_target(i)|)`
- `mu_x(i) = mean(|X(i)|)`
- `denom_i = max(mu_t(i), 0.01 * mu_x(i), 1e-4)`
- `L0_stable = 0.5 * MAE_global(Mhat, IRM) + 0.5 * mean_i[MAE(Mhat_i*|X_i|,|S_target_i|)/denom_i]`

La forma evita división por un denominador ínfimo y conserva la intención de supervisión de máscara + magnitud. **No es algebraicamente idéntica a L0 PI7**, porque introduce floor dependiente de mezcla y normalización por escena. El piso `0.01` y `1e-4` son configuraciones de ingeniería escogidas antes del experimento final, no clínicamente fundamentadas. No hay permiso para retitularla L0 original; reportarla como variante y someterla a aprobación antes de claims científicos.

La penalización opcional de preservación de voz existente en el código se mantiene `speech_weight=0` para la primera comparación. Un valor diferente requiere un experimento preespecificado con decisión basada **exclusivamente en train/val**; las pruebas sintéticas ya observadas no autorizan seleccionar ese parámetro como resultado científico.

## Tests ejecutados (fixtures únicamente)

- Target ausente con mezcla no nula: pérdida finita y gradientes finitos.
- Target y mezcla casi silenciosos: no NaN, no Inf y gradientes finitos.
- Penalización de voz deshabilitada por defecto y variante no confundida con primaria.

Archivo: `experiments/test_m4_loss_gate.py`; implementación ya existente `src/m4_causal_bridge.py`. Esta ADR no modifica la implementación previamente versionada ni sobrescribe resultados anteriores.

## Decisión de gobernanza

- **Permitido:** pruebas de regresión, integración de pipeline y candidatos de entrenamiento de ingeniería con rótulo inequívoco.
- **Bloqueado:** adoptar `L0_stable` como pérdida definitiva de tesis, afirmar eficacia sobre audios reales o seleccionar pesos basándose en test antes de la revisión del asesor y el congelamiento del protocolo.
- **Próxima aprobación necesaria:** registrar conformidad con pérdida estabilizada o definir alternativa justificable para negativos ausentes; guardar decisión junto a versión de corpus/split y presupuesto de candidatos.
