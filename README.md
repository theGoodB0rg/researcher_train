# Expert Eureka

Expert Eureka is a multi-agent research system for finding realistic B2B micro-SaaS opportunities with a path to $5k MRR. It combines real-source scouting with deterministic scoring, hard validation gates, and iterative pivots.

## Overview

The system runs as a staged pipeline:

1.  **Trend Scout (Researcher)**: Scans the web using DuckDuckGo to identify real-world complaints, operational inefficiencies, and recurring problems in specific industries.
2.  **Pain Analyst (Product Manager)**: Analyzes the raw data to filter for "boring but sticky" problems. It evaluates issues based on pain intensity, frequency, and willingness to pay.
3.  **SaaS Strategist (Founder)**: Develops a concrete MVP (Minimum Viable Product) proposal and business model (specifically targeting \$5k MRR) for the validated problem.
4.  **Competitor / Willingness / Founder Sales Validators**: Add market saturation, payment intent, and acquisition-feasibility checks.
5.  **The Skeptic (Venture Capitalist)**: Makes the final GO / QUALIFIED / NO GO recommendation.

## Recent Upgrades (Implemented)

- **Context-aware topic routing**
  - `B2B_STRICT`: direct B2B topics.
  - `B2B_ADJACENT`: consumer topics are translated into business-operations pain.
  - `B2B_DISCOVERY`: neutral topics are reframed into operational discovery.
- **Deterministic opportunity scorecard**
  - Pain severity, frequency, willingness, competition whitespace, buildability, and mode-fit.
- **Hard gates before acceptance**
  - Budget owner must be explicit.
  - Monthly pricing should generally be \$150+.
  - RED competition without a wedge blocks.
  - DIFFICULT founder-sales feasibility blocks.
- **Non-repeating pivot behavior**
  - Auto-pivots no longer loop on the same topic text.
- **Competitor research hardening**
  - Fixed pitch parsing bug that could produce noisy `pitch pitch ...` queries.
  - Cleaner search seed extraction.
- **Validator extraction fixes**
  - Monthly price extraction no longer misreads `\$5k` as `\$5`.
  - Willingness signals are restricted to evidence-bearing agent outputs.
- **Calibration harness**
  - Batch-run topics and export scorecards, gate failures, verdict stats for threshold tuning.

## Features

-   **Autonomous Web Research**: Uses modular source providers (Reddit, HackerNews, DuckDuckGo) with strict provenance metadata.
-   **Multi-Agent Architecture**: Implements a modular agent system where context is passed and refined through strictly defined personas.
-   **OpenAI Integration**: Powered by GPT-4o for high-level reasoning, synthesis, and critique.
-   **Risk Analysis**: Includes a dedicated adversarial agent to identify "kill switches" and reasons for potential failure.
-   **Strict Real-Data Mode**: Synthetic fallback is disabled by default (`ALLOW_MOCK_DATA=false`) so results are decision-grade.
-   **Quality-Filtered Inputs**: Source evidence is scored and low-signal pages are filtered before analysis (`MIN_RECORD_QUALITY_SCORE`).
-   **Calibration Output**: Captures scorecard and gate telemetry per iteration for post-run tuning.

## Prerequisites

-   Python 3.8+
-   OpenAI API Key

## Installation

1.  **Clone the repository**
    ```bash
    git clone https://github.com/theGoodB0rg/expert-eureka.git
    cd expert-eureka
    ```

2.  **Create a virtual environment (Optional but Recommended)**
    ```bash
    python -m venv venv
    # Windows
    venv\Scripts\activate
    # macOS/Linux
    source venv/bin/activate
    ```

3.  **Install dependencies**
    ```bash
    pip install -r requirements.txt
    ```

## Configuration

1.  Copy the example environment file:
    ```bash
    cp .env.example .env
    # or manually create a .env file
    ```

2.  Edit `.env` and add your OpenAI API key:
    ```env
    OPENAI_API_KEY=sk-your-api-key-here
    OPENAI_MODEL=gpt-4o
    MAX_ITERATIONS=5
    REQUIRE_REAL_DATA=true
    ALLOW_MOCK_DATA=false
    ENABLE_REDDIT_SOURCE=false
    MIN_RECORD_QUALITY_SCORE=0.50
    ```

    *Note: Set `ENABLE_REDDIT_SOURCE=true` only if you have working Reddit credentials.*

## Usage

Run the main application entry point:

```bash
python src/main.py
```

Or use the provided batch script on Windows:

```bash
run.bat
```

Run the calibration harness (mock mode by default):

```bash
python -m src.tools.calibration_harness --topic "small business accounting" --topic "agency operations"
```

Run harness with live agents/data:

```bash
python -m src.tools.calibration_harness --live --topics-file topics.txt --max-iterations 3
```

### Operation
1.  The system will initialize the agent team.
2.  Enter a research topic or industry niche (e.g., "dental practice", "inventory management", "plumbers").
3.  Observe mode routing, scorecard output, hard-gate decisions, and final verdicts.

## Project Structure

-   `src/core/`: Contains the base `Agent` and `Orchestrator` classes.
-   `src/agents/`: Specialized agent implementations (e.g., `ScoutAgent`).
-   `src/utils/`: Utility modules for search and API interactions.
-   `src/tools/calibration_harness.py`: Batch harness for scoring/gate calibration and threshold tuning.
-   `src/prompts.py`: System definitions and persona instructions for the AI agents.

## License

This project is open source and available under the MIT License.
