# M4 — descubrimiento separado de fuentes objetivo y escenas reales (2026-10-22)

Este expediente preserva una distinción metodológica esencial: para supervisar la máscara de atenuación M4 se necesitan referencias **objetivo aisladas**; grabaciones de calle con sirena + tráfico + voces **no son stems puros**. No fingir ground truth cuantitativo separable.

- [FS_746302, TitanKaempfer](https://freesound.org/people/TitanKaempfer/sounds/746302/): Freesound CC0, 15.554 s, Ogg Vorbis, sirena policial sintetizada mediante onda triangular. Se incorpora como **candidato target sin descarga ni aprobación manual** al catálogo m4; no equivale a sirena acústica de un vehículo real.
- [FS_716552, AudioPapkin](https://freesound.org/people/AudioPapkin/sounds/716552/): CC0, 15.183 s, WAV, ambulancia grabada en exterior con contexto vehicular; **mezcla real**, no referencia pura.
- [FS_834507, RutgerMuller](https://freesound.org/people/RutgerMuller/sounds/834507/): CC0, 39.850 s, M4A/ALAC 48 kHz, sirena de emergencia distante grabada en Países Bajos; **mezcla real**.
- [FS_834502, RutgerMuller](https://freesound.org/people/RutgerMuller/sounds/834502/): CC0, 34.560 s, M4A/ALAC 48 kHz, sirenas y tráfico de Barcelona; **mezcla real**.
- [FS_329774, paulmessier](https://freesound.org/people/paulmessier/sounds/329774/): CC0, 15.193 s, WAV, sirena de ambulancia y sonidos urbanos con voces; **mezcla real**.

La selección no implica que estén descargados ni examinados, ni garantiza ausencia de sonidos imprevistos. Estas escenas podrían emplearse más adelante como demostración cualitativa y evaluación perceptiva externa; no se deben presentar como referencias puras para métricas de separación sin aislar y validar fuentes. Mantener test externo sellado y proteger independencia por uploader, origen y grabación. Las cinco fuentes necesitan comprobación de bytes, licencias por ficha y escucha antes de cualquiera de esos usos.

Metadatos de descubrimiento: `04_build/selective_audio_lab/m4_field_eval_discovery_v1.csv`. No contiene audio ni otorga admisión al corpus.
