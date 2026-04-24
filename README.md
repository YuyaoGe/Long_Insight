<p align="center">
  <img src="https://img.shields.io/badge/python-3.9+-blue.svg" alt="Python 3.9+">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="MIT License">
  <img src="https://img.shields.io/badge/LLM-OpenAI%20%7C%20Anthropic-orange.svg" alt="LLM Support">
</p>

# Long-Insight

**Interactive analysis and visualization platform for long-horizon agent trajectories.**

Long-Insight decomposes complex, multi-turn agent conversations into structured, hierarchical steps — then scores their quality and renders them as interactive DAG visualizations. Built for researchers studying LLM agent behavior in software engineering tasks.

## Overview

When LLM agents tackle real-world software tasks, they produce long trajectories (50–200+ turns) that are difficult to analyze manually. Long-Insight provides three capabilities:

| Module | What it does |
|--------|-------------|
| **Analyzer** | Decomposes trajectories into a DAG of logical steps (task understanding → exploration → implementation → testing) |
| **Evaluator** | Scores trajectories on problem difficulty (0–10) and improvement potential (0–10) via two-stage LLM evaluation |
| **Visualizer** | Generates interactive HTML visualizations with zoomable DAGs, color-coded step types, and detail panels |

```
Input JSONL ──→ [Analyzer] ──→ Step DAG (JSON)
                                    │
                                    ├──→ [Visualizer] ──→ Interactive HTML
                                    │
Input JSONL ──→ [Evaluator] ──→ Scored JSONL + Charts
```

## Quick Start

### Installation

```bash
git clone https://github.com/YuyaoGe/Long-Insight.git
cd Long-Insight
pip install -e .
```

### Set up API key

```bash
export OPENAI_API_KEY="your-key"
# or
export ANTHROPIC_API_KEY="your-key"
```

### Run the full pipeline

```bash
# Decompose a trajectory into steps and generate visualization
long-insight pipeline trajectory.jsonl --output-dir output/

# Or run individual stages:
long-insight analyze trajectory.jsonl -o steps.json
long-insight visualize steps.json -o visualization.html
long-insight evaluate trajectory.jsonl --chart
```

## Architecture

```
long_insight/
├── config.py              # Centralized configuration via env vars
├── cli.py                 # Unified CLI entry point
├── llm/
│   └── client.py          # Multi-provider LLM client (OpenAI + Anthropic)
├── analyzer/
│   ├── decomposer.py      # Step decomposition with DAG parent tracking
│   ├── compressor.py      # Message compression for token efficiency
│   └── prompts.py         # Analysis prompt templates + JSON schema
├── evaluator/
│   ├── scorer.py           # Two-stage concurrent trajectory scorer
│   └── prompts.py          # Difficulty + improvement potential prompts
└── visualizer/
    ├── dag.py              # Interactive HTML DAG generator
    └── charts.py           # Matplotlib score distribution charts
```

## Step Decomposition

The analyzer classifies each turn of an agent trajectory into one of 8 step types:

| Type | Description |
|------|-------------|
| `task_understanding` | Reading requirements, analyzing the problem |
| `project_exploration` | Browsing files, searching code, reading docs |
| `environment_setup` | Installing dependencies, creating directories |
| `code_implementation` | Writing or modifying source code |
| `test_verification` | Running tests, checking correctness |
| `debugging` | Analyzing errors, fixing bugs |
| `documentation` | Writing docs, notes, summaries |
| `planning` | Strategizing, making plans |

Steps form a **directed acyclic graph (DAG)** — a step can depend on multiple parent steps, enabling representation of parallel work streams that later converge.

## Two-Stage Evaluation

### Stage 1: Problem Difficulty (0–10)

Scores based on:
- Intrinsic problem complexity (files, logic, edge cases)
- Fix difficulty (architecture understanding required)
- Problem description clarity
- Project scale (issue count)
- Actual resolution difficulty (rounds, tokens, test results)

### Stage 2: Improvement Potential (0–10)

Detects 8 anti-patterns in agent behavior:
- **Test avoidance** — skipping failed tests
- **Missing verification** — no re-test after changes
- **Repetitive loops** — circular behavior
- **Inefficient exploration** — irrelevant file browsing
- **Ignored errors** — not responding to error messages
- **Verbose thinking** — long reasoning with little substance
- **Mid-trajectory deviation** — going off-track
- **Late-stage waste** — unnecessary work after problem is solved

## Input Format

Standard JSONL with one trajectory per line:

```json
{
  "instance_id": "repo__issue-123",
  "problem_statement": "Fix the login validation...",
  "resolved": true,
  "rounds": 45,
  "tokens": 12000,
  "messages": [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
  ]
}
```

## CLI Reference

```bash
# Step decomposition
long-insight analyze <input.jsonl> [-o output.json] [--max-turns 100]

# Quality evaluation
long-insight evaluate <input.jsonl> [-o output.jsonl] [--sample 50] [--chart]

# DAG visualization
long-insight visualize <steps.json> [-o output.html] [--title "My Analysis"]

# Full pipeline
long-insight pipeline <input.jsonl> [--output-dir output/] [--max-turns 100]

# Global options
--provider openai|anthropic    # LLM provider
--api-key KEY                  # API key (or use env var)
--base-url URL                 # Custom API endpoint
```

## Configuration

All settings can be configured via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `openai` | LLM provider (`openai` or `anthropic`) |
| `OPENAI_API_KEY` | — | OpenAI API key |
| `ANTHROPIC_API_KEY` | — | Anthropic API key |
| `API_BASE_URL` | — | Custom API base URL |
| `LLM_MODEL` | `claude-sonnet-4` | Model name |
| `LLM_TEMPERATURE` | `0.7` | Sampling temperature |
| `LLM_MAX_TOKENS` | `4096` | Max output tokens |
| `DEFAULT_CONCURRENCY` | `32` | Thread pool size for evaluation |
| `MAX_TURNS_TO_ANALYZE` | `100` | Default max turns for analysis |
| `DEBUG` | `false` | Enable debug logging |

## License

MIT
