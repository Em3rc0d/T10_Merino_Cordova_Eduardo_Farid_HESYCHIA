# HESYCHIA — DSP baseline contract v1

Date: 2026-11-17
Status: **frozen definition before confirmatory test**. This document defines the non-learned reference arm for OE2; it does not report experimental performance.

## 1. Purpose and fairness
The confirmatory comparison is CNN vs DSP on the **same mixtures**. The DSP arm receives the same semantic clue available to the learned arm at inference: `target_id`. Neither arm may receive clean test stems. Oracle IRM remains a separate privileged reference and is not the DSP baseline.

## 2. Inputs and frontend
- Input waveform: mono mixture, 16 kHz.
- Semantic clue: integer `target_id`.
- STFT: Hann window, `n_fft=512`, `hop=160` samples.
- M3b policy is evaluated before either CNN or DSP. `BLOCK` is bit-exact bypass; `ALLOW` invokes the selected method.

## 3. Training-only class templates
For each admissible training clip, compute the mean power spectrum and L1-normalize it across frequency. For target class c:
- `T_c(f)`: median normalized spectrum of training clips from class c.
- `R_c(f)`: median normalized spectrum of all admissible non-c training clips.
- `M_DSP,c(f) = T_c(f) / (T_c(f) + R_c(f) + eps)`.

The mask is clipped to [0,1] and broadcast over time. It is deterministic, class-conditioned and test-stem-free.

## 4. Shared attenuation policy
Both CNN and DSP masks use:
`g(t,f) = max(1 - alpha * M(t,f), 10^(-cap_db/20))`
with `alpha=1.0` and `cap_db=12.0 dB`. Any post-unsealing change invalidates the freeze.

## 5. Leakage controls
- Templates use only the admissible training pool after corpus exclusions.
- No confirmatory-test stems or Oracle masks enter CNN or DSP inference.
- The same source/speaker leakage exclusions apply to the new test.

## 6. Evidence to freeze
Record SHA-256 for DSP code, DSP config, generated template artifact, training manifest, CNN checkpoint/frontend, evaluation code/metric protocol and confirmatory test manifest before first confirmatory inference.

## 7. Interpretation
This is a deliberately simple non-learned baseline. It tests whether the learned class-conditioned CNN adds value over a target-aware deterministic spectral prior under matched information and matched attenuation policy.

## 8. Source hashes at definition time
- `dsp_class_template.py`: `cc73a934a09dc6305200dbd20daac44330edff5f92b4e7afac412f9adff7d38d`
- `dsp_class_template_v1.json`: `21152fac74d5d16a71db5ca37217bfe654a427fca6bd9394c16812243467e835`

The template-artifact hash is produced only after the final admissible training pool has been established.
