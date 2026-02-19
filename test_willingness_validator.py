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
        self.assertIn("Usage frequency fit score:", output)

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

    def test_market_proof_not_constant_without_explicit_prices(self):
        strong_context = [
            {"role": "Trend Scout", "content": "Manual reconciliation causes delays and errors."},
            {"role": "SaaS Strategist", "content": "Pricing Model: $300/month. Budget Owner: Director."},
            {
                "role": "Competitor Researcher",
                "content": (
                    "Competitors Found:\n"
                    "- Competitor A: https://a.com\n"
                    "- Competitor B: https://b.com\n"
                    "- Competitor C: https://c.com\n"
                    "- Competitor D: https://d.com\n"
                    "Market Saturation Assessment: YELLOW"
                ),
            },
        ]
        weak_context = [
            {"role": "Trend Scout", "content": "Some friction but no concrete complaints."},
            {"role": "SaaS Strategist", "content": "Pricing Model: $300/month. Budget Owner: Director."},
            {"role": "Competitor Researcher", "content": "Market Saturation Assessment: RED"},
        ]

        strong_output = self.agent.process("Validate payment intent", context=strong_context)
        weak_output = self.agent.process("Validate payment intent", context=weak_context)

        strong_market = re.search(r"Market proof score:\s*(\d+)/100", strong_output)
        weak_market = re.search(r"Market proof score:\s*(\d+)/100", weak_output)
        self.assertIsNotNone(strong_market)
        self.assertIsNotNone(weak_market)
        self.assertGreater(int(strong_market.group(1)), int(weak_market.group(1)))

    def test_low_frequency_consumer_pattern_scores_below_recurring_operator_pattern(self):
        low_frequency_context = [
            {
                "role": "Trend Scout",
                "content": "Homeowners describe appliance repairs as occasional, seasonal, and as-needed.",
            },
            {
                "role": "SaaS Strategist",
                "content": "Pricing Model: $10/month. Customer Segment: homeowners.",
            },
            {
                "role": "Competitor Researcher",
                "content": "Market Saturation Assessment: YELLOW",
            },
        ]
        recurring_context = [
            {
                "role": "Trend Scout",
                "content": "Property managers report weekly recurring dispatch delays and tenant churn risk.",
            },
            {
                "role": "SaaS Strategist",
                "content": "Pricing Model: $79/month. Budget Owner: Property Manager.",
            },
            {
                "role": "Competitor Researcher",
                "content": "Market Saturation Assessment: YELLOW\nDirect Product Evidence Count: 2",
            },
        ]

        low_output = self.agent.process("Validate payment intent", context=low_frequency_context)
        recurring_output = self.agent.process("Validate payment intent", context=recurring_context)

        low_score = re.search(r"Price Willingness Score:\s*(\d+)%", low_output)
        recurring_score = re.search(r"Price Willingness Score:\s*(\d+)%", recurring_output)
        self.assertIsNotNone(low_score)
        self.assertIsNotNone(recurring_score)
        self.assertLess(int(low_score.group(1)), int(recurring_score.group(1)))


if __name__ == "__main__":
    unittest.main()
