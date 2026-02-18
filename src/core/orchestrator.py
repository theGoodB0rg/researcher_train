import json
import re
from datetime import datetime
from typing import Dict, List, Optional

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

            scout_output = self._run_agent("Trend Scout", f"Find complaints and issues related to: {topic}")
            if self._failed_data_collection(scout_output):
                self._append_iteration(topic, verdict="NO DATA")
                print(colored("[Orchestrator] Scout failed to collect real data. Iteration abandoned.", "red"))
                continue

            self._run_agent(
                "Pain Analyst",
                "Analyze these findings for 'boring' but painful recurring tasks:",
                context=self.conversation_history,
            )
            strategist_output = self._run_agent(
                "SaaS Strategist",
                "Propose a $5k MRR micro-SaaS solution for the identified problems:",
                context=self.conversation_history,
            )

            self._run_optional_agent("Competitor Researcher", "Research competitors for this idea:")
            self._run_optional_agent("Willingness Validator", "Validate if target customers will pay for this solution:")
            self._run_optional_agent(
                "Founder Sales Validator",
                "Simulate if founders can reach $5k MRR with this idea:",
            )

            skeptic_output = self._run_agent(
                "The Skeptic",
                "Make final GO/NO GO decision based on all validation data:",
                context=self.conversation_history,
            )

            verdict = self._parse_verdict(skeptic_output)
            self._append_iteration(topic, verdict)

            if verdict in {"GO", "QUALIFIED"}:
                print(colored("\n[SUCCESS] RESEARCH QUALIFIED! Proceeding with idea validation.", "green"))
                self.research_results["final_verdict"] = verdict
                self.research_results["final_idea"] = strategist_output
                self.research_results["iteration_count"] = iteration
                return self.research_results

            if verdict == "NO GO":
                pivot = self._extract_pivot_instruction(skeptic_output)
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
            return
        output = agent.process(prompt, context=self.conversation_history)
        self.broadcast(agent.name, output)

    def _append_iteration(self, topic: str, verdict: str):
        iteration_result = {
            "iteration": self.iteration_count,
            "topic": topic,
            "verdict": verdict,
            "conversation_length": len(self.conversation_history),
            "timestamp": datetime.now().isoformat(),
        }
        self.research_results["iterations"].append(iteration_result)

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
        return current_topic

    def _suggest_new_topic(self, current_topic: str) -> str:
        topic_pivots = {
            "junior react developers": "senior developers managing juniors",
            "cto software agency": "small software agency operation efficiency",
            "freelancer productivity": "freelancer project management",
            "small business accounting": "contractor tax compliance",
        }

        pivot = topic_pivots.get(current_topic.lower(), current_topic)
        if not self.interactive_pivots:
            return pivot

        new_topic = input(
            colored(f"\n[Orchestrator] Suggested pivot: '{pivot}'. Enter new topic or press Enter to accept: ", "yellow")
        ).strip()
        return new_topic if new_topic else pivot

    def export_results_json(self, filepath: Optional[str] = None) -> str:
        json_output = json.dumps(self.research_results, indent=2)
        if filepath:
            with open(filepath, "w", encoding="utf-8") as output_file:
                output_file.write(json_output)
            print(colored(f"[Orchestrator] Results exported to {filepath}", "green"))
        return json_output
