from datetime import datetime
from typing import Any, Dict, List, Optional
from src.utils.search.youtube_client import YouTubeClient

class YouTubeSource:
    name = "YouTube"
    source_type = "youtube"
    reliability_weight = 0.6

    def __init__(self, client: Optional[YouTubeClient] = None):
        self.client = client or YouTubeClient()

    def collect(self, query: str, topic: str, limit: int) -> List[Dict[str, Any]]:
        results = self.client.search(query, limit=limit)
        for result in results:
            result["source_type"] = self.source_type
            result["source_name"] = self.name
            result["collected_at"] = datetime.now().isoformat()
            result.setdefault("subreddit", "youtube")
            result.setdefault("score", "N/A")
        return results
