import os
import praw
from typing import List, Dict
from termcolor import colored
import random

class RedditClient:
    def __init__(self):
        self.client_id = os.getenv("REDDIT_CLIENT_ID")
        self.client_secret = os.getenv("REDDIT_CLIENT_SECRET")
        self.user_agent = os.getenv("REDDIT_USER_AGENT", "researcher_agent_v1")
        
        if self.client_id and self.client_secret:
            try:
                self.reddit = praw.Reddit(
                    client_id=self.client_id,
                    client_secret=self.client_secret,
                    user_agent=self.user_agent
                )
                self.authenticated = True
                print(colored("[System] Reddit API Connected.", "green"))
            except Exception as e:
                print(colored(f"[System] Reddit Connection Failed: {e}", "red"))
                self.authenticated = False
        else:
            self.authenticated = False
            print(colored("[System] No Reddit Credentials found. Using Mock Data.", "yellow"))

    def search(self, query: str, subreddits: List[str] = None, limit: int = 10) -> List[Dict[str, str]]:
        if not self.authenticated:
            return self._get_mock_data(query)

        if not subreddits:
            subreddits = ["smallbusiness", "entrepreneur", "startups", "b2b", "marketing"]
        
        results = []
        try:
            # Combine subreddits into a multi-reddit string
            sub_string = "+".join(subreddits)
            print(colored(f"[Scout] Searching r/{sub_string} for '{query}'...", "cyan"))
            
            for post in self.reddit.subreddit(sub_string).search(query, limit=limit, sort="relevance"):
                results.append({
                    "title": post.title,
                    "text": post.selftext[:500] + "...",  # Truncate for token limits
                    "url": post.url,
                    "score": post.score,
                    "subreddit": post.subreddit.display_name
                })
        except Exception as e:
            print(colored(f"[Scout] Error processing Reddit search: {e}", "red"))
            return self._get_mock_data(query) # Fallback

        return results

    def _get_mock_data(self, query: str) -> List[Dict[str, str]]:
        """Fake data for testing without API keys."""
        print(colored(f"[Scout] (MOCK) Searching for '{query}'...", "cyan"))
        return [
            {
                "title": "I hate manually copying data from PDF invoices to Excel",
                "text": "Every day I spend 2 hours copying invoice numbers. Why is there no tool for this that works?",
                "url": "https://reddit.com/r/smallbusiness/123",
                "score": 45,
                "subreddit": "smallbusiness"
            },
            {
                "title": "Medical compliance forms are a nightmare",
                "text": "HIPAA compliance is driving me crazy. Validating these forms takes forever.",
                "url": "https://reddit.com/r/medical/456",
                "score": 120,
                "subreddit": "medicine"
            },
            {
                "title": "How do you guys handle staff scheduling?",
                "text": "Excel is breaking. Verification of availability is a pain.",
                "url": "https://reddit.com/r/restaurantowners/789",
                "score": 30,
                "subreddit": "restaurantowners"
            }
        ]
