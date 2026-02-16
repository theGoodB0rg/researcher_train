from termcolor import colored
from src.core.agent import Agent
from src.utils.search_client import SearchClient
from typing import List, Dict

class ScoutAgent(Agent):
    def __init__(self, name: str, role: str, system_prompt: str, color: str = "cyan"):
        super().__init__(name, role, system_prompt, color)
        self.search_client = SearchClient()

    def process(self, input_data: str, context: List[Dict[str, str]] = None) -> str:
        # Extract the core topic from the input
        # "Find complaints and issues related to: dental practice" -> "dental practice"
        topic = input_data.replace("Find complaints and issues related to:", "").strip()
        
        # Formulate a better search query for complaints
        # We can do multiple searches if needed, but let's start with one.
        search_query = f"{topic} complaints site:reddit.com OR site:quora.com OR site:news.ycombinator.com"
        
        # Fetch data
        print(f"[Scout] Searching for: {search_query}")
        results = self.search_client.search(search_query, limit=10)
        
        # Fallback if no results with strict site operators
        if not results:
            print(colored("[Scout] Strict search failed. Trying broader search...", "yellow"))
            broader_query = f"{topic} complaints problems reddit quora"
            results = self.search_client.search(broader_query, limit=10)

        # Format data
        if not results:
             formatted_data = "No specific search results found. Please rely on your internal knowledge."
        else:
            formatted_data = "Here are search results for potential problems:\n"
            for i, res in enumerate(results):
                formatted_data += f"{i+1}. [{res['source']}] {res['title']}\n   Snippet: {res['text']}\n   URL: {res['url']}\n\n"

        # Inject into prompt
        enriched_input = f"{input_data}\n\n[SEARCH DATA START]\n{formatted_data}\n[SEARCH DATA END]\n\nAnalyze this data according to your system prompt."
        
        return super().process(enriched_input, context)
