import unittest

from src.utils.data_collector import DataCollector


class DataCollectorVariantTests(unittest.TestCase):
    def test_hackernews_variants_are_hn_native(self):
        collector = DataCollector(providers=[])
        variants = collector._build_query_variants(
            query="candidate profile management problems complaints issues",
            topic="candidate profile management",
            source_type="hackernews",
        )
        joined = " ".join(variants).lower()
        self.assertIn("show hn", joined)
        self.assertIn("launch", joined)
        self.assertNotIn("manual process pain points", joined)

    def test_web_variants_keep_pain_templates(self):
        collector = DataCollector(providers=[])
        variants = collector._build_query_variants(
            query="candidate profile management problems complaints issues",
            topic="candidate profile management",
            source_type="web",
        )
        joined = " ".join(variants).lower()
        self.assertIn("manual process pain points", joined)
        self.assertIn("software alternatives", joined)


if __name__ == "__main__":
    unittest.main()
