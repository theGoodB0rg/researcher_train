from duckduckgo_search import DDGS
from termcolor import colored
from typing import List, Dict

class SearchClient:
    def __init__(self):
        self.ddgs = DDGS()

    def search(self, query: str, limit: int = 10) -> List[Dict[str, str]]:
        """
        Searches DuckDuckGo for the query.
        """
        print(colored(f"[Scout] Searching Web for '{query}'...", "cyan"))
        results = []
        try:
            # simple text search
            search_results = self.ddgs.text(query, max_results=limit)
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
            # Fallback mock data if search fails (e.g. rate limits)
            return self._get_mock_data(query)

        return results

    def _get_mock_data(self, query: str) -> List[Dict[str, str]]:
        """Fallback data."""
        return [
            {
                "title": "Forum: I hate doing payroll manually",
                "text": "Every friday I have to calculate hours manually. It sucks.",
                "url": "https://example.com/forum/1",
                "source": "MockWeb"
            }
        ]
