# Demostración de sustentación · noviembre de 2026

La consola incluye dos recorridos distintos. El rótulo de la interfaz ya no identifica el parcial como versión actual.

## Inicio local

Desde `04_build/selective_audio_lab`, con el entorno Windows recreado:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-lock.txt
python -m pip install -r requirements-m4.txt
python src/web_server.py --host 127.0.0.1 --port 8080
```

Abrir http://localhost:8080. Si el servidor estaba abierto durante el pull, detenerlo con Ctrl+C y reiniciarlo. Recargar el navegador con Ctrl+F5. No es necesario reentrenar ni volver a descargar el corpus para inferir un WAV.

## Candidato actual con WAV

1. Estado muestra la versión y el commit de la copia local, con indicación de cambios locales si los hay.
2. Abrir **CNN con audio WAV**. Verificar el checkpoint seleccionado `c0b34027fe1d4165b062f4145ca7173b3d547cedc39846e17298295e99fb1966`.
3. Adjuntar un WAV autorizado, mono o estéreo, de hasta 15 s y 4 MiB. Usar una grabación de desarrollo o propia; no abrir el test reservado para preparar la exposición.
4. Seleccionar aspiradora o motosierra según el audio. Ejecutar ALLOW y escuchar entrada y salida al mismo volumen. La entrada de escucha es el PCM mono remuestreado a 16 kHz, también conservado como artefacto.
5. Mostrar el identificador, motor ejecutado y hashes. La entrada original, entrada 16 kHz, salida, metadatos y figura quedan en `outputs/web/SCIENCE-*/` (o en el output-root configurado).
6. Ejecutar BLOCK: el predictor no se invoca; se verifica la igualdad PCM con la entrada mono/16 kHz. No se promete identidad de bytes con el archivo original estéreo o de otra frecuencia.
7. Abrir **Evidencias** para recuperar registros persistidos, incluso después de reiniciar.

El candidato actual tiene **217 937 parámetros** según su resumen seleccionado. La arquitectura de ingeniería sintética previa tiene **236 833 parámetros**: no son el mismo modelo. Mantener esa distinción en documentos y exposición.

No hay fallback a Oracle si el checkpoint actual falta, cambia su SHA o falla. Sin stems limpios no se calculan A_target, A_protected ni SI-SDRi de un WAV subido. Esta ruta muestra inferencia offline y evidencia; no ejecuta el test confirmatorio ni acredita eficacia clínica, streaming o reconocimiento automático de alertas.

## Comparación sintética de ingeniería

**Demo sintética** conserva el recorrido CNN experimental / Oracle y ALLOW/BLOCK con perforación y señal tonal. Se conserva para verificar la integración histórica y comparación pareada con las mismas mezclas. Utiliza otro checkpoint y no debe presentarse como inferencia del candidato entrenado con grabaciones reales. Sus resultados no son validación con voz humana.

## Recorrido de video de 2–3 minutos

- 0:00–0:20: identificar el artefacto y commit en Estado.
- 0:20–0:45: mostrar el checkpoint del candidato actual y seleccionar WAV / objetivo.
- 0:45–1:25: ejecutar ALLOW, escuchar entrada/salida y mostrar el motor.
- 1:25–1:55: ejecutar BLOCK y mostrar bypass exacto PCM y predictor no invocado.
- 1:55–2:25: abrir evidencia y hashes.
- 2:25–2:40: indicar que la inferencia es offline y que la comparación confirmatoria queda pendiente.

La comparación sintética con Oracle puede grabarse como toma complementaria identificada; no confundir sus resultados con la ejecución WAV del candidato actual.

## Verificación local

```powershell
python -m unittest test_scientific_web test_web_server -v
```

Las nuevas pruebas comprueban inferencia del checkpoint real sobre un tono generado para QA, BLOCK sin llamar al estimador, hashes de artefactos, rechazo de audio/etiquetas inválidas, duración máxima y fallo sin fallback con checkpoint no disponible. Son pruebas de ingeniería, no nuevas mediciones científicas.
