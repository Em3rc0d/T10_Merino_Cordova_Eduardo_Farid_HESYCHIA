# SOURCE OF TRUTH — T10 / HESYCHIA

Este archivo define qué documento prevalece cuando existen formulaciones antiguas que fueron corregidas durante la asesoría.

## Orden de precedencia

1. **PI7 v1.1 corregido e integrado PI6 + PI7**
2. **Correcciones formales recibidas en PI6 y PI7**
3. **PI5 — requisitos y escenarios**
4. **Documento maestro original de Tesis I**, únicamente como antecedente histórico cuando una formulación fue reemplazada

## Correcciones que sustituyen formulaciones antiguas

| Formulación anterior | Formulación vigente |
|---|---|
| “Cancelación” interpretada como ANC físico | Atenuación selectiva mediante máscara/ganancia T-F; no se genera antirruido físico |
| CNN multiclase decide directamente qué bins eliminar | M2 reconoce/monitorea; M4 estima máscara T-F condicionada por target |
| Clasificación = separación | Clasificación y separación son problemas desacoplados |
| Target elegido automáticamente por M2 | Target fijado por configuración experimental en v1.1 |
| M3 único | M3a = mezclas offline; M3b = política runtime |
| M5 como etapa posterior | M5 = orquestador del camino crítico/runtime |
| UrbanSound8K + ESC-50 como contrato principal | UrbanSound8K = benchmark/eventos; LibriSpeech = señal protegida; ESC-50 = robustez opcional |
| “latencia <20 ms” como una sola métrica | Laptop: p95 camino crítico por hop ≤10 ms y E2E p95 ≤60 ms; Android TFLite p95 ≤20 ms |
| Android como streaming completo | Android limitado a perfilado TFLite hasta implementación física real |
| SNR genérico como única métrica acústica | A_target, A_protected y SI-SDRi(protected) |
| Sin RF explícito para entrenamiento/exportación | RF-10 entrenamiento del estimador; RF-11 exportación/paridad TFLite |
| Modelo de datos sin N:M explícita | RUN_ASSET resuelve N:M; POLICY_DECISION persiste política |
| Jobs largos síncronos | 202 Accepted + jobId + consulta GET /jobs/{id} |
| Resultados ilustrativos en UI | UI no debe mostrar valores como si fueran mediciones reales |
| Afirmaciones clínicas | Prohibidas: alcance técnico/computacional, no clínico |

## Regla para PI8 y siguientes

Ningún avance posterior puede reintroducir una formulación antigua sin una nueva decisión documentada y versionada.  
Si un requisito técnico no se alcanza, debe registrarse como **incumplido** o versionarse formalmente antes de la evaluación final; nunca ajustarse retrospectivamente después de observar el test.

## Estado PI8

El incremento PI8 actual es una **baseline funcional reproducible con IRM oracle y stems conocidos**. Sirve para probar el contrato DSP, trazabilidad y métricas; **no equivale al estimador CNN final**.

Pendientes para completar la tesis:
- benchmark semántico real;
- entrenamiento de M4 aprendido;
- integración con datasets reales;
- streaming real por bloques;
- TFLite/paridad;
- perfil físico Honor X8c;
- estabilidad de 10 min;
- validación definitiva congelada.

## Estado técnico PI9 y PI10 al 26 de octubre de 2026

El [contrato de integración](docs/PI9_PI10_INTEGRATION_CONTRACT_2026-10-26.md) y el [cierre técnico](docs/PI9_PI10_CIERRE_TECNICO.md) actualizan el estado de implementación: CNN experimental conectada a backend/UI, checkpoint procedural drilling-only, comparación con Oracle, bypass previo a carga y M6 con modelo real. No cambian los objetivos oficiales, el título, los RNF ni los gates científicos. Las menciones PI8 a M4 completamente pendiente quedan como estado histórico; la validación científica del M4 final continúa pendiente.
