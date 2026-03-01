import time
from typing import Any, Dict, List
from .base import SourceProvider
from src.utils.search.github_client import GitHubClient

class GitHubSource(SourceProvider):
    def __init__(self):
        super().__init__()
        self.client = GitHubClient()

    @property
    def name(self) -> str:
        return "GitHub Issues"

    @property
    def source_type(self) -> str:
        return "github"

    def collect(self, query: str, topic: str, limit: int = 15) -> List[Dict[str, Any]]:
        try:
            raw_results = self.client.search(query=query, limit=limit)
        except Exception as e:
            print(f"[GitHubSource] Error: {e}")
            return []

        if not raw_results:
            return []

        standardized = []
        for result in raw_results:
            standardized.append({
                "source_type": self.source_type,
                "subreddit": "github",
                "title": result.get("title", ""),
                "text": result.get("text", ""),
                "url": result.get("url", ""),
                "score": 0, # Could use positive reactions later
                "collected_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            })
            
        return standardized
