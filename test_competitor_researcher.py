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


if __name__ == "__main__":
    unittest.main()
