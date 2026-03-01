import requests
from typing import List, Dict
from src.utils.console import colored
from .base import BaseSearchClient

class GitHubClient(BaseSearchClient):
    def search(self, query: str, limit: int = 15) -> List[Dict[str, str]]:
        print(colored(f"[Search: GitHub] Searching issues for '{query}'...", "cyan"))
        results = []
        try:
            # Strip site: operators that the LLM might generate for DDG
            clean_query = query.replace("site:github.com", "").replace("site:github.com/issues", "").strip()
            if not clean_query:
                clean_query = "bug OR enhancement"
            
            url = "https://api.github.com/search/issues"
            params = {
                "q": f"{clean_query} is:issue",
                "per_page": limit,
                "sort": "updated",
            }
            headers = {"Accept": "application/vnd.github.v3+json"}
            
            response = requests.get(url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            for item in data.get("items", []):
                title = item.get("title", "")
                body = item.get("body", "") or ""
                # Strip markdown/comments to keep it relatively clean for the LLM
                body_clean = body.replace("\r", " ").replace("\n", " ")[:1500]
                
                results.append({
                    "title": title,
                    "text": body_clean,
                    "url": item.get("html_url", ""),
                    "source": "GitHub Issue"
                })
                
        except Exception as e:
            print(colored(f"[Search: GitHub] Error fetching data: {e}", "red"))
            
        return results
