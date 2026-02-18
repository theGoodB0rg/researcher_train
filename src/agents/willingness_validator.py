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

        budget_fit = self._score_budget_fit(strategist_text)
        inaction_score = self._score_cost_of_inaction(pain_text)
        substitution_penalty = self._substitution_penalty(pain_text, competitor_text)

        composite_score = self._composite_score(
            direct_score=direct_score,
            pricing_fit=pricing_fit,
            budget_fit=budget_fit,
            inaction_score=inaction_score,
            substitution_penalty=substitution_penalty,
        )

        recommendation = self._recommendation_from_score(composite_score, direct_signals)
        confidence = self._confidence(
            direct_signals=direct_signals,
            competitor_anchor=competitor_anchor,
            strategist_text=strategist_text,
        )

        output = self._format_output(
            score=composite_score,
            recommendation=recommendation,
            direct_signals=direct_signals,
            proposed_price=pricing.get("monthly_price"),
            competitor_anchor=competitor_anchor,
            pricing_fit=pricing_fit,
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
        for match in re.finditer(r"\$(\d+(?:\.\d+)?)\s*/\s*year\b", text, flags=re.IGNORECASE):
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
            if proposed_monthly <= 500:
                return 60.0
            if proposed_monthly <= 1200:
                return 45.0
            return 30.0

        ratio = proposed_monthly / max(1.0, anchor_monthly)
        if ratio <= 1.3:
            return 82.0
        if ratio <= 2.0:
            return 70.0
        if ratio <= 4.0:
            return 50.0
        if ratio <= 8.0:
            return 35.0
        return 20.0

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
        budget_fit: float,
        inaction_score: float,
        substitution_penalty: float,
    ) -> float:
        base = (
            (0.25 * direct_score)
            + (0.25 * pricing_fit)
            + (0.20 * budget_fit)
            + (0.20 * inaction_score)
            + (0.10 * (100.0 - substitution_penalty))
        )
        return max(0.0, min(100.0, base))

    def _recommendation_from_score(self, score: float, signals: List[str]) -> str:
        if not signals and score < 45:
            return "NO SIGNAL"
        if score >= 70:
            return "STRONG SIGNAL"
        if score >= 45:
            return "WEAK SIGNAL"
        return "NO SIGNAL"

    def _confidence(self, direct_signals: List[str], competitor_anchor: Optional[float], strategist_text: str) -> float:
        confidence = 45.0
        if direct_signals:
            confidence += 15.0
        if competitor_anchor is not None:
            confidence += 20.0
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
