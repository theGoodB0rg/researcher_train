import unittest

from src.core.orchestrator import Orchestrator


class StubAgent:
    def __init__(self, name, response):
        self.name = name
        self.response = response

    def process(self, input_data, context=None):
        return self.response


class FailOnCallAgent:
    def __init__(self, name):
        self.name = name

    def process(self, input_data, context=None):
        raise AssertionError(f"{self.name} should not be called")


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

    def test_mode_classifier_routes_consumer_topics_to_b2c_plg(self):
        orchestrator = Orchestrator({}, max_iterations=1, interactive_pivots=False)
        plan = orchestrator._classify_topic_mode("horny men and women")
        self.assertEqual(plan["mode"], "B2C_PLG")
        self.assertIn("feature requests", plan["scout_topic"])

    def test_buyer_first_brief_parsing(self):
        orchestrator = Orchestrator({}, max_iterations=1, interactive_pivots=False)
        brief = orchestrator._parse_buyer_first_brief(
            "buyer: staffing agencies; workflow: candidate intake; pain: manual profile updates"
        )
        self.assertIsNotNone(brief)
        self.assertEqual(brief["buyer"], "staffing agencies")
        self.assertEqual(brief["workflow"], "candidate intake")
        self.assertEqual(brief["pain"], "manual profile updates")

    def test_suggest_new_topic_never_repeats_original(self):
        orchestrator = Orchestrator({}, max_iterations=1, interactive_pivots=False)
        next_topic = orchestrator._suggest_new_topic("niche domain")
        self.assertNotEqual(next_topic.lower(), "niche domain")

    def test_hard_gate_blocks_low_price(self):
        orchestrator = Orchestrator({}, max_iterations=1, interactive_pivots=False)
        gates = orchestrator._evaluate_hard_gates(
            topic="staff scheduling",
            scout_topic="staff scheduling operations",
            scout_output="https://example.com/source-a",
            analyst_output="Boring Score: 7\nhttps://example.com/source-a",
            strategist_output="Pricing Model: $49/month for teams\nBudget Owner: Operations Manager",
            competitor_output=None,
            willingness_output=None,
            sales_output=None,
            domain_shift_authorized=False,
        )
        self.assertTrue(gates["blocked"])
        self.assertIn("Price floor gate failed", gates["issues"][0])

    def test_next_topic_price_pivot_for_b2c_stays_plg(self):
        orchestrator = Orchestrator({}, max_iterations=1, interactive_pivots=False)
        next_topic = orchestrator._next_topic(
            current_topic="portfolio website maker using resume or linkedin profile",
            pivot_instruction="Low willingness to pay - raise price point for high-value customers",
            topic_mode="B2C_PLG",
        )
        self.assertNotIn("compliance", next_topic.lower())
        self.assertIn("narrower user segment", next_topic.lower())

    def test_next_topic_price_pivot_for_b2b_keeps_budget_owner_direction(self):
        orchestrator = Orchestrator({}, max_iterations=1, interactive_pivots=False)
        next_topic = orchestrator._next_topic(
            current_topic="staff scheduling",
            pivot_instruction="Low willingness to pay - raise price point for high-value customers",
            topic_mode="B2B_STRICT",
        )
        self.assertIn("budget ownership", next_topic.lower())

    def test_b2c_hard_gates_allow_realistic_plg_plan(self):
        orchestrator = Orchestrator({}, max_iterations=1, interactive_pivots=False)
        gates = orchestrator._evaluate_hard_gates(
            topic="portfolio website maker",
            scout_topic="portfolio website maker user complaints",
            scout_output="URL: https://example.com/source-a",
            analyst_output="Boring Score: 6\nhttps://example.com/source-a",
            strategist_output=(
                "The Pitch: Portfolio website builder for designers.\n"
                "Pricing Model: $19/month.\n"
                "Acquisition Channel: SEO content and Product Hunt launch.\n"
                "Target users: designers."
            ),
            competitor_output="Market Saturation Assessment: YELLOW",
            willingness_output="Price Willingness Score: 48%",
            sales_output=None,
            domain_shift_authorized=False,
            topic_mode="B2C_PLG",
        )
        self.assertFalse(gates["blocked"])

    def test_b2c_hard_gates_block_missing_plg_channel(self):
        orchestrator = Orchestrator({}, max_iterations=1, interactive_pivots=False)
        gates = orchestrator._evaluate_hard_gates(
            topic="portfolio website maker",
            scout_topic="portfolio website maker user complaints",
            scout_output="URL: https://example.com/source-a",
            analyst_output="Boring Score: 6\nhttps://example.com/source-a",
            strategist_output="Pricing Model: $29/month for users.",
            competitor_output=None,
            willingness_output="Price Willingness Score: 52%",
            sales_output=None,
            domain_shift_authorized=False,
            topic_mode="B2C_PLG",
        )
        self.assertTrue(gates["blocked"])
        self.assertTrue(any("Acquisition gate failed" in issue for issue in gates["issues"]))

    def test_no_data_recovery_changes_topic_after_failure(self):
        agents = {
            "Trend Scout": StubAgent(
                "Trend Scout",
                "[DATA COLLECTION FAILED] Insufficient high-confidence primary-source coverage",
            ),
        }
        orchestrator = Orchestrator(agents, max_iterations=2, interactive_pivots=False)
        results = orchestrator.run_round_table("portfolio website maker using resume or linkedin profile")

        self.assertEqual(len(results["iterations"]), 2)
        self.assertEqual(results["iterations"][0]["verdict"], "NO DATA")
        self.assertEqual(results["iterations"][1]["verdict"], "NO DATA")
        self.assertNotEqual(results["iterations"][0]["topic"], results["iterations"][1]["topic"])
        self.assertEqual(results["final_verdict"], "NO_DATA_PIVOT_REQUIRED")

    def test_no_evidence_gate_skips_downstream_agents(self):
        agents = {
            "Trend Scout": StubAgent(
                "Trend Scout",
                (
                    "1. Lack of Pain Signals: no pain signals were found.\n"
                    "2. Absence of specific complaints in source data."
                ),
            ),
            "Pain Analyst": FailOnCallAgent("Pain Analyst"),
            "SaaS Strategist": FailOnCallAgent("SaaS Strategist"),
            "The Skeptic": FailOnCallAgent("The Skeptic"),
        }
        orchestrator = Orchestrator(agents, max_iterations=1, interactive_pivots=False)
        results = orchestrator.run_round_table("portfolio tooling")

        self.assertEqual(results["iterations"][0]["verdict"], "NO GO")
        self.assertTrue(results["iterations"][0]["hard_gates"]["blocked"])
        self.assertIn("No evidence gate failed", results["iterations"][0]["hard_gates"]["issues"][0])

    def test_evidence_grounding_gate_blocks_non_scout_urls(self):
        orchestrator = Orchestrator({}, max_iterations=1, interactive_pivots=False)
        gates = orchestrator._evaluate_hard_gates(
            topic="recruitment operations",
            scout_topic="recruitment and candidate profile management operations",
            scout_output="1. URL: https://source-one.com/post\n2. URL: https://source-two.com/post",
            analyst_output=(
                "Problem A\nBoring Score: 8\nhttps://source-one.com/post\n"
                "Problem B\nBoring Score: 7\nhttps://not-in-scout.com/post"
            ),
            strategist_output="Pricing Model: $250/month\nBudget Owner: Operations Manager",
            competitor_output=None,
            willingness_output="Price Willingness Score: 70%",
            sales_output="1-Month Feasibility: CHALLENGING",
            domain_shift_authorized=False,
        )
        self.assertTrue(gates["blocked"])
        self.assertTrue(any("Evidence grounding gate failed" in issue for issue in gates["issues"]))

    def test_domain_lock_blocks_unrelated_vertical_without_authorization(self):
        orchestrator = Orchestrator({}, max_iterations=1, interactive_pivots=False)
        gates = orchestrator._evaluate_hard_gates(
            topic="portfolio website maker using resume or linkedin profile",
            scout_topic="recruitment and candidate profile management operations",
            scout_output="URL: https://recruitment-source.com/post",
            analyst_output="Boring Score: 7\nhttps://recruitment-source.com/post",
            strategist_output="The Pitch: GDPR compliance tool for hospitals.\nPricing Model: $500/month\nBudget Owner: CIO",
            competitor_output=None,
            willingness_output="Price Willingness Score: 70%",
            sales_output="1-Month Feasibility: CHALLENGING",
            domain_shift_authorized=False,
        )
        self.assertTrue(gates["blocked"])
        self.assertTrue(any("Domain lock gate failed" in issue for issue in gates["issues"]))

    def test_pricing_sanity_gate_blocks_outlier_price_without_wedge(self):
        orchestrator = Orchestrator({}, max_iterations=1, interactive_pivots=False)
        gates = orchestrator._evaluate_hard_gates(
            topic="candidate profile management",
            scout_topic="candidate profile management operations",
            scout_output="URL: https://source-one.com/post",
            analyst_output="Boring Score: 8\nhttps://source-one.com/post",
            strategist_output="Pricing Model: $1500/month\nBudget Owner: Operations Manager",
            competitor_output="Competitor A: $90/month. Competitor B: $120/month.",
            willingness_output="Price Willingness Score: 80%",
            sales_output="1-Month Feasibility: CHALLENGING",
            domain_shift_authorized=False,
        )
        self.assertTrue(gates["blocked"])
        self.assertTrue(any("Pricing sanity gate failed" in issue for issue in gates["issues"]))

    def test_buyer_first_mode_routes_scout_topic(self):
        strategist_response = """
1. The Pitch: IntakeOps for staffing agencies.
2. Pricing Model: $250/month for staffing agencies.
5. Budget Owner: Operations Manager.
"""
        agents = {
            "Trend Scout": StubAgent("Trend Scout", "1. complaint from real source https://example.com/a"),
            "Pain Analyst": StubAgent("Pain Analyst", "Boring Score: 8\nhttps://example.com/a"),
            "SaaS Strategist": StubAgent("SaaS Strategist", strategist_response),
            "The Skeptic": StubAgent("The Skeptic", "Final Verdict: GO"),
        }
        orchestrator = Orchestrator(agents, max_iterations=1, interactive_pivots=False)
        results = orchestrator.run_round_table(
            "buyer: staffing agencies; workflow: candidate intake; pain: manual profile updates"
        )
        self.assertEqual(results["mode"], "B2B_BUYER_FIRST")
        self.assertIsNotNone(results["buyer_brief"])
        first_iteration = results["iterations"][0]
        self.assertIn("staffing agencies", first_iteration["scout_topic"].lower())
        self.assertIn("candidate intake", first_iteration["scout_topic"].lower())


if __name__ == "__main__":
    unittest.main()
