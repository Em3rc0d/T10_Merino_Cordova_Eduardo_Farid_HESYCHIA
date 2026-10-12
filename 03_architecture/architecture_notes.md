# Arquitectura corregida PI6 → PI7 → PI8

El sistema mantiene una arquitectura modular **Pipes and Filters**, pero **no debe representarse como una única cadena lineal M1→M2→M3a→M3b→M4→M5→M6**.

## Camino experimental / offline

```text
Datasets / corpus
      ↓
M1 Ingesta y representación
      ├────────────→ M2 Reconocimiento semántico / benchmark
      │
      └→ M3a Mezclas controladas
               ↓
          M3b Política target/protected
               ↓
          M4 Máscara T-F + reconstrucción
               ↓
          M6 Evidencia y métricas
```

## Camino runtime objetivo en laptop

```text
Audio / bloques
      ↓
M5 Runtime / orquestador
      ├→ M1 representación
      ├→ M3b política
      ├→ M4 máscara + reconstrucción
      └→ M6 evidencia / métricas
```

M2 puede operar como benchmark o monitor semántico, pero en v1.1 **no cambia automáticamente el target**. M3a es exclusivamente offline.

## Estado PI8+

- M5 ya expone una consola web/orquestación de jobs para la demo controlada.
- El procesamiento de clip es funcional.
- El streaming real por bloques y la medición E2E final **siguen pendientes**.
- El smartphone permanece limitado a futuro perfilado TFLite con tensores exportados.
- La evaluación física del Honor X8c no se considera realizada hasta ejecutarla en el dispositivo.

Esta distinción evita presentar el diseño final del runtime como si ya fuese evidencia construida.
