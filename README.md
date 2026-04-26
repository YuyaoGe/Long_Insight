<div align="center">
  <a href="https://geyuyao.com/long-insight/"><img src="assets/logo.webp" alt="Long-Insight logo" width="100%" /></a>

  **Interactive analysis and visualization platform for long-context agent trajectories.**

  <a href="https://geyuyao.com/long-insight/"><img src="https://img.shields.io/badge/🌐_Website-Long--Insight-blue" /></a>&nbsp;
  <a href="https://geyuyao.com/project/long-insight/"><img src="https://img.shields.io/badge/📝_Blog-Project_Page-red" /></a>&nbsp;
  <a href="https://github.com/YuyaoGe/Long_Insight#quick-start"><img src="https://img.shields.io/badge/🚀_Quick_Start-Guide-2ea44f" /></a>

</div>

Long-Insight is designed for **ultra-long agent trajectories** — the kind produced by frontier coding agents solving real-world software engineering tasks. These trajectories routinely span **400+ turns** and exceed **1M tokens**, making manual inspection practically impossible. Long-Insight decomposes these massive trajectories into structured, hierarchical step DAGs, scores their quality, and renders them as interactive visualizations.

## The Problem

When LLM-based coding agents (e.g., Claude Code, Cursor, Devin) tackle complex software tasks, they generate extremely long execution trajectories:

- **400+ interaction turns** per task — far beyond what a human can read through
- **1,000,000+ tokens** of context — tool calls, code edits, test outputs, reasoning traces
- **Complex branching behavior** — parallel exploration paths, backtracking, retries

These trajectories contain rich signal about agent capabilities and failure modes, but their sheer length makes analysis intractable. Long-Insight solves this by automatically compressing and structuring the raw trajectory into an interpretable DAG.

## Overview

| Module | What it does |
|--------|-------------|
| **Analyzer** | Decomposes long-context trajectories (400+ turns, 1M+ tokens) into a DAG of logical steps |
| **Evaluator** | Scores trajectories on problem difficulty (0–10) and improvement potential (0–10) via two-stage LLM evaluation |
| **Visualizer** | Generates interactive HTML visualizations with zoomable DAGs, color-coded step types, and detail panels |

```
Raw Trajectory          Structured Analysis          Interactive Output
(400+ turns)            (Step DAG)                   (HTML / Charts)

┌──────────┐     ┌─────────────────────┐     ┌──────────────────────┐
│ JSONL    │────→│ [Analyzer]          │────→│ [Visualizer]         │
│ 1M+ tok  │     │  Step Decomposition │     │  Zoomable DAG HTML   │
└──────────┘     │  DAG Construction   │     └──────────────────────┘
                 └─────────────────────┘
┌──────────┐     ┌─────────────────────┐     ┌──────────────────────┐
│ JSONL    │────→│ [Evaluator]         │────→│ Score Distribution   │
│ 1M+ tok  │     │  Difficulty Scoring │     │  Charts + Reports    │
└──────────┘     │  Quality Detection  │     └──────────────────────┘
```

## Quick Start

### Installation

```bash
git clone https://github.com/YuyaoGe/Long_Insight.git
cd Long_Insight
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
│   ├── compressor.py      # Trajectory compression for long-context inputs
│   └── prompts.py         # Analysis prompt templates + JSON schema
├── evaluator/
│   ├── scorer.py           # Two-stage concurrent trajectory scorer
│   └── prompts.py          # Difficulty + improvement potential prompts
└── visualizer/
    ├── dag.py              # Interactive HTML DAG generator
    └── charts.py           # Matplotlib score distribution charts
```

## Step Decomposition

The analyzer processes each turn of a long-context agent trajectory and classifies it into one of 8 step types:

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

Steps form a **directed acyclic graph (DAG)** — a step can depend on multiple parent steps, capturing the branching and merging patterns common in long trajectories (e.g., parallel file exploration → converging implementation).

### Trajectory Compression

Raw trajectories at the 1M-token scale cannot be fed directly to an analysis LLM. The built-in compressor:
- Truncates verbose thinking blocks (keep head + tail)
- Compresses tool output and observation content
- Strips redundant metadata (signatures, etc.)

This reduces token consumption by 60–80% while preserving the causal structure needed for accurate step decomposition.

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

Standard JSONL with one trajectory per line. Each trajectory typically contains 400+ turns and 1M+ tokens:

```json
{
  "instance_id": "repo__issue-123",
  "problem_statement": "Fix the login validation...",
  "resolved": true,
  "rounds": 450,
  "tokens": 1200000,
  "messages": [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
  ]
}
```

## CLI Reference

```bash
# Step decomposition
long-insight analyze <input.jsonl> [-o output.json] [--max-turns 500]

# Quality evaluation
long-insight evaluate <input.jsonl> [-o output.jsonl] [--sample 50] [--chart]

# DAG visualization
long-insight visualize <steps.json> [-o output.html] [--title "My Analysis"]

# Full pipeline
long-insight pipeline <input.jsonl> [--output-dir output/] [--max-turns 500]

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
| `MAX_TURNS_TO_ANALYZE` | `500` | Default max turns for analysis |
| `DEBUG` | `false` | Enable debug logging |

## License

MIT
