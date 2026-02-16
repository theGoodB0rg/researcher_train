from typing import List, Dict
from .agent import Agent

class Orchestrator:
    def __init__(self, agents: List[Agent]):
        self.agents = {agent.name: agent for agent in agents}
        self.conversation_history: List[Dict[str, str]] = []

    def broadcast(self, sender_name: str, message: str):
        """Adds a message to the shared history."""
        self.conversation_history.append({"role": sender_name, "content": message})

    def run_round_table(self, initial_topic: str):
        """
        Simulates the workflow:
        1. Scout finds info.
        2. Analyst filters it.
        3. Strategist proposes solution.
        4. Skeptic critiques it.
        """
        print(f"--- Starting Round Table on: {initial_topic} ---\n")
        
        # Step 1: Scout
        scout = self.agents.get("Trend Scout")
        scout_output = scout.process(f"Find complaints and issues related to: {initial_topic}")
        self.broadcast(scout.name, scout_output)
        
        # Step 2: Analyst
        analyst = self.agents.get("Pain Analyst")
        analyst_output = analyst.process(f"Analyze these findings for 'boring' but painful recurring tasks:", context=self.conversation_history)
        self.broadcast(analyst.name, analyst_output)

        # Step 3: Strategist
        strategist = self.agents.get("SaaS Strategist")
        strategist_output = strategist.process(f"Propose a $5k MRR micro-SaaS solution for the identified problems:", context=self.conversation_history)
        self.broadcast(strategist.name, strategist_output)

        # Step 4: Skeptic
        skeptic = self.agents.get("The Skeptic")
        skeptic_output = skeptic.process(f"Roast this idea. Find flaws in viability, competition, and user adoption:", context=self.conversation_history)
        self.broadcast(skeptic.name, skeptic_output)

        print("\n--- Round Table Finished ---")
