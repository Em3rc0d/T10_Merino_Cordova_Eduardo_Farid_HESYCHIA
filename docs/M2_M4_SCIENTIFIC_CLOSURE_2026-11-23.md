# M2 + M4 scientific closure — 2026-11-23

Status: implementation candidate / no new scientific result. Existing thresholds, title and historical evidence unchanged.

## M2

The historical 0.7257 is SVM, not CNN. Add a small PyTorch CNN with 64-band log-Mel, train-only spectral masking, square-root inverse-frequency weights, fixed seeds 42/43/44, AdamW, 50 epochs maximum and patience 8. Select on fold 9 Macro-F1, then Macro-Recall, then lowest seed. All 10 labels are scored. Keep folds 1–8 / 9 / 10 and existing occurrence-level guards. Exact audio hashes are an additional check, not proof against perceptual duplication. Existing full dataset metadata hash is required.

From 04_build/selective_audio_lab, use an environment with requirements-scientific.txt plus requirements.txt dependencies (resolve in an isolated environment; record installed versions):

```bash
python src/m2_cnn_candidate.py develop --dataset-root /path/UrbanSound8K --out outputs/m2_cnn_dev_001
```

Archive freeze.json, all referenced artifacts, environment and its SHA-256 before any new fold-10 evaluation. Inspect only validation confusion matrix. Do not invoke test repeatedly after failure. The test subcommand requires explicit acknowledgement and a matching freeze hash, creates an exclusive attempt receipt before reading audio and labels the result as a historical holdout evaluation, NOT a new blind test. The CLI does not prove external publication of the freeze; that is an operator responsibility.

A separate independent confirmation requires a new source-disjoint cohort and prospective protocol, not retroactive tuning. No claim of meeting 0.85 is made here.

## M4

Keep PI15 external campaign and frozen seed61 unchanged; complete the human audit with 93 paired reviews, pre-adjudication kappa >=0.60 and final contamination report. Candidate reserve pool is metadata only: 28 source groups (14 chainsaw and 14 vacuum cleaner). Audit eligibility before any model inference; retain at least 20 independent target groups across both classes and >=4 independent speakers. Use the existing freeze and confirmatory scripts. The legacy test is exposed; never use external outcomes to choose a model and rerun on the same cohort. If selectivity fails, use a distinct development corpus for constrained-mask Pareto analysis (target >=6 dB; protected <=1 dB); compare unchanged CNN, DSP, privileged Oracle and counterfactual conditioning. A new candidate must be evaluated on a new untouched cohort.

Do not treat presence of files or a synthetic unit test as scientific validation. No new run, human reviews, or device benchmark claimed.
