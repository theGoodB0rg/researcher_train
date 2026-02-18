from datetime import datetime
from typing import Any, Dict, List, Optional

from src.utils.reddit_client import RedditClient


class RedditSource:
    name = "Reddit"
    source_type = "reddit"
    reliability_weight = 1.0

    def __init__(self, reddit_client: Optional[RedditClient] = None):
        self.reddit_client = reddit_client or RedditClient()

    def collect(self, query: str, topic: str, limit: int) -> List[Dict[str, Any]]:
        results = self.reddit_client.search(
            query=query,
            subreddits=["smallbusiness", "entrepreneur", "startups", "SideProject", "b2b", "Freelance"],
            limit=limit,
        )

        filtered: List[Dict[str, Any]] = []
        for result in results:
            score = int(result.get("score", 0) or 0)
            if score < 5:
                continue
            result["source_type"] = self.source_type
            result["source_name"] = self.name
            result["collected_at"] = datetime.now().isoformat()
            filtered.append(result)
        return filtered
