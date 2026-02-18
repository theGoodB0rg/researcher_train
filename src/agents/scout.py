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
            quality_summary = collection_result.get("quality_summary", {})
            if quality_summary:
                print(
                    colored(
                        f"[Scout] Quality filter summary: accepted={quality_summary.get('accepted_count', 0)} "
                        f"dropped={quality_summary.get('dropped_count', 0)} "
                        f"threshold={quality_summary.get('threshold', 0.0):.2f}",
                        "red",
                    )
                )
            for source_type, diag in diagnostics.items():
                attempted_count = len(diag.get("attempted_queries", []))
                print(
                    colored(
                        f"  - {diag.get('provider', source_type)} [{source_type}] "
                        f"status={diag.get('status')} raw={diag.get('raw_records', diag.get('results', 0))} "
                        f"accepted={diag.get('accepted_records', 0)} "
                        f"dropped={diag.get('dropped_low_quality', 0)} attempts={attempted_count}",
                        "red",
                    )
                )
                if diag.get("error"):
                    print(colored(f"    error={diag.get('error')}", "red"))
            
            # Return deterministic failure marker for orchestrator parsing.
            failure_message = (
                f"[DATA COLLECTION FAILED] {error_msg}\n\n"
                "The research system could not retrieve enough real data from configured sources.\n"
                "Without real data, this research round cannot proceed."
            )
            self.speak(failure_message)
            return failure_message
        else:
            # Format real data for LLM
            formatted_data = self.data_collector.format_for_prompt(collection_result)

        # Inject into prompt
        enriched_input = (
            f"{input_data}\n\n"
            "[DATA QUALITY STATUS]\nPASS\n[END STATUS]\n\n"
            "[DATA START]\n"
            f"{formatted_data}\n"
            "[DATA END]\n\n"
            "Analyze this data according to your system prompt. "
            "Do not output 'NO REAL DATA' when status is PASS."
        )
        
        return super().process(enriched_input, context)
