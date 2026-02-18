from ddgs import DDGS
from termcolor import colored
from typing import List, Dict

from src.config import get_settings


class SearchClient:
    def __init__(self):
        self.allow_mock_data = get_settings().allow_mock_data

    def search(self, query: str, limit: int = 10) -> List[Dict[str, str]]:
        """
        Searches DuckDuckGo for the query.
        """
        print(colored(f"[Scout] Searching Web for '{query}'...", "cyan"))
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
            print(colored(f"[Scout] Search Error: {e}", "red"))
            return self._maybe_mock_data(query)

        return results

    def _maybe_mock_data(self, query: str) -> List[Dict[str, str]]:
        if not self.allow_mock_data:
            return []

        print(colored(f"[Scout] (MOCK MODE ENABLED) Returning mock web data for '{query}'", "yellow"))
        return [
            {
                "title": "Forum: I hate doing payroll manually",
                "text": "Every friday I have to calculate hours manually. It sucks.",
                "url": "https://example.com/forum/1",
                "source": "MockWeb"
            }
        ]
