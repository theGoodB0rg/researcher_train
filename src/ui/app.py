import os
import sys
import re
import threading
import builtins
import contextlib

import streamlit as st
from dotenv import load_dotenv

# Ensure project root is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

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
    COMPETITOR_RESEARCHER_PROMPT, WILLINGNESS_PROMPT, FOUNDER_SALES_PROMPT, CHAT_BOT_PROMPT
)

load_dotenv()

def clean_ansi(text):
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)

class StreamlitPrintCapture:
    def __init__(self, st_container):
        self.st_container = st_container
        self.original_print = builtins.print
        
    def __enter__(self):
        def patched_print(*args, **kwargs):
            text = " ".join(str(val) for val in args)
            clean_text = clean_ansi(text)
            if clean_text.strip():
                # Avoid printing full agent messages in the status block if we can,
                # but since we capture everything, we'll just log it.
                self.st_container.markdown(f"```text\n{clean_text}\n```")
            self.original_print(*args, **kwargs)
        builtins.print = patched_print
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        builtins.print = self.original_print

st.set_page_config(page_title="AI Research Co-Founder", page_icon="🕵️", layout="wide")

st.sidebar.header("Project Settings")
business_model = st.sidebar.radio("Business Model", ["B2B", "B2C"])
target_mrr = st.sidebar.slider("Target MRR ($/mo)", min_value=1, max_value=5000, value=50, step=10, help="Minimum monthly revenue per user to sustain the business")

project_settings = {
    "business_model": business_model,
    "target_mrr": target_mrr
}

st.title("🕵️ AI Research Co-Founder")
st.markdown("Enter your idea or hypothesis to begin the buyer-aware iterative research process.")

if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("E.g. I want to build a tool for plumbers to track invoices..."):
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Initialize Agents
    agents = {
        "Intake Router": IntakeRouterAgent("Intake Router", "Research Planner", INTAKE_ROUTER_PROMPT, color="yellow"),
        "Trend Scout": ScoutAgent("Trend Scout", "Researcher", SCOUT_PROMPT, color="cyan"),
        "Pain Analyst": Agent("Pain Analyst", "Product Manager", ANALYST_PROMPT, color="blue"),
        "SaaS Strategist": Agent("SaaS Strategist", "Founder", STRATEGIST_PROMPT, color="magenta"),
        "Competitor Researcher": CompetitorResearcherAgent("Competitor Researcher", "Market Analyst", COMPETITOR_RESEARCHER_PROMPT, color="cyan"),
        "Willingness Validator": WillingnessToPayValidatorAgent("Willingness Validator", "Market Researcher", WILLINGNESS_PROMPT, color="blue"),
        "Founder Sales Validator": FounderSalesValidatorAgent("Founder Sales Validator", "Sales Expert", FOUNDER_SALES_PROMPT, color="green"),
        "The Skeptic": Agent("The Skeptic", "VC", SKEPTIC_PROMPT, color="red"),
        "Chat Bot": Agent("Chat Bot", "Co-Founder", CHAT_BOT_PROMPT, color="white"),
    }
    
    settings = get_settings()
    orchestrator = Orchestrator(agents, max_iterations=settings.max_iterations, interactive_pivots=False)

    # Monkey patch the orchestrator's broadcast to also stream to Streamlit
    original_broadcast = orchestrator.broadcast
    def st_broadcast(sender_name: str, message: str):
        original_broadcast(sender_name, message)
        # Store in session state so it persists across reruns
        st.session_state.messages.append({"role": "assistant", "content": f"**{sender_name}**\n\n{message}"})
        # Note: We don't call st.chat_message here directly to avoid nesting inside st.status
        
    orchestrator.broadcast = st_broadcast

    # Create a placeholder for live messages above the status block if we wanted, 
    # but the print capture will put it in the status block anyway.
    with st.status("Agents are parsing request...", expanded=True) as status:
        with StreamlitPrintCapture(status):
            # Extract context for the Chat Bot
            chat_context = [{"role": msg["role"], "content": msg["content"]} for msg in st.session_state.messages[:-1]]
            try:
                orchestrator.run_round_table(
                    prompt, 
                    context=st.session_state.messages,
                    project_settings=project_settings
                )
                
                final_state = orchestrator.research_results.get('final_verdict', 'UNKNOWN')
            except Exception as e:
                st.error(f"An error occurred during orchestration: {e}")
                final_state = "ERROR"
        
        if final_state == "CONVERSATIONAL":
            status.update(label="Response", state="complete", expanded=False)
        else:
            status.update(label="Research Complete!", state="complete", expanded=False)
        
        if final_state == "CONVERSATIONAL":
            reply = orchestrator.research_results.get("final_recommendation", "How can I help you refine this idea?")
            st.markdown(reply)
            st.session_state.messages.append({"role": "assistant", "content": reply})
        else:
            st.markdown(f"### Research Complete\n**Final Verdict:** {final_state}")
            
            if final_state in ["GO", "QUALIFIED"] and "final_idea" in orchestrator.research_results:
                st.markdown("### Validated Idea")
                st.markdown(orchestrator.research_results["final_idea"])
            
            st.session_state.messages.append({"role": "assistant", "content": f"**Research Complete**\nVerdict: {final_state}"})
