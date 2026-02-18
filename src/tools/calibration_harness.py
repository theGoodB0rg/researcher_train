"""
Calibration harness for tuning scorecard and gate thresholds across many topics.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from dotenv import load_dotenv

from src.agents.competitor_researcher import CompetitorResearcherAgent
from src.agents.founder_sales_validator import FounderSalesValidatorAgent
from src.agents.scout import ScoutAgent
from src.agents.willingness_validator import WillingnessToPayValidatorAgent
from src.config import get_settings
from src.core.agent import Agent
from src.core.orchestrator import Orchestrator
from src.prompts import (
    ANALYST_PROMPT,
    COMPETITOR_RESEARCHER_PROMPT,
    FOUNDER_SALES_PROMPT,
    SCOUT_PROMPT,
    SKEPTIC_PROMPT,
    STRATEGIST_PROMPT,
    WILLINGNESS_PROMPT,
)


class StaticMockAgent:
    def __init__(self, name: str, response: str):
        self.name = name
        self.response = response

    def process(self, input_data: str, context: Optional[List[Dict[str, str]]] = None) -> str:
        return self.response


def build_live_agents() -> Dict[str, Any]:
    return {
        "Trend Scout": ScoutAgent("Trend Scout", "Researcher", SCOUT_PROMPT, color="cyan"),
        "Pain Analyst": Agent("Pain Analyst", "Product Manager", ANALYST_PROMPT, color="blue"),
        "SaaS Strategist": Agent("SaaS Strategist", "Founder", STRATEGIST_PROMPT, color="magenta"),
        "Competitor Researcher": CompetitorResearcherAgent(
            "Competitor Researcher",
            "Market Analyst",
            COMPETITOR_RESEARCHER_PROMPT,
            color="cyan",
        ),
        "Willingness Validator": WillingnessToPayValidatorAgent(
            "Willingness Validator",
            "Market Researcher",
            WILLINGNESS_PROMPT,
            color="blue",
        ),
        "Founder Sales Validator": FounderSalesValidatorAgent(
            "Founder Sales Validator",
            "Sales Expert",
            FOUNDER_SALES_PROMPT,
            color="green",
        ),
        "The Skeptic": Agent("The Skeptic", "VC", SKEPTIC_PROMPT, color="red"),
    }


def build_mock_agents() -> Dict[str, Any]:
    return {
        "Trend Scout": StaticMockAgent(
            "Trend Scout",
            (
                "1. Manual follow-up takes hours each week.\n"
                "2. Teams repeatedly copy data between systems.\n"
                "3. Owners complain about recurring compliance admin work."
            ),
        ),
        "Pain Analyst": StaticMockAgent(
            "Pain Analyst",
            (
                "Top 3 Validated Problems\n"
                "Boring Score: 8\n"
                "Boring Score: 7\n"
                "Boring Score: 9\n"
                "Structured Evidence Table: Buyer=Operations Manager"
            ),
        ),
        "SaaS Strategist": StaticMockAgent(
            "SaaS Strategist",
            (
                "1. The Pitch: OpsPulse reduces recurring admin bottlenecks.\n"
                "2. The MVP Feature Set: intake, routing, compliance reminders.\n"
                "3. Pricing Model: $250/month for small business operations teams.\n"
                "4. Acquisition Channel: direct outbound and community groups.\n"
                "5. Budget Owner: Operations Manager."
            ),
        ),
        "Competitor Researcher": StaticMockAgent(
            "Competitor Researcher",
            (
                "1. Competitors Found: 3\n"
                "2. Market Saturation Assessment: YELLOW\n"
                "3. Differentiation Opportunities: vertical niche wedge.\n"
                "4. Recommendation: PROCEED"
            ),
        ),
        "Willingness Validator": StaticMockAgent(
            "Willingness Validator",
            (
                "1. Price Willingness Score: 68%\n"
                "2. Key signals of payment intent: teams report cost and delay from manual work.\n"
                "3. Price elasticity: acceptable.\n"
                "4. Recommendation: STRONG SIGNAL"
            ),
        ),
        "Founder Sales Validator": StaticMockAgent(
            "Founder Sales Validator",
            (
                "1. Customers Needed to Hit $5k MRR: 20\n"
                "2. Acquisition Scenario: medium value.\n"
                "3. Founder Effort Estimate: 160 hours.\n"
                "4. 1-Month Feasibility: CHALLENGING."
            ),
        ),
        "The Skeptic": StaticMockAgent(
            "The Skeptic",
            (
                "1. The Kill Switch: none critical.\n"
                "2. Validation Summary: acceptable signals.\n"
                "3. Final Verdict: QUALIFIED\n"
                "Final Verdict: QUALIFIED"
            ),
        ),
    }


def load_topics(topics: Sequence[str], topics_file: Optional[Path]) -> List[str]:
    selected = [topic.strip() for topic in topics if topic and topic.strip()]
    if topics_file:
        file_topics = [
            line.strip()
            for line in topics_file.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        selected.extend(file_topics)
    deduped: List[str] = []
    seen = set()
    for topic in selected:
        key = topic.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(topic)
    return deduped


def run_calibration(
    topics: Sequence[str],
    output_path: Path,
    use_live_agents: bool = False,
    max_iterations: int = 3,
) -> Dict[str, Any]:
    runs: List[Dict[str, Any]] = []
    agents = build_live_agents() if use_live_agents else build_mock_agents()

    for topic in topics:
        orchestrator = Orchestrator(agents=agents, max_iterations=max_iterations, interactive_pivots=False)
        result = orchestrator.run_round_table(topic)
        runs.append(
            {
                "topic": topic,
                "mode": result.get("mode"),
                "final_verdict": result.get("final_verdict"),
                "iteration_count": result.get("iteration_count"),
                "iterations": result.get("iterations", []),
                "researched_at": result.get("researched_at"),
            }
        )

    summary = aggregate_calibration(runs)
    payload = {
        "generated_at": datetime.now().isoformat(),
        "use_live_agents": use_live_agents,
        "max_iterations": max_iterations,
        "topic_count": len(topics),
        "summary": summary,
        "runs": runs,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def aggregate_calibration(runs: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    verdict_counts = Counter(str(run.get("final_verdict", "UNKNOWN")) for run in runs)
    weighted_scores: List[float] = []
    qualified_scores: List[float] = []
    no_go_scores: List[float] = []
    gate_issue_counts = Counter()

    for run in runs:
        for iteration in run.get("iterations", []):
            scorecard = iteration.get("scorecard") or {}
            weighted = scorecard.get("weighted_score")
            if isinstance(weighted, (int, float)):
                weighted_scores.append(float(weighted))
                verdict = str(iteration.get("verdict", "")).upper()
                if verdict in {"GO", "QUALIFIED"}:
                    qualified_scores.append(float(weighted))
                if verdict == "NO GO":
                    no_go_scores.append(float(weighted))

            hard_gates = iteration.get("hard_gates") or {}
            for issue in hard_gates.get("issues", []):
                gate_issue_counts[str(issue)] += 1

    run_count = max(1, len(runs))
    go_like = verdict_counts.get("GO", 0) + verdict_counts.get("QUALIFIED", 0)
    go_rate = round((go_like / run_count) * 100, 2)

    return {
        "run_count": len(runs),
        "go_rate_percent": go_rate,
        "verdict_counts": dict(verdict_counts),
        "average_weighted_score": round(sum(weighted_scores) / len(weighted_scores), 2) if weighted_scores else None,
        "average_weighted_score_go_or_qualified": (
            round(sum(qualified_scores) / len(qualified_scores), 2) if qualified_scores else None
        ),
        "average_weighted_score_no_go": round(sum(no_go_scores) / len(no_go_scores), 2) if no_go_scores else None,
        "hard_gate_issue_counts": dict(gate_issue_counts),
    }


def _default_output_path() -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path(f"calibration_results_{timestamp}.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run calibration harness for idea scoring and gating.")
    parser.add_argument("--topic", action="append", default=[], help="Topic to evaluate. Can be used multiple times.")
    parser.add_argument("--topics-file", type=Path, help="Path to newline-separated topics file.")
    parser.add_argument("--output", type=Path, default=None, help="Path to output JSON report.")
    parser.add_argument("--max-iterations", type=int, default=3, help="Max orchestrator iterations per topic.")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Use live OpenAI agents and external data sources. Default uses deterministic mock agents.",
    )
    return parser.parse_args()


def main() -> int:
    load_dotenv()
    args = parse_args()

    topics = load_topics(args.topic, args.topics_file)
    if not topics:
        print("No topics provided. Use --topic or --topics-file.")
        return 1

    if args.live and not get_settings().openai_api_key:
        print("OPENAI_API_KEY is required when running with --live.")
        return 1

    output_path = args.output or _default_output_path()
    payload = run_calibration(
        topics=topics,
        output_path=output_path,
        use_live_agents=args.live,
        max_iterations=max(1, args.max_iterations),
    )

    summary = payload["summary"]
    print(f"Calibration complete. Results written to: {output_path}")
    print(f"Runs: {summary['run_count']} | GO/QUALIFIED rate: {summary['go_rate_percent']}%")
    print(f"Verdicts: {summary['verdict_counts']}")
    print(f"Average weighted score: {summary['average_weighted_score']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
