from termcolor import colored
from src.core.agent import Agent
from src.utils.data_collector import DataCollector
from typing import List, Dict, Any
import re

class ScoutAgent(Agent):
    def __init__(self, name: str, role: str, system_prompt: str, color: str = "cyan"):
        super().__init__(name, role, system_prompt, color)
        self.data_collector = DataCollector()

    def process(self, input_data: str, context: List[Dict[str, str]] = None) -> str:
        # Extract scoped topic + research mode from orchestrator prompt.
        topic = self._extract_topic(input_data)
        research_mode = self._extract_research_mode(input_data)
        query_seed = self._build_query_seed(topic)
        
        # Collect data from real sources (Reddit, HackerNews, Web)
        print(f"[Scout] Collecting real data for: {topic}")
        print(colored(f"[Scout] Research mode: {research_mode}", "yellow"))
        if query_seed.lower() != topic.lower():
            print(colored(f"[Scout] Query seed (compacted): {query_seed}", "cyan"))
        collection_result = self._collect_with_adaptive_strategy(
            topic=topic,
            query_seed=query_seed,
            research_mode=research_mode,
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
                rejection_reasons = diag.get("quality_rejection_reasons") or {}
                if rejection_reasons:
                    top_reasons = ", ".join(f"{reason}={count}" for reason, count in rejection_reasons.items())
                    print(colored(f"    dropped_reasons={top_reasons}", "red"))
            
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

    def _extract_topic(self, input_data: str) -> str:
        marker = "Find complaints and issues related to:"
        if marker not in input_data:
            return input_data.strip()

        remainder = input_data.split(marker, 1)[1].strip()
        topic_line = remainder.splitlines()[0].strip()
        return topic_line

    def _extract_research_mode(self, input_data: str) -> str:
        match = re.search(r"Research mode\s*:\s*([A-Z0-9_]+)", input_data, flags=re.IGNORECASE)
        if match:
            return match.group(1).upper()
        return "B2B_DISCOVERY"

    def _build_query_seed(self, topic: str, max_terms: int = 7) -> str:
        structured = self._extract_structured_focus(topic)
        if structured:
            return self._compact_focus_terms(structured, max_terms=12)

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

    def _extract_structured_focus(self, topic: str) -> str:
        text = (topic or "").strip()
        if ":" not in text:
            return ""

        segments = [segment.strip() for segment in re.split(r"[;\|]", text) if segment.strip()]
        parsed: Dict[str, str] = {}
        for segment in segments:
            match = re.match(r"^\s*([a-zA-Z_ ]+)\s*:\s*(.+)$", segment)
            if not match:
                continue
            key = match.group(1).strip().lower().replace(" ", "_")
            value = match.group(2).strip()
            parsed[key] = value

        workflow = parsed.get("workflow", "")
        pain = parsed.get("pain", "") or parsed.get("problem", "")
        vertical = parsed.get("vertical", "")
        buyer = parsed.get("buyer", "")
        combined = " ".join(part for part in [vertical, workflow, pain, buyer] if part).strip()
        return combined

    def _compact_focus_terms(self, text: str, max_terms: int = 12) -> str:
        tokens = re.findall(r"[a-z0-9]+", (text or "").lower())
        if not tokens:
            return text
        stop_words = {
            "the",
            "and",
            "for",
            "with",
            "from",
            "into",
            "via",
            "buyer",
            "vertical",
            "workflow",
            "pain",
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

    def _collect_with_adaptive_strategy(self, topic: str, query_seed: str, research_mode: str) -> Dict[str, object]:
        strategies = self._build_strategy_plan(query_seed=query_seed, research_mode=research_mode)

        fallback_result = None
        for index, strategy in enumerate(strategies, start=1):
            if index > 1:
                threshold = strategy.get("threshold")
                threshold_text = "default" if threshold is None else f"{threshold:.2f}"
                print(
                    colored(
                        f"[Scout] Adaptive retrieval attempt {index}/{len(strategies)}: {strategy['label']} "
                        f"(threshold={threshold_text})",
                        "yellow",
                    )
                )

            result = self.data_collector.collect(
                query=strategy["query"],
                topic=query_seed,
                limit=15,
                min_quality_threshold=strategy["threshold"],
                source_query_overrides=strategy.get("source_query_overrides"),
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

    def _build_strategy_plan(self, query_seed: str, research_mode: str) -> List[Dict[str, Any]]:
        mode = (research_mode or "").upper()
        if mode == "B2C_PLG":
            return [
                {
                    "label": "user_frustrations",
                    "query": f"{query_seed} problems complaints issues",
                    "threshold": None,
                    "source_query_overrides": {
                        "hackernews": [
                            f"{query_seed} ask hn alternatives",
                            f"{query_seed} switched from",
                            f"{query_seed} frustrations",
                        ],
                        "web": [
                            f"{query_seed} user complaints",
                            f"{query_seed} alternatives comparison",
                            f"{query_seed} churn reasons",
                            f"{query_seed} annoying workflow",
                        ],
                    },
                },
                {
                    "label": "feature_requests",
                    "query": f"{query_seed} feature requests wishlist alternatives workaround",
                    "threshold": 0.38,
                    "source_query_overrides": {
                        "hackernews": [f"{query_seed} ask hn feature request"],
                        "web": [
                            f"{query_seed} feature request",
                            f"{query_seed} missing features",
                            f"{query_seed} workaround",
                        ],
                    },
                },
                {
                    "label": "switching_triggers",
                    "query": f"{query_seed} switched from alternatives why",
                    "threshold": 0.32,
                    "source_query_overrides": {
                        "hackernews": [f"{query_seed} ask hn switched"],
                        "web": [
                            f"{query_seed} switched from",
                            f"{query_seed} alternative to",
                            f"{query_seed} better than",
                        ],
                    },
                },
            ]

        # Default B2B strategy family.
        return [
            {
                "label": "pain_complaints",
                "query": f"{query_seed} problems complaints issues",
                "threshold": None,
                "source_query_overrides": {
                    "hackernews": [
                        f"{query_seed} ask hn ops",
                        f"{query_seed} show hn automation",
                        f"{query_seed} manual workflow",
                    ],
                    "web": [
                        f"{query_seed} workflow bottlenecks",
                        f"{query_seed} manual process pain points",
                        f"{query_seed} operations complaints",
                    ],
                },
            },
            {
                "label": "ops_workarounds",
                "query": f"{query_seed} manual workflow workaround bottleneck",
                "threshold": 0.45,
                "source_query_overrides": {
                    "hackernews": [
                        f"{query_seed} ask hn workaround",
                        f"{query_seed} spreadsheet hell",
                    ],
                    "web": [
                        f"{query_seed} manual workaround",
                        f"{query_seed} process delays",
                        f"{query_seed} error-prone workflow",
                    ],
                },
            },
            {
                "label": "cost_risk_signals",
                "query": f"{query_seed} compliance risk delays penalties",
                "threshold": 0.40,
                "source_query_overrides": {
                    "hackernews": [f"{query_seed} compliance automation"],
                    "web": [
                        f"{query_seed} compliance risk",
                        f"{query_seed} audit errors",
                        f"{query_seed} cost of manual process",
                    ],
                },
            },
        ]
