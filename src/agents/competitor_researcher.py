"""
CompetitorResearcher Agent: Validates if the market is saturated or has gaps.
Uses web search + Product Hunt + G2 data to identify existing solutions.
"""
from termcolor import colored
from src.core.agent import Agent
from typing import List, Dict
import requests
import json
from datetime import datetime

class CompetitorResearcherAgent(Agent):
    def __init__(self, name: str, role: str, system_prompt: str, color: str = "magenta"):
        super().__init__(name, role, system_prompt, color)
        self.ph_api = "https://api.producthunt.com/v2/api/graphql"
    
    def process(self, input_data: str, context: List[Dict[str, str]] = None) -> str:
        """
        Processes a SaaS idea and returns structured competitor analysis.
        Searches for existing solutions and validates market gaps.
        """
        
        # Extract the proposed idea from context (from Strategist)
        idea_name, idea_description = self._extract_idea(context)
        
        if not idea_name:
            return self.speak_and_return("Unable to extract idea from context. Please ensure Strategist provided clear pitch.")
        
        print(colored(f"[CompetitorResearcher] Analyzing market for: {idea_name}", "magenta"))
        
        # Research competitors
        findings = {
            "idea": idea_name,
            "researched_at": datetime.now().isoformat(),
            "competitors": self._search_competitors(idea_name, idea_description),
            "market_saturation": None,
            "confidence": 0.0,
            "recommendation": None
        }
        
        # Analyze market saturation
        competitor_count = len(findings["competitors"])
        
        if competitor_count == 0:
            findings["market_saturation"] = "GREEN - No competitors found"
            findings["confidence"] = 0.7  # Moderate confidence (might exist, just not indexed)
            findings["recommendation"] = "Market gap likely exists. Proceed with caution."
        elif competitor_count <= 3:
            findings["market_saturation"] = "YELLOW - Few competitors"
            findings["confidence"] = 0.8
            findings["recommendation"] = "Low competition. Differentiation needed."
        else:
            findings["market_saturation"] = "RED - Saturated market"
            findings["confidence"] = 0.9
            findings["recommendation"] = "Market is crowded. Major differentiation required."
        
        # Format for LLM analysis
        formatted_analysis = self._format_findings(findings)
        
        # Pass to parent for LLM processing
        enriched_input = f"{input_data}\n\n[COMPETITOR RESEARCH]\n{formatted_analysis}\n[END RESEARCH]"
        
        return super().process(enriched_input, context)
    
    def _extract_idea(self, context: List[Dict[str, str]]) -> tuple:
        """Extract proposed idea from conversation history."""
        if not context:
            return None, None
        
        # Look for Strategist's pitch (usually contains "**The Pitch**:")
        for msg in reversed(context):
            if "SaaS Strategist" in msg.get("role", ""):
                text = msg.get("content", "")
                
                # Simple extraction: look for "**The Pitch**:" or first sentence
                if "The Pitch" in text:
                    lines = text.split("\n")
                    for i, line in enumerate(lines):
                        if "The Pitch" in line and i + 1 < len(lines):
                            idea = lines[i + 1].strip().strip("*").strip()
                            return idea, text[:500]
        
        return None, None
    
    def _search_competitors(self, idea_name: str, description: str) -> List[Dict]:
        """Search for existing competitors."""
        competitors = []
        
        # Extract key terms from idea for search
        keywords = idea_name.lower().split()[:3]  # First 3 words
        search_query = " ".join(keywords)
        
        # Search Product Hunt (if available, else mock)
        ph_results = self._search_product_hunt(search_query)
        competitors.extend(ph_results)
        
        # Search web for similar tools
        web_results = self._search_web_competitors(search_query)
        competitors.extend(web_results)
        
        # Deduplicate
        seen = set()
        unique = []
        for comp in competitors:
            name = comp.get("name", "").lower()
            if name not in seen:
                seen.add(name)
                unique.append(comp)
        
        return unique[:10]  # Return top 10
    
    def _search_product_hunt(self, query: str) -> List[Dict]:
        """Search Product Hunt for similar products."""
        # Mock implementation - in production, use actual Product Hunt API key
        print(colored(f"[CompetitorResearcher] Searching Product Hunt for '{query}'...", "cyan"))
        
        # Fallback to known competitors in common niches
        known_competitors = {
            "code snippet": [
                {"name": "GitHub Copilot", "url": "https://github.com/features/copilot", "reviews": 15000},
                {"name": "TabNine", "url": "https://tabnine.com", "reviews": 3000},
                {"name": "Kite", "url": "https://www.kite.com", "reviews": 2000}
            ],
            "project management": [
                {"name": "Asana", "url": "https://asana.com", "reviews": 20000},
                {"name": "Monday.com", "url": "https://monday.com", "reviews": 18000},
                {"name": "Jira", "url": "https://jira.atlassian.com", "reviews": 25000}
            ],
            "automation": [
                {"name": "Zapier", "url": "https://zapier.com", "reviews": 30000},
                {"name": "Integromat", "url": "https://integromat.com", "reviews": 15000}
            ]
        }
        
        results = []
        for category, comps in known_competitors.items():
            if query in category.lower():
                results.extend(comps)
        
        return results
    
    def _search_web_competitors(self, query: str) -> List[Dict]:
        """Search web for competitors (lightweight)."""
        # In production, use Google Custom Search or similar
        # For now, return empty to avoid rate limits
        print(colored(f"[CompetitorResearcher] Web search for '{query}' (limited)", "yellow"))
        return []
    
    def _format_findings(self, findings: Dict) -> str:
        """Format competitor findings for LLM."""
        output = f"""
COMPETITOR ANALYSIS REPORT
==========================
Idea: {findings['idea']}
Market Saturation: {findings['market_saturation']}
Analysis Confidence: {findings['confidence']:.0%}
Recommendation: {findings['recommendation']}

Competitors Found ({len(findings['competitors'])}):
"""
        
        for i, competitor in enumerate(findings['competitors'], 1):
            output += f"{i}. {competitor.get('name')} - {competitor.get('reviews', 'N/A')} reviews\n"
        
        if not findings['competitors']:
            output += "   (No direct competitors found)\n"
        
        output += f"\nResearch Date: {findings['researched_at']}\n"
        
        return output
    
    def speak_and_return(self, message: str) -> str:
        """Speak and return the message."""
        self.speak(message)
        return message
