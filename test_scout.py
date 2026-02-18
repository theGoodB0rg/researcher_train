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


if __name__ == "__main__":
    unittest.main()
