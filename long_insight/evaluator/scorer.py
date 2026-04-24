"""Two-stage trajectory quality scorer.

Stage 1: Problem difficulty rating (0-10)
Stage 2: Improvement potential / trajectory quality (0-10)
"""

import json
import os
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

from tqdm import tqdm

from long_insight import config
from long_insight.analyzer.compressor import TrajectoryCompressor
from long_insight.evaluator.prompts import format_stage1_prompt, format_stage2_prompt
from long_insight.llm.client import LLMClient


class TrajectoryScorer:
    """Scores agent trajectories on difficulty and quality.

    Processes JSONL files containing trajectory data with:
    - problem_statement, messages, resolved, rounds, tokens, etc.

    Outputs enriched JSONL with difficulty_score and improvement_potential_score.
    """

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        sample_num: int = -1,
        resolved_only: bool = True,
        concurrency: Optional[int] = None,
    ):
        self.llm_client = llm_client or LLMClient()
        self.sample_num = sample_num
        self.resolved_only = resolved_only
        self.concurrency = concurrency or config.DEFAULT_CONCURRENCY
        self.compressor = TrajectoryCompressor()

        # Score tracking
        self.difficulty_scores: List[int] = []
        self.improvement_scores: List[int] = []

    def score_file(
        self,
        input_path: str,
        output_path: Optional[str] = None,
    ) -> str:
        """Score all trajectories in a JSONL file.

        Args:
            input_path: Path to input JSONL file.
            output_path: Path to write scored JSONL. Auto-generated if None.

        Returns:
            Path to the output file.
        """
        if output_path is None:
            base = os.path.splitext(os.path.basename(input_path))[0]
            output_dir = os.path.join(os.path.dirname(input_path) or ".", "output")
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, f"scored-{base}.jsonl")

        # Load trajectories
        with open(input_path, "r", encoding="utf-8") as f:
            trajectories = [json.loads(line) for line in f if line.strip()]

        # Filter
        if self.resolved_only:
            original = len(trajectories)
            trajectories = [t for t in trajectories if t.get("resolved") is True]
            print(f"Filtered: {original} → {len(trajectories)} (resolved only)")

        # Sample
        total = len(trajectories)
        if 0 < self.sample_num < total:
            trajectories = trajectories[: self.sample_num]
            print(f"Sampling: first {self.sample_num} of {total}")

        # Process concurrently
        results = {}
        next_write = 0

        with open(output_path, "w", encoding="utf-8") as out_f:
            with ThreadPoolExecutor(max_workers=self.concurrency) as executor:
                futures = {
                    executor.submit(self._score_one, t, i + 1): i
                    for i, t in enumerate(trajectories)
                }

                with tqdm(total=len(trajectories), desc="Scoring") as pbar:
                    for future in as_completed(futures):
                        idx = futures[future]
                        try:
                            results[idx] = future.result()
                        except Exception as e:
                            print(f"\nWarning: trajectory {idx + 1} failed: {e}")
                            results[idx] = trajectories[idx]
                        pbar.update(1)

                        # Write in order
                        while next_write in results:
                            out_f.write(
                                json.dumps(results[next_write], ensure_ascii=False) + "\n"
                            )
                            del results[next_write]
                            next_write += 1

        print(f"Scored {next_write} trajectories → {output_path}")
        return output_path

    def _score_one(self, trajectory: Dict, index: int) -> Dict:
        """Score a single trajectory through both stages."""
        # Skip if already scored
        if "difficulty_score" in trajectory and "improvement_potential_score" in trajectory:
            self.difficulty_scores.append(trajectory["difficulty_score"])
            self.improvement_scores.append(trajectory["improvement_potential_score"])
            return trajectory

        # Stage 1: Difficulty
        if "difficulty_score" not in trajectory:
            prompt = format_stage1_prompt(trajectory)
            result = self._call_with_json_retry(prompt)
            if result:
                trajectory["difficulty_score"] = result.get("difficulty_score", 0)
                trajectory["difficulty_reasoning"] = result.get("difficulty_reasoning", "")
                self.difficulty_scores.append(trajectory["difficulty_score"])

        # Stage 2: Improvement potential
        if "improvement_potential_score" not in trajectory:
            messages = trajectory.get("messages", [])
            compressed = self.compressor.compress_messages(messages)
            prompt = format_stage2_prompt(trajectory, compressed)
            result = self._call_with_json_retry(prompt)
            if result:
                trajectory["improvement_potential_score"] = result.get(
                    "improvement_potential_score", 0
                )
                trajectory["improvement_potential_reasoning"] = result.get(
                    "improvement_potential_reasoning", ""
                )
                self.improvement_scores.append(trajectory["improvement_potential_score"])

        return trajectory

    def _call_with_json_retry(self, prompt: str) -> Optional[Dict]:
        """Call LLM and parse JSON response with retries."""
        messages = [{"role": "user", "content": prompt}]

        for attempt in range(config.JSON_MAX_RETRIES):
            try:
                text = self.llm_client.chat_with_retry(messages)
                return self.llm_client._parse_json(text)
            except Exception:
                if attempt >= config.JSON_MAX_RETRIES - 1:
                    return None

    def get_score_distribution(self) -> Dict[str, Any]:
        """Return score distribution statistics."""
        def _dist(scores, name):
            if not scores:
                return {"name": name, "total": 0}
            return {
                "name": name,
                "total": len(scores),
                "average": sum(scores) / len(scores),
                "min": min(scores),
                "max": max(scores),
                "distribution": dict(Counter(scores)),
            }

        return {
            "difficulty": _dist(self.difficulty_scores, "difficulty"),
            "improvement": _dist(self.improvement_scores, "improvement_potential"),
        }

    def print_stats(self) -> None:
        """Print scoring statistics."""
        dist = self.get_score_distribution()
        token_stats = self.llm_client.get_token_stats()

        print(f"\n{'=' * 60}")
        print("Score Distribution")
        print(f"{'=' * 60}")

        for key in ("difficulty", "improvement"):
            d = dist[key]
            if d["total"] > 0:
                print(
                    f"  {d['name']}: n={d['total']}, "
                    f"avg={d['average']:.2f}, range=[{d['min']}, {d['max']}]"
                )

        print(f"\nToken Usage")
        print(f"  API calls: {token_stats.get('api_calls', 0)}")
        print(f"  Total tokens: {token_stats.get('total_tokens', 0):,}")
