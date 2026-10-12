# Informe consolidado S5–S8 — T10

**UNMSM · FISI · Proyecto de Tesis II**  
**Tesista:** Merino Córdova, Eduardo Farid  
**Grupo:** B — aporte práctico/software  
**Asesor:** Daniel Alfonso Quinto Pazce  
**Tema institucional:** Diseño de un sistema inteligente de cancelación selectiva de ruido mediante aprendizaje profundo para la atenuación de estímulos acústicos asociados a la hiperacusia en personas con TEA.

> Nota terminológica: se mantiene el título institucional. Técnicamente, “cancelación” se operacionaliza como **atenuación selectiva mediante máscara/ganancia tiempo–frecuencia**. No se implementa ANC físico por antirruido ni se realizan afirmaciones clínicas.

## 0. Resumen ejecutivo

El parcial demuestra la cadena solicitada por el curso:

```text
Problema → OE → Requisitos S5 → Arquitectura S6 → Diseño S7 → Construcción S8 → Validación
```

PI5 cerró requisitos, restricciones, escenarios y ética. PI6 definió arquitectura modular Edge-local. PI7 v1.1 integró observaciones de PI6/PI7 y cerró M3a/M3b, A5-train/A5-infer, modelo de datos, presupuesto de latencia y alcance Android. PI8 convierte el diseño en un incremento funcional reproducible.

## 1. Estructura de trabajo

| Carpeta | Rol |
|---|---|
| 00_brainstorming | narrativa de defensa y preguntas |
| 01_design | decisiones cerradas |
| 02_plan | entrega, demo, validación |
| 03_architecture | arquitectura y esquema |
| 04_build | incremento funcional |
| 05_evidence | resultados reproducibles |
| 06_presentation | exposición |
| 07_submission | documentos de entrega |
| 08_existing_context | contexto previo |

## 2. Requisitos consolidados

### RF
- **RF-01:** ingesta WAV/FLAC y mono 16 kHz.
- **RF-02:** STFT/log-Mel/MFCC versionados.
- **RF-03:** benchmark semántico con particiones oficiales.
- **RF-04:** target, protected y límites de atenuación.
- **RF-05:** mezclas controladas conservando stems.
- **RF-06:** máscara T-F condicionada por target.
- **RF-07:** reconstrucción iSTFT/OLA.
- **RF-08:** runtime local y perfilado.
- **RF-09:** expediente por Run ID.
- **RF-10:** entrenamiento del estimador de máscara con partición congelada.
- **RF-11:** exportación/paridad TFLite.

### RNF medibles
- reproducibilidad: |ΔMacro-F1| ≤ 0.005 bajo misma configuración/seed/fold;
- integridad: folds oficiales y ausencia de fuga train/test;
- Macro-F1 candidato ≥ 0.85 como criterio de ingeniería preespecificado;
- mediana A_target ≥ 6 dB; A_protected ≤ 1 dB; SI-SDRi(protected) > 0 dB;
- laptop: p95 camino crítico ≤ 10 ms/hop y E2E p95 ≤ 60 ms;
- Android: inferencia TFLite p95 ≤ 20 ms;
- TFLite ≤ 10 MB; benchmark Android ≤ 256 MB RAM;
- 10 min de estabilidad, drop/underrun < 1 %;
- sin audio primario de personas con TEA en validación base;
- paridad TFLite float32: MAE máscara ≤ 0.01.

Estos valores son criterios técnicos del prototipo, no umbrales clínicos.

## 3. Arquitectura

**Patrón:** Pipes and Filters, Edge-local.

| Módulo | Responsabilidad |
|---|---|
| M1 | ingesta y representación |
| M2 | reconocimiento semántico/monitor |
| M3a | mezclas controladas offline |
| M3b | política target/protected |
| M4 | máscara T-F y reconstrucción |
| M5 | runtime y perfilado |
| M6 | evidencia y métricas |

Correcciones clave:
- M5 envuelve/orquesta el camino crítico;
- M3a no participa en streaming;
- M2 no cambia automáticamente el target;
- Android queda en perfilado TFLite con tensores exportados;
- el streaming E2E completo **se validará en laptop en una fase posterior**; PI8+ demuestra procesamiento local de clip y consola reproducible, no streaming final.

## 4. Diseño detallado

### Proceso de atenuación controlada
```text
stems + target + configuración
          ↓
mezcla controlada (M3a)
          ↓
política target/protected (M3b)
          ↓
máscara/gain T-F (M4)
          ↓
iSTFT/OLA
          ↓
audio + métricas + artefactos (M6)
```

### A5 — diseño final
Entrenamiento: mezcla |X| + target_id + stems. Target embedding de 16 dimensiones; arquitectura causal; IRM objetivo:

```text
M*(t,f) = |S_target| / (|S_target| + |S_rest| + ε)
```

Ganancia:

```text
g_min = 10^(-cap_dB/20)
BLOCK → g=1
ALLOW → g=max(1-α·M_hat, g_min)
Y = g·X
```

### Datos
SQLite conserva DATASET, AUDIO_ASSET, MODEL_VERSION, EXPERIMENT, RUN, RUN_ASSET, POLICY_DECISION, METRIC y ARTIFACT. Los binarios viven en filesystem y se resuelven por SHA-256.

## 5. Construcción PI8

PI8 implementa una **línea base funcional y reproducible**, no el modelo final:

- stems sintéticos controlados;
- mezcla;
- STFT;
- máscara IRM oracle basada en stems;
- ganancia selectiva con cap_dB;
- iSTFT;
- A_target, A_protected y SI-SDRi;
- benchmark local;
- JSON/CSV/checksums.

La baseline oracle sirve para demostrar el contrato de M4 y la trazabilidad del pipeline. **No se presenta como CNN entrenada ni como resultado final.**

## 6. Evidencia PI8

Run de referencia: `PI8-DEMO-RUN-001`.

| Métrica | Valor observado |
|---|---:|
| A_target | 11.994 dB |
| A_protected | 0.007 dB |
| SI-SDRi protected | 11.518 dB |
| Latencia local p50 | 14.035 ms |
| Latencia local p95 | 15.702 ms |

La latencia registrada corresponde al procesamiento del clip completo de 4 s en el entorno local de desarrollo; no debe confundirse con p95 por hop, E2E de captura/salida ni perfil Android.

## 7. Trazabilidad

| OE | Requisitos | Componentes | Diseño | Evidencia PI8 |
|---|---|---|---|---|
| OE1 | RF-01/02/03 | M1/M2 | A1/A2 | M1 construido; benchmark real preparado |
| OE2 | RF-04/05/06/07 | M3a/M3b/M4 | A3–A6 | mezcla, máscara baseline, salida, métricas |
| OE3 | RF-08/09/11 | M5/M6 | A7–A9 | latencia local, JSON/CSV/checksums; Android pendiente |

## 8. Plan de validación

| Semana | Hito |
|---|---|
| S9 | entrenar estimador de máscara real |
| S10 | integrar M4 real y perfilar |
| S11 | cerrar plan formal de validación |
| S12 | casos formales + baseline DSP |
| S13 | validación definitiva sin cambios post hoc |
| S14–S15 | resultados, discusión y defensa |

## 9. Riesgos
1. **Latencia del M4 aprendido:** optimizar o reportar incumplimiento.
2. **Daño a señal protegida:** política de precedencia, cap_dB y métricas separadas.
3. **Android:** no afirmar mediciones hasta ejecutar en Honor X8c.
4. **Ambigüedad “cancelación”:** explicar atenuación T-F, no ANC físico.
5. **Datos reales:** UrbanSound8K y LibriSpeech con particiones oficiales.

## 10. Ética
La validación base no requiere participantes con TEA ni datos clínicos. Se utilizan datasets públicos/licenciados y mezclas sintéticas. Cualquier captura humana primaria requerirá consentimiento informado y autorización aplicable.

## 11. Conclusión
El parcial demuestra que la tesis ya pasa de especificación a construcción: existe una cadena verificable desde OE y requisitos hasta código y evidencia reproducible. El PI8 actual es un primer incremento controlado; el siguiente gate es sustituir la baseline oracle por el estimador M4 aprendido y ejecutar el perfil TFLite real.

## Referencias nucleares
- ISO/IEC 25010:2023.
- Oppenheim & Schafer (2010).
- Salamon, Jacoby, & Bello (2014), UrbanSound8K.
- Panayotov et al. (2015), LibriSpeech.
- Wang & Chen (2018), supervised speech separation.
- Kavalerov et al. (2019), universal sound separation.
- Le Roux et al. (2019), SI-SDR.
