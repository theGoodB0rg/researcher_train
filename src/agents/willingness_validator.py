"""
WillingnessToPayValidator Agent: deterministic composite willingness model.
"""

import re
from datetime import datetime
from statistics import median
from typing import Dict, List, Optional

from src.utils.console import colored

from src.core.agent import Agent


class WillingnessToPayValidatorAgent(Agent):
    def __init__(self, name: str, role: str, system_prompt: str, color: str = "blue"):
        super().__init__(name, role, system_prompt, color)

    def process(self, input_data: str, context: List[Dict[str, str]] = None, system_overrides: str = None) -> str:
        reply = super().process(input_data, context=context, system_overrides=system_overrides)
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
        usage_fit = self._score_usage_frequency_fit(strategist_text=strategist_text, pain_text=pain_text)

        composite_score = self._composite_score(
            direct_score=direct_score,
            pricing_fit=pricing_fit,
            market_proof=market_proof,
            budget_fit=budget_fit,
            inaction_score=inaction_score,
            substitution_penalty=substitution_penalty,
            usage_fit=usage_fit,
            has_direct_signals=bool(direct_signals),
            competitor_anchor=competitor_anchor,
        )

        recommendation = self._recommendation_from_score(composite_score, direct_signals, market_proof)
        confidence = self._confidence(
            direct_signals=direct_signals,
            competitor_anchor=competitor_anchor,
            market_proof=market_proof,
            strategist_text=strategist_text,
            usage_fit=usage_fit,
        )
        score_drivers = self._score_driver_notes(
            pricing_fit=pricing_fit,
            market_proof=market_proof,
            budget_fit=budget_fit,
            inaction_score=inaction_score,
            substitution_penalty=substitution_penalty,
            usage_fit=usage_fit,
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
            usage_fit=usage_fit,
            confidence=confidence,
            score_drivers=score_drivers,
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
        competitor_count = max(
            self._estimate_competitor_count(competitor_text),
            self._extract_competitors_found_count(competitor_text),
        )
        saturation = self._extract_market_saturation(competitor_text)
        direct_evidence_count = self._extract_direct_competitor_evidence_count(competitor_text)
        listicle_noise = self._estimate_listicle_noise(competitor_text)

        if competitor_prices:
            # Explicit paid anchors are the strongest evidence that buyers already spend.
            base = 58.0 + (7.0 * min(4, len(competitor_prices))) + (4.0 * min(5, direct_evidence_count))
        elif direct_evidence_count > 0:
            base = 40.0 + (6.0 * min(6, direct_evidence_count))
        else:
            # Fallback when LLM omitted prices/direct counts: infer from breadth of discovered products.
            base = 28.0 + min(30.0, 3.0 * float(competitor_count))

        # RED means crowded, not necessarily low willingness. Treat it as proof unless evidence is sparse.
        if saturation == "RED":
            if competitor_count >= 4 or direct_evidence_count >= 2 or len(competitor_prices) >= 2:
                base += 6.0
            else:
                base -= 6.0
        elif saturation == "YELLOW":
            base += 4.0
        elif saturation == "GREEN":
            if competitor_count == 0 and direct_evidence_count == 0 and not competitor_prices:
                base -= 8.0
            else:
                base += 2.0

        # Penalize noisy roundup-heavy evidence so listicles don't look like strong proof.
        if listicle_noise >= 4 and direct_evidence_count == 0 and not competitor_prices:
            base -= min(18.0, 2.5 * float(listicle_noise))
        elif listicle_noise >= 2:
            base -= min(8.0, 1.5 * float(listicle_noise))

        if competitor_count >= 8 and direct_evidence_count <= 1 and not competitor_prices:
            base -= 6.0

        return max(12.0, min(95.0, base))

    def _estimate_competitor_count(self, competitor_text: str) -> int:
        text = competitor_text or ""
        if not text.strip():
            return 0

        bullet_count = len(re.findall(r"^\s*[-*]\s+", text, flags=re.MULTILINE))
        numbered_count = len(re.findall(r"^\s*\d+\.\s+", text, flags=re.MULTILINE))
        url_count = len(re.findall(r"https?://", text, flags=re.IGNORECASE))
        # Heuristic: URLs are often one per competitor entry.
        return max(bullet_count, numbered_count, url_count)

    def _extract_competitors_found_count(self, competitor_text: str) -> int:
        text = competitor_text or ""
        if not text.strip():
            return 0

        parenthesized = re.search(r"Competitors Found\s*\((\d+)\)", text, flags=re.IGNORECASE)
        if parenthesized:
            return int(parenthesized.group(1))

        inline = re.search(r"Competitors Found\s*:\s*(\d+)", text, flags=re.IGNORECASE)
        if inline:
            return int(inline.group(1))
        return 0

    def _extract_market_saturation(self, text: str) -> str:
        upper = (text or "").upper()
        if "GREEN" in upper:
            return "GREEN"
        if "YELLOW" in upper:
            return "YELLOW"
        if "RED" in upper:
            return "RED"
        return "UNKNOWN"

    def _extract_direct_competitor_evidence_count(self, competitor_text: str) -> int:
        text = competitor_text or ""
        direct_match = re.search(
            r"Direct Product Evidence Count\s*:\s*(\d+)",
            text,
            flags=re.IGNORECASE,
        )
        if direct_match:
            return int(direct_match.group(1))

        evidence_hits = [
            int(value)
            for value in re.findall(r"Evidence hits\s*:\s*(\d+)", text, flags=re.IGNORECASE)
        ]
        if evidence_hits:
            return sum(1 for value in evidence_hits if value >= 2)
        return 0

    def _estimate_listicle_noise(self, competitor_text: str) -> int:
        text = (competitor_text or "").lower()
        if not text.strip():
            return 0

        markers = [
            r"\bbest\b",
            r"\btop\s+\d+\b",
            r"\balternatives?\b",
            r"\bcomparison\b",
            r"\broundup\b",
            r"\bvs\b",
            r"\bguide\b",
        ]
        marker_hits = sum(len(re.findall(pattern, text, flags=re.IGNORECASE)) for pattern in markers)
        url_hits = len(
            re.findall(
                r"https?://[^\s]+/(?:blog|articles|advisor|tools|top|best)",
                text,
                flags=re.IGNORECASE,
            )
        )
        return min(12, marker_hits + url_hits)

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

    def _score_usage_frequency_fit(self, strategist_text: str, pain_text: str) -> float:
        text = f"{strategist_text}\n{pain_text}".lower()
        high_terms = [
            "daily",
            "weekly",
            "monthly",
            "recurring",
            "repeat usage",
            "ongoing",
            "continuous",
            "every day",
            "every week",
        ]
        low_terms = [
            "once a year",
            "yearly",
            "rarely",
            "seasonal",
            "one-off",
            "sporadic",
            "occasional",
            "as needed",
            "emergency",
        ]
        score = 50.0
        score += 8.0 * sum(1 for term in high_terms if term in text)
        score -= 10.0 * sum(1 for term in low_terms if term in text)

        consumer_terms = ["homeowner", "homeowners", "consumer", "household"]
        operator_terms = ["property manager", "landlord", "operations", "warranty", "portfolio"]
        if any(term in text for term in consumer_terms) and any(term in text for term in low_terms):
            score -= 8.0
        if any(term in text for term in operator_terms):
            score += 8.0
        return max(10.0, min(95.0, score))

    def _composite_score(
        self,
        direct_score: float,
        pricing_fit: float,
        market_proof: float,
        budget_fit: float,
        inaction_score: float,
        substitution_penalty: float,
        usage_fit: float,
        has_direct_signals: bool,
        competitor_anchor: Optional[float],
    ) -> float:
        if has_direct_signals:
            weights = {
                "direct": 0.20,
                "pricing": 0.21,
                "market": 0.18,
                "budget": 0.12,
                "inaction": 0.14,
                "usage": 0.10,
                "substitution": 0.05,
            }
        elif competitor_anchor is not None or market_proof >= 65.0:
            # Avoid over-penalizing the common "no quote" case when real market pricing exists.
            weights = {
                "direct": 0.03,
                "pricing": 0.27,
                "market": 0.25,
                "budget": 0.13,
                "inaction": 0.17,
                "usage": 0.10,
                "substitution": 0.05,
            }
        else:
            weights = {
                "direct": 0.10,
                "pricing": 0.20,
                "market": 0.18,
                "budget": 0.13,
                "inaction": 0.20,
                "usage": 0.14,
                "substitution": 0.05,
            }

        base = (
            (weights["direct"] * direct_score)
            + (weights["pricing"] * pricing_fit)
            + (weights["market"] * market_proof)
            + (weights["budget"] * budget_fit)
            + (weights["inaction"] * inaction_score)
            + (weights["usage"] * usage_fit)
            + (weights["substitution"] * (100.0 - substitution_penalty))
        )

        # Explicit anchors widen score spread to avoid constant-midband outcomes.
        if market_proof >= 78.0 and pricing_fit >= 78.0 and budget_fit >= 68.0 and usage_fit >= 65.0:
            base = max(base, 74.0)
        if usage_fit <= 30.0 and substitution_penalty >= 12.0 and direct_score < 30.0:
            base = min(base, 38.0)
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
        usage_fit: float,
    ) -> float:
        confidence = 45.0
        if direct_signals:
            confidence += 15.0
        if competitor_anchor is not None:
            confidence += 20.0
        if market_proof >= 75.0:
            confidence += 10.0
        if usage_fit <= 30.0 or usage_fit >= 70.0:
            confidence += 5.0
        if "budget owner" in strategist_text.lower():
            confidence += 10.0
        return max(30.0, min(95.0, confidence))

    def _score_driver_notes(
        self,
        pricing_fit: float,
        market_proof: float,
        budget_fit: float,
        inaction_score: float,
        substitution_penalty: float,
        usage_fit: float,
    ) -> List[str]:
        notes: List[str] = []
        if pricing_fit >= 75:
            notes.append("pricing_fit_strong")
        elif pricing_fit <= 40:
            notes.append("pricing_fit_weak")
        if market_proof >= 70:
            notes.append("market_proof_strong")
        elif market_proof <= 40:
            notes.append("market_proof_weak")
        if budget_fit >= 70:
            notes.append("buyer_budget_fit_strong")
        if inaction_score >= 60:
            notes.append("inaction_cost_high")
        elif inaction_score <= 38:
            notes.append("inaction_cost_low")
        if usage_fit <= 35:
            notes.append("usage_frequency_low")
        elif usage_fit >= 70:
            notes.append("usage_frequency_high")
        if substitution_penalty >= 12:
            notes.append("substitution_pressure_high")
        return notes

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
        usage_fit: float,
        confidence: float,
        score_drivers: List[str],
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
                f"   - Usage frequency fit score: {usage_fit:.0f}/100",
                f"   - Substitution pressure penalty: {substitution_penalty:.0f}/24",
                "",
                f"4. Recommendation: {recommendation}",
                "",
                "5. Score Drivers:",
                (
                    "   - " + ", ".join(score_drivers)
                    if score_drivers
                    else "   - neutral_mix"
                ),
                "",
                f"Composite confidence: {confidence:.0f}% | Analysis Date: {datetime.now().isoformat()}",
            ]
        )
        return "\n".join(lines)

