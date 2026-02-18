import unittest

from src.core.orchestrator import Orchestrator


class StubAgent:
    def __init__(self, name, response):
        self.name = name
        self.response = response

    def process(self, input_data, context=None):
        return self.response


class OrchestratorHardeningTests(unittest.TestCase):
    def test_parse_verdict_prioritizes_no_go(self):
        orchestrator = Orchestrator({}, max_iterations=1, interactive_pivots=False)
        self.assertEqual(orchestrator._parse_verdict("Final Verdict: NO GO"), "NO GO")
        self.assertEqual(orchestrator._parse_verdict("Final Verdict: QUALIFIED"), "QUALIFIED")
        self.assertEqual(orchestrator._parse_verdict("Final Verdict: GO"), "GO")

    def test_run_state_resets_between_calls(self):
        agents = {
            "Trend Scout": StubAgent("Trend Scout", "real source data available"),
            "Pain Analyst": StubAgent("Pain Analyst", "top pains"),
            "SaaS Strategist": StubAgent("SaaS Strategist", "Idea A"),
            "The Skeptic": StubAgent("The Skeptic", "Final Verdict: GO"),
        }
        orchestrator = Orchestrator(agents, max_iterations=2, interactive_pivots=False)

        first = orchestrator.run_round_table("topic one")
        second = orchestrator.run_round_table("topic two")

        self.assertEqual(first["topic"], "topic one")
        self.assertEqual(second["topic"], "topic two")
        self.assertEqual(first["iteration_count"], 1)
        self.assertEqual(second["iteration_count"], 1)
        self.assertEqual(len(first["iterations"]), 1)
        self.assertEqual(len(second["iterations"]), 1)


if __name__ == "__main__":
    unittest.main()
