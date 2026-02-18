from typing import List, Dict
from .agent import Agent
from termcolor import colored
from datetime import datetime
import json

class Orchestrator:
    def __init__(self, agents: Dict[str, Agent]):
        """Initialize with a dict of agents instead of a list."""
        self.agents = agents
        self.conversation_history: List[Dict[str, str]] = []
        self.iteration_count = 0
        self.max_iterations = 5
        self.research_results = {
            "topic": None,
            "iterations": [],
            "final_verdict": None,
            "final_idea": None,
            "researched_at": None
        }

    def broadcast(self, sender_name: str, message: str):
        """Adds a message to the shared history."""
        self.conversation_history.append({"role": sender_name, "content": message})

    def run_round_table(self, initial_topic: str) -> Dict:
        """
        Intelligent iterative research loop.
        Runs agents in sequence, validates output, and loops based on Skeptic verdict.
        Returns: Research result with verdict and idea details.
        """
        print(colored(f"\n{'='*60}", "cyan"))
        print(colored(f"=== STARTING INTELLIGENT RESEARCH: {initial_topic.upper()} ===", "cyan"))
        print(colored(f"{'='*60}\n", "cyan"))
        
        self.research_results["topic"] = initial_topic
        self.research_results["researched_at"] = datetime.now().isoformat()
        topic = initial_topic
        
        while self.iteration_count < self.max_iterations:
            self.iteration_count += 1
            print(colored(f"\n--- ITERATION {self.iteration_count}/{self.max_iterations} ---", "yellow"))
            
            # Clear history for fresh iteration
            self.conversation_history = []
            
            # Step 1: Scout
            scout = self.agents.get("Trend Scout")
            scout_output = scout.process(f"Find complaints and issues related to: {topic}")
            self.broadcast(scout.name, scout_output)
            
            # Check if Scout found real data
            if "NO REAL DATA" in scout_output.upper() or "DATA COLLECTION FAILED" in scout_output.upper():
                print(colored("[Orchestrator] Scout failed to collect real data. Iteration abandoned.", "red"))
                continue
            
            # Step 2: Analyst
            analyst = self.agents.get("Pain Analyst")
            analyst_output = analyst.process(
                f"Analyze these findings for 'boring' but painful recurring tasks:",
                context=self.conversation_history
            )
            self.broadcast(analyst.name, analyst_output)
            
            # Step 3: Strategist
            strategist = self.agents.get("SaaS Strategist")
            strategist_output = strategist.process(
                f"Propose a $5k MRR micro-SaaS solution for the identified problems:",
                context=self.conversation_history
            )
            self.broadcast(strategist.name, strategist_output)
            
            # Step 4: Competitor Researcher (NEW)
            competitor_researcher = self.agents.get("Competitor Researcher")
            if competitor_researcher:
                competitor_output = competitor_researcher.process(
                    f"Research competitors for this idea:",
                    context=self.conversation_history
                )
                self.broadcast(competitor_researcher.name, competitor_output)
            
            # Step 5: Willingness Validator (NEW)
            willingness_validator = self.agents.get("Willingness Validator")
            if willingness_validator:
                willingness_output = willingness_validator.process(
                    f"Validate if target customers will pay for this solution:",
                    context=self.conversation_history
                )
                self.broadcast(willingness_validator.name, willingness_output)
            
            # Step 6: Founder Sales Validator (NEW)
            founder_sales_validator = self.agents.get("Founder Sales Validator")
            if founder_sales_validator:
                sales_output = founder_sales_validator.process(
                    f"Simulate if founders can reach $5k MRR with this idea:",
                    context=self.conversation_history
                )
                self.broadcast(founder_sales_validator.name, sales_output)
            
            # Step 7: Skeptic (with new validation data)
            skeptic = self.agents.get("The Skeptic")
            skeptic_output = skeptic.process(
                f"Make final GO/NO GO decision based on all validation data:",
                context=self.conversation_history
            )
            self.broadcast(skeptic.name, skeptic_output)
            
            # Parse Skeptic verdict
            verdict = self._parse_verdict(skeptic_output)
            
            # Store iteration result
            iteration_result = {
                "iteration": self.iteration_count,
                "topic": topic,
                "verdict": verdict,
                "conversation_length": len(self.conversation_history)
            }
            self.research_results["iterations"].append(iteration_result)
            
            # Handle verdict
            if verdict == "GO" or verdict == "QUALIFIED":
                print(colored(f"\n[SUCCESS] RESEARCH QUALIFIED! Proceeding with idea validation.", "green"))
                self.research_results["final_verdict"] = verdict
                self.research_results["final_idea"] = strategist_output
                self.research_results["iteration_count"] = self.iteration_count
                return self.research_results
            
            elif verdict == "NO GO":
                # Extract pivot instruction from Skeptic
                pivot = self._extract_pivot_instruction(skeptic_output)
                print(colored(f"\n[REJECTED] Idea rejected. Reason: {pivot}", "red"))
                
                # Decide on next action
                if "different pain point" in pivot.lower():
                    print(colored("[Orchestrator] Returning to Scout for new topic...", "yellow"))
                    topic = self._suggest_new_topic(topic)
                    continue
                
                elif "raise price" in pivot.lower():
                    print(colored("[Orchestrator] Need higher-value customer focus. Re-strategizing...", "yellow"))
                    # Could loop back to Strategist here, but for now restart
                    continue
                
                elif "reduce scope" in pivot.lower() or "simplify" in pivot.lower():
                    print(colored("[Orchestrator] MVP scope too complex. Retrying with stripped features...", "yellow"))
                    continue
                
                else:
                    print(colored("[Orchestrator] No clear pivot direction. Trying new topic...", "yellow"))
                    topic = self._suggest_new_topic(topic)
                    continue
            
            else:
                print(colored(f"[Orchestrator] Unclear verdict: {verdict}", "yellow"))
                continue
        
        # Exhausted iterations
        print(colored(f"\n[WARNING] Reached max iterations ({self.max_iterations}). Stopping research.", "red"))
        self.research_results["final_verdict"] = "NO_QUALIFIED_IDEA"
        self.research_results["iteration_count"] = self.iteration_count
        return self.research_results
    
    def _parse_verdict(self, skeptic_output: str) -> str:
        """Extract GO/NO GO/QUALIFIED from Skeptic output."""
        output_upper = skeptic_output.upper()
        
        if "GO" in output_upper and "NO GO" not in output_upper:
            return "GO"
        elif "QUALIFIED" in output_upper:
            return "QUALIFIED"
        elif "NO GO" in output_upper:
            return "NO GO"
        else:
            return "UNCLEAR"
    
    def _extract_pivot_instruction(self, skeptic_output: str) -> str:
        """Extract what to pivot on from Skeptic output."""
        if "saturated" in skeptic_output.lower():
            return "Market is saturated - need different pain point"
        elif "willingness" in skeptic_output.lower() or "won't pay" in skeptic_output.lower():
            return "Low willingness to pay - raise price point for high-value customers"
        elif "feasib" in skeptic_output.lower() or "unrealistic" in skeptic_output.lower():
            return "Sales feasibility too low - reduce MVP scope or pivot to easier customer acquisition"
        elif "technical" in skeptic_output.lower():
            return "Technical complexity too high - simplify feature set"
        else:
            return "General market/product fit issues"
    
    def _suggest_new_topic(self, current_topic: str) -> str:
        """Suggest a related but different topic."""
        topic_pivots = {
            "junior react developers": "senior developers managing juniors",
            "cto software agency": "small software agency operation efficiency",
            "freelancer productivity": "freelancer project management",
            "small business accounting": "contractor tax compliance",
        }
        
        pivot = topic_pivots.get(current_topic.lower())
        if pivot:
            new_topic = input(colored(f"\n[Orchestrator] Suggest pivot to: '{pivot}'? Or enter new topic: ", "yellow")).strip()
            return new_topic if new_topic else pivot
        else:
            new_topic = input(colored(f"\n[Orchestrator] Enter new research topic: ", "yellow")).strip()
            return new_topic if new_topic else current_topic
    
    def export_results_json(self, filepath: str = None) -> str:
        """Export research results as JSON."""
        json_output = json.dumps(self.research_results, indent=2)
        
        if filepath:
            with open(filepath, "w") as f:
                f.write(json_output)
            print(colored(f"[Orchestrator] Results exported to {filepath}", "green"))
        
        return json_output

