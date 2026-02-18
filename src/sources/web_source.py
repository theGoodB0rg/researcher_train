from datetime import datetime
from typing import Any, Dict, List, Optional

from src.utils.search_client import SearchClient


class WebSource:
    name = "Web"
    source_type = "web"
    reliability_weight = 0.5

    def __init__(self, search_client: Optional[SearchClient] = None):
        self.search_client = search_client or SearchClient()

    def collect(self, query: str, topic: str, limit: int) -> List[Dict[str, Any]]:
        results = self.search_client.search(query, limit=limit)
        for result in results:
            result["source_type"] = self.source_type
            result["source_name"] = self.name
            result["collected_at"] = datetime.now().isoformat()
            result.setdefault("subreddit", "web")
            result.setdefault("score", "N/A")
        return results
