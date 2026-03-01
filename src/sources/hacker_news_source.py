from datetime import datetime
from typing import Any, Dict, List, Optional
from src.utils.search.hn_client import HackerNewsClient

class HackerNewsSource:
    name = "HackerNews"
    source_type = "hackernews"
    reliability_weight = 0.8

    def __init__(self, client: Optional[HackerNewsClient] = None):
        self.client = client or HackerNewsClient()

    def collect(self, query: str, topic: str, limit: int) -> List[Dict[str, Any]]:
        results = self.client.search(query, limit=limit)
        for result in results:
            result["source_type"] = self.source_type
            result["source_name"] = self.name
            result["collected_at"] = datetime.now().isoformat()
            result.setdefault("subreddit", "hackernews")
            result.setdefault("score", "N/A")
        return results
