import html
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List

import requests

from src.config import get_settings


class HackerNewsSource:
    name = "HackerNews"
    source_type = "hackernews"
    reliability_weight = 0.9
    hn_api_base = "https://hn.algolia.com/api/v1/search"

    def collect(self, query: str, topic: str, limit: int) -> List[Dict[str, Any]]:
        settings = get_settings()
        lookback_days = max(30, settings.hn_lookback_days)
        created_after = int((datetime.now() - timedelta(days=lookback_days)).timestamp())
        per_type_limit = max(1, limit)

        story_hits = self._search_hits(
            query=query,
            tags="story",
            hits_per_page=per_type_limit,
            created_after=created_after,
            timeout_sec=settings.source_timeout_sec,
        )
        comment_hits = []
        if settings.hn_include_comments:
            comment_hits = self._search_hits(
                query=query,
                tags="comment",
                hits_per_page=per_type_limit,
                created_after=created_after,
                timeout_sec=settings.source_timeout_sec,
            )

        findings: List[Dict[str, Any]] = []
        seen_keys = set()
        for hit in (story_hits + comment_hits):
            normalized = self._normalize_hit(hit)
            key = normalized["url"].lower().strip()
            if key in seen_keys:
                continue
            seen_keys.add(key)
            findings.append(normalized)
            if len(findings) >= limit:
                break
        return findings

    def _search_hits(
        self,
        query: str,
        tags: str,
        hits_per_page: int,
        created_after: int,
        timeout_sec: int,
    ) -> List[Dict[str, Any]]:
        params = {
            "query": query,
            "tags": tags,
            "hitsPerPage": hits_per_page,
            "numericFilters": f"created_at_i>{created_after}",
        }

        response = requests.get(self.hn_api_base, params=params, timeout=timeout_sec)
        if response.status_code != 200:
            body_preview = (response.text or "")[:240].replace("\n", " ").strip()
            raise RuntimeError(
                f"HackerNews API error status={response.status_code} tags={tags} "
                f"query='{query[:80]}' body='{body_preview}'"
            )

        payload = response.json()
        return payload.get("hits", [])[:hits_per_page]

    def _normalize_hit(self, hit: Dict[str, Any]) -> Dict[str, Any]:
        object_id = str(hit.get("objectID", "") or "").strip()
        story_title = str(hit.get("story_title", "") or "").strip()
        title = str(hit.get("title", "") or "").strip() or story_title
        if not title:
            title = "HackerNews discussion"

        text_candidates = [
            str(hit.get("story_text", "") or ""),
            str(hit.get("comment_text", "") or ""),
            str(hit.get("text", "") or ""),
            str(hit.get("body", "") or ""),
        ]
        text_raw = next((value for value in text_candidates if value.strip()), "")
        text_clean = self._clean_text(text_raw)
        if not text_clean:
            text_clean = f"See discussion: https://news.ycombinator.com/item?id={object_id}"

        resolved_url = str(hit.get("url", "") or "").strip()
        if not resolved_url:
            story_url = str(hit.get("story_url", "") or "").strip()
            resolved_url = story_url or f"https://news.ycombinator.com/item?id={object_id}"

        score_raw = hit.get("points", hit.get("num_comments", 0))
        try:
            score_value = int(score_raw)
        except (TypeError, ValueError):
            score_value = 0

        return {
            "title": title,
            "text": text_clean[:300],
            "url": resolved_url,
            "score": score_value,
            "subreddit": "HackerNews",
            "source_type": self.source_type,
            "source_name": self.name,
            "collected_at": datetime.now().isoformat(),
        }

    def _clean_text(self, value: str) -> str:
        if not value:
            return ""
        unescaped = html.unescape(value)
        no_tags = re.sub(r"<[^>]+>", " ", unescaped)
        return re.sub(r"\s+", " ", no_tags).strip()
