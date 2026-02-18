# Quick Start Guide - Intelligent Research System v2

## What You Now Have

An AI-powered research system that finds **real $5k MRR SaaS ideas in non-competitive markets** through:
- Real community data (Reddit, HackerNews, web search)
- Intelligent iteration (tries up to 5 different angles)
- Market validation (competitor research + willingness to pay + sales feasibility)
- Founder-sales optimization (high-value customers, no ads budget required)

## Installation

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment
# Edit .env file:
OPENAI_API_KEY=sk-proj-...
REDDIT_CLIENT_ID=...        # Optional (system falls back to mock data)
REDDIT_CLIENT_SECRET=...
REDDIT_USER_AGENT=researcher_v2
```

## Usage

### Option 1: Interactive Mode
```bash
python src/main.py

# System prompts you for a research topic
# Runs intelligent iteration loop (up to 5 iterations)
# Exports results to JSON
```

**Example Topics**:
- `freelance project managers dealing with scope creep`
- `small accounting firms handling tax compliance`
- `contractors hiring other contractors`
- `subscription box businesses with churn issues`
- `API integration companies serving SMBs`

### Option 2: Automated Test
```bash
python test_research.py

# Automatically runs research on: "junior react developers facing career stagnation"
# Exports: test_results.json
# Shows system behavior end-to-end
```

## System Output

**Console**: Real-time agent decisions, validation feedback, iteration progress

**JSON Export** (after research completes):
```json
{
  "topic": "your research topic",
  "final_verdict": "GO" | "QUALIFIED" | "NO_QUALIFIED_IDEA",
  "final_idea": "ProductName: [Full strategist proposal]",
  "iteration_count": 2,
  "iterations": [
    {"iteration": 1, "verdict": "NO GO", ...},
    {"iteration": 2, "verdict": "QUALIFIED", ...}
  ],
  "researched_at": "2026-02-16T..."
}
```

## How It Works

### 1. ITERATION LOOP (max 5 times)

```
Scout (finds real complaints)
  ↓
Analyst (filters for painkiller problems)
  ↓
Strategist (creates $5k MRR MVP idea)
  ↓
CompetitorResearcher (validates market gap)
  ↓
WillingnessValidator (checks if customers will pay)
  ↓
FounderSalesValidator (confirms founder can reach $5k)
  ↓
Skeptic (GO / NO GO verdict)

If QUALIFIED/GO → ✓ Export results, done
If NO GO → Analyze failure reason → Pivot & retry
```

### 2. AUTO-PIVOT ON FAILURE

When Skeptic says NO GO, system auto-pivots:

| Failure Reason | Action |
|---|---|
| Market saturated | Ask user for new topic, restart Scout |
| Low willingness to pay | Return to Strategist, raise price point |
| Unfeasible sales volume | Reduce MVP scope, simplify features |
| Saturated market | Find adjacent market angle |

## Key Decisions

### Verdict Types

- **GO**: Excellent idea, proceed to launch
- **QUALIFIED**: Good idea after validation, proceed with caution  
- **NO GO**: Market too saturated or unfeasible, needs pivot
- **NO_QUALIFIED_IDEA**: Exhausted 5 iterations without qualified idea

### Price Targeting

System targets **HIGH-VALUE customers** ($300-500/mo), not low-value volume:
- Easier to reach (founder outreach works)
- No marketing budget required
- Faster to $5k MRR (only need 10-15 customers)
- Sustainable (better retention)

### Data Quality

All data is real or "fails loudly":
- ✓ Reddit posts with upvotes/engagement
- ✓ HackerNews top posts and comments
- ✓ Web search results with sources
- ✗ NO synthetic fallback - system refuses to proceed if data unavailable

## Customization

### Change Research Topic Mid-Run
When prompted for new topic during pivot:
```
[Orchestrator] Suggest pivot to: 'small agency project management'? Or enter new topic: 
```

Just type a new topic and press Enter.

### Adjust Max Iterations
Edit in `src/core/orchestrator.py`:
```python
self.max_iterations = 5  # Change to desired number
```

### Add More Data Sources
Edit `src/utils/data_collector.py`:
```python
def collect(self, query, topic, limit=15):
    # Add new collect_twitter(), collect_linkedin(), etc.
```

### Tune Agent Prompts
Edit `src/prompts.py`:
```python
SKEPTIC_PROMPT = """
Your customized instructions...
"""
```

## Troubleshooting

### No Real Data Found
**Symptom**: "Scout failed to collect real data. Iteration abandoned."

**Why**: Reddit API authentication failed (401), HackerNews returned no results, DuckDuckGo has rate limit

**Fix**: 
- Add valid Reddit credentials to `.env`
- Try different search topic
- Wait before retrying (rate limits)

### Topic Exhausted (5 iterations)
**Symptom**: "Reached max iterations (5). Stopping research."

**Why**: System couldn't find $5k MRR idea with viable market gap

**Fix**:
- Restart with different topic
- Try more specific niche
- Consider different customer segment

### Unicode Errors in Console
**Symptom**: "UnicodeEncodeError" with special characters

**Why**: Windows CMD can't render certain Unicode (✓, ✗, etc.)

**Fix**: Already fixed in code - using ASCII alternatives

## Metrics That Matter

When evaluating research results:

| Metric | Target | Signal |
|--------|--------|--------|
| Data Quality | >80% real sources | Trust the analysis |
| Competitor Count | 0-3 | Market gap exists |
| Willingness Score | >60% | Customers will pay |
| Feasibility | VIABLE | Founder can achieve $5k in 1mo |
| Iteration Count | <3 | Good product-market fit |

## Next Steps After Research

### If QUALIFIED/GO:
1. Create founding customer list (10-15 high-value targets)
2. Design outreach sequence (LinkedIn, cold email, communities)
3. Build MVP (target: buildable in 1 month)
4. Validate with 3-5 pre-sales conversations
5. Launch beta (aim for $5k MRR by day 30)

### If NO GO:
1. Analyze Skeptic feedback for specific issue
2. Adjust: market, pricing, features, customer segment
3. Restart with new topic or pivot

## Pro Tips

1. **Be Specific with Topics**: "Contractors managing projects" → Better than "Project management"
2. **Know Your Market**: Research existing tools before starting
3. **Test Multiple Topics**: Run 5-10 research iterations to find patterns
4. **Track Results**: Save all JSON outputs for pattern analysis
5. **Iterate Based on Feedback**: If results are bad, adjust prompts (use `src/prompts.py`)

## System Architecture

```
src/
├── main.py                    # Entry point, agent setup
├── agents/
│   ├── scout.py              # Scrapes real community data
│   ├── competitor_researcher.py
│   ├── willingness_validator.py
│   └── founder_sales_validator.py
├── core/
│   ├── agent.py              # Base agent + LLM interface
│   └── orchestrator.py        # Iteration loop + pivoting logic
├── utils/
│   ├── data_collector.py      # Real data aggregation
│   ├── reddit_client.py       # Reddit API
│   └── search_client.py       # DuckDuckGo
└── prompts.py                 # Agent system prompts
```

## Deployment

Ready to deploy on:
- **AWS Lambda**: Serverless, event-triggered research
- **Modal**: Simple scaling, free tier available
- **Local**: Development, single-run research
- **Cron Job**: Automated daily/weekly research

Would you like a deployment guide for any of these?

---

## Questions?

- **How long does research take?** ~2-3 minutes per iteration (gpt-4o inference)
- **How much does it cost?** ~$0.10-0.30 per research (OpenAI API)
- **Can I use different LLM?** Yes, edit `src/core/agent.py` to use any OpenAI-compatible API
- **What if competitors exist?** System continues seeking high-value/low-volume niches
- **Can ideas be refined?** Yes, Skeptic feedback can be used to pivot

**Ready to find your first $5k MRR idea? Run `python src/main.py` now!**
