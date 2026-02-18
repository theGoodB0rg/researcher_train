import unittest
import re

from src.agents.willingness_validator import WillingnessToPayValidatorAgent


class WillingnessValidatorCompositeTests(unittest.TestCase):
    def setUp(self):
        self.agent = WillingnessToPayValidatorAgent(
            "Willingness Validator",
            "Market Researcher",
            "test prompt",
        )

    def test_composite_model_uses_pricing_budget_and_inaction(self):
        context = [
            {
                "role": "Trend Scout",
                "content": (
                    "Teams report manual data entry delays and time lost. "
                    "URL: https://example.com/scout-1"
                ),
            },
            {
                "role": "Pain Analyst",
                "content": (
                    "Cost of Inaction: revenue leakage, delayed placements, manual bottlenecks. "
                    "URL: https://example.com/analyst-1"
                ),
            },
            {
                "role": "SaaS Strategist",
                "content": (
                    "Pricing Model: $250/month per agency.\n"
                    "Budget Owner: Operations Manager.\n"
                    "Customer Segment: staffing agencies."
                ),
            },
            {
                "role": "Competitor Researcher",
                "content": (
                    "Competitors Found:\n"
                    "- ToolA: $120/month\n"
                    "- ToolB: $150/month\n"
                    "Market Saturation Assessment: YELLOW"
                ),
            },
        ]

        output = self.agent.process("Validate if target customers will pay for this solution:", context=context)
        self.assertIn("Price Willingness Score:", output)
        self.assertIn("Competitor monthly anchor:", output)
        self.assertIn("Market proof score:", output)
        self.assertIn("Buyer budget fit score:", output)
        self.assertIn("Cost-of-inaction score:", output)

    def test_outputs_no_direct_signal_when_quotes_absent(self):
        context = [
            {"role": "Trend Scout", "content": "General frustration about time spent. URL: https://example.com/a"},
            {"role": "SaaS Strategist", "content": "Pricing Model: $300/month. Budget Owner: Director."},
        ]
        output = self.agent.process("Validate payment intent", context=context)
        self.assertIn("NO DIRECT SIGNAL", output)

    def test_high_market_proof_can_reach_strong_signal_without_direct_quotes(self):
        context = [
            {
                "role": "Trend Scout",
                "content": (
                    "Manual AP reconciliation causes delays, rework, and revenue leakage. "
                    "Teams report recurring bottlenecks."
                ),
            },
            {
                "role": "SaaS Strategist",
                "content": (
                    "Pricing Model: $220/month.\n"
                    "Budget Owner: Finance Director.\n"
                    "Customer Segment: AP teams."
                ),
            },
            {
                "role": "Competitor Researcher",
                "content": (
                    "Competitors Found:\n"
                    "- ToolA: $180/month\n"
                    "- ToolB: $220/month\n"
                    "- ToolC: $260/month\n"
                    "Market Saturation Assessment: YELLOW"
                ),
            },
        ]
        output = self.agent.process("Validate payment intent", context=context)
        match = re.search(r"Price Willingness Score:\s*(\d+)%", output)
        self.assertIsNotNone(match)
        self.assertGreaterEqual(int(match.group(1)), 70)

    def test_low_market_proof_and_substitutes_produce_low_signal(self):
        context = [
            {
                "role": "Trend Scout",
                "content": "Users mention free templates and many alternatives. Not worth paying a lot.",
            },
            {
                "role": "SaaS Strategist",
                "content": "Pricing Model: $1800/month. Customer Segment: individuals.",
            },
            {
                "role": "Competitor Researcher",
                "content": "Market Saturation Assessment: RED. Many free alternatives.",
            },
        ]
        output = self.agent.process("Validate payment intent", context=context)
        match = re.search(r"Price Willingness Score:\s*(\d+)%", output)
        self.assertIsNotNone(match)
        self.assertLessEqual(int(match.group(1)), 45)


if __name__ == "__main__":
    unittest.main()
