import unittest

from src.utils.data_collector import DataCollector


class _StubProvider:
    def __init__(self, name, source_type, responses):
        self.name = name
        self.source_type = source_type
        self.reliability_weight = 0.6
        self._responses = responses

    def collect(self, query, topic, limit):
        return self._responses.get(query, [])


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

    def test_source_query_overrides_are_used_for_provider_attempts(self):
        provider = _StubProvider(
            name="Web",
            source_type="web",
            responses={
                "custom query one": [],
                "custom query two": [
                    {
                        "title": "Manual work causes delays",
                        "text": "The workflow is manual and error-prone with repeated bottlenecks.",
                        "url": "https://example.com/post-1",
                        "score": 11,
                        "subreddit": "web",
                        "source_type": "web",
                    }
                ],
            },
        )
        collector = DataCollector(providers=[provider])
        result = collector.collect(
            query="base query",
            topic="manual workflow operations",
            source_query_overrides={"web": ["custom query one", "custom query two"]},
            min_quality_threshold=0.20,
        )

        diag = result["source_diagnostics"]["web"]
        self.assertEqual(diag["attempted_queries"][0], "base query")
        self.assertIn("custom query two", diag["attempted_queries"])
        self.assertGreaterEqual(diag["accepted_records"], 1)

    def test_quality_rejection_reasons_are_exposed_per_source(self):
        provider = _StubProvider(
            name="Web",
            source_type="web",
            responses={
                "query": [
                    {
                        "title": "Dictionary definition",
                        "text": "A reference term entry.",
                        "url": "https://dictionary.com/word/example",
                        "score": 0,
                        "subreddit": "web",
                        "source_type": "web",
                    }
                ]
            },
        )
        collector = DataCollector(providers=[provider])
        result = collector.collect(
            query="query",
            topic="operations pain points",
            min_quality_threshold=0.80,
        )
        diag = result["source_diagnostics"]["web"]
        reasons = diag.get("quality_rejection_reasons", {})
        self.assertTrue(result["data_quality"] == "none")
        self.assertGreaterEqual(diag["dropped_low_quality"], 1)
        self.assertTrue(any(reason in reasons for reason in {"reference_dictionary_source", "thin_content"}))

    def test_home_assistant_brand_is_excluded_for_appliance_assistant_topics(self):
        collector = DataCollector(providers=[])
        variants = collector._resolve_query_variants(
            query="home appliance inventory troubleshooting assistant homeowners user complaints",
            topic="home appliance inventory troubleshooting assistant for homeowners",
            source_type="web",
        )
        self.assertTrue(any("-site:home-assistant.io" in query for query in variants))
        self.assertTrue(any('-"home assistant"' in query for query in variants))

    def test_home_assistant_topics_do_not_add_negative_brand_filters(self):
        collector = DataCollector(providers=[])
        variants = collector._resolve_query_variants(
            query="home assistant zigbee troubleshooting issues",
            topic="home assistant zigbee automation troubleshooting",
            source_type="web",
        )
        self.assertTrue(all("-site:home-assistant.io" not in query for query in variants))


if __name__ == "__main__":
    unittest.main()
