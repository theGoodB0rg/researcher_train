"""
Unified real-data collection pipeline with modular source providers.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from termcolor import colored

from src.config import get_settings
from src.sources import HackerNewsSource, RedditSource, SourceProvider, WebSource


class DataCollector:
    def __init__(self, providers: Optional[List[SourceProvider]] = None):
        self.settings = get_settings()
        self.providers: List[SourceProvider] = providers or [
            RedditSource(),
            HackerNewsSource(),
            WebSource(),
        ]

    def collect(self, query: str, topic: str, limit: int = 15) -> Dict[str, Any]:
        """
        Collect real data from all configured providers with source provenance.
        """
        aggregated: List[Dict[str, Any]] = []
        source_breakdown: Dict[str, int] = {}
        weighted_real_score = 0.0
        total_weight = 0.0

        per_source_limit = max(1, limit // max(1, len(self.providers)))

        for provider in self.providers:
            try:
                records = provider.collect(query=query, topic=topic, limit=per_source_limit)
            except Exception as exc:
                print(colored(f"[DataCollector] {provider.name} collection failed: {exc}", "red"))
                records = []

            if not records:
                continue

            aggregated.extend(records)
            source_breakdown[provider.source_type] = len(records)
            weighted_real_score += provider.reliability_weight * len(records)
            total_weight += provider.reliability_weight * per_source_limit
            print(colored(f"[DataCollector] {provider.name}: {len(records)} results", "green"))

        if not aggregated:
            return self._no_data_response(topic=topic, query=query)

        deduped = self._dedupe_results(aggregated)[:limit]
        confidence = min(1.0, weighted_real_score / total_weight) if total_weight else 0.0
        quality = "real" if confidence >= 0.5 else "mixed"

        if self.settings.require_real_data and quality == "mixed":
            return self._no_data_response(
                topic=topic,
                query=query,
                reason="Insufficient high-confidence primary-source coverage",
            )

        return {
            "topic": topic,
            "query": query,
            "collected_at": datetime.now().isoformat(),
            "results": deduped,
            "source_breakdown": source_breakdown,
            "confidence": confidence,
            "data_quality": quality,
            "total_results": len(deduped),
        }

    def format_for_prompt(self, collection_result: Dict[str, Any]) -> str:
        """Format collection output for downstream LLM agents."""
        quality = collection_result.get("data_quality", "none")
        if quality == "none":
            return (
                "[DATA COLLECTION FAILED]\n"
                f"Topic: {collection_result.get('topic', 'unknown')}\n"
                f"Error: {collection_result.get('error', 'Unknown')}"
            )

        results = collection_result.get("results", [])
        sources = collection_result.get("source_breakdown", {})
        confidence = collection_result.get("confidence", 0.0)

        output = [
            "[REAL DATA COLLECTION]",
            f"Quality: {quality.upper()} | Confidence: {confidence:.1%}",
            f"Sources: {sources}",
            "",
        ]

        for idx, result in enumerate(results, start=1):
            output.append(f"{idx}. [{result.get('source_type', 'unknown').upper()}] {result.get('title', '')}")
            output.append(f"   Community: {result.get('subreddit', 'unknown')}")
            output.append(f"   Engagement: {result.get('score', 'N/A')}")
            output.append(f"   Collected At: {result.get('collected_at', 'N/A')}")
            output.append(f"   Content: {result.get('text', '')[:220]}...")
            output.append(f"   URL: {result.get('url', '')}")
            output.append("")

        return "\n".join(output)

    def _dedupe_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen_urls = set()
        deduped: List[Dict[str, Any]] = []
        for result in results:
            url = result.get("url", "").strip().lower()
            key = url or f"{result.get('title', '').strip().lower()}::{result.get('source_type', '')}"
            if key in seen_urls:
                continue
            seen_urls.add(key)
            deduped.append(result)
        return deduped

    def _no_data_response(self, topic: str, query: str, reason: Optional[str] = None) -> Dict[str, Any]:
        message = reason or "No real data available from configured sources"
        print(colored(f"[DataCollector] CRITICAL: {message} for topic '{topic}'", "red"))
        return {
            "topic": topic,
            "query": query,
            "collected_at": datetime.now().isoformat(),
            "results": [],
            "source_breakdown": {},
            "confidence": 0.0,
            "data_quality": "none",
            "error": message,
        }
