import json
import re

from src.agents.intake_router import IntakeRouterAgent
from src.prompts import INTAKE_ROUTER_PROMPT

router = IntakeRouterAgent("Intake Router", "Research Planner", INTAKE_ROUTER_PROMPT, color="yellow")
prompt = "Route and normalize this research request:\nHi, I'm just here to brainstorm some ideas."
# 1. Get raw string from process()
output = router.process(prompt)

# 2. Simulate _parse_intake_plan
print("--- EXACT OUTPUT STRING ---")
print(output)
print("--- PRE-PARSE REGEX ---")
match = re.search(r"(\{.*\})", output, re.DOTALL)
print("REGEX MATCH FOUND:", match is not None)
if match:
    loaded = json.loads(match.group(1))
    print("LOADED TYPE:", type(loaded))
    print("LOADED CONTENT:")
    print(loaded)
    print("INTENT VALUE:", loaded.get("intent"))
    print("IS IT CONVERSATIONAL?", loaded.get("intent") == "CONVERSATIONAL")
