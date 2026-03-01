"""
FounderSalesValidator Agent: Validates if founders can reach $5k MRR via direct sales.
Calculates realistic adoption paths given zero marketing budget.
"""
from src.utils.console import colored
from src.core.agent import Agent
from typing import List, Dict
from datetime import datetime
import re

class FounderSalesValidatorAgent(Agent):
    def __init__(self, name: str, role: str, system_prompt: str, color: str = "green"):
        super().__init__(name, role, system_prompt, color)
    
    def process(self, input_data: str, context: List[Dict[str, str]] = None, system_overrides: str = None) -> str:
        """
        Simulates founder sales feasibility to reach $5k MRR.
        Extracts target audience, pricing, and acquisition channel from prior research.
        """
        
        print(colored("[FounderSalesValidator] Simulating founder sales path to $5k MRR...", "green"))
        
        # Extract key info from conversation
        pricing = self._extract_pricing(context)
        target_audience = self._extract_target_audience(context)
        acquisition_channel = self._extract_acquisition_channel(context)
        competitor_count = self._extract_competitor_count(context)
        
        # Calculate founder sales simulation
        simulation = {
            "researched_at": datetime.now().isoformat(),
            "pricing_extracted": pricing,
            "target_audience": target_audience,
            "acquisition_channel": acquisition_channel,
            "mrr_target": 5000,
            "calculations": self._calculate_sales_scenarios(pricing),
            "feasibility": None,
            "recommendations": []
        }
        
        # Run scenarios
        if pricing.get("monthly_price"):
            scenarios = simulation["calculations"]
            
            # Best case: high-value customers (low volume needed)
            if scenarios.get("high_value"):
                simulation["feasibility"] = "VIABLE"
                simulation["recommendations"].append(
                    f"Target {scenarios['high_value']['customers_needed']} high-value customers at ${scenarios['high_value']['price']}/mo"
                )
            # Medium case
            elif scenarios.get("medium_value"):
                simulation["feasibility"] = "CHALLENGING"
                simulation["recommendations"].append(
                    f"Target {scenarios['medium_value']['customers_needed']} mid-tier customers at ${scenarios['medium_value']['price']}/mo"
                )
            # Low-value case
            else:
                simulation["feasibility"] = "DIFFICULT"
                simulation["recommendations"].append(
                    f"Requires {scenarios.get('low_value', {}).get('customers_needed', 'many')} low-value customers - acquisition cost too high without budget"
                )
        else:
            simulation["feasibility"] = "UNKNOWN"
            simulation["recommendations"].append("Could not extract pricing model")
        
        # Add founder work estimate
        if simulation["feasibility"] in ["VIABLE", "CHALLENGING"]:
            hours = simulation["calculations"].get("high_value", {}).get("hours_required", 100)
            simulation["recommendations"].append(
                f"Estimated {hours} founder hours needed (cold outreach, demos, sales)"
            )
        
        formatted = self._format_simulation(simulation)
        
        # Pass to LLM
        enriched_input = f"{input_data}\n\n[FOUNDER SALES SIMULATION]\n{formatted}\n[END SIMULATION]"
        
        return super().process(enriched_input, context, system_overrides=system_overrides)
    
    def _extract_pricing(self, context: List[Dict[str, str]]) -> Dict:
        """Extract pricing model from Strategist."""
        pricing = {}
        
        if not context:
            return pricing
        
        for msg in reversed(context):
            if "SaaS Strategist" in msg.get("role", ""):
                text = msg.get("content", "")

                # Prefer explicit monthly pricing references to avoid picking "$5k MRR".
                monthly_patterns = [
                    r"\$(\d+)\s*/\s*(?:month|mo)\b",
                    r"\$(\d+)\s*(?:per|/)\s*(?:month|mo)\b",
                    r"price point\s*[:\-]?\s*\$(\d+)",
                ]
                monthly_price = None
                for pattern in monthly_patterns:
                    match = re.search(pattern, text, flags=re.IGNORECASE)
                    if match:
                        monthly_price = int(match.group(1))
                        break

                if monthly_price is None:
                    all_prices = [int(value) for value in re.findall(r"\$(\d+)", text)]
                    filtered_prices = [value for value in all_prices if value >= 20]
                    if filtered_prices:
                        monthly_price = filtered_prices[0]

                if monthly_price is not None:
                    pricing["monthly_price"] = monthly_price
                
                # Look for target customer count
                counts = re.findall(r'(\d+).*(?:users?|customers?|subscribers?)', text)
                if counts:
                    pricing["target_count"] = int(counts[0])
        
        return pricing
    
    def _extract_target_audience(self, context: List[Dict[str, str]]) -> str:
        """Extract target audience from research."""
        audience_keywords = ["small business", "freelancer", "solopreneur", "contractor", 
                            "startup", "agency", "developer", "student"]
        
        if not context:
            return "Unknown"
        
        full_text = " ".join([msg.get("content", "").lower() for msg in context])
        
        for keyword in audience_keywords:
            if keyword in full_text:
                return keyword
        
        return "Unknown"
    
    def _extract_acquisition_channel(self, context: List[Dict[str, str]]) -> str:
        """Extract free acquisition channel from Strategist."""
        if not context:
            return "Unknown"
        
        for msg in reversed(context):
            if "SaaS Strategist" in msg.get("role", ""):
                text = msg.get("content", "")
                
                if "Acquisition" in text:
                    lines = text.split("\n")
                    for i, line in enumerate(lines):
                        if "Acquisition" in line and i + 1 < len(lines):
                            return lines[i + 1:i + 3].__str__()
        
        return "Unknown"
    
    def _extract_competitor_count(self, context: List[Dict[str, str]]) -> int:
        """Extract competitor count from CompetitorResearcher."""
        if not context:
            return 0
        
        for msg in reversed(context):
            if "Competitor" in msg.get("role", ""):
                text = msg.get("content", "")
                
                # Look for "Competitors Found (X)"
                matches = re.findall(r'Competitors Found \((\d+)\)', text)
                if matches:
                    return int(matches[0])
        
        return 0
    
    def _calculate_sales_scenarios(self, pricing: Dict) -> Dict:
        """Calculate realistic sales scenarios."""
        monthly_price = pricing.get("monthly_price", 100)
        mrr_target = 5000
        
        scenarios = {}
        
        # Scenario 1: High-value customer ($300-500/mo)
        if monthly_price >= 300:
            scenarios["high_value"] = {
                "price": monthly_price,
                "customers_needed": max(10, int(mrr_target / monthly_price)),
                "hours_required": max(10, int(mrr_target / monthly_price)) * 5,  # ~5 hours per customer
                "feasibility": "GOOD - Low acquisition volume needed"
            }
        
        # Scenario 2: Medium-value customer ($100-200/mo)
        if 100 <= monthly_price < 300:
            scenarios["medium_value"] = {
                "price": monthly_price,
                "customers_needed": int(mrr_target / monthly_price),
                "hours_required": int(mrr_target / monthly_price) * 8,  # ~8 hours per customer
                "feasibility": "CHALLENGING - Medium acquisition volume needed"
            }
        
        # Scenario 3: Low-value customer (<$100/mo)
        scenarios["low_value"] = {
            "price": monthly_price,
            "customers_needed": int(mrr_target / monthly_price),
            "hours_required": int(mrr_target / monthly_price) * 15,  # ~15 hours per customer
            "feasibility": "DIFFICULT - High acquisition volume needed without budget"
        }
        
        return scenarios
    
    def _format_simulation(self, simulation: Dict) -> str:
        """Format simulation results for LLM."""
        output = f"""
FOUNDER SALES SIMULATION TO $5K MRR
====================================
Target Audience: {simulation['target_audience']}
Acquisition Channel: {simulation['acquisition_channel']}
Overall Feasibility: {simulation['feasibility']}

SALES SCENARIOS & CALCULATIONS:
"""
        
        for scenario_name, details in simulation.get("calculations", {}).items():
            output += f"\n{scenario_name.upper().replace('_', ' ')}:\n"
            output += f"  - Price Point: ${details['price']}/month\n"
            output += f"  - Customers Needed: {details['customers_needed']}\n"
            output += f"  - Founder Hours: ~{details['hours_required']} hours total\n"
            output += f"  - Viability: {details['feasibility']}\n"
        
        output += f"\nRECOMMENDATIONS:\n"
        for i, rec in enumerate(simulation.get("recommendations", []), 1):
            output += f"{i}. {rec}\n"
        
        output += f"\nSimulation Date: {simulation['researched_at']}\n"
        
        return output

