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
        self.conversation_history: List[Dict[str, str]] = []
        self.iteration_count = 0
        self.research_results: Dict[str, object] = {}
        self._reset_run_state(topic=None)

    def _reset_run_state(self, topic: Optional[str]):
        self.conversation_history = []
        self.iteration_count = 0
        self.research_results = {
            "topic": topic,
            "mode": None,
            "iterations": [],
            "final_verdict": None,
            "final_idea": None,
            "researched_at": datetime.now().isoformat(),
            "iteration_count": 0,
        }

    def broadcast(self, sender_name: str, message: str):
        self.conversation_history.append({"role": sender_name, "content": message})

    def run_round_table(self, initial_topic: str) -> Dict[str, object]:
        self._reset_run_state(topic=initial_topic)
        topic = initial_topic

        print(colored(f"\n{'=' * 60}", "cyan"))
        print(colored(f"=== STARTING INTELLIGENT RESEARCH: {initial_topic.upper()} ===", "cyan"))
        print(colored(f"{'=' * 60}\n", "cyan"))

        for iteration in range(1, self.max_iterations + 1):
            self.iteration_count = iteration
            print(colored(f"\n--- ITERATION {iteration}/{self.max_iterations} ---", "yellow"))
            self.conversation_history = []

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
                self._append_iteration(
                    topic,
                    verdict="NO DATA",
                    topic_mode=topic_mode,
                    scout_topic=scout_topic,
                )
                print(colored("[Orchestrator] Scout failed to collect real data. Iteration abandoned.", "red"))
                continue

            analyst_output = self._run_agent(
                "Pain Analyst",
                (
                    "Analyze these findings for recurring operational pain in a B2B context. "
                    f"Research mode: {topic_mode}. "
                    "Include structured evidence fields: buyer, workflow step, frequency, current workaround, cost of inaction."
                ),
                context=self.conversation_history,
            )
            strategist_output = self._run_agent(
                "SaaS Strategist",
                (
                    "Propose a $5k MRR micro-SaaS solution for the identified problems. "
                    "Target budget-owning buyers and keep monthly pricing high enough for a realistic path to $5k MRR."
                ),
                context=self.conversation_history,
            )

            competitor_output = self._run_optional_agent("Competitor Researcher", "Research competitors for this idea:")
            willingness_output = self._run_optional_agent(
                "Willingness Validator",
                "Validate if target customers will pay for this solution:",
            )
            sales_output = self._run_optional_agent(
                "Founder Sales Validator",
                "Simulate if founders can reach $5k MRR with this idea:",
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
                strategist_output=strategist_output,
                competitor_output=competitor_output,
                willingness_output=willingness_output,
                sales_output=sales_output,
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
                topic = self._next_topic(current_topic=topic, pivot_instruction=pivot)
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
        }
        consumer_terms = {
            "dating",
            "relationship",
            "men",
            "women",
            "sex",
            "fitness",
            "anxiety",
            "parenting",
            "travel",
            "recipe",
            "beauty",
            "game",
        }

        if any(term in lowered for term in b2b_terms):
            return {"mode": "B2B_STRICT", "scout_topic": normalized}

        if any(term in lowered for term in consumer_terms):
            if any(term in lowered for term in {"dating", "relationship", "men", "women", "sex"}):
                scout_topic = "dating and relationship service business operations"
            elif any(term in lowered for term in {"fitness", "beauty", "anxiety"}):
                scout_topic = "wellness service business operations"
            else:
                scout_topic = f"{normalized} service business operations"
            return {"mode": "B2B_ADJACENT", "scout_topic": scout_topic}

        return {"mode": "B2B_DISCOVERY", "scout_topic": f"{normalized} business operations"}

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
        if "willingness" in normalized or "won't pay" in normalized:
            return "Low willingness to pay - raise price point for high-value customers"
        if "feasib" in normalized or "unrealistic" in normalized:
            return "Sales feasibility too low - reduce MVP scope or pivot to easier customer acquisition"
        if "technical" in normalized:
            return "Technical complexity too high - simplify feature set"
        return "General market/product fit issues"

    def _next_topic(self, current_topic: str, pivot_instruction: str) -> str:
        lower_pivot = pivot_instruction.lower()
        if "different pain point" in lower_pivot or "saturated" in lower_pivot:
            return self._suggest_new_topic(current_topic)
        if "budget owner" in lower_pivot:
            return f"{current_topic} for operations managers"
        if "price point" in lower_pivot:
            return f"{current_topic} for high-cost compliance workflows"
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
        strategist_output: str,
        competitor_output: Optional[str],
        willingness_output: Optional[str],
        sales_output: Optional[str],
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
