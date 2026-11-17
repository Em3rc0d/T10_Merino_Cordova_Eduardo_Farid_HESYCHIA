# HESYCHIA — DSP baseline contract v2

Date: 2026-11-17  
Status: **definition frozen before confirmatory test; no final templates generated yet.**

## 1. Fair comparison

The confirmatory contrast is CNN vs DSP on the same mixture bytes. Both inference arms receive exactly:

1. mono mixture waveform;
2. requested `target_id`.

Neither arm receives clean test stems. Oracle IRM is a third, explicitly privileged reference and is not the DSP baseline.

## 2. Exact frontend parity

DSP v2 uses the **same scientific spectral grid as M4 CNN**, imported from `m4_scientific.model`:

- sample rate: 16 kHz;
- `n_fft=512`;
- `hop=160`;
- periodic Hann square-root analysis window;
- left padding: `512-160 = 352` samples;
- declared tail: 3 hops;
- 257 one-sided bins;
- normalized WOLA scientific synthesis for evaluation.

The earlier generic SciPy/Hann frontend is not used by the confirmatory DSP baseline.

## 3. Training-only target templates

For every admissible **training** source after OE1 exclusions:

1. compute the exact M4 scientific STFT;
2. mean power over frames;
3. L1-normalize over frequency.

For target class `c`:

- `T_c(f)`: median normalized spectrum among training sources of class `c`;
- `R_c(f)`: median normalized spectrum among the other target class;
- `M_DSP,c(f)=T_c(f)/(T_c(f)+R_c(f)+eps)`.

The resulting 257-bin mask is clipped to [0,1] and broadcast over the same frames produced by the scientific frontend.

## 4. Shared attenuation policy

For both learned and deterministic masks:

`g(t,f)=max(1-M(t,f),10^(-12/20))`.

M3b is evaluated before the method. `BLOCK` remains exact bypass and must not call CNN or DSP processing.

## 5. Leakage controls

- DSP templates are generated only after OE1 exclusions.
- Confirmatory target/speech sources never enter DSP template estimation.
- CNN and DSP use identical mixture SHA-256 values for CP10.
- Test clean stems are available only to the evaluation/Oracle layer, never to either inference arm.

## 6. Freeze evidence

Before first confirmatory inference record SHA-256 for:

- DSP v2 source;
- DSP v2 config;
- generated template NPZ;
- admissible training manifest;
- CNN checkpoint;
- M4 frontend/evaluation code;
- external target + speech manifests;
- scene manifest and metric protocol.

Any post-freeze change invalidates the run and requires a new test version.

## 7. Interpretation

DSP v2 is intentionally non-learned but target-conditioned. The hypothesis therefore asks whether learned class-conditioned masking adds value over a deterministic target-aware spectral prior **without confounding the comparison through a different STFT frontend**.
