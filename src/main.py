import os
import sys

# Ensure project root is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
from src.utils.console import colored

from src.core.agent import Agent
from src.core.orchestrator import Orchestrator
from src.agents.intake_router import IntakeRouterAgent
from src.agents.scout import ScoutAgent
from src.agents.competitor_researcher import CompetitorResearcherAgent
from src.agents.willingness_validator import WillingnessToPayValidatorAgent
from src.agents.founder_sales_validator import FounderSalesValidatorAgent
from src.config import get_settings
from src.prompts import (
    INTAKE_ROUTER_PROMPT, SCOUT_PROMPT, ANALYST_PROMPT, STRATEGIST_PROMPT, SKEPTIC_PROMPT,
    COMPETITOR_RESEARCHER_PROMPT, WILLINGNESS_PROMPT, FOUNDER_SALES_PROMPT
)


def _read_topic_input(read_line=input, print_line=print) -> str:
    prompt = (
        "\nEnter your message (or 'quit'). "
        "Multi-line supported: press Enter twice on empty lines to send. "
        "For raw paste mode use ':paste': "
    )
    first_line = read_line(colored(prompt, "white"))
    if first_line.strip().lower() in {"quit", "exit"}:
        return first_line
    if first_line.strip().lower() == ":paste":
        print_line(colored("Paste your brief. End with ':end' on its own line.", "yellow"))
        lines = []
        while True:
            line = read_line()
            if line.strip().lower() == ":end":
                break
            lines.append(line)
        return "\n".join(lines).strip()
    if not first_line.strip():
        return ""

    # Default chat-like composer: one blank line for paragraph spacing, double blank to submit.
    print_line(colored("Continue typing. Press Enter twice on empty lines to submit.", "yellow"))
    lines = [first_line]
    blank_streak = 0
    while True:
        line = read_line()
        lines.append(line)
        if line.strip():
            blank_streak = 0
        else:
            blank_streak += 1
            if blank_streak >= 2:
                break

    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines).strip()


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
    print(
        colored(
            "Tip: normal chat-style multi-line input is enabled (double blank line to submit).",
            "yellow",
        )
    )
    print(colored("Tip: use ':paste' then ':end' for large markdown documents.", "yellow"))

    # Initialize Agents (as dictionary for flexible orchestration)
    agents = {
        "Intake Router": IntakeRouterAgent("Intake Router", "Research Planner", INTAKE_ROUTER_PROMPT, color="yellow"),
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
        try:
            topic = _read_topic_input()
        except KeyboardInterrupt:
            print(colored("\nInterrupted. Exiting.", "yellow"))
            break
        if topic.lower() in ['quit', 'exit']:
            break
        
        if not topic.strip():
            print("Please enter a valid topic.")
            continue

        # Run intelligent iterative research
        try:
            results = orchestrator.run_round_table(topic)
        except KeyboardInterrupt:
            print(colored("\nResearch interrupted by user. Returning to topic prompt.", "yellow"))
            continue
        
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


