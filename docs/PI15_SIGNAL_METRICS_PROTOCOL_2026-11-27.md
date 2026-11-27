# HESYCHIA · protocolo de métricas de señal para cierre PI15

Fecha de preespecificación: 27/11/2026. Este documento debe quedar congelado antes
de abrir el test confirmatorio externo.

## 1. Endpoints primarios — sin cambios

La decisión de OE2 continúa exactamente con los criterios aprobados por el asesor:

- superioridad de atenuación: ΔA_target = A_target(CNN) - A_target(DSP);
- bootstrap pareado por source_group, 10 000 réplicas, unilateral α=0.05;
- no inferioridad de señal protegida: límite superior IC95% de
  ΔA_protected = A_protected(CNN) - A_protected(DSP) <= 1 dB;
- Oracle IRM es referencia privilegiada y no forma parte de la hipótesis CNN-DSP;
- both_ok 6/1 dB permanece descriptivo.

Ninguna métrica añadida en este documento puede cambiar H1/H0 ni utilizarse para
seleccionar un modelo después de abrir el test.

## 2. Métricas objetivas suplementarias

Para acompañar la demostración y la tabla solicitada para el examen final se
reportarán, por método y sobre las mismas escenas congeladas:

- SI-SDRi de la señal protegida;
- SNR protegido/target a la salida y mejora de SNR frente a la mezcla;
- STOI entre el stem de habla protegido limpio y el mismo stem tras aplicar la
  ganancia estimada por cada método;
- PESQ wideband a 16 kHz, únicamente si el wrapper reproducible está disponible.

STOI y PESQ son métricas intrusivas: utilizan el stem de habla limpio conocido en
el experimento. No se calculan sobre WAV de usuario sin referencia limpia.

## 3. Interpretación

STOI/PESQ se reportan como evidencia complementaria de inteligibilidad/calidad de
la señal protegida. No demuestran beneficio clínico, seguridad auditiva ni eficacia
en personas con TEA.

PESQ (P.862) se conserva solo como métrica suplementaria porque fue solicitada
para la sustentación. ITU-T retiró P.862 en 2024 y remite a P.863; por ello un
resultado PESQ no se presenta como estándar vigente ni como endpoint principal.

## 4. Reproducibilidad

La campaña debe registrar en cada fila: scene_id, source_group, speaker_group,
mix_sha256, method, A_target, A_protected, SI-SDRi, SNR, STOI y, cuando esté
disponible, PESQ. El freeze debe incluir el SHA-256 de este protocolo y del script
de campaña. Si PESQ no puede ejecutarse en el entorno congelado, se reportará como
no disponible; no se sustituirá silenciosamente por otra métrica después de abrir
el test.
