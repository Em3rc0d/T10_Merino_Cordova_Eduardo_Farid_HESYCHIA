"""Independent contract checks for the synthetic engineering design."""
import os
os.environ['KERAS_BACKEND'] = 'torch'
import sys
from pathlib import Path
import unittest
import numpy as np
sys.path.insert(0, str(Path(__file__).parent))
from m4_robustness_iteration import scene, scene_features, dataset, TRAIN_CASES, EVAL_CASES, safe_training_loss
from stress_m4_keras_torch import BINS


class SyntheticTest(unittest.TestCase):
    def test_negatives_have_zero_target_and_zero_irm(self):
        for name in [s for s in TRAIN_CASES if s.startswith('negative_')]:
            s=scene(np.random.default_rng(41),name)
            self.assertEqual(0, np.max(np.abs(s[2])))
            _, m=scene_features(s)
            self.assertEqual(0, np.max(np.abs(m)))

    def test_all_families_produce_finite_mixture(self):
        for name in sorted(set(TRAIN_CASES + EVAL_CASES)):
            s=scene(np.random.default_rng(42),name)
            self.assertEqual(4, len(s))
            self.assertTrue(all(np.isfinite(x).all() for x in s),name)
            features,mask=scene_features(s)
            self.assertEqual(features.shape,(32,BINS))
            self.assertEqual(mask.shape,(32,BINS))

    def test_ood_families_excluded_from_train(self):
        self.assertFalse({'ood_dual_target', 'ood_irregular_pulse_target',
                          'ood_confuser_cluster'} & set(TRAIN_CASES))

    def test_seeded_dataset_reproduces_and_ids_differ(self):
        a=dataset(22,142,TRAIN_CASES)
        b=dataset(22,142,TRAIN_CASES)
        c=dataset(22,143,TRAIN_CASES)
        np.testing.assert_array_equal(a[0],b[0])
        self.assertEqual(a[4],b[4])
        self.assertFalse(np.array_equal(a[0],c[0]))
        self.assertTrue(set(a[4]).isdisjoint(c[4]))

    def test_invalid_sample_count_fails(self):
        with self.assertRaises(ValueError): dataset(7,42,TRAIN_CASES)

    def test_loss_finite_with_target_absent(self):
        import keras
        from keras import ops
        y_true=ops.convert_to_tensor(np.zeros((2,32,2*BINS),dtype=np.float32))
        y_pred=ops.convert_to_tensor(np.zeros((2,32,BINS),dtype=np.float32))
        self.assertTrue(np.isfinite(ops.convert_to_numpy(safe_training_loss(y_true,y_pred))).all())

if __name__=='__main__':unittest.main()
