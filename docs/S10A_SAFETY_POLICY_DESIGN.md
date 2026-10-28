# S10-A — Contrato de política de protección acústica

**Fecha del diseño:** 2026-10-25. **Origen:** observación 6 del parcial T10. **Ámbito:** simulación reproducible de software con señales controladas. **No es certificación de seguridad auditiva o eficacia clínica.**

## Problema, causa y decisión

La demo PI8 permitía `ALLOW` para `siren_synthetic` cuando la etiqueta faltaba en el conjunto protegido. La solución no consiste en ocultar la opción de la interfaz: M3b debe impedir una decisión insegura desde cualquier consumidor, incluso API. Los experimentos históricos de sirena conservan su valor como investigación offline; no se reescriben resultados anteriores.

## Contrato M3b — POLICY_VERSION S10A-1.0

- `MANDATORY_PROTECTED`: `siren_synthetic`, `siren`, `emergency_siren`, `fire_alarm`, `evacuation_alarm`, `car_horn`, `vehicle_horn`, `warning_horn`, `speech`, `speech_like_synthetic`.
- `ATTENUABLE_TARGETS`: `drilling_synthetic`, único target atenuable aprobado para esta demo; **no** implica capacidad de la CNN aprendida para localizar perforaciones.
- La interfaz solo ofrece `drilling_synthetic` y `siren_synthetic` (el segundo para probar bloqueo).
- El conjunto protegido efectivo es la unión del solicitado por el operador más las clases obligatorias. No existen anulaciones.
- Target obligatorio → `BLOCK / mandatory_protected_signal`.
- Target permitido pero protegido manualmente → `BLOCK / target_is_protected`.
- Target permitido no bloqueado → `ALLOW / approved_attenuable_target`.
- Target desconocido → rechazo antes de ejecutar audio; no inferir que es seguro.

## Pipeline y contratos de salida

`configuración → validación → M3b → [BLOCK: bypass digital | ALLOW: IRM oracle] → M6 evidencia`.

Ante `BLOCK`: salida digital igual a la mezcla; ganancia 1, máscara cero **como placeholder** para el archivo de evidencia, sin ejecutar STFT/IRM/iSTFT. Esto demuestra bloqueo de una etiqueta configurada, **no detección automática de señales de emergencia en una mezcla**.

Ante `ALLOW`: `synthesize_drilling` genera una fuente procedural (textura de ruido filtrado, armónicos altos y pulsos), con stems separados. La IRM es una máscara privilegiada calculada a partir de estos stems, **no M4 aprendido**. `speech_like_synthetic` es una fuente tonal, no voz humana inteligible.

La configuración de cada run registra `safety_policy_version=S10A-1.0` y `source_scope=synthetic_procedural_fixture_only`. Los runs antiguos no se reclasifican.

## Limitaciones obligatorias para defensa

1. Protección por etiquetas, no por percepción autónoma de alarma o ubicación espacial.
2. Ausencia de garantías frente a alarmas concurrentes, fallos del clasificador, eventos desconocidos o señales de seguridad presentes en otra fuente de la mezcla.
3. Bypass digital no garantiza audibilidad física ni seguridad del usuario en entornos reales.
4. No se modifican M2, modelo profundo M4, arquitectura científica, título oficial ni resultados previos.
5. El cumplimiento de RNF-04 exige experimentos con habla real y particiones disjuntas. **Esta demo no lo acredita.**
6. La declaración formal de asistencia de IA en la tesis sigue como observación 3 pendiente.

## Criterio de levantamiento O6

Requiere política probada, caso ALLOW no crítico, caso BLOCK de sirena, API y consola reproducibles, integridad de artefactos, versión documental y video narrado con minuto de evidencia. Solo entonces el tesista podrá proponer `LEVANTADA` para validación del asesor.
