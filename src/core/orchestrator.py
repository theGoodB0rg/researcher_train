import json
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from termcolor import colored

from .agent import Agent


class Orchestrator:
    def __init__(self, agents: Dict[str, Agent], max_iterations: int = 5, interactive_pivots: bool = True):
        self.agents = agents
        self.max_iterations = max_iterations
        self.interactive_pivots = interactive_pivots
        self._domain_shift_authorized_next_iteration = False
        self.conversation_history: List[Dict[str, str]] = []
        self.iteration_count = 0
        self.research_results: Dict[str, object] = {}
        self._reset_run_state(topic=None)

    def _reset_run_state(self, topic: Optional[str]):
        self.conversation_history = []
        self.iteration_count = 0
        self._domain_shift_authorized_next_iteration = False
        self.research_results = {
            "topic": topic,
            "mode": None,
            "buyer_brief": None,
            "iterations": [],
            "final_verdict": None,
            "final_idea": None,
            "final_recommendation": None,
            "researched_at": datetime.now().isoformat(),
            "iteration_count": 0,
        }

    def broadcast(self, sender_name: str, message: str):
        self.conversation_history.append({"role": sender_name, "content": message})

    def run_round_table(self, initial_topic: str) -> Dict[str, object]:
        self._reset_run_state(topic=initial_topic)
        buyer_brief = self._parse_buyer_first_brief(initial_topic)
        topic = buyer_brief.get("pain", initial_topic) if buyer_brief else initial_topic
        self.research_results["buyer_brief"] = buyer_brief
        consecutive_no_data = 0

        print(colored(f"\n{'=' * 60}", "cyan"))
        print(colored(f"=== STARTING INTELLIGENT RESEARCH: {initial_topic.upper()} ===", "cyan"))
        print(colored(f"{'=' * 60}\n", "cyan"))

        for iteration in range(1, self.max_iterations + 1):
            self.iteration_count = iteration
            domain_shift_authorized = self._domain_shift_authorized_next_iteration
            self._domain_shift_authorized_next_iteration = False
            print(colored(f"\n--- ITERATION {iteration}/{self.max_iterations} ---", "yellow"))
            self.conversation_history = []

            if buyer_brief:
                topic_mode = "B2B_BUYER_FIRST"
                scout_topic = self._build_buyer_first_scout_topic(buyer_brief=buyer_brief, pain_focus=topic)
            else:
                topic_plan = self._classify_topic_mode(topic)
                topic_mode = topic_plan["mode"]
                scout_topic = topic_plan["scout_topic"]
            self.research_results["mode"] = topic_mode
            print(
                colored(
                    f"[Orchestrator] Research mode: {topic_mode} | Scout topic: {scout_topic}",
                    "yellow",
                )
            )

            scout_output = self._run_agent("Trend Scout", f"Find complaints and issues related to: {scout_topic}")
            if self._failed_data_collection(scout_output):
                consecutive_no_data += 1
                failure_reason = self._extract_data_failure_reason(scout_output)
                hard_gates = {
                    "blocked": True,
                    "issues": [f"Data coverage gate failed: {failure_reason}"],
                    "pivot": "Insufficient evidence - broaden to adjacent operational pain point",
                }
                self._append_iteration(
                    topic,
                    verdict="NO DATA",
                    topic_mode=topic_mode,
                    scout_topic=scout_topic,
                    scorecard=self._build_low_evidence_scorecard(scout_output),
                    hard_gates=hard_gates,
                )
                print(colored("[Orchestrator] Scout failed to collect real data. Iteration abandoned.", "red"))
                if consecutive_no_data >= 2:
                    print(
                        colored(
                            "[Orchestrator] Stopping early after repeated NO DATA. Please provide a narrower topic with clearer public evidence.",
                            "red",
                        )
                    )
                    self.research_results["final_verdict"] = "NO_DATA_PIVOT_REQUIRED"
                    self.research_results["final_recommendation"] = (
                        "Provide a narrower workflow or user segment with explicit recurring pain and public discussion."
                    )
                    self.research_results["iteration_count"] = iteration
                    return self.research_results
                recovered_topic = self._recover_topic_after_no_data(topic=topic, topic_mode=topic_mode)
                if recovered_topic != topic:
                    print(colored(f"[Orchestrator] No-data recovery: '{topic}' -> '{recovered_topic}'", "yellow"))
                    topic = recovered_topic
                continue
            consecutive_no_data = 0

            if self._is_no_evidence_scout_output(scout_output):
                opportunity = self._build_low_evidence_scorecard(scout_output)
                hard_gates = {
                    "blocked": True,
                    "issues": ["No evidence gate failed: Scout found no explicit pain signals or recurring complaints."],
                    "pivot": "Insufficient evidence - pivot to adjacent workflow pain point",
                }
                scorecard_text = self._format_scorecard(opportunity)
                gate_text = self._format_hard_gates(hard_gates)
                self.broadcast("Opportunity Scorer", scorecard_text)
                self.broadcast("Gatekeeper", gate_text)
                print(colored("[Orchestrator] No evidence signals found. Skipping strategist and forcing pivot.", "red"))
                self._append_iteration(
                    topic,
                    verdict="NO GO",
                    topic_mode=topic_mode,
                    scout_topic=scout_topic,
                    scorecard=opportunity,
                    hard_gates=hard_gates,
                )
                print(colored(f"\n[REJECTED] Idea rejected. Reason: {hard_gates['pivot']}", "red"))
                topic = self._next_topic(
                    current_topic=topic,
                    pivot_instruction=hard_gates["pivot"],
                    topic_mode=topic_mode,
                )
                continue

            analyst_prompt = self._analyst_prompt_for_mode(topic_mode=topic_mode, buyer_brief=buyer_brief)
            analyst_output = self._run_agent(
                "Pain Analyst",
                analyst_prompt,
                context=self.conversation_history,
            )
            strategist_prompt = self._strategist_prompt_for_mode(topic_mode=topic_mode, buyer_brief=buyer_brief)
            strategist_output = self._run_agent(
                "SaaS Strategist",
                strategist_prompt,
                context=self.conversation_history,
            )

            competitor_output = self._run_optional_agent("Competitor Researcher", "Research competitors for this idea:")
            willingness_output = self._run_optional_agent(
                "Willingness Validator",
                "Validate if target customers will pay for this solution:",
            )
            sales_output = self._run_optional_agent(
                "Founder Sales Validator",
                self._sales_prompt_for_mode(topic_mode=topic_mode),
            )

            opportunity = self._build_opportunity_scorecard(
                topic_mode=topic_mode,
                scout_output=scout_output,
                analyst_output=analyst_output,
                strategist_output=strategist_output,
                competitor_output=competitor_output,
                willingness_output=willingness_output,
                sales_output=sales_output,
            )
            scorecard_text = self._format_scorecard(opportunity)
            self.broadcast("Opportunity Scorer", scorecard_text)

            hard_gates = self._evaluate_hard_gates(
                topic=topic,
                scout_topic=scout_topic,
                scout_output=scout_output,
                analyst_output=analyst_output,
                strategist_output=strategist_output,
                competitor_output=competitor_output,
                willingness_output=willingness_output,
                sales_output=sales_output,
                domain_shift_authorized=domain_shift_authorized,
                topic_mode=topic_mode,
            )
            gate_text = self._format_hard_gates(hard_gates)
            self.broadcast("Gatekeeper", gate_text)

            skeptic_output = self._run_agent(
                "The Skeptic",
                (
                    "Make final GO/NO GO decision based on all validation data and the scorecard/gates below.\n\n"
                    f"[OPPORTUNITY SCORECARD]\n{scorecard_text}\n[END SCORECARD]\n\n"
                    f"[HARD GATES]\n{gate_text}\n[END HARD GATES]\n"
                ),
                context=self.conversation_history,
            )

            verdict = self._parse_verdict(skeptic_output)
            if hard_gates["blocked"]:
                print(colored("[Orchestrator] Hard gate failed. Forcing NO GO.", "red"))
                verdict = "NO GO"

            self._append_iteration(
                topic,
                verdict,
                topic_mode=topic_mode,
                scout_topic=scout_topic,
                scorecard=opportunity,
                hard_gates=hard_gates,
            )

            if verdict in {"GO", "QUALIFIED"} and not hard_gates["blocked"]:
                print(colored("\n[SUCCESS] RESEARCH QUALIFIED! Proceeding with idea validation.", "green"))
                self.research_results["final_verdict"] = verdict
                self.research_results["final_idea"] = strategist_output
                self.research_results["iteration_count"] = iteration
                return self.research_results

            if verdict == "NO GO":
                pivot = hard_gates["pivot"] if hard_gates["blocked"] else self._extract_pivot_instruction(skeptic_output)
                print(colored(f"\n[REJECTED] Idea rejected. Reason: {pivot}", "red"))
                topic = self._next_topic(current_topic=topic, pivot_instruction=pivot, topic_mode=topic_mode)
            else:
                print(colored(f"[Orchestrator] Unclear verdict: {verdict}. Retrying.", "yellow"))

        print(colored(f"\n[WARNING] Reached max iterations ({self.max_iterations}). Stopping research.", "red"))
        self.research_results["final_verdict"] = "NO_QUALIFIED_IDEA"
        self.research_results["iteration_count"] = self.iteration_count
        return self.research_results

    def _run_agent(self, agent_name: str, prompt: str, context: Optional[List[Dict[str, str]]] = None) -> str:
        agent = self.agents.get(agent_name)
        if not agent:
            raise ValueError(f"Required agent missing: {agent_name}")
        output = agent.process(prompt, context=context)
        self.broadcast(agent.name, output)
        return output

    def _run_optional_agent(self, agent_name: str, prompt: str):
        agent = self.agents.get(agent_name)
        if not agent:
            return None
        output = agent.process(prompt, context=self.conversation_history)
        self.broadcast(agent.name, output)
        return output

    def _append_iteration(
        self,
        topic: str,
        verdict: str,
        topic_mode: Optional[str] = None,
        scout_topic: Optional[str] = None,
        scorecard: Optional[Dict[str, Any]] = None,
        hard_gates: Optional[Dict[str, Any]] = None,
    ):
        iteration_result = {
            "iteration": self.iteration_count,
            "topic": topic,
            "mode": topic_mode,
            "scout_topic": scout_topic,
            "verdict": verdict,
            "scorecard": scorecard or {},
            "hard_gates": hard_gates or {},
            "conversation_length": len(self.conversation_history),
            "timestamp": datetime.now().isoformat(),
        }
        self.research_results["iterations"].append(iteration_result)

    def _classify_topic_mode(self, topic: str) -> Dict[str, str]:
        normalized = (topic or "").strip()
        lowered = normalized.lower()

        b2b_terms = {
            "b2b",
            "agency",
            "saas",
            "invoic",
            "compliance",
            "operations",
            "freelancer",
            "startup",
            "small business",
            "accounting",
            "crm",
            "hr",
            "workflow",
            "procurement",
            "accounts payable",
            "invoice",
            "sop",
            "back office",
        }
        b2c_plg_terms = {
            "dating",
            "relationship",
            "men",
            "women",
            "sex",
            "linkedin",
            "resume",
            "portfolio",
            "fitness",
            "anxiety",
            "parenting",
            "travel",
            "recipe",
            "beauty",
            "game",
            "creator",
            "course",
            "newsletter",
            "youtube",
            "tiktok",
            "instagram",
            "template",
            "plugin",
            "portfolio",
            "resume",
            "linkedin",
        }

        if any(term in lowered for term in b2b_terms):
            return {"mode": "B2B_STRICT", "scout_topic": normalized}

        if any(term in lowered for term in b2c_plg_terms):
            scout_topic = f"{normalized} user complaints feature requests alternatives"
            return {"mode": "B2C_PLG", "scout_topic": scout_topic}

        return {"mode": "B2B_DISCOVERY", "scout_topic": f"{normalized} business operations"}

    def _parse_buyer_first_brief(self, raw_topic: str) -> Optional[Dict[str, str]]:
        text = (raw_topic or "").strip()
        if not text:
            return None

        if not re.search(r"\bbuyer\s*:", text, flags=re.IGNORECASE):
            return None

        segments = [segment.strip() for segment in re.split(r"[;\|]", text) if segment.strip()]
        parsed: Dict[str, str] = {}
        for segment in segments:
            match = re.match(r"^\s*([a-zA-Z_ ]+)\s*:\s*(.+)$", segment)
            if not match:
                continue
            key = match.group(1).strip().lower().replace(" ", "_")
            value = match.group(2).strip()
            parsed[key] = value

        buyer = parsed.get("buyer")
        workflow = parsed.get("workflow")
        pain = parsed.get("pain") or parsed.get("problem") or parsed.get("topic")
        if not buyer or not workflow:
            return None

        return {
            "buyer": buyer,
            "workflow": workflow,
            "pain": pain or "recurring operational bottlenecks",
        }

    def _build_buyer_first_scout_topic(self, buyer_brief: Dict[str, str], pain_focus: str) -> str:
        buyer = buyer_brief.get("buyer", "").strip()
        workflow = buyer_brief.get("workflow", "").strip()
        pain = self._compact_topic_terms(pain_focus or buyer_brief.get("pain", ""))
        return f"{buyer} {workflow} {pain} operational pain points".strip()

    def _format_buyer_brief(self, buyer_brief: Optional[Dict[str, str]]) -> str:
        if not buyer_brief:
            return "None"
        buyer = buyer_brief.get("buyer", "unknown")
        workflow = buyer_brief.get("workflow", "unknown")
        pain = buyer_brief.get("pain", "unknown")
        return f"buyer={buyer}; workflow={workflow}; pain={pain}"

    def _analyst_prompt_for_mode(self, topic_mode: str, buyer_brief: Optional[Dict[str, str]]) -> str:
        if topic_mode == "B2C_PLG":
            return (
                "Analyze these findings for recurring user pain in a B2C/Prosumer product context. "
                f"Research mode: {topic_mode}. "
                "Extract concrete retention and conversion blockers with evidence. "
                "Include structured evidence fields: user persona, user workflow step, frequency, current workaround, cost of inaction."
            )
        return (
            "Analyze these findings for recurring operational pain in a B2B context. "
            f"Research mode: {topic_mode}. "
            f"Buyer Brief: {self._format_buyer_brief(buyer_brief)}. "
            "Include structured evidence fields: buyer, workflow step, frequency, current workaround, cost of inaction."
        )

    def _strategist_prompt_for_mode(self, topic_mode: str, buyer_brief: Optional[Dict[str, str]]) -> str:
        if topic_mode == "B2C_PLG":
            return (
                "Propose a realistic $5k MRR B2C/Prosumer PLG product for the identified problems. "
                "Do not force enterprise framing. Use self-serve channels and realistic pricing ($5-$80/month). "
                "Show a volume-based path to $5k MRR with explicit conversion assumptions."
            )
        return (
            "Propose a $5k MRR micro-SaaS solution for the identified problems. "
            "Target budget-owning buyers and keep monthly pricing high enough for a realistic path to $5k MRR. "
            f"Buyer Brief: {self._format_buyer_brief(buyer_brief)}."
        )

    def _sales_prompt_for_mode(self, topic_mode: str) -> str:
        if topic_mode == "B2C_PLG":
            return (
                "Simulate if a founder can reach $5k MRR for a self-serve PLG product in 30-90 days. "
                "Estimate activation, free-to-paid conversion, and realistic paid customer counts."
            )
        return "Simulate if founders can reach $5k MRR with this idea:"

    def _failed_data_collection(self, scout_output: str) -> bool:
        output_upper = (scout_output or "").upper()
        return "DATA COLLECTION FAILED" in output_upper

    def _parse_verdict(self, skeptic_output: str) -> str:
        text = skeptic_output or ""

        explicit_match = re.search(r"FINAL\s+VERDICT\s*:\s*(GO|QUALIFIED|NO\s*GO)", text, flags=re.IGNORECASE)
        if explicit_match:
            verdict = explicit_match.group(1).upper().replace("  ", " ")
            return "NO GO" if "NO" in verdict else verdict

        if re.search(r"\bNO\s*GO\b", text, flags=re.IGNORECASE):
            return "NO GO"
        if re.search(r"\bQUALIFIED\b", text, flags=re.IGNORECASE):
            return "QUALIFIED"
        if re.search(r"\bGO\b", text, flags=re.IGNORECASE):
            return "GO"
        return "UNCLEAR"

    def _extract_pivot_instruction(self, skeptic_output: str) -> str:
        normalized = (skeptic_output or "").lower()
        if "saturated" in normalized:
            return "Market is saturated - need different pain point"
        if "insufficient evidence" in normalized or "no evidence" in normalized:
            return "Insufficient evidence - pivot to adjacent workflow pain point"
        if "willingness" in normalized or "won't pay" in normalized:
            return "Low willingness to pay - raise price point for high-value customers"
        if "feasib" in normalized or "unrealistic" in normalized:
            return "Sales feasibility too low - reduce MVP scope or pivot to easier customer acquisition"
        if "technical" in normalized:
            return "Technical complexity too high - simplify feature set"
        return "General market/product fit issues"

    def _next_topic(self, current_topic: str, pivot_instruction: str, topic_mode: Optional[str] = None) -> str:
        active_mode = topic_mode or self._classify_topic_mode(current_topic)["mode"]
        lower_pivot = pivot_instruction.lower()
        if "different pain point" in lower_pivot or "saturated" in lower_pivot:
            self._domain_shift_authorized_next_iteration = True
            return self._suggest_new_topic(current_topic)
        if "insufficient evidence" in lower_pivot or "no evidence" in lower_pivot:
            self._domain_shift_authorized_next_iteration = True
            return self._recover_topic_after_no_data(topic=current_topic, topic_mode=active_mode)
        if "budget owner" in lower_pivot:
            self._domain_shift_authorized_next_iteration = False
            return f"{current_topic} for operations managers"
        if "price point" in lower_pivot:
            compacted = self._compact_topic_terms(current_topic)
            self._domain_shift_authorized_next_iteration = False
            if active_mode == "B2C_PLG":
                return f"{compacted} for a narrower user segment with higher repeat usage"
            return f"{compacted} for operations teams with budget ownership"
        if "willingness" in lower_pivot and active_mode == "B2C_PLG":
            compacted = self._compact_topic_terms(current_topic)
            self._domain_shift_authorized_next_iteration = False
            return f"{compacted} with stronger activation and conversion hooks"
        self._domain_shift_authorized_next_iteration = False
        return current_topic

    def _suggest_new_topic(self, current_topic: str) -> str:
        topic_pivots = {
            "junior react developers": "senior developers managing juniors",
            "cto software agency": "small software agency operation efficiency",
            "freelancer productivity": "freelancer project management",
            "small business accounting": "contractor tax compliance",
            "dating and relationship service business operations": "therapy clinic intake and scheduling operations",
            "wellness service business operations": "clinic documentation and follow-up operations",
        }

        pivot = topic_pivots.get(current_topic.lower())
        if not pivot:
            pivot = f"{current_topic} internal operations workflow"
        if pivot.strip().lower() == current_topic.strip().lower():
            pivot = f"{current_topic} compliance and documentation workflow"

        if not self.interactive_pivots:
            return pivot

        new_topic = input(
            colored(f"\n[Orchestrator] Suggested pivot: '{pivot}'. Enter new topic or press Enter to accept: ", "yellow")
        ).strip()
        return new_topic if new_topic else pivot

    def _recover_topic_after_no_data(self, topic: str, topic_mode: str) -> str:
        compacted = self._compact_topic_terms(topic)

        if topic_mode == "B2C_PLG":
            recovered = f"{compacted} user complaints and switching triggers"
        elif topic_mode == "B2B_STRICT":
            recovered = f"{compacted} workflow bottlenecks"
        else:
            recovered = f"{compacted} operations workflow pain points"

        recovered = re.sub(r"\s+", " ", recovered).strip()
        if recovered.lower() == topic.lower():
            recovered = f"{compacted} manual process pain points"
        return recovered

    def _compact_topic_terms(self, topic: str, max_terms: int = 7) -> str:
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
        }
        selected: List[str] = []
        seen = set()
        for token in tokens:
            if token in seen or token in stop_words:
                continue
            seen.add(token)
            selected.append(token)
            if len(selected) >= max_terms:
                break
        return " ".join(selected) if selected else " ".join(tokens[:max_terms])

    def _extract_data_failure_reason(self, scout_output: str) -> str:
        text = scout_output or ""
        match = re.search(r"\[DATA COLLECTION FAILED\]\s*(.+)", text, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return "Insufficient real-source coverage"

    def _is_no_evidence_scout_output(self, scout_output: str) -> bool:
        lowered = (scout_output or "").lower()
        evidence_gap_markers = [
            "no pain signals",
            "lack of pain signals",
            "no significant operational pains",
            "absence of specific complaints",
            "no explicit complaints",
            "no expressed frustration",
            "insufficient user feedback",
        ]
        return any(marker in lowered for marker in evidence_gap_markers)

    def _build_low_evidence_scorecard(self, scout_output: str) -> Dict[str, Any]:
        frequency = self._score_frequency(scout_output)
        return {
            "pain": 15.0,
            "frequency": round(max(15.0, min(45.0, frequency)), 1),
            "willingness": 20.0,
            "competition": 50.0,
            "buildability": 35.0,
            "mode_fit": 70.0,
            "weighted_score": 27.0,
        }

    def _check_evidence_grounding(self, scout_output: str, analyst_output: str) -> Optional[str]:
        scout_urls = self._extract_urls(scout_output)
        if not scout_urls:
            return None

        pain_count = len(re.findall(r"boring score\s*:\s*\d+(?:\.\d+)?", analyst_output or "", flags=re.IGNORECASE))
        analyst_url_mentions = len(re.findall(r"https?://[^\s\]\)\>,]+", analyst_output or "", flags=re.IGNORECASE))
        analyst_urls = self._extract_urls(analyst_output)

        if pain_count > 0 and analyst_url_mentions < pain_count:
            return f"found {pain_count} accepted pains but only {analyst_url_mentions} URL citations"

        missing = [url for url in analyst_urls if url not in scout_urls]
        if missing:
            missing_preview = ", ".join(missing[:3])
            return f"analyst cited URL(s) not present in Scout evidence: {missing_preview}"
        return None

    def _extract_urls(self, text: str) -> List[str]:
        if not text:
            return []
        matches = re.findall(r"https?://[^\s\]\)\>,]+", text, flags=re.IGNORECASE)
        urls: List[str] = []
        seen = set()
        for match in matches:
            normalized = self._normalize_url(match)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            urls.append(normalized)
        return urls

    def _normalize_url(self, raw_url: str) -> str:
        url = (raw_url or "").strip().rstrip(".,);]>\"'")
        return url.lower()

    def _is_cross_domain_shift(self, topic: str, scout_topic: str, strategist_output: str) -> bool:
        anchor_terms = self._domain_terms(topic) | self._domain_terms(scout_topic)
        if not anchor_terms:
            return False

        strategist_terms = self._domain_terms(strategist_output)
        overlap = anchor_terms & strategist_terms
        return len(overlap) == 0

    def _domain_terms(self, text: str) -> set:
        tokens = re.findall(r"[a-z0-9]+", (text or "").lower())
        stop_words = {
            "the",
            "and",
            "for",
            "with",
            "from",
            "into",
            "using",
            "tool",
            "tools",
            "software",
            "saas",
            "business",
            "operations",
            "workflow",
            "workflows",
            "pain",
            "points",
            "topic",
            "one",
            "two",
            "three",
            "teams",
            "manager",
            "managers",
            "owner",
            "owners",
            "high",
            "value",
            "budget",
        }
        return {token for token in tokens if len(token) >= 4 and token not in stop_words}

    def _extract_competitor_price_anchor(self, competitor_output: Optional[str]) -> Optional[float]:
        if not competitor_output:
            return None
        text = competitor_output.lower()
        monthly_values: List[float] = []

        for match in re.finditer(r"\$(\d+(?:\.\d+)?)\s*/\s*(month|mo)\b", text, flags=re.IGNORECASE):
            monthly_values.append(float(match.group(1)))

        for match in re.finditer(r"\$(\d+(?:\.\d+)?)\s*/\s*year\b", text, flags=re.IGNORECASE):
            monthly_values.append(float(match.group(1)) / 12.0)

        if monthly_values:
            return sum(monthly_values) / len(monthly_values)
        return None

    def _build_opportunity_scorecard(
        self,
        topic_mode: str,
        scout_output: str,
        analyst_output: str,
        strategist_output: str,
        competitor_output: Optional[str],
        willingness_output: Optional[str],
        sales_output: Optional[str],
    ) -> Dict[str, Any]:
        pain_score = self._score_pain(analyst_output)
        frequency_score = self._score_frequency(scout_output)
        willingness_score = self._extract_willingness_score(willingness_output)
        competition_score = self._score_competition(competitor_output)
        buildability_score = self._score_buildability(sales_output)
        mode_fit_score = self._score_mode_fit(topic_mode, strategist_output)

        weighted = (
            (0.30 * pain_score)
            + (0.20 * frequency_score)
            + (0.25 * willingness_score)
            + (0.15 * competition_score)
            + (0.10 * buildability_score)
        )
        final_score = max(0.0, min(100.0, weighted * (mode_fit_score / 100.0)))

        return {
            "pain": round(pain_score, 1),
            "frequency": round(frequency_score, 1),
            "willingness": round(willingness_score, 1),
            "competition": round(competition_score, 1),
            "buildability": round(buildability_score, 1),
            "mode_fit": round(mode_fit_score, 1),
            "weighted_score": round(final_score, 1),
        }

    def _evaluate_hard_gates(
        self,
        topic: str,
        scout_topic: str,
        scout_output: str,
        analyst_output: str,
        strategist_output: str,
        competitor_output: Optional[str],
        willingness_output: Optional[str],
        sales_output: Optional[str],
        domain_shift_authorized: bool,
        topic_mode: str = "B2B_STRICT",
    ) -> Dict[str, Any]:
        if topic_mode == "B2C_PLG":
            return self._evaluate_b2c_hard_gates(
                topic=topic,
                scout_topic=scout_topic,
                scout_output=scout_output,
                analyst_output=analyst_output,
                strategist_output=strategist_output,
                competitor_output=competitor_output,
                willingness_output=willingness_output,
                domain_shift_authorized=domain_shift_authorized,
            )
        return self._evaluate_b2b_hard_gates(
            topic=topic,
            scout_topic=scout_topic,
            scout_output=scout_output,
            analyst_output=analyst_output,
            strategist_output=strategist_output,
            competitor_output=competitor_output,
            willingness_output=willingness_output,
            sales_output=sales_output,
            domain_shift_authorized=domain_shift_authorized,
        )

    def _evaluate_b2b_hard_gates(
        self,
        topic: str,
        scout_topic: str,
        scout_output: str,
        analyst_output: str,
        strategist_output: str,
        competitor_output: Optional[str],
        willingness_output: Optional[str],
        sales_output: Optional[str],
        domain_shift_authorized: bool,
    ) -> Dict[str, Any]:
        issues: List[str] = []
        pivot = "General market/product fit issues"

        price = self._extract_monthly_price(strategist_output)
        if price is None or price < 150:
            issues.append("Price floor gate failed: monthly price must be at least $150 for realistic founder-led $5k MRR.")
            pivot = "Low willingness to pay - raise price point for high-value customers"

        if not self._has_budget_owner(strategist_output):
            issues.append("Buyer gate failed: target segment does not clearly include a budget-owning B2B operator.")
            pivot = "Target a budget owner and operational workflow"

        if willingness_output:
            willingness_score = self._extract_willingness_score(willingness_output)
            if willingness_score < 55:
                issues.append("Payment intent gate failed: willingness signal is too weak (<55%).")
                pivot = "Low willingness to pay - raise price point for high-value customers"

        if competitor_output:
            saturation = self._extract_market_saturation(competitor_output)
            if saturation == "RED" and not self._has_clear_wedge(strategist_output, competitor_output):
                issues.append("Competition gate failed: market appears saturated with no clear wedge.")
                pivot = "Market is saturated - need different pain point"

        if sales_output:
            feasibility = self._extract_sales_feasibility(sales_output)
            if feasibility == "DIFFICULT":
                issues.append("Sales feasibility gate failed: founder-led path is marked DIFFICULT.")
                pivot = "Sales feasibility too low - reduce MVP scope or pivot to easier customer acquisition"

        evidence_issue = self._check_evidence_grounding(scout_output=scout_output, analyst_output=analyst_output)
        if evidence_issue:
            issues.append(f"Evidence grounding gate failed: {evidence_issue}")
            pivot = "Evidence mismatch - map each accepted pain to explicit Scout URLs"

        if not domain_shift_authorized and self._is_cross_domain_shift(topic=topic, scout_topic=scout_topic, strategist_output=strategist_output):
            issues.append("Domain lock gate failed: Strategist shifted to an unrelated vertical without pivot authorization.")
            pivot = "Unrelated pivot detected - keep solution inside current domain or explicitly authorize a pivot"

        competitor_price_anchor = self._extract_competitor_price_anchor(competitor_output)
        if (
            competitor_price_anchor is not None
            and price is not None
            and competitor_price_anchor > 0
            and price > (10 * competitor_price_anchor)
            and not self._has_clear_wedge(strategist_output, competitor_output)
        ):
            issues.append(
                "Pricing sanity gate failed: proposed price exceeds 10x competitor anchor without a differentiated wedge."
            )
            pivot = "Pricing anchor mismatch - align to market band or provide explicit differentiation"

        return {"blocked": len(issues) > 0, "issues": issues, "pivot": pivot}

    def _evaluate_b2c_hard_gates(
        self,
        topic: str,
        scout_topic: str,
        scout_output: str,
        analyst_output: str,
        strategist_output: str,
        competitor_output: Optional[str],
        willingness_output: Optional[str],
        domain_shift_authorized: bool,
    ) -> Dict[str, Any]:
        issues: List[str] = []
        pivot = "General market/product fit issues"

        price = self._extract_monthly_price(strategist_output)
        if price is None:
            issues.append("Pricing gate failed: B2C_PLG strategy must include explicit monthly pricing.")
            pivot = "Clarify price band and self-serve packaging"
        elif price < 5 or price > 80:
            issues.append("Pricing gate failed: B2C_PLG monthly price should generally stay in $5-$80 range.")
            pivot = "Price-band mismatch - align to realistic PLG willingness"

        if not self._has_plg_channel(strategist_output):
            issues.append(
                "Acquisition gate failed: B2C_PLG must include at least one self-serve channel (SEO/content/community/product-launch)."
            )
            pivot = "Distribution mismatch - add concrete PLG channel"

        if willingness_output:
            willingness_score = self._extract_willingness_score(willingness_output)
            if willingness_score < 40:
                issues.append("Payment intent gate failed: willingness signal is too weak (<40%) for B2C_PLG.")
                pivot = "Low willingness to pay - improve activation and conversion proof"

        if competitor_output:
            saturation = self._extract_market_saturation(competitor_output)
            if saturation == "RED" and not self._has_clear_wedge(strategist_output, competitor_output):
                issues.append("Competition gate failed: market appears saturated with no clear wedge.")
                pivot = "Market is saturated - focus on a narrower persona/use-case wedge"

        evidence_issue = self._check_evidence_grounding(scout_output=scout_output, analyst_output=analyst_output)
        if evidence_issue:
            issues.append(f"Evidence grounding gate failed: {evidence_issue}")
            pivot = "Evidence mismatch - map each accepted pain to explicit Scout URLs"

        if not domain_shift_authorized and self._is_cross_domain_shift(topic=topic, scout_topic=scout_topic, strategist_output=strategist_output):
            issues.append("Domain lock gate failed: Strategist shifted to an unrelated vertical without pivot authorization.")
            pivot = "Unrelated pivot detected - keep solution inside current domain or explicitly authorize a pivot"

        competitor_price_anchor = self._extract_competitor_price_anchor(competitor_output)
        if (
            competitor_price_anchor is not None
            and price is not None
            and competitor_price_anchor > 0
            and price > (10 * competitor_price_anchor)
            and not self._has_clear_wedge(strategist_output, competitor_output)
        ):
            issues.append(
                "Pricing sanity gate failed: proposed price exceeds 10x competitor anchor without a differentiated wedge."
            )
            pivot = "Pricing anchor mismatch - align to market band or provide explicit differentiation"

        return {"blocked": len(issues) > 0, "issues": issues, "pivot": pivot}

    def _score_pain(self, analyst_output: str) -> float:
        text = (analyst_output or "").lower()
        scores = [float(score) for score in re.findall(r"boring score\s*:\s*(\d+(?:\.\d+)?)", text, flags=re.IGNORECASE)]
        base = (sum(scores) / len(scores)) * 10 if scores else 45.0
        pain_keywords = ["urgent", "blocks", "manual", "compliance", "penalty", "waste of time", "recurring"]
        keyword_hits = sum(1 for keyword in pain_keywords if keyword in text)
        return max(0.0, min(100.0, base + (keyword_hits * 4)))

    def _score_frequency(self, scout_output: str) -> float:
        text = scout_output or ""
        observation_count = len(re.findall(r"^\s*\d+\.", text, flags=re.MULTILINE))
        lowered = text.lower()
        freq_terms = ["daily", "weekly", "recurring", "often", "every", "repeated"]
        freq_hits = sum(1 for term in freq_terms if term in lowered)
        return max(0.0, min(100.0, 30 + (observation_count * 8) + (freq_hits * 4)))

    def _extract_willingness_score(self, willingness_output: Optional[str]) -> float:
        if not willingness_output:
            return 40.0
        text = willingness_output.lower()
        match = re.search(r"price willingness score\s*:\s*(\d+(?:\.\d+)?)\s*%", text, flags=re.IGNORECASE)
        if not match:
            match = re.search(r"willingness score\s*:\s*(\d+(?:\.\d+)?)\s*%", text, flags=re.IGNORECASE)
        if match:
            return max(0.0, min(100.0, float(match.group(1))))
        return 40.0

    def _score_competition(self, competitor_output: Optional[str]) -> float:
        saturation = self._extract_market_saturation(competitor_output)
        if saturation == "GREEN":
            return 80.0
        if saturation == "YELLOW":
            return 65.0
        if saturation == "RED":
            return 30.0
        return 50.0

    def _score_buildability(self, sales_output: Optional[str]) -> float:
        feasibility = self._extract_sales_feasibility(sales_output)
        if feasibility == "VIABLE":
            return 85.0
        if feasibility == "CHALLENGING":
            return 60.0
        if feasibility == "DIFFICULT":
            return 35.0
        return 50.0

    def _score_mode_fit(self, topic_mode: str, strategist_output: str) -> float:
        if topic_mode == "B2B_STRICT":
            return 100.0
        if topic_mode == "B2C_PLG":
            if self._has_plg_channel(strategist_output):
                return 95.0
            return 70.0
        if self._has_budget_owner(strategist_output):
            return 95.0
        return 70.0

    def _extract_market_saturation(self, competitor_output: Optional[str]) -> str:
        if not competitor_output:
            return "UNKNOWN"
        upper = competitor_output.upper()
        if "GREEN" in upper:
            return "GREEN"
        if "YELLOW" in upper:
            return "YELLOW"
        if "RED" in upper:
            return "RED"
        return "UNKNOWN"

    def _extract_sales_feasibility(self, sales_output: Optional[str]) -> str:
        if not sales_output:
            return "UNKNOWN"
        upper = sales_output.upper()
        if "VIABLE" in upper:
            return "VIABLE"
        if "CHALLENGING" in upper:
            return "CHALLENGING"
        if "DIFFICULT" in upper:
            return "DIFFICULT"
        return "UNKNOWN"

    def _extract_monthly_price(self, strategist_output: str) -> Optional[int]:
        text = strategist_output or ""
        monthly_patterns = [
            r"\$(\d+)\s*/\s*(?:month|mo)\b",
            r"\$(\d+)\s*(?:per|/)\s*(?:month|mo)\b",
            r"price point\s*[:\-]?\s*\$(\d+)",
        ]
        for pattern in monthly_patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                return int(match.group(1))

        all_prices = [int(value) for value in re.findall(r"\$(\d+)", text)]
        filtered_prices = [value for value in all_prices if value >= 20]
        if filtered_prices:
            return filtered_prices[0]
        return None

    def _has_budget_owner(self, strategist_output: str) -> bool:
        text = (strategist_output or "").lower()
        budget_terms = [
            "operations manager",
            "owner",
            "head of",
            "director",
            "finance lead",
            "hr manager",
            "small business",
            "agency",
            "clinic",
            "firm",
        ]
        return any(term in text for term in budget_terms)

    def _has_plg_channel(self, strategist_output: str) -> bool:
        text = (strategist_output or "").lower()
        plg_terms = [
            "seo",
            "content",
            "community",
            "product hunt",
            "app store",
            "self-serve",
            "freemium",
            "free trial",
            "template gallery",
            "creator partnerships",
            "social media",
        ]
        return any(term in text for term in plg_terms)

    def _has_clear_wedge(self, strategist_output: str, competitor_output: Optional[str]) -> bool:
        combined = f"{strategist_output}\n{competitor_output or ''}".lower()
        wedge_terms = ["niche", "vertical", "industry-specific", "differentiation", "unique", "wedge", "specialized"]
        return any(term in combined for term in wedge_terms)

    def _format_scorecard(self, scorecard: Dict[str, Any]) -> str:
        return (
            "OPPORTUNITY SCORECARD\n"
            f"- Pain Severity: {scorecard['pain']}/100\n"
            f"- Frequency: {scorecard['frequency']}/100\n"
            f"- Willingness to Pay: {scorecard['willingness']}/100\n"
            f"- Competition Whitespace: {scorecard['competition']}/100\n"
            f"- Buildability: {scorecard['buildability']}/100\n"
            f"- Mode Fit: {scorecard['mode_fit']}/100\n"
            f"- Weighted Score: {scorecard['weighted_score']}/100"
        )

    def _format_hard_gates(self, hard_gates: Dict[str, Any]) -> str:
        if not hard_gates["blocked"]:
            return "HARD GATES: PASS"
        issue_lines = "\n".join(f"- {issue}" for issue in hard_gates["issues"])
        return f"HARD GATES: FAIL\n{issue_lines}\nPivot: {hard_gates['pivot']}"

    def export_results_json(self, filepath: Optional[str] = None) -> str:
        json_output = json.dumps(self.research_results, indent=2)
        if filepath:
            with open(filepath, "w", encoding="utf-8") as output_file:
                output_file.write(json_output)
            print(colored(f"[Orchestrator] Results exported to {filepath}", "green"))
        return json_output
