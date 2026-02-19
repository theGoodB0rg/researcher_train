import unittest

from src.agents.scout import ScoutAgent


class ScoutQuerySeedTests(unittest.TestCase):
    def test_query_seed_is_compact_and_intent_focused(self):
        scout = ScoutAgent("Trend Scout", "Researcher", "test prompt")
        seed = scout._build_query_seed("portfolio website maker using resume or linkedin profile business operations")
        token_count = len(seed.split())
        self.assertLessEqual(token_count, 7)
        self.assertIn("portfolio", seed)
        self.assertIn("linkedin", seed)
        self.assertNotIn("using", seed)
        self.assertNotIn("operations", seed)

    def test_extracts_research_mode_from_prompt(self):
        scout = ScoutAgent("Trend Scout", "Researcher", "test prompt")
        mode = scout._extract_research_mode(
            "Find complaints and issues related to: portfolio tools\nResearch mode: B2C_PLG"
        )
        self.assertEqual(mode, "B2C_PLG")

    def test_b2c_strategy_contains_switching_triggers(self):
        scout = ScoutAgent("Trend Scout", "Researcher", "test prompt")
        strategies = scout._build_strategy_plan("portfolio resume builder", "B2C_PLG")
        labels = [entry["label"] for entry in strategies]
        self.assertIn("switching_triggers", labels)
        self.assertIn("source_query_overrides", strategies[0])
        self.assertIn("web", strategies[0]["source_query_overrides"])

    def test_b2b_strategy_contains_workflow_and_cost_signals(self):
        scout = ScoutAgent("Trend Scout", "Researcher", "test prompt")
        strategies = scout._build_strategy_plan("accounts payable automation", "B2B_STRICT")
        labels = [entry["label"] for entry in strategies]
        self.assertIn("ops_workarounds", labels)
        self.assertIn("cost_risk_signals", labels)

    def test_structured_buyer_first_seed_preserves_workflow_and_pain_terms(self):
        scout = ScoutAgent("Trend Scout", "Researcher", "test prompt")
        seed = scout._build_query_seed(
            "buyer: operations leads; vertical: construction subcontractors; "
            "workflow: invoice approval and reconciliation; pain: manual invoice matching and delayed approvals"
        )
        lowered = seed.lower()
        self.assertIn("construction", lowered)
        self.assertIn("invoice", lowered)
        self.assertIn("approval", lowered)
        self.assertIn("delayed", lowered)
        self.assertNotIn("buyer", lowered)
        self.assertNotIn("vertical", lowered)

    def test_query_seed_ignores_modifier_noise_and_single_char_tokens(self):
        scout = ScoutAgent("Trend Scout", "Researcher", "test prompt")
        cleaned = scout._strip_query_modifiers(
            "home appliance troubleshooting for a specific persona with explicit switching triggers user complaints feature requests alternatives"
        )
        seed = scout._build_query_seed(cleaned)
        lowered = seed.lower()
        self.assertNotIn("persona", lowered)
        self.assertNotIn("switching", lowered)
        self.assertNotIn(" a ", f" {lowered} ")

    def test_strip_query_modifiers_removes_scout_suffixes(self):
        scout = ScoutAgent("Trend Scout", "Researcher", "test prompt")
        cleaned = scout._strip_query_modifiers(
            "portfolio tooling user complaints feature requests alternatives"
        )
        lowered = cleaned.lower()
        self.assertNotIn("user complaints", lowered)
        self.assertNotIn("feature requests", lowered)


if __name__ == "__main__":
    unittest.main()
