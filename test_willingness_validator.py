import unittest

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
        self.assertIn("Buyer budget fit score:", output)
        self.assertIn("Cost-of-inaction score:", output)

    def test_outputs_no_direct_signal_when_quotes_absent(self):
        context = [
            {"role": "Trend Scout", "content": "General frustration about time spent. URL: https://example.com/a"},
            {"role": "SaaS Strategist", "content": "Pricing Model: $300/month. Budget Owner: Director."},
        ]
        output = self.agent.process("Validate payment intent", context=context)
        self.assertIn("NO DIRECT SIGNAL", output)


if __name__ == "__main__":
    unittest.main()
