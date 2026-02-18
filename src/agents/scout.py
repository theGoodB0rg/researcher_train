from termcolor import colored
from src.core.agent import Agent
from src.utils.data_collector import DataCollector
from typing import List, Dict

class ScoutAgent(Agent):
    def __init__(self, name: str, role: str, system_prompt: str, color: str = "cyan"):
        super().__init__(name, role, system_prompt, color)
        self.data_collector = DataCollector()

    def process(self, input_data: str, context: List[Dict[str, str]] = None) -> str:
        # Extract the core topic from the input
        # "Find complaints and issues related to: dental practice" -> "dental practice"
        topic = input_data.replace("Find complaints and issues related to:", "").strip()
        
        # Collect data from real sources (Reddit, HackerNews, Web)
        print(f"[Scout] Collecting real data for: {topic}")
        collection_result = self.data_collector.collect(
            query=f"{topic} problems complaints issues",
            topic=topic,
            limit=15
        )
        
        # Check data quality
        if collection_result.get("data_quality") == "none":
            # FAIL LOUDLY - no synthetic data fallback
            error_msg = collection_result.get("error", "Unknown error")
            print(colored(f"[Scout] DATA COLLECTION FAILED: {error_msg}", "red"))
            print(colored(f"[Scout] Source diagnostics:", "red"))
            diagnostics = collection_result.get("source_diagnostics", {})
            for source_type, diag in diagnostics.items():
                attempted_count = len(diag.get("attempted_queries", []))
                print(
                    colored(
                        f"  - {diag.get('provider', source_type)} [{source_type}] "
                        f"status={diag.get('status')} results={diag.get('results')} attempts={attempted_count}",
                        "red",
                    )
                )
                if diag.get("error"):
                    print(colored(f"    error={diag.get('error')}", "red"))
            
            # Pass failure to LLM so it understands the situation
            formatted_data = f"DATA COLLECTION FAILED: {error_msg}\n\nThe research system could not retrieve real data from Reddit, HackerNews, or DuckDuckGo.\nWithout real data, this research round cannot proceed.\nPlease resolve the data collection issue and try again."
        else:
            # Format real data for LLM
            formatted_data = self.data_collector.format_for_prompt(collection_result)

        # Inject into prompt
        enriched_input = f"{input_data}\n\n[DATA START]\n{formatted_data}\n[DATA END]\n\nAnalyze this data according to your system prompt."
        
        return super().process(enriched_input, context)
