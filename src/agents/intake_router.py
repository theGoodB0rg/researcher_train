"""
IntakeRouter agent: normalizes free-form user requests into a structured research plan.
"""

import json
import re
from typing import Any, Dict, List, Optional, Tuple

from src.core.agent import Agent


class IntakeRouterAgent(Agent):
    _META_STOP_WORDS = {
        "here",
        "this",
        "that",
        "these",
        "those",
        "your",
        "our",
        "their",
        "project",
        "brief",
        "comprehensive",
        "document",
        "designed",
        "focused",
        "focus",
        "ensuring",
        "ensure",
        "avoid",
        "avoiding",
        "mistakes",
        "current",
        "competitors",
        "timeline",
        "month",
        "build",
        "saas",
        "working",
        "title",
        "objective",
        "core",
        "philosophy",
        "execution",
        "plan",
        "immediate",
        "next",
        "step",
        "generate",
        "system",
        "prompt",
        "who",
        "whom",
        "whose",
        "are",
        "they",
        "them",
        "there",
        "once",
        "does",
        "doing",
        "done",
        "each",
        "other",
        "about",
    }

    _QUERY_STOP_WORDS = _META_STOP_WORDS | {
        "the",
        "and",
        "for",
        "with",
        "from",
        "into",
        "via",
        "buyer",
        "workflow",
        "pain",
        "problem",
        "related",
        "issues",
        "request",
        "requests",
        "feature",
        "features",
        "alternatives",
        "user",
        "users",
        "also",
        "just",
        "target",
        "launch",
        "risk",
        "solution",
        "phase",
        "week",
        "days",
        "day",
    }

    _LOW_SIGNAL_TERMS = _META_STOP_WORDS | {"high", "keep", "while", "stickiness"}
    _FOCUS_LINE_HINTS = (
        "objective",
        "pain",
        "problem",
        "workflow",
        "target audience",
        "buyer",
        "risk",
        "maintenance",
        "troubleshoot",
        "error",
        "manual",
        "claim",
        "dispatch",
    )

    def __init__(self, name: str, role: str, system_prompt: str, color: str = "yellow"):
        super().__init__(name, role, system_prompt, color)

    def process(self, input_data: str, context: Optional[List[Dict[str, str]]] = None) -> str:
        raw_request = self._extract_user_request(input_data)
        
        fallback_request = raw_request
        if context:
            user_messages = [msg["content"] for msg in context if msg["role"] == "user"]
            if user_messages:
                accumulated_text = " ".join(user_messages)
                if raw_request not in accumulated_text:
                    fallback_request = f"{accumulated_text} {raw_request}"

        if self.client:
            reply = super().process(input_data, context=context)
            try:
                json_match = re.search(r'\{.*\}', reply, re.DOTALL)
                if json_match:
                    plan = json.loads(json_match.group(0))
                    if "intent" in plan:
                        return json.dumps(plan, indent=2)
            except Exception:
                pass
                    
        plan = self._build_plan(fallback_request)
        output = json.dumps(plan, indent=2)
        if not self.client:
            self.speak(output)
        return output

    def _extract_user_request(self, input_data: str) -> str:
        marker = "Route and normalize this research request:"
        if marker in (input_data or ""):
            return input_data.split(marker, 1)[1].strip()
        return (input_data or "").strip()

    def _build_plan(self, raw_request: str) -> Dict[str, Any]:
        raw_text = (raw_request or "").strip()
        compact_text = re.sub(r"\s+", " ", raw_text).strip()
        parsed = self._parse_key_value_fields(raw_text)
        brief_signals = self._extract_brief_signals(raw_text)

        buyer = parsed.get("buyer", "") or brief_signals.get("buyer", "")
        workflow = parsed.get("workflow", "") or brief_signals.get("workflow", "")
        pain = parsed.get("pain", "") or parsed.get("problem", "") or brief_signals.get("pain", "")
        vertical = parsed.get("vertical", "") or brief_signals.get("vertical", "")

        explicit_structured = bool(parsed.get("buyer", "").strip()) and bool(parsed.get("workflow", "").strip()) and bool(
            (parsed.get("pain", "") or parsed.get("problem", "")).strip()
        )
        intent = self._infer_intent(
            raw_request=raw_text,
            buyer=buyer,
            workflow=workflow,
            pain=pain,
            explicit_structured=explicit_structured,
        )
        summary = self._build_summary(raw_request=raw_text, brief_signals=brief_signals)
        constraints = self._extract_constraints(raw_request=raw_text)
        assumptions = self._extract_assumptions(raw_request=raw_text)

        normalized_topic = self._normalize_topic(
            text=compact_text,
            buyer=buyer,
            workflow=workflow,
            pain=pain,
            vertical=vertical,
            raw_request=raw_text,
            summary=summary,
            brief_signals=brief_signals,
            explicit_structured=explicit_structured,
        )
        research_mode = self._infer_research_mode(
            normalized_topic=normalized_topic,
            buyer=buyer,
            workflow=workflow,
            explicit_structured=explicit_structured,
        )
        query_seed = self._build_query_seed(
            normalized_topic=normalized_topic,
            buyer=buyer,
            workflow=workflow,
            pain=pain,
            vertical=vertical,
            summary=summary,
            intent=intent,
            raw_request=raw_text,
            brief_signals=brief_signals,
            explicit_structured=explicit_structured,
        )
        if self._is_low_signal_query_seed(query_seed):
            query_seed = self._build_query_seed(
                normalized_topic=summary or normalized_topic,
                buyer=buyer,
                workflow=workflow,
                pain=pain,
                vertical=vertical,
                summary=summary,
                intent=intent,
                raw_request=summary or raw_text,
                brief_signals=brief_signals,
                explicit_structured=explicit_structured,
            )
        must_include_terms = self._must_include_terms(
            buyer=buyer,
            workflow=workflow,
            pain=pain,
            normalized_topic=summary or normalized_topic,
            query_seed=query_seed,
        )
        must_exclude_terms = self._must_exclude_terms(normalized_topic=normalized_topic)
        clarification_needed, clarification_question = self._clarification(
            raw=raw_text,
            buyer=buyer,
            workflow=workflow,
            pain=pain,
            intent=intent,
        )
        confidence = self._confidence(
            buyer=buyer,
            workflow=workflow,
            pain=pain,
            query_seed=query_seed,
            clarification_needed=clarification_needed,
            intent=intent,
        )

        return {
            "intent": intent,
            "summary": summary,
            "constraints": constraints,
            "assumptions": assumptions,
            "research_mode": research_mode,
            "normalized_topic": normalized_topic,
            "buyer": buyer,
            "workflow": workflow,
            "pain": pain,
            "vertical": vertical,
            "query_seed": query_seed,
            "must_include_terms": must_include_terms,
            "must_exclude_terms": must_exclude_terms,
            "source_priority": ["reddit", "forums", "reviews", "hackernews", "web"],
            "clarification_needed": clarification_needed,
            "clarification_question": clarification_question,
            "confidence": confidence,
        }

    def _infer_intent(
        self,
        raw_request: str,
        buyer: str,
        workflow: str,
        pain: str,
        explicit_structured: bool = False,
    ) -> str:
        lowered = (raw_request or "").lower()
        if explicit_structured:
            return "MARKET_DISCOVERY"
        
        conversational_terms = {"hi", "hello", "hey", "how are you", "who are you", "what can you do", "brainstorm", "testing", "test", "conversational"}
        if not buyer and not workflow and not pain and len(lowered.split()) < 20:
            if any(term in lowered.split() for term in conversational_terms) or len(lowered.split()) <= 10:
                return "CONVERSATIONAL"

        feasibility_terms = {
            "feasibility",
            "project brief",
            "working title",
            "objective",
            "execution plan",
            "roadmap",
            "pricing model",
            "target launch",
            "unit economics",
            "mrr",
            "go to market",
            "go-to-market",
            "gtm",
            "will this work",
            "is this viable",
        }
        discovery_terms = {
            "complaints",
            "pain points",
            "frustrations",
            "alternatives",
            "switching",
            "user feedback",
            "market research",
            "find pain",
            "find problems",
        }
        ideation_terms = {
            "what should i build",
            "startup idea",
            "micro saas idea",
            "suggest an idea",
            "brainstorm idea",
            "new product idea",
            "build me an idea",
        }

        if any(term in lowered for term in feasibility_terms):
            return "FEASIBILITY_REVIEW"
        if any(term in lowered for term in discovery_terms):
            return "MARKET_DISCOVERY"
        if any(term in lowered for term in ideation_terms):
            return "IDEA_SYNTHESIS"
        return "MARKET_DISCOVERY"

    def _build_summary(self, raw_request: str, brief_signals: Dict[str, str], max_chars: int = 260) -> str:
        objective = brief_signals.get("objective", "")
        pain = brief_signals.get("pain", "")
        target = brief_signals.get("target_audience", "")

        summary_parts: List[str] = []
        if objective:
            summary_parts.append(objective)
        if pain and pain.lower() not in (objective or "").lower():
            summary_parts.append(pain)
        if target:
            summary_parts.append(f"Target users: {target}")

        if not summary_parts:
            candidates = []
            for sentence in re.split(r"(?<=[.!?])\s+", " ".join(self._clean_lines(raw_request))):
                normalized = sentence.strip()
                if not normalized:
                    continue
                lowered = normalized.lower()
                if "here is the comprehensive project brief" in lowered:
                    continue
                if "this document is designed to keep you focused" in lowered:
                    continue
                candidates.append(normalized)
                if len(candidates) >= 2:
                    break
            summary_parts = candidates

        summary = " ".join(summary_parts).strip()
        summary = re.sub(r"\s+", " ", summary).strip(" ,;")
        if len(summary) > max_chars:
            return summary[:max_chars].rstrip(" ,;")
        return summary

    def _extract_constraints(self, raw_request: str) -> List[str]:
        lowered = (raw_request or "").lower()
        constraints: List[str] = []

        deadline_matches = re.findall(r"\b\d+\s*(?:day|days|week|weeks|month|months)\b", lowered)
        for match in deadline_matches[:3]:
            constraints.append(f"timeline: {match}")

        price_matches = re.findall(r"\$\s*\d+(?:[.,]\d+)?", raw_request or "")
        for match in price_matches[:3]:
            constraints.append(f"price_or_budget: {match.replace(' ', '')}")

        phrase_constraints = [
            ("no paid ads", "constraint: no paid ads"),
            ("zero budget", "constraint: zero budget"),
            ("bootstrapped", "constraint: bootstrapped"),
            ("one month", "constraint: one-month build"),
            ("30 days", "constraint: 30-day build"),
        ]
        for phrase, label in phrase_constraints:
            if phrase in lowered and label not in constraints:
                constraints.append(label)

        return constraints[:8]

    def _extract_assumptions(self, raw_request: str) -> List[str]:
        assumptions: List[str] = []
        for line in self._clean_lines(raw_request):
            lowered = line.lower()
            if any(token in lowered for token in ["assume", "assuming", "must", "should", "target", "goal"]):
                assumptions.append(line)
            if len(assumptions) >= 6:
                break
        if assumptions:
            return assumptions

        sentences = [segment.strip() for segment in re.split(r"[.!?]+", raw_request or "") if segment.strip()]
        for sentence in sentences:
            lowered = sentence.lower()
            if any(token in lowered for token in ["must", "should", "target", "goal"]):
                assumptions.append(re.sub(r"\s+", " ", sentence))
            if len(assumptions) >= 4:
                break
        return assumptions

    def _parse_key_value_fields(self, text: str) -> Dict[str, str]:
        segments: List[str] = []
        for chunk in re.split(r"[;\|\n\r]+", text or ""):
            cleaned = self._clean_markdown_line(chunk)
            if cleaned:
                segments.append(cleaned)

        aliases = {
            "target_audience": "buyer",
            "audience": "buyer",
            "customer_segment": "buyer",
            "budget_owner": "buyer",
            "workflow_step": "workflow",
            "core_problem": "pain",
        }
        parsed: Dict[str, str] = {}
        for segment in segments:
            match = re.match(r"^\s*([a-zA-Z_ ]+)\s*:\s*(.+)$", segment)
            if not match:
                continue
            key = match.group(1).strip().lower().replace(" ", "_")
            value = match.group(2).strip()
            normalized_key = aliases.get(key, key)
            if normalized_key not in {"buyer", "workflow", "pain", "problem", "vertical"}:
                continue
            parsed[normalized_key] = value
        return parsed

    def _normalize_topic(
        self,
        text: str,
        buyer: str,
        workflow: str,
        pain: str,
        vertical: str,
        raw_request: str,
        summary: str,
        brief_signals: Dict[str, str],
        explicit_structured: bool = False,
    ) -> str:
        if explicit_structured and buyer and workflow:
            structured_parts = [f"buyer: {buyer}"]
            if vertical:
                structured_parts.append(f"vertical: {vertical}")
            structured_parts.append(f"workflow: {workflow}")
            structured_parts.append(f"pain: {pain or 'recurring operational bottlenecks'}")
            return "; ".join(structured_parts)

        if self._looks_like_structured_brief(raw_request):
            return self._compose_focus_topic(brief_signals=brief_signals, fallback=summary or text)

        cleaned = re.sub(
            r"\b(can you|please|help me|i want to|i am thinking about|idea for)\b",
            " ",
            text,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
        return cleaned or text

    def _compose_focus_topic(self, brief_signals: Dict[str, str], fallback: str) -> str:
        focus_segments = [
            brief_signals.get("title", ""),
            brief_signals.get("objective", ""),
            brief_signals.get("pain", ""),
            brief_signals.get("workflow", ""),
            brief_signals.get("target_audience", ""),
        ]
        text = " ".join(part for part in focus_segments if part).strip() or fallback
        compact = self._compact_focus_phrase(text=text, max_terms=18)
        return compact or fallback

    def _infer_research_mode(
        self,
        normalized_topic: str,
        buyer: str,
        workflow: str,
        explicit_structured: bool = False,
    ) -> str:
        lowered = (normalized_topic or "").lower()
        if explicit_structured and buyer and workflow:
            return "B2B_BUYER_FIRST"

        b2b_terms = {
            "company",
            "operations",
            "agency",
            "manager",
            "workflow",
            "dispatch",
            "claims",
            "compliance",
            "accounting",
            "invoice",
            "warranty",
            "tenant",
            "landlord",
            "property manager",
        }
        b2c_terms = {
            "homeowner",
            "homeowners",
            "consumer",
            "household",
            "creator",
            "dating",
            "fitness",
            "resume",
            "portfolio",
            "appliance",
            "diy",
            "travel",
            "recipe",
        }

        b2b_hits = sum(1 for term in b2b_terms if term in lowered)
        b2c_hits = sum(1 for term in b2c_terms if term in lowered)
        if b2c_hits > 0 and b2b_hits <= 1:
            return "B2C_PLG"
        if b2b_hits > 0:
            return "B2B_STRICT"
        return "B2B_DISCOVERY"

    def _build_query_seed(
        self,
        normalized_topic: str,
        buyer: str,
        workflow: str,
        pain: str,
        vertical: str,
        summary: str,
        intent: str,
        raw_request: str,
        brief_signals: Dict[str, str],
        explicit_structured: bool = False,
        max_terms: int = 12,
    ) -> str:
        seed_source = ""
        if explicit_structured:
            seed_source = " ".join(part for part in [vertical, buyer, workflow, pain] if part).strip()
        elif intent == "MARKET_DISCOVERY" and buyer and workflow and pain:
            seed_source = " ".join(part for part in [vertical, buyer, workflow, pain] if part).strip()
        if not seed_source:
            seed_source = self._build_focus_text(
                raw_request=raw_request,
                summary=summary,
                normalized_topic=normalized_topic,
                brief_signals=brief_signals,
                intent=intent,
            )
        compact = self._compact_focus_phrase(text=seed_source or normalized_topic, max_terms=max_terms)
        return compact or (normalized_topic or summary)

    def _build_focus_text(
        self,
        raw_request: str,
        summary: str,
        normalized_topic: str,
        brief_signals: Dict[str, str],
        intent: str,
    ) -> str:
        parts: List[str] = []
        for key in ["objective", "pain", "workflow", "target_audience", "title"]:
            value = brief_signals.get(key, "")
            if value:
                parts.append(value)

        for line in self._clean_lines(raw_request):
            lowered = line.lower()
            if any(hint in lowered for hint in self._FOCUS_LINE_HINTS):
                parts.append(line)
            if len(parts) >= 10:
                break

        if intent == "FEASIBILITY_REVIEW" and summary:
            parts.append(summary)
        parts.append(normalized_topic)
        return " ".join(part for part in parts if part).strip()

    def _extract_brief_signals(self, raw_request: str) -> Dict[str, str]:
        lines = self._clean_lines(raw_request)
        title = self._extract_title(raw_request=raw_request, lines=lines)
        objective = self._extract_labeled_value(lines, labels=["objective"])
        target_audience = self._extract_labeled_value(
            lines,
            labels=["target audience", "audience", "customer segment", "persona", "icp"],
        )
        buyer = self._extract_labeled_value(lines, labels=["buyer", "budget owner"])
        workflow = self._extract_labeled_value(lines, labels=["workflow", "workflow step"])
        vertical = self._extract_labeled_value(lines, labels=["vertical", "industry"])
        pain = self._extract_labeled_value(lines, labels=["pain", "problem", "core problem"])
        if not pain:
            pain = self._extract_problem_from_text(objective=objective, lines=lines)
        if not workflow:
            workflow = self._infer_workflow_from_lines(lines)
        if not buyer and target_audience:
            buyer = target_audience

        return {
            "title": title,
            "objective": objective,
            "target_audience": target_audience,
            "buyer": buyer,
            "workflow": workflow,
            "vertical": vertical,
            "pain": pain,
        }

    def _extract_title(self, raw_request: str, lines: List[str]) -> str:
        match = re.search(r"(?im)project\s+brief\s*:\s*[\"“]?([^\"\n(]+)", raw_request or "")
        if match:
            return re.sub(r"\s+", " ", match.group(1)).strip(" -:;,.")

        for line in lines:
            lowered = line.lower()
            if lowered.startswith("project brief:"):
                return line.split(":", 1)[1].strip(" -:;,.")
            if lowered.startswith(("objective:", "core philosophy:", "target launch:")):
                continue
            if len(line.split()) > 12:
                continue
            if "comprehensive project brief" in lowered:
                continue
            return line
        return ""

    def _extract_labeled_value(self, lines: List[str], labels: List[str]) -> str:
        normalized_labels = [label.lower() for label in labels]
        for index, line in enumerate(lines):
            lowered = line.lower()
            for label in normalized_labels:
                prefix = f"{label}:"
                if lowered.startswith(prefix):
                    value = line[len(prefix):].strip()
                    cursor = index + 1
                    while cursor < len(lines):
                        next_line = lines[cursor].strip()
                        if not next_line:
                            break
                        if re.match(r"^[a-z][a-z0-9 _\-]{1,40}:\s*", next_line.lower()):
                            break
                        if next_line.lower().startswith(("phase ", "risk ", "week ")):
                            break
                        if len(value) > 220:
                            break
                        value = f"{value} {next_line}".strip()
                        cursor += 1
                    return value
        return ""

    def _extract_problem_from_text(self, objective: str, lines: List[str]) -> str:
        objective_match = re.search(r"\bproblem\s+of\s+(.+)", objective or "", flags=re.IGNORECASE)
        if objective_match:
            return objective_match.group(1).strip(" .")

        for line in lines:
            lowered = line.lower()
            if "problem of " in lowered:
                return re.sub(r".*problem of\s+", "", line, flags=re.IGNORECASE).strip(" .")
            if lowered.startswith("risk "):
                return line
        return ""

    def _infer_workflow_from_lines(self, lines: List[str]) -> str:
        for line in lines:
            lowered = line.lower()
            if lowered.startswith("goal:"):
                return line.split(":", 1)[1].strip()
            if lowered.startswith("context injection:"):
                return "context-aware troubleshooting using stored appliance metadata"
            if "maintenance tracking" in lowered:
                return "appliance maintenance tracking and reminders"
            if "error" in lowered and "model" in lowered:
                return "model-specific appliance troubleshooting"
        return ""

    def _clean_lines(self, raw_request: str) -> List[str]:
        lines: List[str] = []
        for raw_line in re.split(r"[\n\r]+", raw_request or ""):
            cleaned = self._clean_markdown_line(raw_line)
            if not cleaned:
                continue
            if self._is_separator_line(cleaned):
                continue
            if cleaned.startswith("|") and cleaned.endswith("|"):
                continue
            lines.append(cleaned)
        return lines

    def _clean_markdown_line(self, line: str) -> str:
        cleaned = (line or "").strip()
        if not cleaned:
            return ""

        cleaned = cleaned.replace("**", "")
        cleaned = cleaned.replace("__", "")
        cleaned = cleaned.replace("`", "")
        cleaned = re.sub(r"^\s*[#>\-\*\+\u2022]+\s*", "", cleaned)
        cleaned = re.sub(r"^\s*\d+\.\s*", "", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    def _is_separator_line(self, line: str) -> bool:
        if not line:
            return True
        if re.fullmatch(r"[-=]{3,}", line):
            return True
        if re.fullmatch(r"\|?\s*[-:| ]{3,}\|?", line):
            return True
        return False

    def _looks_like_structured_brief(self, raw_request: str) -> bool:
        text = (raw_request or "").lower()
        markers = [
            "project brief",
            "objective:",
            "target audience:",
            "pricing model:",
            "execution plan",
            "roadmap",
        ]
        if any(marker in text for marker in markers):
            return True
        return text.count("\n") >= 6

    def _compact_focus_phrase(self, text: str, max_terms: int = 12) -> str:
        tokens = re.findall(r"[a-z0-9]+", (text or "").lower())
        if not tokens:
            return ""

        selected: List[str] = []
        seen = set()
        for token in tokens:
            if len(token) <= 2:
                continue
            if token in self._QUERY_STOP_WORDS:
                continue
            if token.isdigit():
                continue
            if token in seen:
                continue
            seen.add(token)
            selected.append(token)
            if len(selected) >= max_terms:
                break
        return " ".join(selected)

    def _is_low_signal_query_seed(self, query_seed: str) -> bool:
        tokens = re.findall(r"[a-z0-9]+", (query_seed or "").lower())
        if len(tokens) < 3:
            return True
        low_hits = sum(1 for token in tokens if token in self._LOW_SIGNAL_TERMS)
        return low_hits >= max(2, len(tokens) // 2)

    def _must_include_terms(self, buyer: str, workflow: str, pain: str, normalized_topic: str, query_seed: str) -> List[str]:
        pool = " ".join([buyer, workflow, pain, query_seed, normalized_topic]).lower()
        tokens = re.findall(r"[a-z0-9]+", pool)
        priority: List[str] = []
        skip_tokens = self._META_STOP_WORDS | {
            "build",
            "month",
            "days",
            "timeline",
            "launch",
            "roadmap",
            "week",
            "plan",
        }
        for token in tokens:
            if len(token) <= 3 or token in skip_tokens:
                continue
            if token in priority:
                continue
            priority.append(token)
            if len(priority) >= 8:
                break
        return priority

    def _must_exclude_terms(self, normalized_topic: str) -> List[str]:
        lowered = (normalized_topic or "").lower()
        tokens = set(re.findall(r"[a-z0-9]+", lowered))
        has_assistant = "assistant" in tokens
        appliance_context = bool(
            {
                "appliance",
                "homeowner",
                "homeowners",
                "inventory",
                "troubleshooting",
                "warranty",
                "repair",
            }
            & tokens
        )
        explicit_home_assistant = "home assistant" in lowered or "home-assistant" in lowered
        if has_assistant and appliance_context and not explicit_home_assistant:
            return ["home assistant", "site:home-assistant.io", "site:community.home-assistant.io"]
        return []

    def _clarification(self, raw: str, buyer: str, workflow: str, pain: str, intent: str) -> Tuple[bool, str]:
        if intent == "CONVERSATIONAL":
            return True, "Hello! I'm your AI Research Co-Founder. Tell me about a specific audience (like 'plumbers') or a workflow you want to investigate."
        if intent == "FEASIBILITY_REVIEW":
            return False, ""
        lowered = (raw or "").lower()
        tokens = re.findall(r"[a-z0-9]+", lowered)
        preamble_markers = [
            "project brief",
            "comprehensive",
            "working title",
            "core philosophy",
            "target launch",
            "execution plan",
            "objective",
        ]
        if any(marker in lowered for marker in preamble_markers):
            return True, (
                "Share one concise line in this format: "
                "buyer: <who pays>; workflow: <step>; pain: <recurring problem>."
            )
        if not buyer and not workflow and not pain:
            return True, "I need a specific target audience or clear pain point to start researching. What exactly are they struggling with?"
        if not buyer:
            return True, "Who is the primary buyer/user persona for this request?"
        if not workflow and not pain:
            return True, "What exact workflow step or problem should research focus on?"
        if not pain:
            return True, "What recurring pain should be prioritized (time, errors, delays, or cost)?"
        return False, ""

    def _confidence(
        self,
        buyer: str,
        workflow: str,
        pain: str,
        query_seed: str,
        clarification_needed: bool,
        intent: str,
    ) -> float:
        score = 0.55
        if intent == "FEASIBILITY_REVIEW":
            score += 0.12
        if intent == "IDEA_SYNTHESIS":
            score += 0.06
        if buyer:
            score += 0.15
        if workflow:
            score += 0.12
        if pain:
            score += 0.08
        if len(query_seed.split()) >= 4:
            score += 0.05
        if clarification_needed:
            score -= 0.15
        return round(max(0.2, min(0.98, score)), 2)
