import json
import tempfile
import unittest
from pathlib import Path

from src.tools.calibration_harness import aggregate_calibration, run_calibration


class CalibrationHarnessTests(unittest.TestCase):
    def test_run_calibration_writes_output_with_summary(self):
        topics = ["small business accounting", "agency operations"]
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "calibration.json"
            payload = run_calibration(
                topics=topics,
                output_path=output_path,
                use_live_agents=False,
                max_iterations=2,
            )

            self.assertTrue(output_path.exists())
            saved = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["topic_count"], 2)
            self.assertIn("summary", saved)
            self.assertIn("runs", saved)
            self.assertEqual(len(saved["runs"]), 2)
            self.assertEqual(payload["summary"]["run_count"], 2)

            first_iteration = saved["runs"][0]["iterations"][0]
            self.assertIn("scorecard", first_iteration)
            self.assertIn("hard_gates", first_iteration)

    def test_aggregate_calibration_counts_gate_issues(self):
        runs = [
            {
                "final_verdict": "NO GO",
                "iterations": [
                    {
                        "verdict": "NO GO",
                        "scorecard": {"weighted_score": 42},
                        "hard_gates": {"issues": ["Price floor gate failed"]},
                    }
                ],
            },
            {
                "final_verdict": "QUALIFIED",
                "iterations": [
                    {
                        "verdict": "QUALIFIED",
                        "scorecard": {"weighted_score": 71},
                        "hard_gates": {"issues": []},
                    }
                ],
            },
        ]
        summary = aggregate_calibration(runs)
        self.assertEqual(summary["run_count"], 2)
        self.assertEqual(summary["verdict_counts"]["NO GO"], 1)
        self.assertEqual(summary["verdict_counts"]["QUALIFIED"], 1)
        self.assertEqual(summary["hard_gate_issue_counts"]["Price floor gate failed"], 1)


if __name__ == "__main__":
    unittest.main()
