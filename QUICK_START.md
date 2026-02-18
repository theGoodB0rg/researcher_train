# Quick Start Guide - Intelligent Research System v3

## What You Have

A B2B-first multi-agent research workflow optimized for realistic paths to $5k MRR:
- Real-source scouting (Reddit/HackerNews/Web).
- Context-aware routing (`B2B_STRICT`, `B2B_DISCOVERY`, `B2C_PLG`).
- Buyer-first mode (`buyer: ...; workflow: ...; pain: ...`) for stronger initial problem framing.
- Deterministic scorecard (pain, frequency, willingness, competition, buildability, mode-fit).
- Composite willingness model (direct intent + market pricing anchor + buyer budget + cost of inaction).
- Hard gates by mode:
  - B2B: budget owner, price floor, competition wedge, sales feasibility.
  - B2C_PLG: self-serve pricing band, PLG channel, competition wedge, willingness floor.
- Iterative pivots with non-repeating fallback topics.
- Calibration harness for threshold tuning across topic batches.

## Setup

```bash
pip install -r requirements.txt
```

`.env` baseline:

```env
OPENAI_API_KEY=sk-your-key
OPENAI_MODEL=gpt-4o
MAX_ITERATIONS=5
REQUIRE_REAL_DATA=true
ALLOW_MOCK_DATA=false
ENABLE_REDDIT_SOURCE=false
MIN_RECORD_QUALITY_SCORE=0.50
SOURCE_TIMEOUT_SEC=8
HN_LOOKBACK_DAYS=180
HN_INCLUDE_COMMENTS=true
```

## Run

Interactive run:

```bash
python src/main.py
```

Buyer-first example input:

```text
buyer: staffing agencies; workflow: candidate intake; pain: manual profile updates
```

B2C_PLG example input:

```text
portfolio website maker using resume or linkedin profile
```

## Calibration Harness

Mock mode (deterministic, no API spend):

```bash
python -m src.tools.calibration_harness --topic "small business accounting" --topic "agency operations"
```

Live mode (real agents + real sources):

```bash
python -m src.tools.calibration_harness --live --topics-file topics.txt --max-iterations 3
```

Output file: `calibration_results_*.json`

Contains:
- Per-topic run metadata.
- Per-iteration scorecard + gate diagnostics.
- Aggregate verdict counts and weighted-score summaries.
- Hard-gate failure frequencies for tuning.

## Result JSON (Main Orchestrator)

`research_results_*.json` now includes:
- `mode`: selected routing mode.
- `iterations[].scorecard`: component-level scores + weighted score.
- `iterations[].hard_gates`: blocked flag, issues, pivot reason.

## Validation Commands

```bash
python -m unittest -v
python -m py_compile src/core/orchestrator.py src/agents/competitor_researcher.py src/agents/founder_sales_validator.py src/agents/willingness_validator.py src/prompts.py src/tools/calibration_harness.py
```

## What Changed in This Iteration

- Added context-aware topic mode router.
- Added deterministic opportunity scoring.
- Added hard-gate enforcement before acceptance.
- Fixed repeated-topic pivot issue.
- Fixed competitor pitch parsing/search-seed noise (`pitch pitch` issue).
- Hardened monthly price extraction to avoid `$5k` parsing errors.
- Tightened willingness-signal extraction to evidence-bearing sources.
- Added calibration harness + tests.
- Added buyer-first brief parsing and routing.
- Replaced quote-only willingness gate with composite willingness scoring.
- Added B2C_PLG routing, prompts, pivots, and mode-specific hard gates without changing B2B strict gates.
- Updated docs and ignored calibration output artifacts.
