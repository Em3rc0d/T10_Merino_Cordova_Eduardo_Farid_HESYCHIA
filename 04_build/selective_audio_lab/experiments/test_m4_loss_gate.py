"""Numerical audit of previously proposed L0 stability variant with absent target."""
from pathlib import Path
import sys
import unittest
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
# Read from the existing HESYCHIA module when run in the repo checkout.
from m4_causal_bridge import loss_components
import torch

class L0StabilityChecks(unittest.TestCase):
    def test_absent_target_finite_gradients(self):
        raw=torch.zeros((2,20,257),requires_grad=True)
        mask=torch.sigmoid(raw)
        zero=torch.zeros_like(mask)
        mix=torch.rand_like(mask)+.01
        loss,components=loss_components(mask,zero,mix,zero,mix,speech_weight=0.0)
        loss.backward()
        self.assertTrue(bool(torch.isfinite(loss)))
        self.assertTrue(bool(torch.isfinite(raw.grad).all()))
        self.assertLess(float(raw.grad.abs().max()),1.0)
    def test_nearly_silent_mixture_no_divergence(self):
        raw=torch.zeros((1,5,257),requires_grad=True)
        mask=torch.sigmoid(raw)
        zero=torch.zeros_like(mask)
        low=torch.full_like(mask,1e-9)
        loss,_=loss_components(mask,zero,low,zero,low,speech_weight=0)
        loss.backward()
        self.assertTrue(bool(torch.isfinite(loss)))
        self.assertTrue(bool(torch.isfinite(raw.grad).all()))
    def test_regularizer_disabled_by_default(self):
        raw=torch.zeros((1,5,257),requires_grad=True)
        mask=torch.sigmoid(raw)
        mix=torch.full_like(mask,.2)
        label=torch.full_like(mask,.3)
        a,_=loss_components(mask,label,mix,label,mix,speech_weight=0)
        b,_=loss_components(mask,label,mix,label,mix,speech_weight=.1)
        self.assertGreater(float(b.detach()),float(a.detach()))
if __name__=='__main__':unittest.main()
