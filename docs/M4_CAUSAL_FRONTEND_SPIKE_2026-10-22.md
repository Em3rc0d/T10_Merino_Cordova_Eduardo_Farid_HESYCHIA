# D2 · Prueba de concepto causal STFT/WOLA — 2026-10-22

**Estado: referencia de ingeniería validada con fixtures, NO streaming E2E ni frontend integrado a M4.**

Se incorpora m4_causal_frontend.py separado del DSP PI8 histórico. La implementación reference-only:
- recibe hops mono exactos de 160 muestras a 16 kHz;
- conserva ventana de 512 muestras, ventana sqrt-Hann periódica, FFT real y superposición-suma ponderada con normalización;
- sólo lee historia y bloque presente, no futuro;
- devuelve posición absoluta lógica de cada salida; posiciones negativas durante pre-roll no se contabilizan como muestras útiles;
- ofrece un helper offline_as_stream para comparar reconstrucción, NO simula captura/salida física;
- admite máscara de ganancia por frecuencia [257], válida en [0,1] para pruebas de identidad/bypass/silencio.

Pruebas del diseño local: reconstrucción con ganancia=1 de seno+ruido aleatorio, máscara cero, no-lookahead en prefijos idénticos, shapes/rangos y equivalencia de ganancia unitaria. No se utilizaron datos científicos ni se entrenó CNN.

**No satisface todo el gate D2**: falta unir el extractor y normalizador para M4, verificar invariancia offline-vs-stream para una red con 14 frames de historia, cuantificar latencia algorítmica y jitter real, gestionar BLOCK/ALLOW dinámico, cambios de buffer y dispositivos. Los 512/16000=32ms son contexto de ventana; 160/16000=10ms es periodo de hop. No equivalen por sí solos a E2E. El algoritmo emite su bloque con timestamp lógico que exige considerar pre-roll y el calendario de captura/salida.

No alterar resultados anteriores ni afirmar que el p95 whole-clip Acer 34.607 ms equivale a p95/hop.

### Smoke tests
cd 04_build/selective_audio_lab
python -m unittest test_m4_data_gate.py test_m4_causal_frontend.py
