import requests
from src.utils.console import colored
from typing import List, Dict
from .base import BaseSearchClient

class HackerNewsClient(BaseSearchClient):
    def search(self, query: str, limit: int = 10) -> List[Dict[str, str]]:
        print(colored(f"[Search: HackerNews] Querying Algolia for '{query}'...", "cyan"))
        results = []
        try:
            url = "http://hn.algolia.com/api/v1/search"
            params = {
                "query": query,
                "hitsPerPage": limit,
                "tags": "story" # Can also be 'comment', but stories represent whole threads
            }
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                for hit in data.get("hits", []):
                    title = hit.get("title", "")
                    text = hit.get("story_text", "")
                    url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
                    
                    results.append({
                        "title": title,
                        "text": text if text else "HackerNews thread discussion.",
                        "url": url,
                        "source": "HackerNews"
                    })
        except Exception as e:
            print(colored(f"[Search: HackerNews] Error: {e}", "red"))
        
        return results
