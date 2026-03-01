import json
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.utils.console import colored

from .agent import Agent


class Orchestrator:
    def __init__(self, agents: Dict[str, Agent], max_iterations: int = 5, interactive_pivots: bool = True):
        self.agents = agents
        self.max_iterations = max_iterations
        self.interactive_pivots = interactive_pivots
        self._domain_shift_authorized_next_iteration = False
        self._seen_scout_fingerprints: Dict[str, int] = {}
        self._topic_history: List[str] = []
        self._pivot_variant_index: Dict[str, int] = {}
        self.conversation_history: List[Dict[str, str]] = []
        self.iteration_count = 0
        self.research_results: Dict[str, object] = {}
        self._reset_run_state(topic=None)

    def _reset_run_state(self, topic: Optional[str]):
        self.conversation_history = []
        self.iteration_count = 0
        self._domain_shift_authorized_next_iteration = False
        self._seen_scout_fingerprints = {}
        self._topic_history = []
        self._pivot_variant_index = {}
        self.research_results = {
            "topic": topic,
            "root_topic": None,
            "intent": None,
            "mode": None,
            "intake_plan": None,
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

    def _prompt_user(self, prompt_text: str, color: str = "yellow") -> str:
        return input(colored(prompt_text, color)).strip()

    def _seed_iteration_context(self, raw_brief: str, intake_plan: Dict[str, Any]) -> None:
        brief_text = (raw_brief or "").strip()
        if brief_text:
            self.broadcast("User Brief", brief_text)
        compact_plan = {
            "intent": intake_plan.get("intent", "MARKET_DISCOVERY"),
            "summary": intake_plan.get("summary", ""),
            "research_mode": intake_plan.get("research_mode", ""),
            "query_seed": intake_plan.get("query_seed", ""),
            "buyer": intake_plan.get("buyer", ""),
            "workflow": intake_plan.get("workflow", ""),
            "pain": intake_plan.get("pain", ""),
            "constraints": intake_plan.get("constraints", []),
            "assumptions": intake_plan.get("assumptions", []),
            "generated_search_queries": intake_plan.get("generated_search_queries", []),
            "confidence": intake_plan.get("confidence", 0.0),
            "clarification_needed": intake_plan.get("clarification_needed", False),
        }
        self.broadcast("Intake Plan", json.dumps(compact_plan))

    def run_round_table(self, initial_topic: str, context: Optional[List[Dict[str, str]]] = None) -> Dict[str, object]:
        self._reset_run_state(topic=initial_topic)
        if context:
            self.conversation_history = context

        intake_output = self._run_optional_agent(
            "Intake Router",
            f"Route and normalize this research request:\n{initial_topic}",
        )
        intake_plan = self._parse_intake_plan(intake_output, raw_topic=initial_topic)

        if (
            self.interactive_pivots
            and intake_plan.get("clarification_needed")
            and intake_plan.get("clarification_question")
        ):
            clarification_question = str(intake_plan.get("clarification_question", "")).strip()
            clarification = self._prompt_user(
                f"[Orchestrator] Intake clarification: {clarification_question} (optional, press Enter to skip): ",
                color="yellow",
            )
            if clarification:
                enriched_topic = f"{initial_topic}; clarification: {clarification}"
                intake_output = self._run_optional_agent(
                    "Intake Router",
                    f"Route and normalize this research request:\n{enriched_topic}",
                )
                intake_plan = self._parse_intake_plan(intake_output, raw_topic=enriched_topic)
            else:
                print(
                    colored(
                        "[Orchestrator] Intake clarification skipped. Continuing with lower-confidence routing.",
                        "yellow",
                    )
                )
                intake_plan["clarification_skipped"] = True
                intake_plan["confidence"] = min(float(intake_plan.get("confidence", 0.55)), 0.35)

        buyer_brief = self._buyer_brief_from_intake_plan(intake_plan) or self._parse_buyer_first_brief(initial_topic)
        topic = self._strip_search_modifiers(
            str(intake_plan.get("normalized_topic", "")).strip()
            or (buyer_brief.get("pain", initial_topic) if buyer_brief else initial_topic)
        )
        intake_intent = str(intake_plan.get("intent", "MARKET_DISCOVERY")).upper().strip()
        
        needs_clarification = not self.interactive_pivots and intake_plan.get("clarification_needed")
        
        if intake_intent == "CONVERSATIONAL" or needs_clarification:
            print(colored("\n[Orchestrator] Conversational or Clarification intent detected. Skipping research loop.", "cyan"))
            
            chat_output = self._run_optional_agent("Chat Bot", initial_topic)
            if not chat_output:
                chat_output = intake_plan.get("clarification_question", "How can I help you refine this idea?")
            
            self.research_results["intent"] = "CONVERSATIONAL"
            self.research_results["final_verdict"] = "CONVERSATIONAL"
            self.research_results["final_recommendation"] = chat_output.replace("[MOCK OUTPUT]", "").strip()
            self._seed_iteration_context(raw_brief=initial_topic, intake_plan=intake_plan)
            return self.research_results

        intake_mode_hint = str(intake_plan.get("research_mode", "")).upper()
        intake_query_seed_hint = str(intake_plan.get("query_seed", "")).strip()
        self._topic_history.append(topic)
        root_topic = self._build_root_topic_seed(initial_topic=initial_topic, buyer_brief=buyer_brief, topic=topic)
        self.research_results["intent"] = intake_intent
        self.research_results["intake_plan"] = intake_plan
        self.research_results["buyer_brief"] = buyer_brief
        self.research_results["root_topic"] = root_topic
        consecutive_no_data = 0

        print(colored(f"\n{'=' * 60}", "cyan"))
        print(colored(f"=== STARTING INTELLIGENT RESEARCH: {initial_topic.upper()} ===", "cyan"))
        print(colored(f"{'=' * 60}\n", "cyan"))

        if intake_intent == "FEASIBILITY_REVIEW":
            return self._run_feasibility_review(
                initial_topic=initial_topic,
                topic=topic,
                intake_plan=intake_plan,
                buyer_brief=buyer_brief,
            )
        if intake_intent == "IDEA_SYNTHESIS":
            return self._run_idea_synthesis(
                initial_topic=initial_topic,
                topic=topic,
                intake_plan=intake_plan,
                buyer_brief=buyer_brief,
            )

        for iteration in range(1, self.max_iterations + 1):
            self.iteration_count = iteration
            domain_shift_authorized = self._domain_shift_authorized_next_iteration
            self._domain_shift_authorized_next_iteration = False
            print(colored(f"\n--- ITERATION {iteration}/{self.max_iterations} ---", "yellow"))
            self.conversation_history = []
            self._seed_iteration_context(raw_brief=initial_topic, intake_plan=intake_plan)

            iteration_buyer_brief = buyer_brief or self._parse_buyer_first_brief(topic)
            if iteration_buyer_brief:
                topic_mode = "B2B_BUYER_FIRST"
                scout_topic = self._build_buyer_first_scout_topic(
                    buyer_brief=iteration_buyer_brief,
                    pain_focus=topic,
                )
            else:
                mode_override = intake_mode_hint if iteration == 1 else ""
                topic_plan = self._classify_topic_mode(topic, preferred_mode=mode_override)
                topic_mode = topic_plan["mode"]
                scout_topic = topic_plan["scout_topic"]
            self.research_results["mode"] = topic_mode
            print(
                colored(
                    f"[Orchestrator] Research mode: {topic_mode} | Scout topic: {scout_topic}",
                    "yellow",
                )
            )

            scout_prompt = f"Find complaints and issues related to: {scout_topic}\nResearch mode: {topic_mode}"
            if iteration == 1 and intake_query_seed_hint:
                scout_prompt += f"\nQuery seed hint: {intake_query_seed_hint}"
                
            generated_queries = intake_plan.get("generated_search_queries")
            if iteration == 1 and generated_queries:
                 scout_prompt += f"\n\n[GENERATED QUERIES]\n{generated_queries}\n[END QUERIES]"

            scout_output = self._run_agent(
                "Trend Scout",
                scout_prompt,
            )
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
                    topic = self._strip_search_modifiers(recovered_topic)
                continue
            consecutive_no_data = 0

            scout_fingerprint = self._build_scout_fingerprint(scout_topic=scout_topic, scout_output=scout_output)
            if self._is_repeated_scout_cycle(scout_fingerprint):
                hard_gates = {
                    "blocked": True,
                    "issues": ["Loop gate failed: Scout evidence fingerprint repeated across iterations."],
                    "pivot": "Repeated scout evidence - diversify persona/use-case before continuing",
                }
                self._append_iteration(
                    topic,
                    verdict="NO GO",
                    topic_mode=topic_mode,
                    scout_topic=scout_topic,
                    scorecard=self._build_low_evidence_scorecard(scout_output),
                    hard_gates=hard_gates,
                )
                print(colored("[Orchestrator] Repeated scout evidence detected. Forcing diversification pivot.", "red"))
                topic = self._next_topic(
                    current_topic=topic,
                    pivot_instruction=hard_gates["pivot"],
                    topic_mode=topic_mode,
                    root_topic=root_topic,
                )
                continue

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
                    root_topic=root_topic,
                )
                continue

            analyst_prompt = self._analyst_prompt_for_mode(topic_mode=topic_mode, buyer_brief=iteration_buyer_brief)
            analyst_output = self._run_agent(
                "Pain Analyst",
                analyst_prompt,
                context=self.conversation_history,
            )
            strategist_prompt = self._strategist_prompt_for_mode(
                topic_mode=topic_mode,
                buyer_brief=iteration_buyer_brief,
            )
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
            verdict = self._apply_soft_verdict_override(
                verdict=verdict,
                hard_gates=hard_gates,
                scorecard=opportunity,
                skeptic_output=skeptic_output,
            )
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
                topic = self._next_topic(
                    current_topic=topic,
                    pivot_instruction=pivot,
                    topic_mode=topic_mode,
                    root_topic=root_topic,
                )
            else:
                print(colored(f"[Orchestrator] Unclear verdict: {verdict}. Retrying.", "yellow"))

        print(colored(f"\n[WARNING] Reached max iterations ({self.max_iterations}). Stopping research.", "red"))
        self.research_results["final_verdict"] = "NO_QUALIFIED_IDEA"
        self.research_results["iteration_count"] = self.iteration_count
        return self.research_results

    def _run_feasibility_review(
        self,
        initial_topic: str,
        topic: str,
        intake_plan: Dict[str, Any],
        buyer_brief: Optional[Dict[str, str]],
    ) -> Dict[str, object]:
        self.iteration_count = 1
        self.conversation_history = []
        self._seed_iteration_context(raw_brief=initial_topic, intake_plan=intake_plan)

        topic_mode = str(intake_plan.get("research_mode", "")).upper().strip()
        if topic_mode not in {"B2C_PLG", "B2B_STRICT", "B2B_DISCOVERY", "B2B_BUYER_FIRST"}:
            topic_mode = self._classify_topic_mode(topic).get("mode", "B2B_DISCOVERY")
        self.research_results["mode"] = topic_mode

        print(colored("\n--- FEASIBILITY REVIEW 1/1 ---", "yellow"))
        print(colored(f"[Orchestrator] Review mode: {topic_mode} | Intent: FEASIBILITY_REVIEW", "yellow"))

        feasibility_brief = (
            f"Intent: FEASIBILITY_REVIEW\n"
            f"Summary: {intake_plan.get('summary', topic)}\n"
            f"Constraints: {intake_plan.get('constraints', [])}\n"
            f"Assumptions: {intake_plan.get('assumptions', [])}\n"
            f"Raw Brief: {initial_topic}"
        )
        self.broadcast("Feasibility Brief", feasibility_brief)

        analyst_output = self._run_agent(
            "Pain Analyst",
            self._feasibility_analyst_prompt(topic_mode=topic_mode),
            context=self.conversation_history,
        )
        strategist_output = self._run_agent(
            "SaaS Strategist",
            self._feasibility_strategist_prompt(topic_mode=topic_mode, buyer_brief=buyer_brief),
            context=self.conversation_history,
        )

        competitor_output = self._run_optional_agent("Competitor Researcher", "Research competitors for this idea:")
        willingness_output = self._run_optional_agent(
            "Willingness Validator",
            "Evaluate willingness-to-pay and price realism for this feasibility brief:",
        )
        sales_output = self._run_optional_agent(
            "Founder Sales Validator",
            self._sales_prompt_for_mode(topic_mode=topic_mode),
        )

        opportunity = self._build_opportunity_scorecard(
            topic_mode=topic_mode,
            scout_output=feasibility_brief,
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
            scout_topic=topic,
            scout_output=feasibility_brief,
            analyst_output=analyst_output,
            strategist_output=strategist_output,
            competitor_output=competitor_output,
            willingness_output=willingness_output,
            sales_output=sales_output,
            domain_shift_authorized=True,
            topic_mode=topic_mode if topic_mode != "B2B_BUYER_FIRST" else "B2B_STRICT",
        )
        gate_text = self._format_hard_gates(hard_gates)
        self.broadcast("Gatekeeper", gate_text)

        skeptic_output = self._run_agent(
            "The Skeptic",
            (
                "Make final GO/NO GO decision based on the feasibility review context, "
                "scorecard, and hard gates below.\n\n"
                f"[OPPORTUNITY SCORECARD]\n{scorecard_text}\n[END SCORECARD]\n\n"
                f"[HARD GATES]\n{gate_text}\n[END HARD GATES]\n"
            ),
            context=self.conversation_history,
        )

        verdict = self._parse_verdict(skeptic_output)
        verdict = self._apply_soft_verdict_override(
            verdict=verdict,
            hard_gates=hard_gates,
            scorecard=opportunity,
            skeptic_output=skeptic_output,
        )
        if hard_gates["blocked"]:
            print(colored("[Orchestrator] Hard gate failed. Forcing NO GO.", "red"))
            verdict = "NO GO"

        self._append_iteration(
            topic=topic,
            verdict=verdict,
            topic_mode=topic_mode,
            scout_topic=f"[FEASIBILITY] {topic}",
            scorecard=opportunity,
            hard_gates=hard_gates,
        )

        if verdict in {"GO", "QUALIFIED"} and not hard_gates["blocked"]:
            print(colored("\n[SUCCESS] FEASIBILITY REVIEW QUALIFIED.", "green"))
            self.research_results["final_verdict"] = verdict
            self.research_results["final_idea"] = strategist_output
        else:
            pivot = hard_gates["pivot"] if hard_gates["blocked"] else self._extract_pivot_instruction(skeptic_output)
            self.research_results["final_verdict"] = "NO GO"
            self.research_results["final_recommendation"] = pivot
            print(colored(f"\n[REJECTED] Feasibility not qualified. Reason: {pivot}", "red"))

        self.research_results["iteration_count"] = 1
        return self.research_results

    def _run_idea_synthesis(
        self,
        initial_topic: str,
        topic: str,
        intake_plan: Dict[str, Any],
        buyer_brief: Optional[Dict[str, str]],
    ) -> Dict[str, object]:
        self.iteration_count = 1
        self.conversation_history = []
        self._seed_iteration_context(raw_brief=initial_topic, intake_plan=intake_plan)

        topic_mode = str(intake_plan.get("research_mode", "")).upper().strip()
        if topic_mode not in {"B2C_PLG", "B2B_STRICT", "B2B_DISCOVERY", "B2B_BUYER_FIRST"}:
            topic_mode = self._classify_topic_mode(topic).get("mode", "B2B_DISCOVERY")
        self.research_results["mode"] = topic_mode

        print(colored("\n--- IDEA SYNTHESIS 1/1 ---", "yellow"))
        print(colored(f"[Orchestrator] Synthesis mode: {topic_mode} | Intent: IDEA_SYNTHESIS", "yellow"))

        synthesis_brief = (
            f"Intent: IDEA_SYNTHESIS\n"
            f"Summary: {intake_plan.get('summary', topic)}\n"
            f"Constraints: {intake_plan.get('constraints', [])}\n"
            f"Assumptions: {intake_plan.get('assumptions', [])}\n"
            f"Raw Brief: {initial_topic}"
        )
        self.broadcast("Synthesis Brief", synthesis_brief)

        analyst_output = self._run_agent(
            "Pain Analyst",
            "Idea synthesis mode: identify the strongest recurring pain and buyer/workflow angle from the brief.",
            context=self.conversation_history,
        )
        strategist_output = self._run_agent(
            "SaaS Strategist",
            "Idea synthesis mode: propose the best 30-day executable concept with clear pricing and acquisition.",
            context=self.conversation_history,
        )
        competitor_output = self._run_optional_agent("Competitor Researcher", "Research competitors for this idea:")
        willingness_output = self._run_optional_agent(
            "Willingness Validator",
            "Estimate willingness-to-pay and pricing fit for this synthesized concept:",
        )
        sales_output = self._run_optional_agent(
            "Founder Sales Validator",
            self._sales_prompt_for_mode(topic_mode=topic_mode),
        )

        opportunity = self._build_opportunity_scorecard(
            topic_mode=topic_mode,
            scout_output=synthesis_brief,
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
            scout_topic=topic,
            scout_output=synthesis_brief,
            analyst_output=analyst_output,
            strategist_output=strategist_output,
            competitor_output=competitor_output,
            willingness_output=willingness_output,
            sales_output=sales_output,
            domain_shift_authorized=True,
            topic_mode=topic_mode if topic_mode != "B2B_BUYER_FIRST" else "B2B_STRICT",
        )
        gate_text = self._format_hard_gates(hard_gates)
        self.broadcast("Gatekeeper", gate_text)

        skeptic_output = self._run_agent(
            "The Skeptic",
            (
                "Make final GO/NO GO decision based on idea synthesis outputs, "
                "scorecard, and hard gates below.\n\n"
                f"[OPPORTUNITY SCORECARD]\n{scorecard_text}\n[END SCORECARD]\n\n"
                f"[HARD GATES]\n{gate_text}\n[END HARD GATES]\n"
            ),
            context=self.conversation_history,
        )

        verdict = self._parse_verdict(skeptic_output)
        verdict = self._apply_soft_verdict_override(
            verdict=verdict,
            hard_gates=hard_gates,
            scorecard=opportunity,
            skeptic_output=skeptic_output,
        )
        if hard_gates["blocked"]:
            print(colored("[Orchestrator] Hard gate failed. Forcing NO GO.", "red"))
            verdict = "NO GO"

        self._append_iteration(
            topic=topic,
            verdict=verdict,
            topic_mode=topic_mode,
            scout_topic=f"[SYNTHESIS] {topic}",
            scorecard=opportunity,
            hard_gates=hard_gates,
        )

        if verdict in {"GO", "QUALIFIED"} and not hard_gates["blocked"]:
            print(colored("\n[SUCCESS] IDEA SYNTHESIS QUALIFIED.", "green"))
            self.research_results["final_verdict"] = verdict
            self.research_results["final_idea"] = strategist_output
        else:
            pivot = hard_gates["pivot"] if hard_gates["blocked"] else self._extract_pivot_instruction(skeptic_output)
            self.research_results["final_verdict"] = "NO GO"
            self.research_results["final_recommendation"] = pivot
            print(colored(f"\n[REJECTED] Idea synthesis not qualified. Reason: {pivot}", "red"))

        self.research_results["iteration_count"] = 1
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

    def _classify_topic_mode(self, topic: str, preferred_mode: str = "") -> Dict[str, str]:
        normalized = (topic or "").strip()
        lowered = normalized.lower()
        preferred = (preferred_mode or "").upper().strip()

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
            "home",
            "homeowner",
            "homeowners",
            "appliance",
            "appliances",
            "household",
            "consumer",
            "diy",
            "repair",
            "portfolio",
            "resume",
            "linkedin",
        }

        b2b_hits = sum(1 for term in b2b_terms if term in lowered)
        b2c_hits = sum(1 for term in b2c_plg_terms if term in lowered)

        if preferred in {"B2C_PLG", "B2B_STRICT", "B2B_DISCOVERY"}:
            if preferred == "B2C_PLG":
                scout_topic = f"{normalized} user complaints feature requests alternatives"
                return {"mode": "B2C_PLG", "scout_topic": scout_topic}
            if preferred == "B2B_DISCOVERY":
                return {"mode": "B2B_DISCOVERY", "scout_topic": f"{normalized} business operations"}
            return {"mode": "B2B_STRICT", "scout_topic": normalized}

        # If the only B2B cue is generic wording (often "saas"), prefer B2C_PLG when consumer terms are present.
        if b2c_hits > 0 and b2b_hits <= 1:
            scout_topic = f"{normalized} user complaints feature requests alternatives"
            return {"mode": "B2C_PLG", "scout_topic": scout_topic}

        if b2b_hits > 0:
            return {"mode": "B2B_STRICT", "scout_topic": normalized}

        if b2c_hits > 0:
            scout_topic = f"{normalized} user complaints feature requests alternatives"
            return {"mode": "B2C_PLG", "scout_topic": scout_topic}

        return {"mode": "B2B_DISCOVERY", "scout_topic": f"{normalized} business operations"}

    def _parse_intake_plan(self, intake_output: Optional[str], raw_topic: str) -> Dict[str, Any]:
        fallback = self._default_intake_plan(raw_topic)
        if not intake_output:
            return fallback

        text = intake_output.strip()
        payload_text = text

        fenced = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text, flags=re.IGNORECASE)
        if fenced:
            payload_text = fenced.group(1)
        else:
            object_match = re.search(r"(\{[\s\S]*\})", text)
            if object_match:
                payload_text = object_match.group(1)

        try:
            parsed = json.loads(payload_text)
        except (json.JSONDecodeError, TypeError):
            return fallback

        if not isinstance(parsed, dict):
            return fallback

        plan = dict(fallback)
        for key in [
            "intent",
            "summary",
            "research_mode",
            "normalized_topic",
            "buyer",
            "workflow",
            "pain",
            "vertical",
            "query_seed",
            "clarification_question",
        ]:
            value = parsed.get(key)
            if isinstance(value, str):
                plan[key] = value.strip()
                
        # Handle the new generated_search_queries array
        generated_queries = parsed.get("generated_search_queries")
        if isinstance(generated_queries, list):
             plan["generated_search_queries"] = [str(q).strip() for q in generated_queries if str(q).strip()]

        for key in ["constraints", "assumptions", "must_include_terms", "must_exclude_terms", "source_priority"]:
            value = parsed.get(key)
            if isinstance(value, list):
                plan[key] = [str(item).strip() for item in value if str(item).strip()]

        clarification_needed = parsed.get("clarification_needed")
        if isinstance(clarification_needed, bool):
            plan["clarification_needed"] = clarification_needed
        elif isinstance(clarification_needed, str):
            plan["clarification_needed"] = clarification_needed.strip().lower() in {"1", "true", "yes", "y"}
        else:
            plan["clarification_needed"] = bool(clarification_needed)

        confidence = parsed.get("confidence")
        if isinstance(confidence, (int, float)):
            plan["confidence"] = max(0.0, min(1.0, float(confidence)))
        elif isinstance(confidence, str):
            try:
                plan["confidence"] = max(0.0, min(1.0, float(confidence.strip())))
            except ValueError:
                pass

        if not plan["query_seed"]:
            plan["query_seed"] = self._compact_query_seed(plan["normalized_topic"] or raw_topic)
        if not plan["normalized_topic"]:
            plan["normalized_topic"] = raw_topic
        if not plan.get("summary"):
            plan["summary"] = (plan["normalized_topic"] or raw_topic)[:260]
        intent = str(plan.get("intent", "MARKET_DISCOVERY")).upper().strip()
        if intent not in {"FEASIBILITY_REVIEW", "MARKET_DISCOVERY", "IDEA_SYNTHESIS", "CONVERSATIONAL"}:
            intent = "MARKET_DISCOVERY"
        plan["intent"] = intent

        return plan

    def _default_intake_plan(self, raw_topic: str) -> Dict[str, Any]:
        mode = self._classify_topic_mode(raw_topic).get("mode", "B2B_DISCOVERY")
        normalized_topic = self._strip_search_modifiers(raw_topic)
        return {
            "intent": "MARKET_DISCOVERY",
            "summary": normalized_topic[:260],
            "constraints": [],
            "assumptions": [],
            "research_mode": mode,
            "normalized_topic": normalized_topic,
            "buyer": "",
            "workflow": "",
            "pain": "",
            "vertical": "",
            "query_seed": self._compact_query_seed(normalized_topic),
            "must_include_terms": [],
            "must_exclude_terms": [],
            "source_priority": ["reddit", "forums", "reviews", "hackernews", "web"],
            "clarification_needed": False,
            "clarification_question": "",
            "confidence": 0.55,
        }

    def _buyer_brief_from_intake_plan(self, intake_plan: Dict[str, Any]) -> Optional[Dict[str, str]]:
        buyer = str(intake_plan.get("buyer", "")).strip()
        workflow = str(intake_plan.get("workflow", "")).strip()
        pain = str(intake_plan.get("pain", "")).strip()
        vertical = str(intake_plan.get("vertical", "")).strip()
        if not buyer or not workflow:
            return None
        return {
            "buyer": buyer,
            "workflow": workflow,
            "pain": pain or "recurring operational bottlenecks",
            "vertical": vertical,
        }

    def _compact_query_seed(self, topic: str, max_terms: int = 12) -> str:
        tokens = re.findall(r"[a-z0-9]+", (topic or "").lower())
        if not tokens:
            return topic

        stop_words = {
            "the",
            "and",
            "for",
            "with",
            "from",
            "into",
            "via",
            "user",
            "users",
            "complaints",
            "feature",
            "features",
            "requests",
            "alternatives",
            "pain",
            "workflow",
            "business",
            "operations",
        }
        selected: List[str] = []
        seen = set()
        for token in tokens:
            if len(token) <= 2 or token in stop_words or token in seen:
                continue
            seen.add(token)
            selected.append(token)
            if len(selected) >= max_terms:
                break
        return " ".join(selected) if selected else " ".join(tokens[:max_terms])

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
            "vertical": parsed.get("vertical", ""),
        }

    def _build_buyer_first_scout_topic(self, buyer_brief: Dict[str, str], pain_focus: str) -> str:
        buyer = buyer_brief.get("buyer", "").strip()
        workflow = buyer_brief.get("workflow", "").strip()
        vertical = buyer_brief.get("vertical", "").strip()
        pain = (pain_focus or buyer_brief.get("pain", "")).strip()
        parts = [buyer, vertical, workflow, pain]
        return re.sub(r"\s+", " ", " ".join(part for part in parts if part)).strip()

    def _format_buyer_brief(self, buyer_brief: Optional[Dict[str, str]]) -> str:
        if not buyer_brief:
            return "None"
        buyer = buyer_brief.get("buyer", "unknown")
        workflow = buyer_brief.get("workflow", "unknown")
        pain = buyer_brief.get("pain", "unknown")
        return f"buyer={buyer}; workflow={workflow}; pain={pain}"

    def _build_root_topic_seed(self, initial_topic: str, buyer_brief: Optional[Dict[str, str]], topic: str) -> str:
        if buyer_brief:
            buyer = buyer_brief.get("buyer", "")
            vertical = buyer_brief.get("vertical", "")
            workflow = buyer_brief.get("workflow", "")
            pain = buyer_brief.get("pain", topic)
            seed = f"{buyer} {vertical} {workflow} {pain}".strip()
            return self._normalize_topic_phrase(seed)
        return self._normalize_topic_phrase(initial_topic or topic)

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

    def _feasibility_analyst_prompt(self, topic_mode: str) -> str:
        return (
            "Feasibility review mode. Use the User Brief and Feasibility Brief context as the primary source. "
            f"Research mode: {topic_mode}. "
            "Extract top risks, weak assumptions, missing validation evidence, and economic blockers. "
            "Provide a structured list of what is validated vs speculative."
        )

    def _feasibility_strategist_prompt(self, topic_mode: str, buyer_brief: Optional[Dict[str, str]]) -> str:
        return (
            "Feasibility review mode. Rewrite the proposed concept into the most realistic executable plan. "
            f"Research mode: {topic_mode}. Buyer Brief: {self._format_buyer_brief(buyer_brief)}. "
            "If assumptions are weak, explicitly pivot business model, target segment, or pricing. "
            "Output must include pricing, acquisition channel, and budget owner where applicable."
        )

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

    def _apply_soft_verdict_override(
        self,
        verdict: str,
        hard_gates: Dict[str, Any],
        scorecard: Dict[str, Any],
        skeptic_output: str,
    ) -> str:
        if verdict != "NO GO":
            return verdict
        if hard_gates.get("blocked"):
            return verdict

        weighted_score = float(scorecard.get("weighted_score", 0.0) or 0.0)
        skeptic_text = (skeptic_output or "").lower()
        saturation_focus = "saturat" in skeptic_text

        if saturation_focus and weighted_score >= 55:
            print(
                colored(
                    "[Orchestrator] Soft override: saturation-only NO GO downgraded to QUALIFIED.",
                    "yellow",
                )
            )
            return "QUALIFIED"

        return verdict

    def _extract_pivot_instruction(self, skeptic_output: str) -> str:
        normalized = (skeptic_output or "").lower()
        if "saturated" in normalized:
            return "Market is saturated - need different pain point"
        if "insufficient evidence" in normalized or "no evidence" in normalized:
            return "Insufficient evidence - pivot to adjacent workflow pain point"
        if "willingness" in normalized or "won't pay" in normalized:
            return "Low willingness to pay - raise price point for high-value customers"
        if "low frequency" in normalized or "rare usage" in normalized:
            return "Low frequency B2C usage - pivot to B2B2C budget owner"
        if "feasib" in normalized or "unrealistic" in normalized:
            return "Sales feasibility too low - reduce MVP scope or pivot to easier customer acquisition"
        if "technical" in normalized:
            return "Technical complexity too high - simplify feature set"
        return "General market/product fit issues"

    def _next_topic(
        self,
        current_topic: str,
        pivot_instruction: str,
        topic_mode: Optional[str] = None,
        root_topic: Optional[str] = None,
    ) -> str:
        active_mode = topic_mode or self._classify_topic_mode(current_topic)["mode"]
        base_topic = self._strip_search_modifiers(self._normalize_topic_phrase(root_topic or current_topic))
        current_topic = self._strip_search_modifiers(self._normalize_topic_phrase(current_topic))
        lower_pivot = pivot_instruction.lower()
        if "different pain point" in lower_pivot or "saturated" in lower_pivot:
            self._domain_shift_authorized_next_iteration = True
            candidate = self._suggest_new_topic(
                current_topic=current_topic,
                root_topic=base_topic,
                topic_mode=active_mode,
                reason="SATURATED_MARKET",
            )
            return self._finalize_next_topic(candidate, current_topic=current_topic, root_topic=base_topic, topic_mode=active_mode)
        if "insufficient evidence" in lower_pivot or "no evidence" in lower_pivot:
            self._domain_shift_authorized_next_iteration = True
            recovered = self._recover_topic_after_no_data(topic=base_topic, topic_mode=active_mode)
            return self._finalize_next_topic(recovered, current_topic=current_topic, root_topic=base_topic, topic_mode=active_mode)
        if "repeated scout evidence" in lower_pivot:
            self._domain_shift_authorized_next_iteration = True
            candidate = self._suggest_new_topic(
                current_topic=current_topic,
                root_topic=base_topic,
                topic_mode=active_mode,
                reason="REPEATED_SCOUT_EVIDENCE",
            )
            return self._finalize_next_topic(candidate, current_topic=current_topic, root_topic=base_topic, topic_mode=active_mode)
        if "budget owner" in lower_pivot:
            self._domain_shift_authorized_next_iteration = False
            return self._finalize_next_topic(
                self._merge_root_with_modifier(base_topic, "for budget-owning operators"),
                current_topic=current_topic,
                root_topic=base_topic,
                topic_mode=active_mode,
            )
        if "price point" in lower_pivot:
            if active_mode == "B2C_PLG":
                self._domain_shift_authorized_next_iteration = True
                candidate = self._suggest_business_model_pivot(base_topic, reason="LOW_WILLINGNESS")
                return self._finalize_next_topic(candidate, current_topic=current_topic, root_topic=base_topic, topic_mode=active_mode)
            self._domain_shift_authorized_next_iteration = False
            return self._finalize_next_topic(
                self._merge_root_with_modifier(base_topic, "for budget-owning operators"),
                current_topic=current_topic,
                root_topic=base_topic,
                topic_mode=active_mode,
            )
        if ("low frequency" in lower_pivot or "b2b2c" in lower_pivot) and active_mode == "B2C_PLG":
            self._domain_shift_authorized_next_iteration = True
            candidate = self._suggest_business_model_pivot(base_topic, reason="LOW_FREQUENCY")
            return self._finalize_next_topic(candidate, current_topic=current_topic, root_topic=base_topic, topic_mode=active_mode)
        if "willingness" in lower_pivot and active_mode == "B2C_PLG":
            self._domain_shift_authorized_next_iteration = True
            candidate = self._suggest_business_model_pivot(base_topic, reason="LOW_WILLINGNESS")
            return self._finalize_next_topic(candidate, current_topic=current_topic, root_topic=base_topic, topic_mode=active_mode)
        self._domain_shift_authorized_next_iteration = False
        fallback = current_topic
        if self._is_generic_pivot(fallback):
            fallback = self._suggest_vertical_pivot(root_topic=base_topic, topic_mode=active_mode)
        return self._finalize_next_topic(fallback, current_topic=current_topic, root_topic=base_topic, topic_mode=active_mode)

    def _suggest_new_topic(
        self,
        current_topic: str,
        root_topic: Optional[str] = None,
        topic_mode: str = "B2B_DISCOVERY",
        reason: str = "",
    ) -> str:
        base_topic = self._normalize_topic_phrase(root_topic or current_topic)
        topic_pivots = {
            "junior react developers": "senior developers managing juniors",
            "cto software agency": "small software agency operation efficiency",
            "freelancer productivity": "freelancer project management",
            "small business accounting": "contractor tax compliance",
            "dating and relationship service business operations": "therapy clinic intake and scheduling operations",
            "wellness service business operations": "clinic documentation and follow-up operations",
        }

        if reason.upper() == "SATURATED_MARKET":
            pivot = self._suggest_vertical_pivot(root_topic=base_topic, topic_mode=topic_mode)
        elif reason.upper() == "REPEATED_SCOUT_EVIDENCE":
            if topic_mode == "B2C_PLG":
                pivot = self._suggest_vertical_pivot(root_topic=base_topic, topic_mode=topic_mode)
            else:
                pivot = self._merge_root_with_modifier(base_topic, "for a different workflow bottleneck")
        else:
            pivot = topic_pivots.get(base_topic.lower())
            if not pivot:
                pivot = self._merge_root_with_modifier(base_topic, "workflow bottlenecks for a specific vertical")

        if self._is_generic_pivot(pivot):
            pivot = self._suggest_vertical_pivot(root_topic=base_topic, topic_mode=topic_mode)

        if not self.interactive_pivots:
            return self._normalize_topic_phrase(pivot)

        new_topic = self._prompt_user(
            f"\n[Orchestrator] Suggested pivot: '{pivot}'. Enter new topic or press Enter to accept: ",
            color="yellow",
        )
        selected = new_topic if new_topic else pivot
        if self._is_generic_pivot(selected):
            selected = self._suggest_vertical_pivot(root_topic=base_topic, topic_mode=topic_mode)
        return self._normalize_topic_phrase(selected)

    def _recover_topic_after_no_data(self, topic: str, topic_mode: str) -> str:
        compacted = self._compact_topic_terms(topic)

        if topic_mode == "B2C_PLG":
            recovered = f"{compacted} for a narrower persona with recurring usage"
        elif topic_mode == "B2B_STRICT":
            recovered = f"{compacted} workflow bottlenecks"
        else:
            recovered = f"{compacted} operations workflow pain points"

        recovered = re.sub(r"\s+", " ", recovered).strip()
        if recovered.lower() == topic.lower():
            recovered = f"{compacted} manual process pain points"
        return recovered

    def _merge_root_with_modifier(self, root_topic: str, modifier: str) -> str:
        compacted_root = self._compact_topic_terms(root_topic)
        merged = f"{compacted_root} {modifier}".strip()
        return self._normalize_topic_phrase(merged)

    def _normalize_topic_phrase(self, topic: str, max_terms: int = 14) -> str:
        raw = re.sub(r"\s+", " ", (topic or "").strip())
        if not raw:
            return raw
        if (
            re.search(r"\bbuyer\s*:", raw, flags=re.IGNORECASE)
            and re.search(r"\bworkflow\s*:", raw, flags=re.IGNORECASE)
            and re.search(r"\bpain\s*:", raw, flags=re.IGNORECASE)
        ):
            return raw

        for phrase in [
            "internal operations workflow",
            "operations workflow pain points",
            "compliance and documentation workflow",
        ]:
            pattern = rf"(?:\b{re.escape(phrase)}\b(?:\s+|$)){{2,}}"
            raw = re.sub(pattern, f"{phrase} ", raw, flags=re.IGNORECASE).strip()

        tokens = re.findall(r"[a-z0-9]+", raw.lower())
        if not tokens:
            return raw

        filler_tokens = {"internal", "operations", "operation", "workflow", "workflows", "process", "processes"}
        normalized_tokens: List[str] = []
        previous = ""
        filler_seen = set()
        for token in tokens:
            if token == previous:
                continue
            previous = token
            if token in filler_tokens:
                if token in filler_seen:
                    continue
                filler_seen.add(token)
            normalized_tokens.append(token)

        if len(normalized_tokens) > max_terms:
            normalized_tokens = self._compact_topic_terms(" ".join(normalized_tokens), max_terms=max_terms).split()
        return " ".join(normalized_tokens).strip()

    def _is_generic_pivot(self, topic: str) -> bool:
        lowered = (topic or "").lower()
        generic_markers = [
            "internal operations workflow",
            "operations workflow operations workflow",
            "workflow workflow",
            "compliance and documentation workflow",
        ]
        if any(marker in lowered for marker in generic_markers):
            return True

        tokens = re.findall(r"[a-z0-9]+", lowered)
        if not tokens:
            return False
        repetitive = len(tokens) - len(set(tokens))
        return repetitive >= max(3, len(tokens) // 3)

    def _suggest_vertical_pivot(self, root_topic: str, topic_mode: str) -> str:
        root = self._compact_topic_terms(root_topic, max_terms=6)
        root_tokens = set(re.findall(r"[a-z0-9]+", root.lower()))

        if root_tokens & {"invoice", "invoices", "accounts", "payable", "ap"}:
            buyer = "operations leads at specialized service firms"
            vertical = "construction subcontractors"
            workflow = "invoice approval and reconciliation"
            pain = "manual invoice matching and delayed approvals"
        elif root_tokens & {"dental", "clinic", "inventory"}:
            buyer = "practice managers"
            vertical = "multi-location dental clinics"
            workflow = "inventory reorder and stock reconciliation"
            pain = "stockouts and manual reorder tracking"
        elif root_tokens & {"insurance", "claim", "adjuster", "adjusters"}:
            buyer = "independent insurance adjusters"
            vertical = "property and casualty claims"
            workflow = "claim documentation and evidence packaging"
            pain = "fragmented evidence and repetitive claim writeups"
        elif root_tokens & {"cpa", "tax", "accounting"}:
            buyer = "partners at small CPA firms"
            vertical = "tax and bookkeeping practices"
            workflow = "client document collection and deadline follow-up"
            pain = "missing client files and repeated reminder chasing"
        elif root_tokens & {"appliance", "appliances", "homeowner", "homeowners", "repair"}:
            buyer = "home warranty operations leads"
            vertical = "residential appliance support"
            workflow = "appliance issue triage and maintenance follow-up"
            pain = "manual model lookup and inconsistent troubleshooting notes"
        else:
            buyer = "operations leads"
            vertical = "niche service businesses"
            workflow = "recurring back-office workflow"
            pain = f"manual steps around {root}"

        if topic_mode == "B2C_PLG":
            variants = self._b2c_persona_variants(root=root, root_tokens=root_tokens)
            key = root or "b2c_root"
            index = self._pivot_variant_index.get(key, 0)
            self._pivot_variant_index[key] = index + 1
            return variants[index % len(variants)]
        return f"buyer: {buyer}; vertical: {vertical}; workflow: {workflow}; pain: {pain}"

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
            "a",
            "an",
            "specific",
            "persona",
            "explicit",
            "switching",
            "triggers",
            "user",
            "complaints",
            "feature",
            "features",
            "requests",
            "alternatives",
            "narrower",
            "segment",
            "higher",
            "repeat",
            "usage",
            "hooks",
            "activation",
            "conversion",
        }
        selected: List[str] = []
        seen = set()
        for token in tokens:
            if len(token) <= 1:
                continue
            if token in seen or token in stop_words:
                continue
            seen.add(token)
            selected.append(token)
            if len(selected) >= max_terms:
                break
        return " ".join(selected) if selected else " ".join(tokens[:max_terms])

    def _strip_search_modifiers(self, topic: str) -> str:
        text = re.sub(r"\s+", " ", (topic or "").strip()).lower()
        if not text:
            return text
        patterns = [
            r"\buser complaints\b",
            r"\bfeature requests?\b",
            r"\balternatives?\b",
            r"\bswitching triggers?\b",
            r"\bproblems complaints issues\b",
        ]
        cleaned = text
        for pattern in patterns:
            cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return self._normalize_topic_phrase(cleaned) if cleaned else text

    def _build_scout_fingerprint(self, scout_topic: str, scout_output: str) -> str:
        normalized_topic = " ".join(re.findall(r"[a-z0-9]+", (scout_topic or "").lower()))
        urls = self._extract_urls(scout_output)
        domains: List[str] = []
        for url in urls:
            domain_match = re.search(r"https?://([^/\s]+)", url, flags=re.IGNORECASE)
            if not domain_match:
                continue
            domain = domain_match.group(1).lower().replace("www.", "")
            domains.append(domain)
            if len(domains) >= 3:
                break
        domain_part = ",".join(domains) if domains else "no-domain"
        return f"{normalized_topic}|{domain_part}"

    def _is_repeated_scout_cycle(self, fingerprint: str) -> bool:
        count = self._seen_scout_fingerprints.get(fingerprint, 0) + 1
        self._seen_scout_fingerprints[fingerprint] = count
        return count > 1

    def _suggest_business_model_pivot(self, root_topic: str, reason: str = "LOW_WILLINGNESS") -> str:
        root = self._compact_topic_terms(root_topic, max_terms=7)
        tokens = set(re.findall(r"[a-z0-9]+", root.lower()))
        if tokens & {"appliance", "appliances", "home", "homeowner", "homeowners", "repair"}:
            return (
                "buyer: property managers; vertical: residential rentals; "
                "workflow: appliance issue triage and vendor dispatch; "
                "pain: repeated technician dispatch costs and tenant downtime"
            )
        if tokens & {"fitness", "workout", "coach"}:
            return (
                "buyer: gym operators; vertical: boutique fitness studios; "
                "workflow: member issue triage and retention follow-up; "
                "pain: churn from unresolved support issues"
            )
        return (
            "buyer: operations leads; vertical: service businesses; "
            f"workflow: recurring support triage around {root}; "
            "pain: repeated manual support costs and delayed resolution"
        )

    def _b2c_persona_variants(self, root: str, root_tokens: set) -> List[str]:
        if root_tokens & {"appliance", "appliances", "homeowner", "homeowners", "repair", "home"}:
            return [
                f"{root} for first-time homeowners facing urgent breakdowns",
                f"{root} for landlords managing multiple rental units",
                f"{root} for short-term rental hosts with guest-facing downtime",
                f"{root} for home warranty claim coordinators",
            ]
        return [
            f"{root} for first-time users with urgent needs",
            f"{root} for prosumers with repeated weekly usage",
            f"{root} for power users switching from manual workflows",
            f"{root} for niche communities with high troubleshooting volume",
        ]

    def _finalize_next_topic(self, candidate: str, current_topic: str, root_topic: str, topic_mode: str) -> str:
        normalized_candidate = self._strip_search_modifiers(self._normalize_topic_phrase(candidate))
        normalized_current = self._strip_search_modifiers(self._normalize_topic_phrase(current_topic))
        normalized_root = self._strip_search_modifiers(self._normalize_topic_phrase(root_topic))

        history = set(self._topic_history)
        if normalized_candidate and normalized_candidate != normalized_current and normalized_candidate not in history:
            self._topic_history.append(normalized_candidate)
            return normalized_candidate

        fallback = self._suggest_new_topic(
            current_topic=normalized_current,
            root_topic=normalized_root,
            topic_mode=topic_mode,
            reason="REPEATED_SCOUT_EVIDENCE",
        )
        normalized_fallback = self._strip_search_modifiers(self._normalize_topic_phrase(fallback))
        if not normalized_fallback or normalized_fallback == normalized_current:
            normalized_fallback = self._merge_root_with_modifier(normalized_root, "for a different specific persona")
        self._topic_history.append(normalized_fallback)
        return normalized_fallback

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

        for match in re.finditer(r"\$([\d,]+(?:\.\d+)?)\s*/\s*(month|mo)\b", text, flags=re.IGNORECASE):
            monthly_values.append(float(match.group(1).replace(",", "")))

        for match in re.finditer(r"\$([\d,]+(?:\.\d+)?)\s*/\s*year\b", text, flags=re.IGNORECASE):
            monthly_values.append(float(match.group(1).replace(",", "")) / 12.0)

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
        blocking_issues: List[str] = []
        advisories: List[str] = []
        pivot = "General market/product fit issues"

        price = self._extract_monthly_price(strategist_output)
        if price is None or price < 150:
            blocking_issues.append(
                "Price floor gate failed: monthly price must be at least $150 for realistic founder-led $5k MRR."
            )
            pivot = "Low willingness to pay - raise price point for high-value customers"

        if not self._has_budget_owner(strategist_output):
            blocking_issues.append("Buyer gate failed: target segment does not clearly include a budget-owning B2B operator.")
            pivot = "Target a budget owner and operational workflow"

        demand_risk = False
        if willingness_output:
            willingness_score = self._extract_willingness_score(willingness_output)
            willingness_confidence = self._extract_willingness_confidence(willingness_output)
            if willingness_score < 45:
                demand_risk = True
                blocking_issues.append("Payment intent gate failed: willingness signal is too weak (<45%).")
                pivot = "Low willingness to pay - raise price point for high-value customers"
            elif willingness_score < 55 and willingness_confidence >= 70:
                demand_risk = True
                blocking_issues.append("Payment intent gate failed: low willingness with high confidence evidence.")
                pivot = "Low willingness to pay - raise price point for high-value customers"

        competition_risk = False
        if competitor_output:
            saturation = self._extract_market_saturation(competitor_output)
            relevance = self._assess_competition_relevance(
                topic=topic,
                strategist_output=strategist_output,
                competitor_output=competitor_output,
            )
            has_wedge = self._has_clear_wedge(strategist_output, competitor_output)
            if saturation == "RED" and relevance == "DIRECT" and not has_wedge:
                competition_risk = True
            elif saturation == "RED":
                advisories.append(
                    f"Competition warning: saturation is RED but relevance is {relevance.lower()}; not an auto-kill."
                )

        sales_risk = False
        if sales_output:
            feasibility = self._extract_sales_feasibility(sales_output)
            if feasibility == "DIFFICULT":
                sales_risk = True
                blocking_issues.append("Sales feasibility gate failed: founder-led path is marked DIFFICULT.")
                pivot = "Sales feasibility too low - reduce MVP scope or pivot to easier customer acquisition"

        if competition_risk and (demand_risk or sales_risk):
            blocking_issues.append(
                "Competition gate failed: direct saturated competition with no clear wedge plus weak demand/distribution."
            )
            if demand_risk:
                pivot = "Market is saturated and demand is weak - narrow the workflow wedge or reposition buyer"
            else:
                pivot = "Market is saturated and sales are difficult - narrow the wedge or improve distribution"
        elif competition_risk:
            advisories.append("Competition warning: direct RED saturation detected, but no second independent kill signal.")

        evidence_issue = self._check_evidence_grounding(scout_output=scout_output, analyst_output=analyst_output)
        if evidence_issue:
            blocking_issues.append(f"Evidence grounding gate failed: {evidence_issue}")
            pivot = "Evidence mismatch - map each accepted pain to explicit Scout URLs"

        if not domain_shift_authorized and self._is_cross_domain_shift(topic=topic, scout_topic=scout_topic, strategist_output=strategist_output):
            blocking_issues.append("Domain lock gate failed: Strategist shifted to an unrelated vertical without pivot authorization.")
            pivot = "Unrelated pivot detected - keep solution inside current domain or explicitly authorize a pivot"

        competitor_price_anchor = self._extract_competitor_price_anchor(competitor_output)
        if (
            competitor_price_anchor is not None
            and price is not None
            and competitor_price_anchor > 0
            and price > (10 * competitor_price_anchor)
            and not self._has_clear_wedge(strategist_output, competitor_output)
        ):
            blocking_issues.append(
                "Pricing sanity gate failed: proposed price exceeds 10x competitor anchor without a differentiated wedge."
            )
            pivot = "Pricing anchor mismatch - align to market band or provide explicit differentiation"

        return {
            "blocked": len(blocking_issues) > 0,
            "issues": blocking_issues,
            "advisories": advisories,
            "pivot": pivot,
        }

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
        blocking_issues: List[str] = []
        advisories: List[str] = []
        pivot = "General market/product fit issues"

        price = self._extract_monthly_price(strategist_output)
        if price is None:
            blocking_issues.append("Pricing gate failed: B2C_PLG strategy must include explicit monthly pricing.")
            pivot = "Clarify price band and self-serve packaging"
        elif price < 5 or price > 80:
            blocking_issues.append("Pricing gate failed: B2C_PLG monthly price should generally stay in $5-$80 range.")
            pivot = "Price-band mismatch - align to realistic PLG willingness"

        if not self._has_plg_channel(strategist_output):
            blocking_issues.append(
                "Acquisition gate failed: B2C_PLG must include at least one self-serve channel (SEO/content/community/product-launch)."
            )
            pivot = "Distribution mismatch - add concrete PLG channel"

        demand_risk = False
        if willingness_output:
            willingness_score = self._extract_willingness_score(willingness_output)
            willingness_confidence = self._extract_willingness_confidence(willingness_output)
            if willingness_score < 32:
                demand_risk = True
                blocking_issues.append("Payment intent gate failed: willingness signal is too weak (<32%) for B2C_PLG.")
                pivot = "Low willingness to pay - improve activation and conversion proof"
            elif willingness_score < 40 and willingness_confidence >= 70:
                demand_risk = True
                blocking_issues.append("Payment intent gate failed: low willingness with high confidence evidence for B2C_PLG.")
                pivot = "Low willingness to pay - improve activation and conversion proof"

        competition_risk = False
        if competitor_output:
            saturation = self._extract_market_saturation(competitor_output)
            relevance = self._assess_competition_relevance(
                topic=topic,
                strategist_output=strategist_output,
                competitor_output=competitor_output,
            )
            has_wedge = self._has_clear_wedge(strategist_output, competitor_output)
            if saturation == "RED" and relevance == "DIRECT" and not has_wedge:
                competition_risk = True
            elif saturation == "RED":
                advisories.append(
                    f"Competition warning: saturation is RED but relevance is {relevance.lower()}; not an auto-kill."
                )

        if competition_risk and demand_risk:
            blocking_issues.append(
                "Competition gate failed: direct saturated competition with no clear wedge plus weak payment intent."
            )
            pivot = "Market is saturated and demand is weak - narrow persona/use-case wedge"
        elif competition_risk:
            advisories.append("Competition warning: direct RED saturation detected, but no second independent kill signal.")

        evidence_issue = self._check_evidence_grounding(scout_output=scout_output, analyst_output=analyst_output)
        if evidence_issue:
            blocking_issues.append(f"Evidence grounding gate failed: {evidence_issue}")
            pivot = "Evidence mismatch - map each accepted pain to explicit Scout URLs"

        if not domain_shift_authorized and self._is_cross_domain_shift(topic=topic, scout_topic=scout_topic, strategist_output=strategist_output):
            blocking_issues.append("Domain lock gate failed: Strategist shifted to an unrelated vertical without pivot authorization.")
            pivot = "Unrelated pivot detected - keep solution inside current domain or explicitly authorize a pivot"

        competitor_price_anchor = self._extract_competitor_price_anchor(competitor_output)
        if (
            competitor_price_anchor is not None
            and price is not None
            and competitor_price_anchor > 0
            and price > (10 * competitor_price_anchor)
            and not self._has_clear_wedge(strategist_output, competitor_output)
        ):
            blocking_issues.append(
                "Pricing sanity gate failed: proposed price exceeds 10x competitor anchor without a differentiated wedge."
            )
            pivot = "Pricing anchor mismatch - align to market band or provide explicit differentiation"

        return {
            "blocked": len(blocking_issues) > 0,
            "issues": blocking_issues,
            "advisories": advisories,
            "pivot": pivot,
        }

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

    def _extract_willingness_confidence(self, willingness_output: Optional[str]) -> float:
        if not willingness_output:
            return 50.0
        text = willingness_output.lower()
        match = re.search(r"composite confidence\s*:\s*(\d+(?:\.\d+)?)\s*%", text, flags=re.IGNORECASE)
        if match:
            return max(0.0, min(100.0, float(match.group(1))))
        return 50.0

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
            r"\$([\d,]+(?:\.\d+)?)\s*/\s*(?:month|mo)\b",
            r"\$([\d,]+(?:\.\d+)?)\s*(?:per|/)\s*(?:month|mo)\b",
            r"price point\s*[:\-]?\s*\$([\d,]+(?:\.\d+)?)",
        ]
        for pattern in monthly_patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                return int(float(match.group(1).replace(",", "")))

        all_prices = [int(float(value.replace(",", ""))) for value in re.findall(r"\$([\d,]+(?:\.\d+)?)", text)]
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

    def _assess_competition_relevance(
        self,
        topic: str,
        strategist_output: str,
        competitor_output: Optional[str],
    ) -> str:
        if not competitor_output:
            return "UNKNOWN"

        anchor_terms = self._domain_terms(f"{topic}\n{strategist_output}")
        competitor_terms = self._domain_terms(competitor_output)
        if not anchor_terms or not competitor_terms:
            return "UNKNOWN"

        overlap = anchor_terms & competitor_terms
        overlap_count = len(overlap)
        overlap_ratio = overlap_count / max(1, len(anchor_terms))
        text = (competitor_output or "").lower()

        direct_cues = [
            "direct competitor",
            "exact problem",
            "same workflow",
            "same buyer",
            "same segment",
        ]
        adjacent_cues = [
            "broader",
            "all-in-one",
            "adjacent",
            "similar ones",
            "comprehensive",
            "potentially include",
            "might include",
        ]

        relevance = "IRRELEVANT"
        if any(cue in text for cue in direct_cues) and overlap_count >= 2:
            relevance = "DIRECT"
        elif overlap_count >= 3 and overlap_ratio >= 0.18:
            relevance = "DIRECT"
        elif overlap_count >= 2 or overlap_ratio >= 0.10:
            relevance = "ADJACENT"

        if relevance == "DIRECT" and any(cue in text for cue in adjacent_cues) and overlap_count < 5:
            relevance = "ADJACENT"

        return relevance

    def _has_clear_wedge(self, strategist_output: str, competitor_output: Optional[str]) -> bool:
        combined = f"{strategist_output}\n{competitor_output or ''}".lower()
        wedge_terms = [
            "niche",
            "vertical",
            "industry-specific",
            "differentiation",
            "unique",
            "wedge",
            "specialized",
            "specific persona",
            "narrow persona",
            "specific segment",
            "narrow segment",
            "use-case",
            "model-specific",
            "underserved",
            "first-time",
            "elderly",
        ]
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
        advisories = hard_gates.get("advisories") or []
        if not hard_gates["blocked"]:
            if advisories:
                advisory_lines = "\n".join(f"- {item}" for item in advisories)
                return f"HARD GATES: PASS\nAdvisories:\n{advisory_lines}"
            return "HARD GATES: PASS"
        issue_lines = "\n".join(f"- {issue}" for issue in hard_gates["issues"])
        advisory_text = ""
        if advisories:
            advisory_lines = "\n".join(f"- {item}" for item in advisories)
            advisory_text = f"\nAdvisories:\n{advisory_lines}"
        return f"HARD GATES: FAIL\n{issue_lines}{advisory_text}\nPivot: {hard_gates['pivot']}"

    def export_results_json(self, filepath: Optional[str] = None) -> str:
        json_output = json.dumps(self.research_results, indent=2)
        if filepath:
            with open(filepath, "w", encoding="utf-8") as output_file:
                output_file.write(json_output)
            print(colored(f"[Orchestrator] Results exported to {filepath}", "green"))
        return json_output

