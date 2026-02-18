from termcolor import colored
from src.core.agent import Agent
from src.utils.data_collector import DataCollector
from typing import List, Dict
import re

class ScoutAgent(Agent):
    def __init__(self, name: str, role: str, system_prompt: str, color: str = "cyan"):
        super().__init__(name, role, system_prompt, color)
        self.data_collector = DataCollector()

    def process(self, input_data: str, context: List[Dict[str, str]] = None) -> str:
        # Extract the core topic from the input
        # "Find complaints and issues related to: dental practice" -> "dental practice"
        topic = input_data.replace("Find complaints and issues related to:", "").strip()
        query_seed = self._build_query_seed(topic)
        
        # Collect data from real sources (Reddit, HackerNews, Web)
        print(f"[Scout] Collecting real data for: {topic}")
        if query_seed.lower() != topic.lower():
            print(colored(f"[Scout] Query seed (compacted): {query_seed}", "cyan"))
        collection_result = self._collect_with_adaptive_strategy(topic=topic, query_seed=query_seed)
        
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
            "[QUERY SEED]\n"
            f"{query_seed}\n"
            "[END QUERY SEED]\n\n"
            "[DATA QUALITY STATUS]\nPASS\n[END STATUS]\n\n"
            "[DATA START]\n"
            f"{formatted_data}\n"
            "[DATA END]\n\n"
            "Analyze this data according to your system prompt. "
            "Do not output 'NO REAL DATA' when status is PASS."
        )
        
        return super().process(enriched_input, context)

    def _build_query_seed(self, topic: str, max_terms: int = 7) -> str:
        tokens = re.findall(r"[a-z0-9]+", (topic or "").lower())
        if not tokens:
            return topic

        stop_words = {
            "using",
            "with",
            "and",
            "the",
            "for",
            "from",
            "into",
            "via",
            "business",
            "operations",
            "workflow",
            "workflows",
            "pain",
            "points",
            "related",
            "issues",
        }
        selected = []
        seen = set()
        for token in tokens:
            if token in seen or token in stop_words:
                continue
            seen.add(token)
            selected.append(token)
            if len(selected) >= max_terms:
                break

        return " ".join(selected) if selected else " ".join(tokens[:max_terms])

    def _collect_with_adaptive_strategy(self, topic: str, query_seed: str) -> Dict[str, object]:
        strategies = [
            {
                "label": "pain_complaints",
                "query": f"{query_seed} problems complaints issues",
                "threshold": None,
            },
            {
                "label": "feature_requests",
                "query": f"{query_seed} feature requests wishlist alternatives workaround",
                "threshold": 0.40,
            },
            {
                "label": "demand_intent",
                "query": f"{query_seed} intent demand unmet needs friction",
                "threshold": 0.30,
            },
        ]

        fallback_result = None
        for index, strategy in enumerate(strategies, start=1):
            if index > 1:
                print(
                    colored(
                        f"[Scout] Adaptive retrieval attempt {index}/{len(strategies)}: {strategy['label']} "
                        f"(threshold={strategy['threshold']:.2f})",
                        "yellow",
                    )
                )

            result = self.data_collector.collect(
                query=strategy["query"],
                topic=query_seed,
                limit=15,
                min_quality_threshold=strategy["threshold"],
            )
            fallback_result = result

            if result.get("data_quality") != "none":
                return result

        return fallback_result or {
            "topic": topic,
            "query": query_seed,
            "data_quality": "none",
            "error": "Adaptive retrieval failed",
        }
