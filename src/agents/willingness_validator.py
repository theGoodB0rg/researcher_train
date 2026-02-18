"""
WillingnessToPayValidator Agent: Validates if target customers will actually pay.
Searches community data for price tolerance signals.
"""
from termcolor import colored
from src.core.agent import Agent
from typing import List, Dict
from datetime import datetime
import re

class WillingnessToPayValidatorAgent(Agent):
    def __init__(self, name: str, role: str, system_prompt: str, color: str = "blue"):
        super().__init__(name, role, system_prompt, color)
    
    def process(self, input_data: str, context: List[Dict[str, str]] = None) -> str:
        """
        Analyzes if target customers show willingness to pay.
        Looks for price signals in community data and prior research.
        """
        
        print(colored("[WillingnessToPayValidator] Analyzing price tolerance...", "blue"))
        
        # Extract proposed pricing from Strategist
        pricing_model = self._extract_pricing(context)
        
        # Extract community data from conversation
        community_signals = self._extract_signals(context)
        
        # Analyze willingness to pay
        validation = {
            "researched_at": datetime.now().isoformat(),
            "pricing_model": pricing_model,
            "price_signals": community_signals,
            "willingness_score": self._calculate_willingness_score(community_signals),
            "confidence": self._calculate_confidence(community_signals),
            "recommendation": None
        }
        
        # Generate recommendation
        score = validation["willingness_score"]
        if score >= 0.8:
            validation["recommendation"] = "HIGH - Strong signals of willingness to pay"
        elif score >= 0.6:
            validation["recommendation"] = "MEDIUM - Some price tolerance detected"
        else:
            validation["recommendation"] = "LOW - Insufficient evidence of payment willingness"
        
        formatted = self._format_findings(validation)
        
        # Pass to LLM for analysis
        enriched_input = f"{input_data}\n\n[WILLINGNESS TO PAY ANALYSIS]\n{formatted}\n[END ANALYSIS]"
        
        return super().process(enriched_input, context)
    
    def _extract_pricing(self, context: List[Dict[str, str]]) -> str:
        """Extract pricing model from Strategist's proposal."""
        if not context:
            return "Unknown"
        
        for msg in reversed(context):
            if "SaaS Strategist" in msg.get("role", ""):
                text = msg.get("content", "")
                
                # Look for pricing mentions
                if "Pricing Model" in text or "price" in text.lower():
                    lines = text.split("\n")
                    for i, line in enumerate(lines):
                        if "Pricing" in line and i + 1 < len(lines):
                            pricing = lines[i + 1:i + 3]
                            return "\n".join(pricing).strip()
        
        return "Unknown"
    
    def _extract_signals(self, context: List[Dict[str, str]]) -> List[str]:
        """Extract price/payment signals from Scout and Analyst findings."""
        signals = []
        price_keywords = [
            "would pay", "pay", "subscription", "monthly", "price", "cost",
            "afford", "expensive", "cheap", "worth", "value", "$", "budget",
            "charge", "willing", "investment"
        ]
        
        if not context:
            return signals
        
        for msg in context:
            text = msg.get("content", "").lower()
            
            # Look for any price-related mentions
            for keyword in price_keywords:
                if keyword in text:
                    # Extract sentence containing keyword
                    sentences = text.split(".")
                    for sentence in sentences:
                        if keyword in sentence and len(sentence) > 20:
                            signals.append(sentence.strip())
                            break
        
        return list(set(signals))[:10]  # Deduplicate and limit
    
    def _calculate_willingness_score(self, signals: List[str]) -> float:
        """
        Calculate willingness to pay score based on signals.
        0.0 = no evidence, 1.0 = strong evidence
        """
        if not signals:
            return 0.3  # Base score for unknown
        
        score = 0.0
        strong_indicators = ["would pay", "willing to", "worth", "valuable", "invest"]
        weak_indicators = ["expensive", "too much", "can't afford"]
        
        for signal in signals:
            signal_lower = signal.lower()
            
            # Strong signals increase score
            for indicator in strong_indicators:
                if indicator in signal_lower:
                    score += 0.15
            
            # Weak signals decrease score
            for indicator in weak_indicators:
                if indicator in signal_lower:
                    score -= 0.1
        
        # Cap at 1.0
        return min(1.0, max(0.0, score + 0.4))
    
    def _calculate_confidence(self, signals: List[str]) -> float:
        """Calculate confidence in the analysis based on signal strength."""
        if not signals:
            return 0.3
        
        signal_count = len(signals)
        if signal_count >= 10:
            return 0.9
        elif signal_count >= 5:
            return 0.7
        else:
            return 0.5
    
    def _format_findings(self, validation: Dict) -> str:
        """Format validation findings for LLM."""
        output = f"""
WILLINGNESS TO PAY ANALYSIS
============================
Pricing Model: {validation['pricing_model']}

Price Signals Found: {len(validation['price_signals'])}
Willingness Score: {validation['willingness_score']:.1%}
Analysis Confidence: {validation['confidence']:.0%}
Recommendation: {validation['recommendation']}

Sample Price Signals:
"""
        
        if validation['price_signals']:
            for i, signal in enumerate(validation['price_signals'][:5], 1):
                output += f"{i}. \"{signal[:100]}...\"\n"
        else:
            output += "   (No specific price signals detected in community data)\n"
        
        output += f"\nAnalysis Date: {validation['researched_at']}\n"
        
        return output
