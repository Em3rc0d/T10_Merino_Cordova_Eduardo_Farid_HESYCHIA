import csv
import json
import tempfile
import shutil
from pathlib import Path
import unittest
from audit_m4_robustness import audit

RESULTS = Path(__file__).resolve().parents[1] / 'results'

class PairedAuditTest(unittest.TestCase):
    @unittest.skipUnless((RESULTS / 'paired.csv').exists(),'Local evidence fixture unavailable')
    def test_actual_evidence(self):
        self.assertEqual('PASS', audit(RESULTS)['status'])

    @unittest.skipUnless((RESULTS / 'paired.csv').exists(),'Local evidence fixture unavailable')
    def test_tampered_joint_flag_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            for name in ['paired.csv','results.json','m4_hard_negative.weights.h5']:
                shutil.copy2(RESULTS/name,folder/name)
            p=folder/'paired.csv'
            with p.open(newline='') as f:
                rows=list(csv.DictReader(f))
            target=next(r for r in rows if r['target_present']=='True' and r['joint_ok']=='True')
            target['joint_ok']='False'
            with p.open('w',newline='') as f:
                writer=csv.DictWriter(f,fieldnames=list(rows[0]))
                writer.writeheader();writer.writerows(rows)
            with self.assertRaises(ValueError):audit(folder)

if __name__=='__main__':unittest.main()
