# Target runtime y arquitectura profunda de M4

## Problema que resuelve este contrato

La baseline M2 reconoce una clase acústica, pero una etiqueta global no identifica por sí sola qué bins tiempo-frecuencia pertenecen al target dentro de una mezcla. Por ello M2 y M4 no se modelan como una cadena rígida clasificador -> máscara.

## Decisión de arquitectura

El target operativo se define mediante una **política de clase**:

1. el operador/perfil configura una clase objetivo permitida (`target_id`);
2. M3b valida la política `target/protected`;
3. si el target pertenece al conjunto protegido, la decisión es `BLOCK` y `g=1`;
4. si la política permite actuar, M4 recibe directamente la mezcla y el `target_id`;
5. M4 estima una máscara tiempo-frecuencia **condicionada por clase** para ese target;
6. M2 puede funcionar como benchmark/monitor o sugeridor de eventos, pero no modifica la política sin pasar por M3b.

Con esto, la pregunta «¿quién identifica la sirena?» se separa en dos funciones:

- **qué clase se desea atenuar:** política/configuración de target;
- **dónde está esa clase dentro de la mezcla:** M4 target-conditioned mask estimator.

## Arquitectura aprendida preespecificada

Entrada principal: `|X| -> [B,T,257]`.

Condicionamiento: `target_id -> Embedding(16)`.

Backbone causal:

- Conv1D causal, 128 canales, kernel 3, dilatación 1, ReLU;
- Conv1D causal, 128 canales, kernel 3, dilatación 2, ReLU;
- Conv1D causal, 128 canales, kernel 3, dilatación 4, ReLU.

Salida: `Dense(257, sigmoid) -> M_hat`.

No se permite look-ahead en la variante de streaming.

## Ground truth de entrenamiento

`IRM = |S_target| / (|S_target| + |S_rest| + eps)`.

## Función de pérdida

`L = 0.5 * MAE(M_hat, IRM) + 0.5 * MAE(M_hat*|X|, |S_target|) / (mean(|S_target|)+eps)`.

## Política de aplicación

- `BLOCK`: `g = 1`;
- `ALLOW`: `g = max(1 - alpha*M_hat, 10^(-cap_db/20))`;
- reconstrucción: `Y = g * X`, seguida de iSTFT.

## Estado S8

La arquitectura anterior está **definida y congelada**, pero aún no entrenada como M4 final. Las cifras actuales de M4 provienen de una IRM calculada con stems limpios y deben rotularse como **techo oracle**.

## Gate de implementación

Antes de declarar M4 aprendido:

1. entrenamiento reproducible con mezclas train;
2. selección con validación sin usar test final;
3. evaluación de A_target, A_protected, SI-SDRi protegido y target;
4. comparación contra techo oracle;
5. exportación TFLite y paridad;
6. medición blockwise/E2E en laptop.