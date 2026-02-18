"""
Unified data collection from real sources: Reddit, HackerNews, DuckDuckGo.
Prioritizes real community data over synthetic fallbacks.
"""
import os
import requests
from typing import List, Dict
from termcolor import colored
from datetime import datetime, timedelta
from .reddit_client import RedditClient
from .search_client import SearchClient

class DataCollector:
    def __init__(self):
        self.reddit_client = RedditClient()
        self.search_client = SearchClient()
        self.hn_api_base = "https://hn.algolia.com/api/v1"
        
    def collect(self, query: str, topic: str, limit: int = 15) -> Dict:
        """
        Collects real data from multiple sources.
        Returns: {
            "results": [list of findings],
            "source_breakdown": {"reddit": X, "hn": Y, "web": Z},
            "confidence": 0-1,
            "data_quality": "real" | "synthetic" | "none"
        }
        """
        all_results = []
        sources = {}
        
        # Try Reddit first (best signal-to-noise for complaints)
        reddit_results = self.collect_reddit(query, limit=limit // 3)
        if reddit_results:
            all_results.extend(reddit_results)
            sources["reddit"] = len(reddit_results)
            print(colored(f"[DataCollector] Reddit: {len(reddit_results)} results", "green"))
        
        # Try HackerNews
        hn_results = self.collect_hackernews(query, limit=limit // 3)
        if hn_results:
            all_results.extend(hn_results)
            sources["hackernews"] = len(hn_results)
            print(colored(f"[DataCollector] HackerNews: {len(hn_results)} results", "green"))
        
        # Try DuckDuckGo as supplementary (lower quality)
        if len(all_results) < limit // 2:  # Only fill gaps
            web_results = self.collect_web(query, limit=limit // 3)
            if web_results:
                all_results.extend(web_results)
                sources["web"] = len(web_results)
                print(colored(f"[DataCollector] Web: {len(web_results)} results", "yellow"))
        
        # Determine data quality
        if not all_results:
            print(colored(f"[DataCollector] CRITICAL: No real data found for '{query}'. System will FAIL LOUDLY.", "red"))
            return {
                "results": [],
                "source_breakdown": sources,
                "confidence": 0.0,
                "data_quality": "none",
                "error": "No real data available from any source"
            }
        
        # Calculate confidence based on source types
        real_data_count = sources.get("reddit", 0) + sources.get("hackernews", 0)
        total_count = len(all_results)
        confidence = real_data_count / total_count if total_count > 0 else 0.0
        
        return {
            "results": all_results,
            "source_breakdown": sources,
            "confidence": confidence,
            "data_quality": "real" if confidence >= 0.5 else "mixed",
            "total_results": total_count
        }
    
    def collect_reddit(self, query: str, limit: int = 5) -> List[Dict]:
        """Collect from Reddit subreddits."""
        try:
            results = self.reddit_client.search(
                query, 
                subreddits=["smallbusiness", "entrepreneur", "startups", "SideProject", "b2b", "Freelance"],
                limit=limit
            )
            
            # Filter for quality (must have engagement or recent activity)
            filtered = []
            for result in results:
                if result.get("score", 0) > 5 or not self.reddit_client.authenticated:
                    # Add metadata for traceability
                    result["source_type"] = "reddit"
                    result["collected_at"] = datetime.now().isoformat()
                    filtered.append(result)
            
            return filtered
        except Exception as e:
            print(colored(f"[DataCollector] Reddit collection failed: {e}", "red"))
            return []
    
    def collect_hackernews(self, query: str, limit: int = 5) -> List[Dict]:
        """Collect from HackerNews using Algolia API."""
        try:
            # Search for Show HN and Ask HN posts mentioning the topic
            params = {
                "query": query,
                "tags": ["story", "show_hn", "ask_hn"],
                "hitsPerPage": limit,
                "numericFilters": f"created_at_i>{int((datetime.now() - timedelta(days=30)).timestamp())}"
            }
            
            response = requests.get(f"{self.hn_api_base}/search", params=params, timeout=5)
            if response.status_code != 200:
                return []
            
            data = response.json()
            results = []
            
            for hit in data.get("hits", [])[:limit]:
                results.append({
                    "title": hit.get("title", ""),
                    "text": hit.get("story_text", "")[:300] or f"See comments at: {hit.get('url', '')}",
                    "url": hit.get("url", f"https://news.ycombinator.com/item?id={hit.get('objectID')}"),
                    "score": hit.get("points", 0),
                    "subreddit": "HackerNews",
                    "source_type": "hackernews",
                    "collected_at": datetime.now().isoformat()
                })
            
            return results
        except Exception as e:
            print(colored(f"[DataCollector] HackerNews collection failed: {e}", "yellow"))
            return []
    
    def collect_web(self, query: str, limit: int = 5) -> List[Dict]:
        """Fallback: Collect from web (DuckDuckGo)."""
        try:
            results = self.search_client.search(query, limit=limit)
            for result in results:
                result["source_type"] = "web"
                result["collected_at"] = datetime.now().isoformat()
            return results
        except Exception as e:
            print(colored(f"[DataCollector] Web collection failed: {e}", "red"))
            return []
    
    def format_for_prompt(self, collection_result: Dict) -> str:
        """Format collection result for LLM ingestion."""
        results = collection_result.get("results", [])
        sources = collection_result.get("source_breakdown", {})
        quality = collection_result.get("data_quality", "none")
        confidence = collection_result.get("confidence", 0.0)
        
        if quality == "none":
            return f"[DATA COLLECTION FAILED] No real data found. Error: {collection_result.get('error', 'Unknown')}"
        
        output = f"[REAL DATA COLLECTION]\nQuality: {quality.upper()} | Confidence: {confidence:.1%}\nSources: {sources}\n\n"
        
        for i, result in enumerate(results, 1):
            output += f"{i}. [{result.get('source_type', 'unknown').upper()}] {result.get('title', '')}\n"
            output += f"   Source: r/{result.get('subreddit', 'unknown')}\n"
            output += f"   Score/Engagement: {result.get('score', 'N/A')}\n"
            output += f"   Content: {result.get('text', '')[:200]}...\n"
            output += f"   URL: {result.get('url', '')}\n\n"
        
        return output
