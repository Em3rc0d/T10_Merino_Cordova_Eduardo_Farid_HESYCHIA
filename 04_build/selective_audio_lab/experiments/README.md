# M4 experimental synthetic robustness iteration

**Not a thesis scope change, trained real M4 or final validation.** This
is an engineering study with fake generated sounds (0.31 s), not clinical or
field audio. The HESYCHIA causal mask CNN architecture is unchanged.

Code in this directory is HESYCHIA-owned. It uses QA practices that can be
applied to many acoustic-ML projects, not a third-party event classifier.
No unlicensed foreign-model source code is copied.

Dependencies required only for this optional experiment: Keras 3.13.2 with
KERAS_BACKEND=torch, PyTorch 2.10.0+cpu, SciPy 1.17.0, NumPy 2.3.5,
SoundFile 0.13.1 and h5py 3.15.1 (versions actually observed in sandbox).

To reproduce, obtain `m4_augmented.weights.h5` from the previous thesis
experimental ZIP and place it in a separate local `previous` directory. Run
from this experiments folder:

    python m4_robustness_iteration.py --previous-weights /path/to/m4_augmented.weights.h5 \
      --out /path/to/outputs --train 1650 --val 330 --epochs 12 \
      --test-per-family 25 --seed 42 --threads 2

    python audit_m4_robustness.py --folder /path/to/outputs
    python -m unittest discover -p 'test_m4_robustness*.py'

No weights/audio and no ML packages have been added to the existing PI8 CI
workflow, preserving the existing lightweight reproducibility checks. The
complete executed weights and per-row CSV were supplied as ZIP in the chat.

Validation/test use distinct generated scenes and seeds, but the same
synthetic generator family; this is **not independent real-world evaluation**.
Source isolation, consent/licensing, causal STFT runtime, fixed loss L0, TFLite,
and field holdout remain explicit blockers before real M4 claims.
