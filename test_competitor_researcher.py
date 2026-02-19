import unittest

from src.agents.competitor_researcher import CompetitorResearcherAgent


class CompetitorResearcherParsingTests(unittest.TestCase):
    def setUp(self):
        self.agent = CompetitorResearcherAgent(
            "Competitor Researcher",
            "Market Analyst",
            "test prompt",
        )

    def test_extracts_pitch_content_not_heading(self):
        strategist_text = """
**1. The Pitch**
"CommuniMate: A relationship communication assistant that nudges couples."

**2. The MVP Feature Set**
- Prompt engine
"""
        idea_name, _ = self.agent._extract_idea([{"role": "SaaS Strategist", "content": strategist_text}])
        self.assertIsNotNone(idea_name)
        self.assertIn("CommuniMate", idea_name)
        self.assertNotIn("The Pitch", idea_name)

    def test_search_seed_deduplicates_heading_noise(self):
        seed = self.agent._build_search_seed(
            "The Pitch",
            "**1. The Pitch**\nCommuniMate relationship assistant\n**3. Pricing Model**",
        )
        self.assertNotIn("pitch pitch", seed)
        self.assertIn("communimate", seed)

    def test_market_saturation_requires_direct_product_evidence_for_red(self):
        weak_competitors = [
            {"name": "A", "domain": "a.com", "url": "https://a.com", "evidence_count": 1, "keyword_overlap": 1},
            {"name": "B", "domain": "b.com", "url": "https://b.com", "evidence_count": 1, "keyword_overlap": 1},
            {"name": "C", "domain": "c.com", "url": "https://c.com", "evidence_count": 1, "keyword_overlap": 1},
        ]
        findings = self.agent._build_findings("Idea", weak_competitors)
        self.assertIn("YELLOW", str(findings["market_saturation"]))

        strong_competitors = [
            {"name": "A", "domain": "a.com", "url": "https://a.com", "evidence_count": 3, "keyword_overlap": 2},
            {"name": "B", "domain": "b.com", "url": "https://b.com", "evidence_count": 2, "keyword_overlap": 2},
            {"name": "C", "domain": "c.com", "url": "https://c.com", "evidence_count": 2, "keyword_overlap": 2},
            {"name": "D", "domain": "d.com", "url": "https://d.com", "evidence_count": 2, "keyword_overlap": 2},
        ]
        strong_findings = self.agent._build_findings("Idea", strong_competitors)
        self.assertIn("RED", str(strong_findings["market_saturation"]))
        self.assertGreaterEqual(int(strong_findings.get("direct_competitor_count", 0)), 4)


if __name__ == "__main__":
    unittest.main()
