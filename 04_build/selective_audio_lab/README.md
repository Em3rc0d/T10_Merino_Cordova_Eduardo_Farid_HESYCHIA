# T10 Selective Audio Lab — PI8 Demo

Primer incremento funcional demostrable para la tesis T10.

## Qué demuestra
- Generación de mezcla controlada: señal protegida + evento objetivo + fondo.
- Atenuación selectiva mediante máscara tiempo-frecuencia de línea base.
- Cálculo de métricas: atenuación del objetivo, daño sobre señal protegida, SI-SDRi aproximado y latencia local.
- Evidencia reproducible: JSON, CSV, checksums y artefactos de audio generables.

## Alcance honesto
Este incremento no afirma eficacia clínica ni captura audio de personas con TEA. La máscara PI8 es una baseline/oracle construida con stems conocidos; no es el estimador CNN final. El perfil Android físico queda pendiente de ejecutarse en el Honor X8c.

## Ejecución
```bash
python src/run_demo.py --out outputs/demo_run
python src/latency_benchmark.py --out outputs/latency
```
