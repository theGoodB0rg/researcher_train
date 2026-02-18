"""
Unified real-data collection pipeline with modular source providers.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from termcolor import colored

from src.config import get_settings
from src.sources import HackerNewsSource, RedditSource, SourceProvider, WebSource


class DataCollector:
    def __init__(self, providers: Optional[List[SourceProvider]] = None):
        self.settings = get_settings()
        self.providers: List[SourceProvider] = providers or self._default_providers()

    def _default_providers(self) -> List[SourceProvider]:
        providers: List[SourceProvider] = []
        if self.settings.enable_reddit_source:
            providers.append(RedditSource())
        else:
            print(colored("[DataCollector] Reddit source disabled via ENABLE_REDDIT_SOURCE=false", "yellow"))
        providers.append(HackerNewsSource())
        providers.append(WebSource())
        return providers

    def collect(self, query: str, topic: str, limit: int = 15) -> Dict[str, Any]:
        """
        Collect real data from all configured providers with source provenance and diagnostics.
        """
        if not self.providers:
            return self._no_data_response(
                topic=topic,
                query=query,
                reason="No data providers configured",
            )

        aggregated: List[Dict[str, Any]] = []
        source_breakdown: Dict[str, int] = {}
        source_diagnostics: Dict[str, Dict[str, Any]] = {}
        weighted_real_score = 0.0
        total_weight = 0.0

        per_source_limit = max(1, limit // len(self.providers))

        for provider in self.providers:
            query_variants = [query]
            if provider.source_type in {"hackernews", "web"}:
                query_variants = self._build_query_variants(query=query, topic=topic)

            records, last_error, attempted_queries = self._collect_provider_records(
                provider=provider,
                topic=topic,
                query_variants=query_variants,
                limit=per_source_limit,
            )

            status = "ok" if records else "failed"
            source_diagnostics[provider.source_type] = {
                "provider": provider.name,
                "status": status,
                "results": len(records),
                "attempted_queries": attempted_queries,
                "error": last_error,
            }

            if not records:
                print(
                    colored(
                        f"[DataCollector] {provider.name}: 0 results after {len(attempted_queries)} query attempts",
                        "yellow",
                    )
                )
                if last_error:
                    print(colored(f"[DataCollector] {provider.name} last error: {last_error}", "yellow"))
                continue

            aggregated.extend(records)
            source_breakdown[provider.source_type] = len(records)
            weighted_real_score += provider.reliability_weight * len(records)
            total_weight += provider.reliability_weight * per_source_limit
            print(
                colored(
                    f"[DataCollector] {provider.name}: {len(records)} results after {len(attempted_queries)} query attempts",
                    "green",
                )
            )

        if not aggregated:
            return self._no_data_response(
                topic=topic,
                query=query,
                diagnostics=source_diagnostics,
            )

        deduped = self._dedupe_results(aggregated)[:limit]
        confidence = min(1.0, weighted_real_score / total_weight) if total_weight else 0.0
        quality = "real" if confidence >= 0.5 else "mixed"

        if self.settings.require_real_data and quality == "mixed":
            return self._no_data_response(
                topic=topic,
                query=query,
                reason="Insufficient high-confidence primary-source coverage",
                diagnostics=source_diagnostics,
            )

        return {
            "topic": topic,
            "query": query,
            "collected_at": datetime.now().isoformat(),
            "results": deduped,
            "source_breakdown": source_breakdown,
            "source_diagnostics": source_diagnostics,
            "confidence": confidence,
            "data_quality": quality,
            "total_results": len(deduped),
        }

    def format_for_prompt(self, collection_result: Dict[str, Any]) -> str:
        """Format collection output for downstream LLM agents."""
        quality = collection_result.get("data_quality", "none")
        diagnostics = collection_result.get("source_diagnostics", {})

        if quality == "none":
            lines = [
                "[DATA COLLECTION FAILED]",
                f"Topic: {collection_result.get('topic', 'unknown')}",
                f"Error: {collection_result.get('error', 'Unknown')}",
                "Diagnostics:",
            ]
            for source_type, diag in diagnostics.items():
                lines.append(
                    f"- {diag.get('provider', source_type)} [{source_type}] status={diag.get('status')} "
                    f"results={diag.get('results')} attempts={len(diag.get('attempted_queries', []))}"
                )
                if diag.get("error"):
                    lines.append(f"  error: {diag.get('error')}")
            return "\n".join(lines)

        results = collection_result.get("results", [])
        sources = collection_result.get("source_breakdown", {})
        confidence = collection_result.get("confidence", 0.0)

        output = [
            "[REAL DATA COLLECTION]",
            f"Quality: {quality.upper()} | Confidence: {confidence:.1%}",
            f"Sources: {sources}",
            "Diagnostics:",
        ]

        for source_type, diag in diagnostics.items():
            output.append(
                f"- {diag.get('provider', source_type)} [{source_type}] status={diag.get('status')} "
                f"results={diag.get('results')} attempts={len(diag.get('attempted_queries', []))}"
            )
            if diag.get("error"):
                output.append(f"  error: {diag.get('error')}")
        output.append("")

        for idx, result in enumerate(results, start=1):
            output.append(f"{idx}. [{result.get('source_type', 'unknown').upper()}] {result.get('title', '')}")
            output.append(f"   Community: {result.get('subreddit', 'unknown')}")
            output.append(f"   Engagement: {result.get('score', 'N/A')}")
            output.append(f"   Collected At: {result.get('collected_at', 'N/A')}")
            output.append(f"   Content: {result.get('text', '')[:220]}...")
            output.append(f"   URL: {result.get('url', '')}")
            output.append("")

        return "\n".join(output)

    def _collect_provider_records(
        self,
        provider: SourceProvider,
        topic: str,
        query_variants: List[str],
        limit: int,
    ) -> Tuple[List[Dict[str, Any]], Optional[str], List[str]]:
        collected: List[Dict[str, Any]] = []
        last_error: Optional[str] = None
        attempted_queries: List[str] = []

        for candidate_query in query_variants:
            attempted_queries.append(candidate_query)
            try:
                records = provider.collect(query=candidate_query, topic=topic, limit=limit)
            except Exception as exc:
                last_error = str(exc)
                continue

            if records:
                collected.extend(records)
                if len(collected) >= limit:
                    break

        return collected[:limit], last_error, attempted_queries

    def _build_query_variants(self, query: str, topic: str) -> List[str]:
        candidates = [
            query,
            f"{topic} complaints",
            f"{topic} problems",
            f"{topic} workflow bottlenecks",
            f"{topic} manual process pain points",
            f"{topic} software alternatives",
        ]

        variants: List[str] = []
        seen: Set[str] = set()
        for candidate in candidates:
            normalized = " ".join(candidate.lower().split())
            if normalized in seen:
                continue
            seen.add(normalized)
            variants.append(candidate)
        return variants

    def _dedupe_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen_urls: Set[str] = set()
        deduped: List[Dict[str, Any]] = []
        for result in results:
            url = result.get("url", "").strip().lower()
            key = url or f"{result.get('title', '').strip().lower()}::{result.get('source_type', '')}"
            if key in seen_urls:
                continue
            seen_urls.add(key)
            deduped.append(result)
        return deduped

    def _no_data_response(
        self,
        topic: str,
        query: str,
        reason: Optional[str] = None,
        diagnostics: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        message = reason or "No real data available from configured sources"
        print(colored(f"[DataCollector] CRITICAL: {message} for topic '{topic}'", "red"))
        return {
            "topic": topic,
            "query": query,
            "collected_at": datetime.now().isoformat(),
            "results": [],
            "source_breakdown": {},
            "source_diagnostics": diagnostics or {},
            "confidence": 0.0,
            "data_quality": "none",
            "error": message,
        }
