# Checklist de entrega — Examen Parcial Semana 8

## Antes de exponer

- [x] Repositorio clonado y ejecutable en la laptop.
- [x] Dependencias instaladas.
- [ ] Recrear `.venv` con Python 3.11, no 3.14.
- [ ] Completar descarga de UrbanSound8K.
- [ ] Descomprimir `UrbanSound8K.tar.gz`.
- [ ] Validar estructura con `validate_urbansound8k.py`.
- [ ] Ejecutar benchmark real M2 si el tiempo alcanza.
- [ ] Subir evidencia real M2 si se ejecuta correctamente.

## Evidencia mínima defendible ya disponible

- [x] Pipeline PI8 reproducible.
- [x] M3b política ALLOW/BLOCK.
- [x] M4 baseline IRM oracle.
- [x] M6 evidencia con SQLite.
- [x] Validador de artefactos.
- [x] CI exitoso.
- [x] Pipeline M2 implementado.
- [x] Fixture M2 probado en CI.
- [x] Protocolo UrbanSound8K congelado.

## Qué NO decir

- [ ] “El modelo ya aprendió a cancelar ruido”.
- [ ] “Ya tengo resultados reales de UrbanSound8K”.
- [ ] “Ya corre en Android”.
- [ ] “Ya cumple latencia del Honor X8c”.
- [ ] “Esto demuestra eficacia clínica en TEA/hiperacusia”.

## Qué SÍ decir

- [x] “El primer incremento funcional ya es reproducible”.
- [x] “M2 ya tiene pipeline ejecutable, pero el resultado real depende de correr el dataset completo”.
- [x] “M4 actual usa una baseline oracle, no la CNN final”.
- [x] “No se está haciendo ANC físico, sino atenuación selectiva T-F”.
- [x] “La tesis mantiene alcance técnico-computacional, no clínico”.

## Comandos finales del dataset

```powershell
cd C:\Users\eduar\Desktop\Farid\T10_Merino_Cordova_Eduardo_Farid_HESYCHIA\04_build\selective_audio_lab
Remove-Item -Recurse -Force .venv
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt

$DATASET = "C:\Users\eduar\Desktop\Farid\UrbanSound8K"
.\.venv\Scripts\python.exe src\validate_urbansound8k.py --dataset-root "$DATASET"
.\.venv\Scripts\python.exe src\semantic_benchmark.py --dataset-root "$DATASET" --out "outputs\m2_urbansound8k" --seed 42
```

## Criterio de subida de evidencia

Solo se sube evidencia M2 real si existen:

- `semantic_summary.json`;
- `validation_models.csv`;
- `confusion_matrix_test_fold10.csv`;
- `predictions_test_fold10.csv`;
- modelo `.joblib` seleccionado;
- validación previa del dataset con `official_shape_ok: true`.
