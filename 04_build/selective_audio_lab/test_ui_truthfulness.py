from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).parent
HTML = (ROOT / "web" / "index.html").read_text(encoding="utf-8")


class UITruthfulnessTests(unittest.TestCase):
    def test_old_mock_metrics_are_absent(self):
        for stale_value in (
            "Macro-F1<b>0.87",
            "Recall macro<b>0.89",
            "Inferencia p95<b>18.6 ms",
            "E2E p95<b>47.2 ms",
            "RAM pico<b>412 MB",
            "Atenuación<b>8.4 dB",
            "SI-SNRi<b>+3.2 dB",
        ):
            with self.subTest(stale_value=stale_value):
                self.assertNotIn(stale_value, HTML)

    def test_pending_edge_actions_are_visibly_disabled(self):
        self.assertIn("Iniciar streaming</button>", HTML)
        self.assertIn("Exportar TFLite</button>", HTML)
        self.assertIn('class="btn secondary" disabled>Iniciar streaming', HTML)
        self.assertIn('class="btn secondary" disabled>Exportar TFLite', HTML)

    def test_mobile_overflow_guards_exist(self):
        self.assertIn("overflow-x:hidden", HTML)
        self.assertIn("max-width:100%", HTML)
        self.assertIn("@media(max-width:600px)", HTML)


if __name__ == "__main__":
    unittest.main()
