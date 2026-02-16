import os
import sys
from dotenv import load_dotenv
from termcolor import colored

# Ensure project root is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.agent import Agent
from src.core.orchestrator import Orchestrator
from src.agents.scout import ScoutAgent
from src.prompts import SCOUT_PROMPT, ANALYST_PROMPT, STRATEGIST_PROMPT, SKEPTIC_PROMPT

def main():
    # Load env vars
    load_dotenv()
    
    # Check for API keys
    if not os.getenv("OPENAI_API_KEY"):
        print(colored("WARNING: OPENAI_API_KEY not found in .env. Agents will run in MOCK mode.", "yellow"))

    print(colored("\n=== AI Co-Founder Team Initialized ===\n", "green", attrs=['bold']))

    # Initialize Agents
    scout = ScoutAgent("Trend Scout", "Researcher", SCOUT_PROMPT, color="cyan")
    analyst = Agent("Pain Analyst", "Product Manager", ANALYST_PROMPT, color="blue")
    strategist = Agent("SaaS Strategist", "Founder", STRATEGIST_PROMPT, color="magenta")
    skeptic = Agent("The Skeptic", "VC", SKEPTIC_PROMPT, color="red")

    # Initialize Orchestrator
    team = [scout, analyst, strategist, skeptic]
    orchestrator = Orchestrator(team)

    while True:
        topic = input(colored("\nEnter a research topic (or 'quit'): ", "white"))
        if topic.lower() in ['quit', 'exit']:
            break
        
        if not topic.strip():
            print("Please enter a valid topic.")
            continue

        orchestrator.run_round_table(topic)

if __name__ == "__main__":
    main()
