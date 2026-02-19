import json
import unittest

from src.agents.intake_router import IntakeRouterAgent


class IntakeRouterTests(unittest.TestCase):
    def setUp(self):
        self.agent = IntakeRouterAgent("Intake Router", "Research Planner", "test prompt")

    def test_buyer_first_input_produces_structured_plan(self):
        output = self.agent.process(
            "buyer: home warranty companies; workflow: service claim coordination; "
            "pain: contractor dispatch and status tracking"
        )
        plan = json.loads(output)
        self.assertEqual(plan["intent"], "MARKET_DISCOVERY")
        self.assertIn("summary", plan)
        self.assertEqual(plan["research_mode"], "B2B_BUYER_FIRST")
        self.assertEqual(plan["buyer"], "home warranty companies")
        self.assertIn("service claim coordination", plan["workflow"])
        self.assertIn("contractor", plan["query_seed"])

    def test_consumer_home_appliance_input_routes_to_b2c(self):
        output = self.agent.process(
            "I want to research a home appliance inventory and troubleshooting assistant for homeowners."
        )
        plan = json.loads(output)
        self.assertEqual(plan["intent"], "MARKET_DISCOVERY")
        self.assertEqual(plan["research_mode"], "B2C_PLG")
        self.assertIn("home appliance inventory", plan["normalized_topic"].lower())
        self.assertTrue(any("home-assistant.io" in term for term in plan["must_exclude_terms"]))

    def test_project_brief_preamble_triggers_structured_clarification(self):
        output = self.agent.process(
            """
            Here is the comprehensive Project Brief for your "Boring" SaaS.
            # Project Brief: "The Home Digital Twin" (Working Title)
            **Objective:** Build a $5k MRR SaaS by solving the high-anxiety, low-frequency problem
            of appliance maintenance using a "Digital Twin" data lock-in strategy.
            **Target Audience:** New homeowners, AirBnb hosts.
            **Risk 3: User Churn after the fix.**
            """
        )
        plan = json.loads(output)
        self.assertEqual(plan["intent"], "FEASIBILITY_REVIEW")
        self.assertFalse(plan["clarification_needed"])
        self.assertIn("appliance", plan["normalized_topic"])
        self.assertIn("digital", plan["normalized_topic"])
        self.assertIn("maintenance", plan["query_seed"])
        self.assertNotIn("comprehensive", plan["query_seed"])
        self.assertNotIn("stickiness", plan["query_seed"])
        self.assertIn("constraints", plan)
        self.assertIn("assumptions", plan)

    def test_feasibility_brief_with_inferred_fields_keeps_feasibility_intent(self):
        output = self.agent.process(
            """
            # Project Brief: "Home Digital Twin"
            **Objective:** Build a $5k MRR SaaS by solving appliance maintenance issues using model-aware troubleshooting.
            * **Goal:** Get the user to add 3 appliances.
            * **Target Audience:** New homeowners, Airbnb hosts, family tech support person.
            """
        )
        plan = json.loads(output)
        self.assertEqual(plan["intent"], "FEASIBILITY_REVIEW")
        self.assertFalse(plan["clarification_needed"])
        self.assertIn("appliance", plan["query_seed"])
        self.assertIn("maintenance", plan["query_seed"])


if __name__ == "__main__":
    unittest.main()
