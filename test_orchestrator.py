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
        strategist_response = """
1. The Pitch: OpsPulse for recurring back-office workflow tracking.
2. MVP: intake automation.
3. Pricing Model: $200/month for small business operations teams.
4. Acquisition Channel: outreach.
5. Budget Owner: Operations Manager.
"""
        agents = {
            "Trend Scout": StubAgent("Trend Scout", "real source data available"),
            "Pain Analyst": StubAgent("Pain Analyst", "top pains\nBoring Score: 8"),
            "SaaS Strategist": StubAgent("SaaS Strategist", strategist_response),
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

    def test_mode_classifier_routes_consumer_topics_to_b2b_adjacent(self):
        orchestrator = Orchestrator({}, max_iterations=1, interactive_pivots=False)
        plan = orchestrator._classify_topic_mode("horny men and women")
        self.assertEqual(plan["mode"], "B2B_ADJACENT")
        self.assertIn("business operations", plan["scout_topic"])

    def test_suggest_new_topic_never_repeats_original(self):
        orchestrator = Orchestrator({}, max_iterations=1, interactive_pivots=False)
        next_topic = orchestrator._suggest_new_topic("niche domain")
        self.assertNotEqual(next_topic.lower(), "niche domain")

    def test_hard_gate_blocks_low_price(self):
        orchestrator = Orchestrator({}, max_iterations=1, interactive_pivots=False)
        gates = orchestrator._evaluate_hard_gates(
            strategist_output="Pricing Model: $49/month for teams\nBudget Owner: Operations Manager",
            competitor_output=None,
            willingness_output=None,
            sales_output=None,
        )
        self.assertTrue(gates["blocked"])
        self.assertIn("Price floor gate failed", gates["issues"][0])


if __name__ == "__main__":
    unittest.main()
