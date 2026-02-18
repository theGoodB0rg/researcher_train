#!/usr/bin/env python3
"""
Test script for intelligent iterative research system.
Runs a single research topic without user interaction.
"""
import os
import sys
from dotenv import load_dotenv

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

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

def test_research_system():
    """Test the intelligent research system with a single topic."""
    
    load_dotenv()
    settings = get_settings()
    
    print("\n" + "="*60)
    print("INTELLIGENT RESEARCH SYSTEM - TEST RUN")
    print("="*60 + "\n")
    
    # Initialize agents
    agents = {
        "Trend Scout": ScoutAgent("Trend Scout", "Researcher", SCOUT_PROMPT, color="cyan"),
        "Pain Analyst": Agent("Pain Analyst", "Product Manager", ANALYST_PROMPT, color="blue"),
        "SaaS Strategist": Agent("SaaS Strategist", "Founder", STRATEGIST_PROMPT, color="magenta"),
        "Competitor Researcher": CompetitorResearcherAgent("Competitor Researcher", "Market Analyst", COMPETITOR_RESEARCHER_PROMPT, color="cyan"),
        "Willingness Validator": WillingnessToPayValidatorAgent("Willingness Validator", "Market Researcher", WILLINGNESS_PROMPT, color="blue"),
        "Founder Sales Validator": FounderSalesValidatorAgent("Founder Sales Validator", "Sales Expert", FOUNDER_SALES_PROMPT, color="green"),
        "The Skeptic": Agent("The Skeptic", "VC", SKEPTIC_PROMPT, color="red"),
    }
    
    orchestrator = Orchestrator(agents, max_iterations=settings.max_iterations, interactive_pivots=False)
    
    # Test topic
    test_topic = "junior react developers facing career stagnation"
    
    print(f"Testing with topic: '{test_topic}'\n")
    
    # Run research
    results = orchestrator.run_round_table(test_topic)
    
    # Print summary
    print("\n" + "="*60)
    print("TEST RESULTS SUMMARY")
    print("="*60)
    print(f"Topic: {results.get('topic', 'N/A')}")
    print(f"Final Verdict: {results.get('final_verdict', 'N/A')}")
    print(f"Iterations Completed: {results.get('iteration_count', 'N/A')}")
    print(f"Total Research Rounds: {len(results.get('iterations', []))}")
    
    if results.get('final_idea'):
        print(f"\nFinal Idea (truncated):")
        idea_text = results['final_idea'][:300]
        print(f"{idea_text}...\n")
    
    # Export results
    print("\nExporting results to JSON...")
    json_output = orchestrator.export_results_json("test_results.json")
    print("[SUCCESS] Test completed successfully!")
    
    return results

if __name__ == "__main__":
    test_research_system()
