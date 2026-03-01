import os
import sys
from dotenv import load_dotenv
load_dotenv()

from src.core.agent import Agent
from src.agents.intake_router import IntakeRouterAgent
from src.prompts import INTAKE_ROUTER_PROMPT

def test():
    router = IntakeRouterAgent("Intake Router", "Research Planner", INTAKE_ROUTER_PROMPT)
    prompt = "Hi, I'm just here to brainstorm some ideas."
    output = router.process(f"Route and normalize this research request:\n{prompt}")
    print("ROUTER OUTPUT:")
    print(output)

if __name__ == "__main__":
    test()
