"""
CompetitorResearcher Agent: discovers likely competitors using live web search evidence.
"""

import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

from src.utils.console import colored

from src.core.agent import Agent
from src.utils.search_client import SearchClient


class CompetitorResearcherAgent(Agent):
    def __init__(self, name: str, role: str, system_prompt: str, color: str = "magenta"):
        super().__init__(name, role, system_prompt, color)
        self.search_client = SearchClient()
        self.excluded_domains = {
            "reddit.com",
            "news.ycombinator.com",
            "medium.com",
            "linkedin.com",
            "youtube.com",
            "x.com",
            "twitter.com",
            "github.com",
            "wikipedia.org",
            "sourceforge.net",
            "metapress.com",
            "topbusinesssoftware.com",
            "saasbrowser.com",
            "blogspot.com",
        }
        self.listicle_markers = {
            "best",
            "top",
            "alternatives",
            "comparison",
            "compare",
            "vs",
            "list",
        }

    def process(self, input_data: str, context: Optional[List[Dict[str, str]]] = None) -> str:
        idea_name, idea_description = self._extract_idea(context)
        if not idea_name:
            return self.speak_and_return("Unable to extract idea from context. Please ensure Strategist provided a clear pitch.")

        print(colored(f"[CompetitorResearcher] Running competitor discovery for: {idea_name}", "magenta"))
        competitors = self._search_competitors(idea_name, idea_description)
        findings = self._build_findings(idea_name=idea_name, competitors=competitors)
        formatted_analysis = self._format_findings(findings)

        enriched_input = f"{input_data}\n\n[COMPETITOR RESEARCH]\n{formatted_analysis}\n[END RESEARCH]"
        return super().process(enriched_input, context)

    def _extract_idea(self, context: Optional[List[Dict[str, str]]]) -> Tuple[Optional[str], Optional[str]]:
        if not context:
            return None, None

        for msg in reversed(context):
            if "SaaS Strategist" not in msg.get("role", ""):
                continue
            text = msg.get("content", "")
            pitch = self._extract_pitch(text)
            if pitch:
                return pitch, text[:1000]
        return None, None

    def _search_competitors(self, idea_name: str, description: Optional[str]) -> List[Dict[str, object]]:
        search_seed = self._build_search_seed(idea_name, description)
        seed_keywords = set(re.findall(r"[a-z0-9]+", search_seed.lower()))
        queries = [
            f"{search_seed} app",
            f"{search_seed} software platform",
            f"{search_seed} competitor",
            f"{search_seed} alternative",
        ]

        collected: Dict[str, Dict[str, object]] = {}
        for query in queries:
            results = self.search_client.search(query, limit=8)
            for result in results:
                parsed = self._candidate_from_result(result, seed_keywords=seed_keywords)
                if not parsed:
                    continue
                domain = parsed["domain"]
                if domain in collected:
                    collected[domain]["evidence_count"] = int(collected[domain]["evidence_count"]) + 1
                else:
                    collected[domain] = parsed

        competitors = sorted(
            collected.values(),
            key=lambda item: (int(item.get("evidence_count", 0)), int(item.get("keyword_overlap", 0))),
            reverse=True,
        )
        return competitors[:12]

    def _build_search_seed(self, idea_name: str, description: Optional[str]) -> str:
        words = re.findall(r"[a-zA-Z0-9]+", f"{idea_name} {description or ''}".lower())
        stop_words = {
            "the",
            "pitch",
            "mvp",
            "feature",
            "features",
            "pricing",
            "model",
            "acquisition",
            "channel",
            "customer",
            "segment",
            "path",
            "month",
            "founder",
            "driven",
            "network",
            "communities",
            "with",
            "from",
            "this",
            "that",
            "your",
            "for",
            "and",
        }
        keywords: List[str] = []
        seen = set()
        for word in words:
            if len(word) <= 3 or word in stop_words or word in seen:
                continue
            seen.add(word)
            keywords.append(word)
        seed = " ".join(keywords[:6]).strip()
        return seed or idea_name

    def _candidate_from_result(
        self,
        result: Dict[str, str],
        seed_keywords: Optional[set] = None,
    ) -> Optional[Dict[str, object]]:
        url = (result.get("url") or "").strip()
        title = (result.get("title") or "").strip()
        snippet = (result.get("text") or "").strip()
        if not url or not title:
            return None

        domain = urlparse(url).netloc.lower().replace("www.", "")
        if not domain or domain in self.excluded_domains:
            return None

        lowered = f"{title} {snippet} {url}".lower()
        url_path = (urlparse(url).path or "").lower()
        if any(marker in lowered for marker in {"directory", "listicle", "roundup"}):
            return None
        if any(marker in lowered for marker in self.listicle_markers) and (
            "/blog/" in url_path or "/articles/" in url_path
        ):
            return None

        if seed_keywords:
            overlap = sum(1 for keyword in seed_keywords if len(keyword) > 3 and keyword in lowered)
            min_overlap = 1 if len(seed_keywords) >= 3 else 0
            if overlap < min_overlap:
                return None
        else:
            overlap = 0

        name = re.split(r"[-|:]", title)[0].strip()
        if len(name) < 2 or name.lower() in self.listicle_markers:
            name = domain.split(".")[0]

        return {
            "name": name,
            "domain": domain,
            "url": url,
            "evidence_count": 1,
            "keyword_overlap": overlap,
        }

    def _build_findings(self, idea_name: str, competitors: List[Dict[str, object]]) -> Dict[str, object]:
        strong_competitors = [item for item in competitors if int(item.get("evidence_count", 0)) >= 2]
        competitor_count = len(competitors)
        strong_count = len(strong_competitors)

        if competitor_count == 0:
            market_saturation = "GREEN - No direct competitors found in search evidence"
            recommendation = "Proceed, but validate demand directly with interviews."
            confidence = 0.45
        elif strong_count >= 5 or competitor_count >= 8:
            market_saturation = "RED - Crowded landscape"
            recommendation = "Pivot positioning or customer segment before building."
            confidence = 0.82
        elif competitor_count <= 6:
            market_saturation = "YELLOW - Low to moderate competition"
            recommendation = "Proceed with clear differentiation and niche focus."
            confidence = 0.75
        else:
            market_saturation = "YELLOW - Moderate competition"
            recommendation = "Proceed only with clear wedge and measurable user pull."
            confidence = 0.78

        return {
            "idea": idea_name,
            "researched_at": datetime.now().isoformat(),
            "competitors": competitors,
            "market_saturation": market_saturation,
            "confidence": confidence,
            "recommendation": recommendation,
        }

    def _format_findings(self, findings: Dict[str, object]) -> str:
        competitors: List[Dict[str, object]] = findings.get("competitors", [])  # type: ignore[assignment]
        output = (
            "COMPETITOR ANALYSIS REPORT\n"
            "==========================\n"
            f"Idea: {findings['idea']}\n"
            f"Market Saturation: {findings['market_saturation']}\n"
            f"Analysis Confidence: {findings['confidence']:.0%}\n"
            f"Recommendation: {findings['recommendation']}\n\n"
            f"Competitors Found ({len(competitors)}):\n"
        )

        if competitors:
            for idx, competitor in enumerate(competitors, start=1):
                output += (
                    f"{idx}. {competitor['name']} ({competitor['domain']})\n"
                    f"   Evidence hits: {competitor['evidence_count']}\n"
                    f"   URL: {competitor['url']}\n"
                )
        else:
            output += "   (No direct competitors found)\n"

        output += f"\nResearch Date: {findings['researched_at']}\n"
        return output

    def _extract_pitch(self, text: str) -> Optional[str]:
        section_match = re.search(
            r"the pitch[^\n]*\n(?P<body>(?:.+\n){0,4})",
            text,
            flags=re.IGNORECASE,
        )
        if section_match:
            body_lines = [line.strip() for line in section_match.group("body").splitlines() if line.strip()]
            for line in body_lines:
                candidate = self._clean_candidate(line)
                if candidate:
                    return candidate

        explicit_match = re.search(
            r"(?:^|\n)\s*(?:\*+)?(?:\d+\.\s*)?the pitch(?:\*+)?\s*:\s*(.+)",
            text,
            flags=re.IGNORECASE,
        )
        if explicit_match:
            candidate = self._clean_candidate(explicit_match.group(1))
            if candidate:
                return candidate

        lines = [line.strip() for line in text.splitlines() if line.strip()]
        for idx, line in enumerate(lines):
            if "the pitch" not in line.lower():
                continue
            for next_line in lines[idx + 1:]:
                candidate = self._clean_candidate(next_line)
                if candidate:
                    return candidate

        quoted_match = re.search(r"['\"]([^'\"]{12,180})['\"]", text)
        if quoted_match:
            candidate = self._clean_candidate(quoted_match.group(1))
            if candidate:
                return candidate

        for line in lines:
            candidate = self._clean_candidate(line)
            if candidate and len(candidate) >= 20:
                return candidate[:180]

        return None

    def _clean_candidate(self, value: str) -> Optional[str]:
        cleaned = value.strip().strip("*").strip("-").strip()
        cleaned = cleaned.strip("\"'")
        lowered = cleaned.lower()
        if not cleaned:
            return None
        if lowered.startswith("the pitch"):
            return None
        if lowered in {"1", "2", "3", "4"}:
            return None
        if "mvp feature set" in lowered or "pricing model" in lowered or "acquisition channel" in lowered:
            return None
        return cleaned

    def speak_and_return(self, message: str) -> str:
        self.speak(message)
        return message

