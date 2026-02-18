from datetime import datetime, timedelta
from typing import Any, Dict, List

import requests

from src.config import get_settings


class HackerNewsSource:
    name = "HackerNews"
    source_type = "hackernews"
    reliability_weight = 0.9
    hn_api_base = "https://hn.algolia.com/api/v1/search"

    def collect(self, query: str, topic: str, limit: int) -> List[Dict[str, Any]]:
        settings = get_settings()
        params = {
            "query": query,
            "tags": "story",
            "hitsPerPage": limit,
            "numericFilters": f"created_at_i>{int((datetime.now() - timedelta(days=45)).timestamp())}",
        }
        response = requests.get(self.hn_api_base, params=params, timeout=settings.source_timeout_sec)
        if response.status_code != 200:
            return []

        payload = response.json()
        findings: List[Dict[str, Any]] = []
        for hit in payload.get("hits", [])[:limit]:
            findings.append(
                {
                    "title": hit.get("title", ""),
                    "text": hit.get("story_text", "")[:300] or f"See discussion: https://news.ycombinator.com/item?id={hit.get('objectID')}",
                    "url": hit.get("url", f"https://news.ycombinator.com/item?id={hit.get('objectID')}"),
                    "score": hit.get("points", 0),
                    "subreddit": "HackerNews",
                    "source_type": self.source_type,
                    "source_name": self.name,
                    "collected_at": datetime.now().isoformat(),
                }
            )
        return findings
