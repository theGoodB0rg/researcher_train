import json
import unittest

from src.core.orchestrator import Orchestrator


class StubAgent:
    def __init__(self, name, response):
        self.name = name
        self.response = response

    def process(self, input_data, context=None):
        return self.response


class CaptureContextAgent:
    def __init__(self, name, response):
        self.name = name
        self.response = response
        self.last_context = None

    def process(self, input_data, context=None):
        self.last_context = context or []
        return self.response


class FailOnCallAgent:
    def __init__(self, name):
        self.name = name

    def process(self, input_data, context=None):
        raise AssertionError(f"{self.name} should not be called")


class StubInputOrchestrator(Orchestrator):
    def __init__(self, *args, stub_input_value="", **kwargs):
        super().__init__(*args, **kwargs)
        self._stub_input_value = stub_input_value

    def _prompt_user(self, prompt_text: str, color: str = "yellow") -> str:
        return self._stub_input_value


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

    def test_mode_classifier_routes_home_appliance_homeowners_to_b2c_plg(self):
        orchestrator = Orchestrator({}, max_iterations=1, interactive_pivots=False)
        plan = orchestrator._classify_topic_mode("home appliance inventory and troubleshooting assistant for homeowners")
        self.assertEqual(plan["mode"], "B2C_PLG")

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

    def test_next_topic_price_pivot_for_b2c_pivots_business_model(self):
        orchestrator = Orchestrator({}, max_iterations=1, interactive_pivots=False)
        next_topic = orchestrator._next_topic(
            current_topic="home appliance inventory and troubleshooting assistant for homeowners",
            pivot_instruction="Low willingness to pay - raise price point for high-value customers",
            topic_mode="B2C_PLG",
        )
        lowered = next_topic.lower()
        self.assertIn("buyer:", lowered)
        self.assertIn("property managers", lowered)
        self.assertIn("workflow:", lowered)

    def test_next_topic_price_pivot_for_b2b_keeps_budget_owner_direction(self):
        orchestrator = Orchestrator({}, max_iterations=1, interactive_pivots=False)
        next_topic = orchestrator._next_topic(
            current_topic="staff scheduling",
            pivot_instruction="Low willingness to pay - raise price point for high-value customers",
            topic_mode="B2B_STRICT",
        )
        self.assertIn("budget owning", next_topic.lower())

    def test_next_topic_uses_root_topic_to_prevent_recursive_suffixes(self):
        orchestrator = Orchestrator({}, max_iterations=1, interactive_pivots=False)
        next_topic = orchestrator._next_topic(
            current_topic="invoice processing internal operations workflow internal operations workflow",
            pivot_instruction="Low willingness to pay - raise price point for high-value customers",
            topic_mode="B2B_STRICT",
            root_topic="invoice processing",
        )
        self.assertNotIn("internal operations workflow internal operations workflow", next_topic.lower())
        self.assertIn("invoice", next_topic.lower())
        self.assertIn("budget owning", next_topic.lower())

    def test_saturated_market_forces_vertical_pivot_format(self):
        orchestrator = Orchestrator({}, max_iterations=1, interactive_pivots=False)
        next_topic = orchestrator._next_topic(
            current_topic="accounts payable automation",
            pivot_instruction="Market is saturated - need different pain point",
            topic_mode="B2B_STRICT",
            root_topic="accounts payable automation",
        )
        lowered = next_topic.lower()
        self.assertIn("buyer:", lowered)
        self.assertIn("vertical:", lowered)
        self.assertIn("workflow:", lowered)
        self.assertIn("pain:", lowered)

    def test_generic_internal_workflow_pivot_is_rejected(self):
        orchestrator = Orchestrator({}, max_iterations=1, interactive_pivots=False)
        pivot = orchestrator._suggest_new_topic(
            current_topic="invoice processing internal operations workflow",
            root_topic="invoice processing",
            topic_mode="B2B_STRICT",
            reason="SATURATED_MARKET",
        )
        self.assertNotIn("internal operations workflow", pivot.lower())
        self.assertIn("vertical:", pivot.lower())

    def test_vertical_pivot_does_not_confuse_appliance_with_ap(self):
        orchestrator = Orchestrator({}, max_iterations=1, interactive_pivots=False)
        pivot = orchestrator._suggest_vertical_pivot(
            root_topic="home appliance troubleshooting",
            topic_mode="B2B_STRICT",
        )
        self.assertIn("appliance", pivot.lower())
        self.assertNotIn("invoice approval", pivot.lower())

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

    def test_low_confidence_mid_willingness_does_not_auto_block_b2b(self):
        orchestrator = Orchestrator({}, max_iterations=1, interactive_pivots=False)
        gates = orchestrator._evaluate_hard_gates(
            topic="construction invoicing",
            scout_topic="construction invoicing operations",
            scout_output="URL: https://example.com/source",
            analyst_output="Boring Score: 8\nhttps://example.com/source",
            strategist_output="Pricing Model: $300/month\nBudget Owner: Operations Manager",
            competitor_output=None,
            willingness_output="Price Willingness Score: 52%\nComposite confidence: 55%",
            sales_output="1-Month Feasibility: CHALLENGING",
            domain_shift_authorized=False,
        )
        self.assertFalse(any("Payment intent gate failed" in issue for issue in gates["issues"]))

    def test_high_confidence_mid_willingness_blocks_b2b(self):
        orchestrator = Orchestrator({}, max_iterations=1, interactive_pivots=False)
        gates = orchestrator._evaluate_hard_gates(
            topic="construction invoicing",
            scout_topic="construction invoicing operations",
            scout_output="URL: https://example.com/source",
            analyst_output="Boring Score: 8\nhttps://example.com/source",
            strategist_output="Pricing Model: $300/month\nBudget Owner: Operations Manager",
            competitor_output=None,
            willingness_output="Price Willingness Score: 52%\nComposite confidence: 80%",
            sales_output="1-Month Feasibility: CHALLENGING",
            domain_shift_authorized=False,
        )
        self.assertTrue(any("Payment intent gate failed" in issue for issue in gates["issues"]))

    def test_extract_monthly_price_parses_comma_formatted_currency(self):
        orchestrator = Orchestrator({}, max_iterations=1, interactive_pivots=False)
        price = orchestrator._extract_monthly_price("Pricing Model: $1,200/month for claims teams.")
        self.assertEqual(price, 1200)

    def test_soft_override_downgrades_saturation_only_no_go(self):
        orchestrator = Orchestrator({}, max_iterations=1, interactive_pivots=False)
        verdict = orchestrator._apply_soft_verdict_override(
            verdict="NO GO",
            hard_gates={"blocked": False, "issues": [], "advisories": []},
            scorecard={"weighted_score": 61},
            skeptic_output="Final Verdict: NO GO due to saturated market",
        )
        self.assertEqual(verdict, "QUALIFIED")

    def test_soft_override_does_not_change_low_score_no_go(self):
        orchestrator = Orchestrator({}, max_iterations=1, interactive_pivots=False)
        verdict = orchestrator._apply_soft_verdict_override(
            verdict="NO GO",
            hard_gates={"blocked": False, "issues": [], "advisories": []},
            scorecard={"weighted_score": 44},
            skeptic_output="Final Verdict: NO GO due to saturated market",
        )
        self.assertEqual(verdict, "NO GO")

    def test_red_competition_alone_does_not_auto_block_b2b(self):
        orchestrator = Orchestrator({}, max_iterations=1, interactive_pivots=False)
        gates = orchestrator._evaluate_hard_gates(
            topic="home warranty claims coordination",
            scout_topic="home warranty claims coordination workflow",
            scout_output="URL: https://example.com/source",
            analyst_output="Boring Score: 8\nhttps://example.com/source",
            strategist_output=(
                "The Pitch: claims coordination tool for home warranty companies.\n"
                "Pricing Model: $300/month.\n"
                "Budget Owner: Operations Manager.\n"
                "Differentiation: niche workflow-specific automation."
            ),
            competitor_output=(
                "Competitors Found: direct competitor - home warranty claims workflow tool.\n"
                "Market Saturation Assessment: RED."
            ),
            willingness_output="Price Willingness Score: 70%\nComposite confidence: 65%",
            sales_output="1-Month Feasibility: CHALLENGING",
            domain_shift_authorized=False,
        )
        self.assertFalse(gates["blocked"])
        self.assertTrue(any("Competition warning" in advisory for advisory in gates.get("advisories", [])))

    def test_red_direct_competition_plus_weak_willingness_blocks_b2b(self):
        orchestrator = Orchestrator({}, max_iterations=1, interactive_pivots=False)
        gates = orchestrator._evaluate_hard_gates(
            topic="home warranty claims coordination",
            scout_topic="home warranty claims coordination workflow",
            scout_output="URL: https://example.com/source",
            analyst_output="Boring Score: 8\nhttps://example.com/source",
            strategist_output=(
                "The Pitch: claims coordination tool for home warranty companies.\n"
                "Pricing Model: $300/month.\n"
                "Budget Owner: Operations Manager."
            ),
            competitor_output=(
                "Competitors Found: direct competitor - home warranty claims workflow tool.\n"
                "Market Saturation Assessment: RED."
            ),
            willingness_output="Price Willingness Score: 42%\nComposite confidence: 82%",
            sales_output="1-Month Feasibility: CHALLENGING",
            domain_shift_authorized=False,
        )
        self.assertTrue(gates["blocked"])
        self.assertTrue(any("Competition gate failed" in issue for issue in gates["issues"]))

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

    def test_intake_router_mode_hint_applies_on_first_iteration(self):
        strategist_response = """
1. The Pitch: CreatorHub for portfolio creators.
2. Pricing Model: $19/month for creators.
4. Acquisition Channel: Product Hunt and SEO.
"""
        intake_plan = json.dumps(
            {
                "research_mode": "B2C_PLG",
                "normalized_topic": "portfolio website helper for creators",
                "buyer": "",
                "workflow": "",
                "pain": "",
                "vertical": "",
                "query_seed": "portfolio creator onboarding churn complaints",
                "must_include_terms": ["portfolio", "creator", "onboarding"],
                "must_exclude_terms": [],
                "source_priority": ["reddit", "forums", "reviews"],
                "clarification_needed": False,
                "clarification_question": "",
                "confidence": 0.82,
            }
        )
        agents = {
            "Intake Router": StubAgent("Intake Router", intake_plan),
            "Trend Scout": StubAgent("Trend Scout", "1. complaint from real source https://example.com/a"),
            "Pain Analyst": StubAgent("Pain Analyst", "Boring Score: 6\nhttps://example.com/a"),
            "SaaS Strategist": StubAgent("SaaS Strategist", strategist_response),
            "The Skeptic": StubAgent("The Skeptic", "Final Verdict: GO"),
        }
        orchestrator = Orchestrator(agents, max_iterations=1, interactive_pivots=False)
        results = orchestrator.run_round_table("an ambiguous idea request with mixed wording")

        self.assertEqual(results["mode"], "B2C_PLG")
        self.assertIsNotNone(results["intake_plan"])
        self.assertIn("feature requests", results["iterations"][0]["scout_topic"].lower())

    def test_intake_clarification_skip_continues_with_low_confidence_plan(self):
        intake_plan = json.dumps(
            {
                "research_mode": "B2B_DISCOVERY",
                "normalized_topic": "ambiguous long brief text",
                "buyer": "",
                "workflow": "",
                "pain": "",
                "vertical": "",
                "query_seed": "ambiguous long brief",
                "must_include_terms": [],
                "must_exclude_terms": [],
                "source_priority": ["reddit", "forums", "reviews"],
                "clarification_needed": True,
                "clarification_question": "Who is the primary buyer?",
                "confidence": 0.4,
            }
        )
        agents = {
            "Intake Router": StubAgent("Intake Router", intake_plan),
            "Trend Scout": StubAgent("Trend Scout", "1. complaint from source https://example.com/a"),
            "Pain Analyst": StubAgent("Pain Analyst", "Boring Score: 7\nhttps://example.com/a"),
            "SaaS Strategist": StubAgent(
                "SaaS Strategist",
                "Pricing Model: $250/month\nBudget Owner: Operations Manager",
            ),
            "The Skeptic": StubAgent("The Skeptic", "Final Verdict: GO"),
        }
        orchestrator = StubInputOrchestrator(
            agents,
            max_iterations=1,
            interactive_pivots=True,
            stub_input_value="",
        )
        results = orchestrator.run_round_table("long ambiguous brief")
        self.assertNotEqual(results["final_verdict"], "INTAKE_CLARIFICATION_REQUIRED")
        self.assertGreaterEqual(results.get("iteration_count", 0), 1)
        self.assertLessEqual(float(results["intake_plan"].get("confidence", 1.0)), 0.35)

    def test_feasibility_intent_skips_scout_and_runs_direct_review(self):
        intake_plan = json.dumps(
            {
                "intent": "FEASIBILITY_REVIEW",
                "summary": "Review feasibility of appliance digital twin plan",
                "constraints": ["timeline: 30 days"],
                "assumptions": ["must reach $5k MRR"],
                "research_mode": "B2C_PLG",
                "normalized_topic": "home appliance digital twin feasibility",
                "buyer": "",
                "workflow": "",
                "pain": "",
                "vertical": "",
                "query_seed": "home appliance digital twin troubleshooting",
                "must_include_terms": [],
                "must_exclude_terms": [],
                "source_priority": ["reddit", "forums"],
                "clarification_needed": False,
                "clarification_question": "",
                "confidence": 0.82,
            }
        )
        agents = {
            "Intake Router": StubAgent("Intake Router", intake_plan),
            "Trend Scout": FailOnCallAgent("Trend Scout"),
            "Pain Analyst": StubAgent("Pain Analyst", "Boring Score: 6"),
            "SaaS Strategist": StubAgent(
                "SaaS Strategist",
                "Pricing Model: $19/month.\nAcquisition Channel: SEO and community.\nBudget Owner: Household operator.",
            ),
            "The Skeptic": StubAgent("The Skeptic", "Final Verdict: GO"),
        }
        orchestrator = Orchestrator(agents, max_iterations=1, interactive_pivots=False)
        results = orchestrator.run_round_table("full feasibility brief content")
        self.assertEqual(results["intent"], "FEASIBILITY_REVIEW")
        self.assertEqual(results["iteration_count"], 1)

    def test_user_brief_is_seeded_into_iteration_context(self):
        intake_plan = json.dumps(
            {
                "research_mode": "B2B_DISCOVERY",
                "normalized_topic": "home digital twin for appliances",
                "buyer": "",
                "workflow": "",
                "pain": "",
                "vertical": "",
                "query_seed": "home appliance digital twin maintenance",
                "must_include_terms": [],
                "must_exclude_terms": [],
                "source_priority": ["reddit", "forums"],
                "clarification_needed": False,
                "clarification_question": "",
                "confidence": 0.7,
            }
        )
        analyst = CaptureContextAgent("Pain Analyst", "Boring Score: 7\nhttps://example.com/a")
        agents = {
            "Intake Router": StubAgent("Intake Router", intake_plan),
            "Trend Scout": StubAgent("Trend Scout", "1. complaint from source https://example.com/a"),
            "Pain Analyst": analyst,
            "SaaS Strategist": StubAgent("SaaS Strategist", "Pricing Model: $250/month\nBudget Owner: Operations Manager"),
            "The Skeptic": StubAgent("The Skeptic", "Final Verdict: GO"),
        }
        orchestrator = Orchestrator(agents, max_iterations=1, interactive_pivots=False)
        brief = (
            "Project Brief: Home Digital Twin. The product stores appliance model metadata and "
            "uses it for contextual troubleshooting."
        )
        orchestrator.run_round_table(brief)

        roles = [item.get("role") for item in (analyst.last_context or [])]
        self.assertIn("User Brief", roles)
        self.assertTrue(
            any(
                "home digital twin" in (item.get("content", "").lower())
                for item in (analyst.last_context or [])
                if item.get("role") == "User Brief"
            )
        )

    def test_strip_search_modifiers_removes_prompt_suffixes(self):
        orchestrator = Orchestrator({}, max_iterations=1, interactive_pivots=False)
        cleaned = orchestrator._strip_search_modifiers(
            "home appliance troubleshooting user complaints feature requests alternatives"
        )
        lowered = cleaned.lower()
        self.assertNotIn("user complaints", lowered)
        self.assertNotIn("feature requests", lowered)
        self.assertNotIn("alternatives", lowered)

    def test_repeated_scout_fingerprint_detected_on_second_occurrence(self):
        orchestrator = Orchestrator({}, max_iterations=1, interactive_pivots=False)
        fingerprint = orchestrator._build_scout_fingerprint(
            scout_topic="home appliance troubleshooting user complaints",
            scout_output="1. URL: https://example.com/post-a\n2. URL: https://example.com/post-b",
        )
        self.assertFalse(orchestrator._is_repeated_scout_cycle(fingerprint))
        self.assertTrue(orchestrator._is_repeated_scout_cycle(fingerprint))


if __name__ == "__main__":
    unittest.main()
