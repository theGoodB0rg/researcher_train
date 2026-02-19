"""
WillingnessToPayValidator Agent: deterministic composite willingness model.
"""

import re
from datetime import datetime
from statistics import median
from typing import Dict, List, Optional

from termcolor import colored

from src.core.agent import Agent


class WillingnessToPayValidatorAgent(Agent):
    def __init__(self, name: str, role: str, system_prompt: str, color: str = "blue"):
        super().__init__(name, role, system_prompt, color)

    def process(self, input_data: str, context: List[Dict[str, str]] = None) -> str:
        """
        Composite willingness model using:
        - direct payment intent signals,
        - competitor pricing anchors,
        - buyer budget proxy,
        - cost-of-inaction proxy,
        - substitution pressure.
        """
        print(colored("[WillingnessToPayValidator] Analyzing price tolerance...", "blue"))

        context = context or []
        strategist_text = self._latest_role_content(context, "SaaS Strategist")
        competitor_text = self._latest_role_content(context, "Competitor Researcher")
        pain_text = "\n".join(
            msg.get("content", "")
            for msg in context
            if msg.get("role") in {"Trend Scout", "Pain Analyst"}
        )

        pricing = self._extract_pricing(strategist_text)
        direct_signals = self._extract_direct_signals(pain_text)
        direct_score = self._score_direct_intent(direct_signals)

        competitor_prices = self._extract_competitor_prices(competitor_text)
        competitor_anchor = self._price_anchor(competitor_prices)
        pricing_fit = self._score_pricing_fit(pricing.get("monthly_price"), competitor_anchor)
        market_proof = self._score_market_proof(competitor_prices, competitor_text)

        budget_fit = self._score_budget_fit(strategist_text)
        inaction_score = self._score_cost_of_inaction(pain_text)
        substitution_penalty = self._substitution_penalty(pain_text, competitor_text)

        composite_score = self._composite_score(
            direct_score=direct_score,
            pricing_fit=pricing_fit,
            market_proof=market_proof,
            budget_fit=budget_fit,
            inaction_score=inaction_score,
            substitution_penalty=substitution_penalty,
            has_direct_signals=bool(direct_signals),
            competitor_anchor=competitor_anchor,
        )

        recommendation = self._recommendation_from_score(composite_score, direct_signals, market_proof)
        confidence = self._confidence(
            direct_signals=direct_signals,
            competitor_anchor=competitor_anchor,
            market_proof=market_proof,
            strategist_text=strategist_text,
        )

        output = self._format_output(
            score=composite_score,
            recommendation=recommendation,
            direct_signals=direct_signals,
            proposed_price=pricing.get("monthly_price"),
            competitor_anchor=competitor_anchor,
            pricing_fit=pricing_fit,
            market_proof=market_proof,
            budget_fit=budget_fit,
            inaction_score=inaction_score,
            substitution_penalty=substitution_penalty,
            confidence=confidence,
        )

        self.speak(output)
        return output

    def _latest_role_content(self, context: List[Dict[str, str]], role_name: str) -> str:
        for message in reversed(context):
            if role_name in message.get("role", ""):
                return message.get("content", "")
        return ""

    def _extract_pricing(self, strategist_text: str) -> Dict[str, Optional[float]]:
        monthly_patterns = [
            r"\$(\d+(?:\.\d+)?)\s*/\s*(?:month|mo)\b",
            r"\$(\d+(?:\.\d+)?)\s*(?:per|/)\s*(?:month|mo)\b",
            r"price point\s*[:\-]?\s*\$(\d+(?:\.\d+)?)",
        ]
        for pattern in monthly_patterns:
            match = re.search(pattern, strategist_text, flags=re.IGNORECASE)
            if match:
                return {"monthly_price": float(match.group(1))}

        all_prices = [float(value) for value in re.findall(r"\$(\d+(?:\.\d+)?)", strategist_text)]
        filtered = [value for value in all_prices if value >= 20]
        return {"monthly_price": filtered[0] if filtered else None}

    def _extract_direct_signals(self, text: str) -> List[str]:
        signals: List[str] = []
        strong_patterns = [
            r"\bwould pay\b",
            r"\bwilling to pay\b",
            r"\bbudget (?:approved|allocated)\b",
            r"\bworth paying\b",
            r"\bpaying for\b",
        ]
        weak_patterns = [
            r"\btoo expensive\b",
            r"\bcan(?:not|'t) afford\b",
            r"\bfree alternative\b",
            r"\bnot worth\b",
        ]
        sentences = re.split(r"[.!?\n]+", text)
        for sentence in sentences:
            candidate = sentence.strip()
            if len(candidate) < 20:
                continue
            lowered = candidate.lower()
            if any(re.search(pattern, lowered) for pattern in strong_patterns + weak_patterns):
                signals.append(candidate)
        deduped: List[str] = []
        seen = set()
        for signal in signals:
            key = signal.lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(signal)
        return deduped[:10]

    def _score_direct_intent(self, signals: List[str]) -> float:
        if not signals:
            return 22.0

        score = 35.0
        for signal in signals:
            lowered = signal.lower()
            if any(token in lowered for token in ["would pay", "willing to pay", "budget approved", "budget allocated"]):
                score += 10.0
            if any(token in lowered for token in ["too expensive", "can't afford", "cannot afford", "free alternative", "not worth"]):
                score -= 8.0
        return max(5.0, min(95.0, score))

    def _extract_competitor_prices(self, competitor_text: str) -> List[float]:
        monthly_values: List[float] = []
        text = competitor_text or ""

        for match in re.finditer(r"\$(\d+(?:\.\d+)?)\s*/\s*(?:month|mo)\b", text, flags=re.IGNORECASE):
            monthly_values.append(float(match.group(1)))
        for match in re.finditer(r"\$(\d+(?:\.\d+)?)\s*per\s*(?:month|mo)\b", text, flags=re.IGNORECASE):
            monthly_values.append(float(match.group(1)))
        for match in re.finditer(r"\$(\d+(?:\.\d+)?)\s*/\s*year\b", text, flags=re.IGNORECASE):
            monthly_values.append(float(match.group(1)) / 12.0)
        for match in re.finditer(r"\$(\d+(?:\.\d+)?)\s*per\s*year\b", text, flags=re.IGNORECASE):
            monthly_values.append(float(match.group(1)) / 12.0)
        return monthly_values

    def _price_anchor(self, competitor_prices: List[float]) -> Optional[float]:
        if not competitor_prices:
            return None
        return float(median(competitor_prices))

    def _score_pricing_fit(self, proposed_monthly: Optional[float], anchor_monthly: Optional[float]) -> float:
        if proposed_monthly is None:
            return 30.0
        if anchor_monthly is None:
            if proposed_monthly <= 80:
                return 55.0
            if proposed_monthly <= 250:
                return 70.0
            if proposed_monthly <= 600:
                return 60.0
            if proposed_monthly <= 1200:
                return 40.0
            return 20.0

        ratio = proposed_monthly / max(1.0, anchor_monthly)
        if ratio <= 1.1:
            return 92.0
        if ratio <= 1.5:
            return 85.0
        if ratio <= 2.0:
            return 74.0
        if ratio <= 3.0:
            return 58.0
        if ratio <= 5.0:
            return 40.0
        if ratio <= 8.0:
            return 24.0
        return 10.0

    def _score_market_proof(self, competitor_prices: List[float], competitor_text: str) -> float:
        competitor_count = self._estimate_competitor_count(competitor_text)
        saturation = self._extract_market_saturation(competitor_text)

        if not competitor_prices:
            if competitor_count >= 8:
                base = 52.0
            elif competitor_count >= 4:
                base = 45.0
            elif competitor_count >= 1:
                base = 38.0
            else:
                base = 30.0
            if saturation == "RED":
                base -= 4.0
            elif saturation == "YELLOW":
                base += 4.0
            elif saturation == "GREEN":
                base += 10.0
            return max(20.0, min(85.0, base))

        base = min(90.0, 55.0 + (8.0 * len(competitor_prices)))
        if saturation == "RED":
            base -= 10.0
        elif saturation == "YELLOW":
            base += 2.0
        elif saturation == "GREEN":
            base += 8.0
        return max(20.0, min(95.0, base))

    def _estimate_competitor_count(self, competitor_text: str) -> int:
        text = competitor_text or ""
        if not text.strip():
            return 0

        bullet_count = len(re.findall(r"^\s*[-*]\s+", text, flags=re.MULTILINE))
        numbered_count = len(re.findall(r"^\s*\d+\.\s+", text, flags=re.MULTILINE))
        url_count = len(re.findall(r"https?://", text, flags=re.IGNORECASE))
        # Heuristic: URLs are often one per competitor entry.
        return max(bullet_count, numbered_count, url_count)

    def _extract_market_saturation(self, text: str) -> str:
        upper = (text or "").upper()
        if "GREEN" in upper:
            return "GREEN"
        if "YELLOW" in upper:
            return "YELLOW"
        if "RED" in upper:
            return "RED"
        return "UNKNOWN"

    def _score_budget_fit(self, strategist_text: str) -> float:
        text = strategist_text.lower()
        high_authority = ["cfo", "cio", "cto", "vp", "head of", "director"]
        medium_authority = ["operations manager", "hr manager", "owner", "finance lead", "procurement"]
        low_authority = ["freelancer", "individual", "student", "hobbyist"]

        if any(token in text for token in high_authority):
            return 82.0
        if any(token in text for token in medium_authority):
            return 72.0
        if any(token in text for token in low_authority):
            return 38.0
        return 55.0

    def _score_cost_of_inaction(self, pain_text: str) -> float:
        text = pain_text.lower()
        high_terms = [
            "fine",
            "penalty",
            "compliance risk",
            "revenue leakage",
            "lost revenue",
            "legal",
            "sla",
            "downtime",
        ]
        medium_terms = [
            "time lost",
            "manual",
            "delays",
            "errors",
            "waste",
            "bottleneck",
            "rework",
            "drop-off",
        ]
        score = 35.0
        score += 8.0 * sum(1 for term in high_terms if term in text)
        score += 4.0 * sum(1 for term in medium_terms if term in text)
        return max(20.0, min(92.0, score))

    def _substitution_penalty(self, pain_text: str, competitor_text: str) -> float:
        combined = f"{pain_text}\n{competitor_text}".lower()
        penalty_terms = ["free", "template", "open source", "many alternatives", "saturated", "commoditized", "commodity"]
        penalty = 0.0
        for term in penalty_terms:
            if term in combined:
                penalty += 4.0
        return max(0.0, min(24.0, penalty))

    def _composite_score(
        self,
        direct_score: float,
        pricing_fit: float,
        market_proof: float,
        budget_fit: float,
        inaction_score: float,
        substitution_penalty: float,
        has_direct_signals: bool,
        competitor_anchor: Optional[float],
    ) -> float:
        if has_direct_signals:
            weights = {
                "direct": 0.20,
                "pricing": 0.25,
                "market": 0.20,
                "budget": 0.15,
                "inaction": 0.15,
                "substitution": 0.05,
            }
        elif competitor_anchor is not None or market_proof >= 65.0:
            # Avoid over-penalizing the common "no quote" case when real market pricing exists.
            weights = {
                "direct": 0.05,
                "pricing": 0.30,
                "market": 0.30,
                "budget": 0.15,
                "inaction": 0.15,
                "substitution": 0.05,
            }
        else:
            weights = {
                "direct": 0.15,
                "pricing": 0.25,
                "market": 0.20,
                "budget": 0.15,
                "inaction": 0.20,
                "substitution": 0.05,
            }

        base = (
            (weights["direct"] * direct_score)
            + (weights["pricing"] * pricing_fit)
            + (weights["market"] * market_proof)
            + (weights["budget"] * budget_fit)
            + (weights["inaction"] * inaction_score)
            + (weights["substitution"] * (100.0 - substitution_penalty))
        )

        # Explicit anchors widen score spread to avoid constant-midband outcomes.
        if market_proof >= 80.0 and pricing_fit >= 80.0 and budget_fit >= 68.0 and inaction_score >= 50.0:
            base = max(base, 72.0)
        if pricing_fit <= 20.0 and market_proof <= 40.0 and substitution_penalty >= 12.0:
            base = min(base, 35.0)
        return max(0.0, min(100.0, base))

    def _recommendation_from_score(self, score: float, signals: List[str], market_proof: float) -> str:
        if not signals and market_proof < 45.0 and score < 55.0:
            return "NO SIGNAL"
        if score >= 72:
            return "STRONG SIGNAL"
        if score >= 50:
            return "WEAK SIGNAL"
        return "NO SIGNAL"

    def _confidence(
        self,
        direct_signals: List[str],
        competitor_anchor: Optional[float],
        market_proof: float,
        strategist_text: str,
    ) -> float:
        confidence = 45.0
        if direct_signals:
            confidence += 15.0
        if competitor_anchor is not None:
            confidence += 20.0
        if market_proof >= 75.0:
            confidence += 10.0
        if "budget owner" in strategist_text.lower():
            confidence += 10.0
        return max(30.0, min(95.0, confidence))

    def _format_output(
        self,
        score: float,
        recommendation: str,
        direct_signals: List[str],
        proposed_price: Optional[float],
        competitor_anchor: Optional[float],
        pricing_fit: float,
        market_proof: float,
        budget_fit: float,
        inaction_score: float,
        substitution_penalty: float,
        confidence: float,
    ) -> str:
        lines = [
            f"1. Price Willingness Score: {score:.0f}%",
            "",
            "2. Key signals of payment intent:",
        ]
        if direct_signals:
            for signal in direct_signals[:4]:
                lines.append(f'   - "{signal}"')
        else:
            lines.append("   - NO DIRECT SIGNAL from customers indicating explicit willingness to pay.")

        lines.extend(
            [
                "",
                "3. Price elasticity:",
                (
                    f"   - Proposed monthly price: ${proposed_price:.0f}" if proposed_price is not None else
                    "   - Proposed monthly price: Unknown"
                ),
                (
                    f"   - Competitor monthly anchor: ${competitor_anchor:.0f}" if competitor_anchor is not None else
                    "   - Competitor monthly anchor: Unavailable"
                ),
                f"   - Pricing fit score: {pricing_fit:.0f}/100",
                f"   - Market proof score: {market_proof:.0f}/100",
                f"   - Buyer budget fit score: {budget_fit:.0f}/100",
                f"   - Cost-of-inaction score: {inaction_score:.0f}/100",
                f"   - Substitution pressure penalty: {substitution_penalty:.0f}/24",
                "",
                f"4. Recommendation: {recommendation}",
                "",
                f"Composite confidence: {confidence:.0f}% | Analysis Date: {datetime.now().isoformat()}",
            ]
        )
        return "\n".join(lines)
