"""
Unified real-data collection pipeline with modular source providers.
Includes source-quality scoring and filtering before data reaches agents.
"""

import re
from datetime import datetime
from collections import Counter
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

from src.utils.console import colored

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

    def collect(
        self,
        query: str,
        topic: str,
        limit: int = 15,
        min_quality_threshold: Optional[float] = None,
        source_query_overrides: Optional[Dict[str, List[str]]] = None,
        mode_hint: Optional[str] = None,
    ) -> Dict[str, Any]:
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
        source_diagnostics: Dict[str, Dict[str, Any]] = {}

        per_source_limit = max(1, limit // len(self.providers))

        for provider in self.providers:
            query_variants = self._resolve_query_variants(
                query=query,
                topic=topic,
                source_type=provider.source_type,
                source_query_overrides=source_query_overrides,
            )

            records, attempt_logs = self._collect_provider_records(
                provider=provider,
                topic=topic,
                query_variants=query_variants,
                limit=per_source_limit,
            )
            attempted_queries = [entry.get("query", "") for entry in attempt_logs]
            last_error = None
            for attempt in reversed(attempt_logs):
                if attempt.get("status") == "error" and attempt.get("error"):
                    last_error = attempt["error"]
                    break

            status = "ok" if records else "failed"
            source_diagnostics[provider.source_type] = {
                "provider": provider.name,
                "status": status,
                "raw_records": len(records),
                "results": len(records),
                "attempted_queries": attempted_queries,
                "query_attempts": attempt_logs,
                "error": last_error,
                "accepted_records": 0,
                "dropped_low_quality": 0,
                "avg_quality_score": 0.0,
                "quality_rejection_reasons": {},
                "quality_acceptance_signals": {},
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
        quality_filtered, quality_summary = self._apply_quality_filters(
            deduped,
            topic=topic,
            min_quality_threshold=min_quality_threshold,
            mode_hint=mode_hint,
        )

        by_source_quality = quality_summary.get("by_source", {})
        for source_type, stats in by_source_quality.items():
            diag = source_diagnostics.get(source_type)
            if not diag:
                continue
            diag["accepted_records"] = stats["accepted_records"]
            diag["dropped_low_quality"] = stats["dropped_low_quality"]
            diag["avg_quality_score"] = stats["avg_quality_score"]
            diag["quality_rejection_reasons"] = stats.get("dropped_reason_counts", {})
            diag["quality_acceptance_signals"] = stats.get("accepted_signal_counts", {})
            diag["quality_threshold"] = quality_summary["threshold"]
            if diag["accepted_records"] == 0 and diag["raw_records"] > 0:
                diag["status"] = "filtered"

        if not quality_filtered:
            return self._no_data_response(
                topic=topic,
                query=query,
                reason=(
                    "All collected records were filtered as low-quality evidence "
                    f"(threshold={quality_summary['threshold']:.2f})"
                ),
                diagnostics=source_diagnostics,
                quality_summary=quality_summary,
            )

        if (mode_hint or "").upper() == "B2C_PLG":
            b2c_evidence = self._summarize_b2c_user_evidence(quality_filtered)
            quality_summary["b2c_user_evidence"] = b2c_evidence
            if not b2c_evidence["passes"]:
                return self._no_data_response(
                    topic=topic,
                    query=query,
                    reason=(
                        "Insufficient first-person/user-generated evidence for B2C research mode "
                        "(need community/review sources or multiple first-person signals)"
                    ),
                    diagnostics=source_diagnostics,
                    quality_summary=quality_summary,
                )

        source_breakdown = self._compute_source_breakdown(quality_filtered)
        confidence = self._compute_confidence(
            accepted_results=quality_filtered,
            source_breakdown=source_breakdown,
            per_source_limit=per_source_limit,
        )

        min_records_for_single_source = 2 if (mode_hint or "").upper() == "B2C_PLG" else 3
        strong_single_source_evidence = (
            quality_summary.get("accepted_count", 0) >= min_records_for_single_source
            and quality_summary.get("avg_quality_score_accepted", 0.0) >= quality_summary["threshold"]
        )
        if (mode_hint or "").upper() == "B2C_PLG":
            strong_single_source_evidence = strong_single_source_evidence and bool(
                quality_summary.get("b2c_user_evidence", {}).get("passes")
            )
        quality_summary["strong_single_source_evidence"] = strong_single_source_evidence

        quality = "real" if (confidence >= 0.5 or strong_single_source_evidence) else "mixed"
        if self.settings.require_real_data and quality != "real":
            return self._no_data_response(
                topic=topic,
                query=query,
                reason="Insufficient high-confidence primary-source coverage",
                diagnostics=source_diagnostics,
                quality_summary=quality_summary,
            )

        return {
            "topic": topic,
            "query": query,
            "collected_at": datetime.now().isoformat(),
            "results": quality_filtered,
            "source_breakdown": source_breakdown,
            "source_diagnostics": source_diagnostics,
            "quality_summary": quality_summary,
            "confidence": confidence,
            "data_quality": quality,
            "total_results": len(quality_filtered),
        }

    def format_for_prompt(self, collection_result: Dict[str, Any]) -> str:
        """Format collection output for downstream LLM agents."""
        quality = collection_result.get("data_quality", "none")
        diagnostics = collection_result.get("source_diagnostics", {})
        quality_summary = collection_result.get("quality_summary", {})

        if quality == "none":
            lines = [
                "[DATA COLLECTION FAILED]",
                f"Topic: {collection_result.get('topic', 'unknown')}",
                f"Error: {collection_result.get('error', 'Unknown')}",
            ]
            if quality_summary:
                lines.append(
                    "Quality Summary: "
                    f"accepted={quality_summary.get('accepted_count', 0)} "
                    f"dropped={quality_summary.get('dropped_count', 0)} "
                    f"threshold={quality_summary.get('threshold', 0.0):.2f}"
                )
                b2c_signals = quality_summary.get("b2c_user_evidence")
                if b2c_signals:
                    lines.append(
                        "B2C User Evidence: "
                        f"discussion={b2c_signals.get('discussion_sources', 0)} "
                        f"review={b2c_signals.get('review_sources', 0)} "
                        f"first_person={b2c_signals.get('first_person_signals', 0)} "
                        f"passes={b2c_signals.get('passes', False)}"
                    )
            lines.append("Diagnostics:")
            for source_type, diag in diagnostics.items():
                lines.append(
                    f"- {diag.get('provider', source_type)} [{source_type}] status={diag.get('status')} "
                    f"raw={diag.get('raw_records', 0)} accepted={diag.get('accepted_records', 0)} "
                    f"dropped={diag.get('dropped_low_quality', 0)} attempts={len(diag.get('attempted_queries', []))}"
                )
                dropped_reasons = diag.get("quality_rejection_reasons") or {}
                if dropped_reasons:
                    lines.append(
                        "  dropped_reasons: "
                        + ", ".join(f"{reason}={count}" for reason, count in dropped_reasons.items())
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
            (
                f"Quality Filter: accepted={quality_summary.get('accepted_count', 0)} "
                f"dropped={quality_summary.get('dropped_count', 0)} "
                f"threshold={quality_summary.get('threshold', 0.0):.2f} "
                f"strong_single_source={quality_summary.get('strong_single_source_evidence', False)}"
            ),
            "Diagnostics:",
        ]
        b2c_signals = quality_summary.get("b2c_user_evidence")
        if b2c_signals:
            output.append(
                "B2C User Evidence: "
                f"discussion={b2c_signals.get('discussion_sources', 0)} "
                f"review={b2c_signals.get('review_sources', 0)} "
                f"first_person={b2c_signals.get('first_person_signals', 0)} "
                f"passes={b2c_signals.get('passes', False)}"
            )

        for source_type, diag in diagnostics.items():
            output.append(
                f"- {diag.get('provider', source_type)} [{source_type}] status={diag.get('status')} "
                f"raw={diag.get('raw_records', 0)} accepted={diag.get('accepted_records', 0)} "
                f"dropped={diag.get('dropped_low_quality', 0)} attempts={len(diag.get('attempted_queries', []))}"
            )
            dropped_reasons = diag.get("quality_rejection_reasons") or {}
            if dropped_reasons:
                output.append(
                    "  dropped_reasons: "
                    + ", ".join(f"{reason}={count}" for reason, count in dropped_reasons.items())
                )
            if diag.get("error"):
                output.append(f"  error: {diag.get('error')}")
        output.append("")

        for idx, result in enumerate(results, start=1):
            output.append(f"{idx}. [{result.get('source_type', 'unknown').upper()}] {result.get('title', '')}")
            output.append(f"   Community: {result.get('subreddit', 'unknown')}")
            output.append(f"   Engagement: {result.get('score', 'N/A')}")
            output.append(f"   Quality Score: {result.get('quality_score', 0.0):.2f}")
            output.append(f"   Quality Notes: {', '.join(result.get('quality_notes', [])) or 'none'}")
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
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        collected: List[Dict[str, Any]] = []
        attempt_logs: List[Dict[str, Any]] = []

        for candidate_query in query_variants:
            try:
                records = provider.collect(query=candidate_query, topic=topic, limit=limit)
            except Exception as exc:
                attempt_logs.append(
                    {
                        "query": candidate_query,
                        "status": "error",
                        "result_count": 0,
                        "error": str(exc),
                    }
                )
                continue

            attempt_logs.append(
                {
                    "query": candidate_query,
                    "status": "ok" if records else "empty",
                    "result_count": len(records),
                }
            )
            if records:
                collected.extend(records)
                if len(collected) >= limit:
                    break

        return collected[:limit], attempt_logs

    def _resolve_query_variants(
        self,
        query: str,
        topic: str,
        source_type: str,
        source_query_overrides: Optional[Dict[str, List[str]]] = None,
    ) -> List[str]:
        overrides = source_query_overrides or {}
        override_queries = overrides.get(source_type, [])
        if override_queries:
            return self._normalize_query_list([query] + override_queries)

        if source_type in {"hackernews", "web"}:
            return self._build_query_variants(query=query, topic=topic, source_type=source_type)
        return [query]

    def _build_query_variants(self, query: str, topic: str, source_type: str) -> List[str]:
        if source_type == "hackernews":
            candidates = [
                query,
                topic,
                f"{topic} show hn",
                f"{topic} launch",
                f"{topic} hiring",
                f"{topic} automation",
            ]
        else:
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

    def _normalize_query_list(self, candidates: List[str]) -> List[str]:
        variants: List[str] = []
        seen: Set[str] = set()
        for candidate in candidates:
            candidate = (candidate or "").strip()
            if not candidate:
                continue
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

    def _apply_quality_filters(
        self,
        results: List[Dict[str, Any]],
        topic: str,
        min_quality_threshold: Optional[float] = None,
        mode_hint: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        configured_threshold = self.settings.min_record_quality_score if min_quality_threshold is None else min_quality_threshold
        threshold = max(0.0, min(1.0, configured_threshold))
        topic_terms = self._topic_terms(topic)

        accepted: List[Dict[str, Any]] = []
        dropped_count = 0
        total_quality = 0.0
        by_source: Dict[str, Dict[str, Any]] = {}

        for record in results:
            source_type = str(record.get("source_type", "unknown"))
            stats = by_source.setdefault(
                source_type,
                {
                    "raw_records": 0.0,
                    "accepted_records": 0.0,
                    "dropped_low_quality": 0.0,
                    "quality_sum": 0.0,
                    "dropped_reason_counts": Counter(),
                    "accepted_signal_counts": Counter(),
                },
            )

            score, notes = self._score_record(record, topic_terms, mode_hint=mode_hint)
            stats["raw_records"] += 1
            stats["quality_sum"] += score
            total_quality += score

            enriched = dict(record)
            enriched["quality_score"] = round(score, 3)
            enriched["quality_notes"] = notes

            if score >= threshold:
                accepted.append(enriched)
                stats["accepted_records"] += 1
                for note in notes:
                    stats["accepted_signal_counts"][note] += 1
            else:
                dropped_count += 1
                stats["dropped_low_quality"] += 1
                for note in notes:
                    stats["dropped_reason_counts"][note] += 1

        accepted.sort(key=lambda item: item.get("quality_score", 0.0), reverse=True)

        by_source_summary: Dict[str, Dict[str, Any]] = {}
        for source_type, stats in by_source.items():
            raw = int(stats["raw_records"])
            avg_quality = (stats["quality_sum"] / raw) if raw else 0.0
            by_source_summary[source_type] = {
                "raw_records": raw,
                "accepted_records": int(stats["accepted_records"]),
                "dropped_low_quality": int(stats["dropped_low_quality"]),
                "avg_quality_score": round(avg_quality, 3),
                "dropped_reason_counts": self._top_reason_counts(stats["dropped_reason_counts"]),
                "accepted_signal_counts": self._top_reason_counts(stats["accepted_signal_counts"]),
            }

        avg_all = (total_quality / len(results)) if results else 0.0
        avg_accepted = (
            sum(float(item.get("quality_score", 0.0)) for item in accepted) / len(accepted)
            if accepted
            else 0.0
        )

        summary = {
            "threshold": threshold,
            "accepted_count": len(accepted),
            "dropped_count": dropped_count,
            "avg_quality_score_all": round(avg_all, 3),
            "avg_quality_score_accepted": round(avg_accepted, 3),
            "by_source": by_source_summary,
        }
        return accepted, summary

    def _top_reason_counts(self, reason_counter: Counter, limit: int = 5) -> Dict[str, int]:
        if not reason_counter:
            return {}
        ordered = sorted(reason_counter.items(), key=lambda item: (-item[1], item[0]))
        return {reason: int(count) for reason, count in ordered[:limit]}

    def _score_record(
        self,
        record: Dict[str, Any],
        topic_terms: Set[str],
        mode_hint: Optional[str] = None,
    ) -> Tuple[float, List[str]]:
        source_type = str(record.get("source_type", "unknown")).lower()
        title = str(record.get("title", "") or "")
        text = str(record.get("text", "") or "")
        url = str(record.get("url", "") or "")
        domain = self._domain_from_url(url)
        parsed_url = urlparse(url or "")
        path = (parsed_url.path or "").lower()
        mode = (mode_hint or "").upper()

        notes: List[str] = []
        score = {"reddit": 0.82, "hackernews": 0.76, "web": 0.42}.get(source_type, 0.4)

        full_text = f"{title} {text} {url}".lower()
        text_tokens = set(re.findall(r"[a-z0-9]+", full_text))

        topic_overlap = len(topic_terms & text_tokens) / max(1, len(topic_terms))
        score += min(0.22, 0.22 * topic_overlap)
        if topic_overlap >= 0.35:
            notes.append("strong_topic_overlap")
        elif topic_overlap < 0.15:
            score -= 0.08
            notes.append("low_topic_overlap")

        pain_keywords = [
            "complaint",
            "problem",
            "frustrat",
            "annoy",
            "manual",
            "time-consuming",
            "waste of time",
            "error",
            "penalt",
            "compliance",
            "overwhelmed",
            "struggle",
            "bottleneck",
        ]
        pain_hits = sum(1 for keyword in pain_keywords if keyword in full_text)
        score += min(0.2, pain_hits * 0.04)
        if pain_hits >= 2:
            notes.append("pain_signals")
        elif pain_hits == 0:
            score -= 0.05
            notes.append("no_pain_signals")

        community_domains = {
            "reddit.com",
            "news.ycombinator.com",
            "stackoverflow.com",
            "stackexchange.com",
            "indiehackers.com",
            "quora.com",
        }
        is_forum_domain = (
            domain in community_domains
            or domain.startswith("community.")
            or domain.startswith("forums.")
            or ".forum" in domain
            or "forum" in domain
        )
        if domain in community_domains:
            score += 0.12
            notes.append("community_source")
        if source_type == "web" and is_forum_domain:
            score += 0.12
            notes.append("user_discussion_source")

        review_domains = {
            "apps.apple.com",
            "play.google.com",
            "trustpilot.com",
            "g2.com",
            "capterra.com",
        }
        if source_type == "web" and domain in review_domains:
            score += 0.1
            notes.append("review_source")

        if domain.endswith(".gov") or domain.endswith(".edu") or ".gov." in domain or ".edu." in domain:
            score += 0.1
            notes.append("institutional_source")

        low_signal_domains = {
            "dictionary.com",
            "merriam-webster.com",
            "cambridge.org",
            "vocabulary.com",
            "thesaurus.com",
            "wiktionary.org",
        }
        if domain in low_signal_domains:
            score -= 0.25
            notes.append("reference_dictionary_source")

        listicle_indicators = [
            " best ",
            " top ",
            " alternatives",
            " comparison",
            " versus ",
            " vs ",
            " list of ",
            " software list",
        ]
        if source_type == "web" and any(indicator in f" {full_text} " for indicator in listicle_indicators):
            score -= 0.12
            notes.append("listicle_roundup")

        promo_indicators = [
            "pricing",
            "book a demo",
            "start free",
            "sign up",
            "request demo",
            "features",
            "our platform",
            "solutions",
            "contact us",
            "sales team",
            "/product",
            "/pricing",
            "/solutions",
            "/services",
        ]
        promo_hits = sum(1 for indicator in promo_indicators if indicator in full_text)
        if promo_hits >= 2:
            score -= min(0.32, promo_hits * 0.06)
            notes.append("promotional_content")
        if source_type == "web" and "/blog" in path and pain_hits == 0:
            score -= 0.07
            notes.append("vendor_blog_content")

        first_person_tokens = [" i ", " i'm ", " i've ", " my ", " me ", " we ", " our ", " us "]
        person_text = f" {title.lower()} {text.lower()} "
        if any(token in person_text for token in first_person_tokens):
            score += 0.08
            notes.append("first_person_signal")
        elif source_type == "web":
            score -= 0.04
            notes.append("no_first_person_signal")

        if mode == "B2C_PLG" and source_type == "web" and not (is_forum_domain or domain in review_domains):
            score -= 0.08
            notes.append("non_user_generated_web_source")

        engagement = self._to_int(record.get("score"))
        if engagement is not None:
            if engagement >= 100:
                score += 0.1
                notes.append("high_engagement")
            elif engagement >= 20:
                score += 0.06
                notes.append("moderate_engagement")
            elif engagement >= 5:
                score += 0.03
        elif source_type == "web":
            score -= 0.03

        if len(title.strip()) < 20:
            score -= 0.05
            notes.append("short_title")
        if len(text.strip()) < 60:
            score -= 0.06
            notes.append("thin_content")
        if not url:
            score -= 0.1
            notes.append("missing_url")

        score = max(0.0, min(1.0, score))
        if not notes:
            notes.append("neutral_signal")
        return score, notes[:8]

    def _summarize_b2c_user_evidence(self, accepted_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        discussion_sources = 0
        first_person_signals = 0
        review_sources = 0
        for result in accepted_results:
            notes = {str(note) for note in result.get("quality_notes", [])}
            if "user_discussion_source" in notes or "community_source" in notes:
                discussion_sources += 1
            if "first_person_signal" in notes:
                first_person_signals += 1
            if "review_source" in notes:
                review_sources += 1
        passes = discussion_sources >= 1 or review_sources >= 1 or first_person_signals >= 2
        return {
            "discussion_sources": discussion_sources,
            "review_sources": review_sources,
            "first_person_signals": first_person_signals,
            "passes": passes,
        }

    def _topic_terms(self, topic: str) -> Set[str]:
        stop_words = {
            "the",
            "and",
            "for",
            "with",
            "from",
            "that",
            "this",
            "into",
            "your",
            "their",
            "firms",
            "firm",
            "small",
        }
        terms = set(re.findall(r"[a-z0-9]+", topic.lower()))
        return {term for term in terms if len(term) > 2 and term not in stop_words}

    def _domain_from_url(self, url: str) -> str:
        if not url:
            return ""
        parsed = urlparse(url)
        return parsed.netloc.lower().replace("www.", "")

    def _to_int(self, value: Any) -> Optional[int]:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _compute_source_breakdown(self, accepted_results: List[Dict[str, Any]]) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for record in accepted_results:
            source_type = str(record.get("source_type", "unknown"))
            counts[source_type] = counts.get(source_type, 0) + 1
        return counts

    def _compute_confidence(
        self,
        accepted_results: List[Dict[str, Any]],
        source_breakdown: Dict[str, int],
        per_source_limit: int,
    ) -> float:
        weighted_real_score = 0.0
        total_weight = 0.0
        source_weights = {provider.source_type: provider.reliability_weight for provider in self.providers}

        for source_type, count in source_breakdown.items():
            weight = source_weights.get(source_type, 0.5)
            weighted_real_score += weight * count

        for provider in self.providers:
            total_weight += provider.reliability_weight * per_source_limit

        coverage_confidence = min(1.0, weighted_real_score / total_weight) if total_weight else 0.0
        avg_quality = (
            sum(float(item.get("quality_score", 0.0)) for item in accepted_results) / len(accepted_results)
            if accepted_results
            else 0.0
        )
        return max(0.0, min(1.0, (0.5 * coverage_confidence) + (0.5 * avg_quality)))

    def _no_data_response(
        self,
        topic: str,
        query: str,
        reason: Optional[str] = None,
        diagnostics: Optional[Dict[str, Dict[str, Any]]] = None,
        quality_summary: Optional[Dict[str, Any]] = None,
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
            "quality_summary": quality_summary or {},
            "confidence": 0.0,
            "data_quality": "none",
            "error": message,
        }

