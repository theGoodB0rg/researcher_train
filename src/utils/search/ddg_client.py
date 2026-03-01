from ddgs import DDGS
from src.utils.console import colored
from typing import List, Dict
from src.config import get_settings
from .base import BaseSearchClient

class DuckDuckGoClient(BaseSearchClient):
    def __init__(self):
        self.allow_mock_data = get_settings().allow_mock_data

    def search(self, query: str, limit: int = 10) -> List[Dict[str, str]]:
        print(colored(f"[Search: DDG] Querying '{query}'...", "cyan"))
        results = []
        try:
            with DDGS() as ddgs:
                search_results = ddgs.text(query, max_results=limit)
            if search_results:
                for r in search_results:
                    results.append({
                        "title": r.get('title', ''),
                        "text": r.get('body', ''),
                        "url": r.get('href', ''),
                        "source": "Web"
                    })
        except Exception as e:
            print(colored(f"[Search: DDG] Error: {e}", "red"))
            return self._maybe_mock_data(query)

        return results

    def search_forum(self, query: str, forum_domain: str, limit: int = 10) -> List[Dict[str, str]]:
        """Helper to quickly dork a specific forum domain."""
        dorked_query = f'site:{forum_domain} {query}'
        return self.search(dorked_query, limit)

    def _maybe_mock_data(self, query: str) -> List[Dict[str, str]]:
        if not self.allow_mock_data:
            return []
        print(colored(f"[Search: DDG] (MOCK MODE) Returning mock web data for '{query}'", "yellow"))
        return [
            {
                "title": "Forum: I hate doing payroll manually",
                "text": "Every friday I have to calculate hours manually. It sucks.",
                "url": "https://example.com/forum/1",
                "source": "MockWeb"
            }
        ]
