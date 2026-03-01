import os
import sys
import json
from dotenv import load_dotenv
load_dotenv()

from src.core.orchestrator import Orchestrator
from src.agents.intake_router import IntakeRouterAgent
from src.prompts import INTAKE_ROUTER_PROMPT

class MockAgent:
    def __init__(self, name):
        self.name = name
    def process(self, prompt, context=None):
        return "{}"

def test():
    agents = {
        "Intake Router": IntakeRouterAgent("Intake Router", "Research Planner", INTAKE_ROUTER_PROMPT, color="yellow"),
        "Trend Scout": MockAgent("Trend Scout"),
    }
    # Mocking self.client for IntakeRouterAgent so it doesn't try to init OpenAI!
    # Wait, IntakeRouterAgent.__init__ calls super().__init__, which inits OpenAI!
    # Let's monkey patch Agent.__init__!
    from src.core.agent import Agent
    original_init = Agent.__init__
    def mock_init(self, name, role, system_prompt, color="white"):
        self.name = name
        self.role = role
        self.system_prompt = system_prompt
        self.color = color
        self.client = None # bypassed!
    Agent.__init__ = mock_init

    # Re-instantiate
    agents["Intake Router"] = IntakeRouterAgent("Intake Router", "Research Planner", INTAKE_ROUTER_PROMPT, color="yellow")
    
    orchestrator = Orchestrator(agents, max_iterations=1, interactive_pivots=False)
    
    prompt = "Hi, I'm just here to brainstorm some ideas."
    print("--- RUNNING ORCHESTRATOR ---")
    results = orchestrator.run_round_table(prompt)
    print("--- FINAL RESULTS ---")
    print(results)

if __name__ == "__main__":
    test()
