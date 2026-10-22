# D0 · Auditoría de fuentes y licencias para M4 — 2026-10-22

**Estado: BLOQUEADO PARA ENTRENAMIENTO CIENTÍFICO HASTA INSPECCIÓN DE AUDIO REAL.** La revisión documental de fuentes oficiales sí está hecha; no se ha descargado ni revisado acústicamente el corpus en este entorno.

| Corpus | Hallazgo verificable | Decisión |
|---|---|---|
| UrbanSound8K | 8,732 fragmentos de grabaciones de campo con clases etiquetadas; la etiqueta siren no garantiza stem de sirena aislada. El sitio oficial prohíbe rebarajar folds para comparaciones M2 y recomienda validación cruzada 10-fold. Los términos de uso incluidos en README exigen uso no comercial, con atribución. | Mantener M2 y el baseline congelado; para M4 sólo pseudo-stem etiquetado o selección auditada. No reescribir folds M2. |
| LibriSpeech SLR12 | Corpus de voz leída en inglés, 16 kHz, licencia CC BY 4.0; train-clean-100 ~6.3 GB, dev-clean ~337 MB, test-clean ~346 MB. | Voz protegida; validar speaker IDs disjuntos, disponer de archivos/hashes y atribuir fuente. |
| FSD50K | Grabaciones etiquetadas a nivel de clip; no equivale automáticamente a stems aislados. Licencias Creative Commons varían por clip. | Candidato para búsqueda/curación; no aprobado como sustituto limpio. |
| FUSS | Contiene stems fuente y mezclas controladas, pero los stems no están etiquetados por clase para la tarea estándar. | Candidato alternativo para probar separación genérica; no adjudicar clase siren sin evidencia. |
| DESED Synthetic Soundbank | Publica material de foreground aislado y backgrounds, orientado a sonidos domésticos. | Candidato técnico de fuente aislada; comprobar si posee clases pertinentes y derechos. |

## Referencias verificadas

1. Página oficial de UrbanSound8K: https://urbansounddataset.weebly.com/urbansound8k.html
2. README de la distribución que reproduce condiciones CC BY-NC 3.0: https://github.com/cyrta/UrbanSounds/blob/master/data/UrbanSound8K/README.txt (revalidar con la copia oficial antes de redistribución)
3. LibriSpeech SLR12: https://openslr.elda.org/12/
4. FSD50K: https://fsannotator.upf.edu/fsd/release/FSD50K/
5. FUSS: https://github.com/google-research/sound-separation/blob/master/datasets/fuss/FUSS_license_doc/README.md
6. DESED Synthetic: https://zenodo.org/records/4569063

## Decisiones y blockers

- UrbanSound8K **NO es automáticamente target aislado**. El salience=1 indica evento en primer plano, no una fuente separada.
- Registrar licencias exactas por clip si se extraen de Freesound/FSD50K; no aplicar una única licencia a fuentes mixtas sin evidencia.
- El gate de software valida el registro CSV y hashes y rechaza source_id, recording_id, speaker_id y sha256 compartidos entre splits. **No detecta similitud acústica, un uploader común, contaminación oculta ni calidad de aislamiento**.
- Una vez tengan fuentes reales, llenar CSV con source_id,role,split,recording_id,speaker_id,path,sha256,license,reference_grade. Valores grade: isolated para target puro; pseudo_stem si incluye ambiente; speech y background para los otros roles.
- Para M4 no se usa el fold10 M2 como validación adicional, ni se afirma que una prueba repetida en ese fold sea ciega. El protocolo de M4 es distinto, explícito y necesita referencias aisladas y un test independiente.
- Si no hay fuentes siren aisladas, se puede realizar un experimento acotado pseudo-stem **solo con lenguaje científico limitado**; no transforma el problema en separación pura.

### Ejecución del control

Desde 04_build/selective_audio_lab:
python src/m4_data_gate.py --registry /ruta/m4_sources.csv --out outputs/m4/source_audit.json

Sólo puede afirmarse integridad documental del registro y sus hashes tras ejecución real, no pureza acústica.
