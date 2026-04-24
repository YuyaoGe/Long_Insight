"""Long-Insight CLI — unified entry point for trajectory analysis."""

import argparse
import os
import sys


def cmd_analyze(args):
    """Run step decomposition on a trajectory file."""
    from long_insight.analyzer.decomposer import StepDecomposer
    from long_insight.llm.client import LLMClient

    client = LLMClient(
        provider=args.provider,
        api_key=args.api_key or None,
        base_url=args.base_url or None,
    )
    decomposer = StepDecomposer(llm_client=client)

    output = args.output or os.path.splitext(args.input)[0] + "_steps.json"

    decomposer.analyze(
        trajectory_path=args.input,
        output_path=output,
        max_turns=args.max_turns,
    )
    return output


def cmd_evaluate(args):
    """Run two-stage quality scoring on trajectories."""
    from long_insight.evaluator.scorer import TrajectoryScorer
    from long_insight.llm.client import LLMClient

    client = LLMClient(
        provider=args.provider,
        api_key=args.api_key or None,
        base_url=args.base_url or None,
    )
    scorer = TrajectoryScorer(
        llm_client=client,
        sample_num=args.sample,
        resolved_only=args.resolved_only,
        concurrency=args.concurrency,
    )

    output = scorer.score_file(args.input, args.output)
    scorer.print_stats()

    if args.chart:
        from long_insight.visualizer.charts import plot_score_distribution

        chart_path = os.path.splitext(output)[0] + "_chart.png"
        plot_score_distribution(scorer.get_score_distribution(), chart_path)

    return output


def cmd_visualize(args):
    """Generate interactive DAG visualization."""
    from long_insight.visualizer.dag import visualize

    output = visualize(
        input_file=args.input,
        output_file=args.output,
        title=args.title,
    )
    return output


def cmd_pipeline(args):
    """Run full pipeline: analyze → evaluate → visualize."""
    from long_insight.analyzer.decomposer import StepDecomposer
    from long_insight.llm.client import LLMClient
    from long_insight.visualizer.dag import visualize

    client = LLMClient(
        provider=args.provider,
        api_key=args.api_key or None,
        base_url=args.base_url or None,
    )

    base = os.path.splitext(os.path.basename(args.input))[0]
    output_dir = args.output_dir or "output"
    os.makedirs(output_dir, exist_ok=True)

    # Step 1: Decompose
    steps_path = os.path.join(output_dir, f"{base}_steps.json")
    print(f"\n{'=' * 60}")
    print("Step 1: Trajectory Decomposition")
    print(f"{'=' * 60}")

    decomposer = StepDecomposer(llm_client=client)
    decomposer.analyze(
        trajectory_path=args.input,
        output_path=steps_path,
        max_turns=args.max_turns,
    )

    # Step 2: Visualize
    print(f"\n{'=' * 60}")
    print("Step 2: DAG Visualization")
    print(f"{'=' * 60}")

    html_path = os.path.join(output_dir, f"{base}_visualization.html")
    visualize(steps_path, html_path)

    print(f"\n{'=' * 60}")
    print("Pipeline Complete")
    print(f"{'=' * 60}")
    print(f"  Steps JSON: {steps_path}")
    print(f"  Visualization: {html_path}")


def main():
    parser = argparse.ArgumentParser(
        prog="long-insight",
        description="Long-Insight: Interactive analysis platform for long-horizon agent trajectories",
    )
    parser.add_argument("--version", action="version", version="%(prog)s 0.1.0")

    # Global options
    parser.add_argument("--provider", default=None, help="LLM provider: openai or anthropic")
    parser.add_argument("--api-key", default=None, help="API key (or use env var)")
    parser.add_argument("--base-url", default=None, help="API base URL")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # analyze
    p_analyze = subparsers.add_parser("analyze", help="Decompose trajectory into steps")
    p_analyze.add_argument("input", help="Input JSONL trajectory file")
    p_analyze.add_argument("-o", "--output", help="Output JSON file for steps")
    p_analyze.add_argument("--max-turns", type=int, default=-1, help="Max turns to analyze (-1=all)")

    # evaluate
    p_eval = subparsers.add_parser("evaluate", help="Score trajectory quality")
    p_eval.add_argument("input", help="Input JSONL trajectory file")
    p_eval.add_argument("-o", "--output", help="Output scored JSONL")
    p_eval.add_argument("--sample", type=int, default=-1, help="Sample N trajectories (-1=all)")
    p_eval.add_argument("--no-resolved-only", action="store_false", dest="resolved_only")
    p_eval.add_argument("--concurrency", type=int, default=32, help="Thread pool size")
    p_eval.add_argument("--chart", action="store_true", help="Generate score distribution chart")

    # visualize
    p_viz = subparsers.add_parser("visualize", help="Generate interactive DAG HTML")
    p_viz.add_argument("input", help="Input steps JSON file")
    p_viz.add_argument("-o", "--output", help="Output HTML file")
    p_viz.add_argument("--title", default="Long-Insight: Trajectory Visualization")

    # pipeline
    p_pipe = subparsers.add_parser("pipeline", help="Run full pipeline: analyze → visualize")
    p_pipe.add_argument("input", help="Input JSONL trajectory file")
    p_pipe.add_argument("--output-dir", default="output", help="Output directory")
    p_pipe.add_argument("--max-turns", type=int, default=-1, help="Max turns (-1=all)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    handlers = {
        "analyze": cmd_analyze,
        "evaluate": cmd_evaluate,
        "visualize": cmd_visualize,
        "pipeline": cmd_pipeline,
    }
    handlers[args.command](args)


if __name__ == "__main__":
    main()
