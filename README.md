# Expert Eureka

Expert Eureka is an autonomous multi-agent AI system designed to simulate a co-founder team for researching, validating, and refining SaaS business ideas. By leveraging a specialized team of AI agents, the system identifies high-potential "boring" problems, proposes viable software solutions, and rigorously critiques them for market viability.

## Overview

The system operates as a sequential pipeline of four distinct AI personas, each with a specific role in the research and ideation process:

1.  **Trend Scout (Researcher)**: Scans the web using DuckDuckGo to identify real-world complaints, operational inefficiencies, and recurring problems in specific industries.
2.  **Pain Analyst (Product Manager)**: Analyzes the raw data to filter for "boring but sticky" problems. It evaluates issues based on pain intensity, frequency, and willingness to pay.
3.  **SaaS Strategist (Founder)**: Develops a concrete MVP (Minimum Viable Product) proposal and business model (specifically targeting \$5k MRR) for the validated problem.
4.  **The Skeptic (Venture Capitalist)**: Performs a critical risk assessment, challenging assumptions about implementation, competition, and distribution to prevent costly failures.

## Features

-   **Autonomous Web Research**: Uses modular source providers (Reddit, HackerNews, DuckDuckGo) with strict provenance metadata.
-   **Multi-Agent Architecture**: Implements a modular agent system where context is passed and refined through strictly defined personas.
-   **OpenAI Integration**: Powered by GPT-4o for high-level reasoning, synthesis, and critique.
-   **Risk Analysis**: Includes a dedicated adversarial agent to identify "kill switches" and reasons for potential failure.
-   **Strict Real-Data Mode**: Synthetic fallback is disabled by default (`ALLOW_MOCK_DATA=false`) so results are decision-grade.

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
    ```

    *Note: Reddit credentials are optional but recommended for stronger community-signal quality.*

## Usage

Run the main application entry point:

```bash
python src/main.py
```

Or use the provided batch script on Windows:

```bash
run.bat
```

### Operation
1.  The system will initialize the agent team.
2.  Enter a research topic or industry niche (e.g., "dental practice", "inventory management", "plumbers").
3.  Observe the agents as they research, analyze, propose, and critique ideas in real-time.

## Project Structure

-   `src/core/`: Contains the base `Agent` and `Orchestrator` classes.
-   `src/agents/`: Specialized agent implementations (e.g., `ScoutAgent`).
-   `src/utils/`: Utility modules for search and API interactions.
-   `src/prompts.py`: System definitions and persona instructions for the AI agents.

## License

This project is open source and available under the MIT License.
