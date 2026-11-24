import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from m2_cnn_candidate import AcousticCNN, augment, build_data, metrics, write_json


def test_shape_and_backward():
    model = AcousticCNN()
    x = torch.rand(2, 1, 64, 401)
    out = model(x)
    assert out.shape == (2, 10)
    out.sum().backward()
    assert all(p.grad is not None for p in model.parameters())


def test_augment_does_not_mutate():
    x = torch.ones(2, 1, 64, 401)
    y = augment(x)
    assert torch.equal(x, torch.ones_like(x))
    assert y.shape == x.shape


def test_fold_guard_before_audio_access(tmp_path):
    frame = pd.DataFrame({"fold": [10]})
    with pytest.raises(ValueError, match="forbidden fold"):
        build_data(tmp_path, frame, set(range(1, 9)))


def test_macro_f1_fixed_label_space():
    assert np.isclose(metrics([0, 0], [0, 0])["macro_f1"], 0.1)


def test_attempt_receipt_exclusive(tmp_path):
    target = tmp_path / "receipt.json"
    write_json(target, {"status": "started"})
    with pytest.raises(FileExistsError):
        write_json(target, {"status": "repeat"})
