import os
import sys

# Ensure project root is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
from src.utils.console import colored

from src.core.agent import Agent
from src.core.orchestrator import Orchestrator
from src.agents.scout import ScoutAgent
from src.agents.competitor_researcher import CompetitorResearcherAgent
from src.agents.willingness_validator import WillingnessToPayValidatorAgent
from src.agents.founder_sales_validator import FounderSalesValidatorAgent
from src.config import get_settings
from src.prompts import (
    SCOUT_PROMPT, ANALYST_PROMPT, STRATEGIST_PROMPT, SKEPTIC_PROMPT,
    COMPETITOR_RESEARCHER_PROMPT, WILLINGNESS_PROMPT, FOUNDER_SALES_PROMPT
)

def main():
    # Load env vars
    load_dotenv()
    settings = get_settings()
    
    # Check for API keys
    if not os.getenv("OPENAI_API_KEY"):
        print(colored("WARNING: OPENAI_API_KEY not found in .env. Agents will run in MOCK mode.", "yellow"))

    print(colored("\n=== AI Co-Founder Team Initialized (v3 - Buyer-Aware Iterative Research) ===\n", "green", attrs=['bold']))
    print(
        colored(
            "Tip: buyer-first mode supported. Example: buyer: staffing agencies; workflow: candidate intake; pain: manual profile updates",
            "yellow",
        )
    )

    # Initialize Agents (as dictionary for flexible orchestration)
    agents = {
        "Trend Scout": ScoutAgent("Trend Scout", "Researcher", SCOUT_PROMPT, color="cyan"),
        "Pain Analyst": Agent("Pain Analyst", "Product Manager", ANALYST_PROMPT, color="blue"),
        "SaaS Strategist": Agent("SaaS Strategist", "Founder", STRATEGIST_PROMPT, color="magenta"),
        "Competitor Researcher": CompetitorResearcherAgent("Competitor Researcher", "Market Analyst", COMPETITOR_RESEARCHER_PROMPT, color="cyan"),
        "Willingness Validator": WillingnessToPayValidatorAgent("Willingness Validator", "Market Researcher", WILLINGNESS_PROMPT, color="blue"),
        "Founder Sales Validator": FounderSalesValidatorAgent("Founder Sales Validator", "Sales Expert", FOUNDER_SALES_PROMPT, color="green"),
        "The Skeptic": Agent("The Skeptic", "VC", SKEPTIC_PROMPT, color="red"),
    }

    # Initialize Orchestrator with agent dictionary
    orchestrator = Orchestrator(agents, max_iterations=settings.max_iterations, interactive_pivots=True)

    while True:
        topic = input(colored("\nEnter a research topic (or 'quit'): ", "white"))
        if topic.lower() in ['quit', 'exit']:
            break
        
        if not topic.strip():
            print("Please enter a valid topic.")
            continue

        # Run intelligent iterative research
        results = orchestrator.run_round_table(topic)
        
        # Display results summary
        print(colored(f"\n{'='*60}", "cyan"))
        print(colored("RESEARCH COMPLETE", "cyan", attrs=['bold']))
        print(colored(f"{'='*60}", "cyan"))
        print(colored(f"Topic: {results['topic']}", "white"))
        print(colored(f"Final Verdict: {results['final_verdict']}", "green" if "GO" in str(results['final_verdict']) else "red"))
        print(colored(f"Iterations: {results['iteration_count'] if 'iteration_count' in results else len(results['iterations'])}", "white"))
        
        # Ask if user wants to export results
        export = input(colored("\nExport results to JSON? (y/n): ", "yellow"))
        if export.lower() in ['y', 'yes']:
            filename = f"research_results_{results['topic'].replace(' ', '_')}.json"
            orchestrator.export_results_json(filename)

if __name__ == "__main__":
    main()


