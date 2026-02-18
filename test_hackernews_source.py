import unittest
from unittest.mock import Mock, patch

from src.sources.hackernews_source import HackerNewsSource


class HackerNewsSourceTests(unittest.TestCase):
    @patch("src.sources.hackernews_source.requests.get")
    def test_collect_combines_story_and_comment_hits(self, mock_get):
        story_response = Mock()
        story_response.status_code = 200
        story_response.json.return_value = {
            "hits": [
                {
                    "objectID": "100",
                    "title": "Show HN: Hiring Pipeline Tool",
                    "story_text": "Automates candidate updates",
                    "url": "https://example.com/show-hn-tool",
                    "points": 42,
                }
            ]
        }

        comment_response = Mock()
        comment_response.status_code = 200
        comment_response.json.return_value = {
            "hits": [
                {
                    "objectID": "101",
                    "story_title": "Ask HN: Recruitment workflows",
                    "comment_text": "<p>Manual follow-ups are painful</p>",
                    "story_url": "https://news.ycombinator.com/item?id=101",
                    "num_comments": 12,
                }
            ]
        }
        mock_get.side_effect = [story_response, comment_response]

        source = HackerNewsSource()
        records = source.collect(query="recruitment workflow", topic="recruitment workflow", limit=5)

        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["source_type"], "hackernews")
        self.assertIn("Show HN", records[0]["title"])
        self.assertIn("Manual follow-ups are painful", records[1]["text"])
        self.assertEqual(records[1]["score"], 12)

    @patch("src.sources.hackernews_source.requests.get")
    def test_collect_raises_with_http_error_details(self, mock_get):
        failed = Mock()
        failed.status_code = 503
        failed.text = "Service unavailable"
        mock_get.return_value = failed

        source = HackerNewsSource()
        with self.assertRaises(RuntimeError) as ctx:
            source.collect(query="ops automation", topic="ops automation", limit=5)

        self.assertIn("status=503", str(ctx.exception))
        self.assertIn("tags=story", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
