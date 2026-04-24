"""Score distribution chart generation using matplotlib."""

import json
import os
from typing import Any, Dict, Optional

import matplotlib.pyplot as plt
import numpy as np


def plot_score_distribution(
    stats: Dict[str, Any],
    output_path: str = "score_distribution.png",
) -> str:
    """Generate a side-by-side bar chart of difficulty and improvement scores.

    Args:
        stats: Score distribution dict from TrajectoryScorer.get_score_distribution()
        output_path: Path to save the PNG chart.

    Returns:
        Path to the saved chart.
    """
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    scores = range(11)

    color_diff = "#3498db"
    color_imp = "#e74c3c"

    for ax, key, color, title in [
        (ax1, "difficulty", color_diff, "Difficulty Score Distribution"),
        (ax2, "improvement", color_imp, "Improvement Potential Distribution"),
    ]:
        dist = stats.get(key, {}).get("distribution", {})
        counts = [dist.get(s, dist.get(str(s), 0)) for s in scores]

        ax.bar(scores, counts, color=color, alpha=0.8, edgecolor="black", linewidth=0.5)
        ax.set_title(title, fontsize=14, fontweight="bold", pad=20)
        ax.set_xlabel("Score", fontsize=12)
        ax.set_ylabel("Count", fontsize=12)
        ax.set_xticks(scores)
        ax.grid(axis="y", alpha=0.3)

        for i, v in enumerate(counts):
            if v > 0:
                ax.text(i, v + 0.5, str(v), ha="center", va="bottom", fontweight="bold")

        total = stats.get(key, {}).get("total", 0)
        avg = stats.get(key, {}).get("average", 0)
        ax.text(
            0.02, 0.98,
            f"n={total}\navg={avg:.2f}",
            transform=ax.transAxes,
            va="top",
            ha="left",
            bbox=dict(boxstyle="round", facecolor="white", alpha=0.8),
        )

    max_count = max(
        max((stats.get(k, {}).get("distribution", {}).get(s, 0) for s in scores), default=0)
        for k in ("difficulty", "improvement")
    )
    ax1.set_ylim(0, max(max_count * 1.15, 1))
    ax2.set_ylim(0, max(max_count * 1.15, 1))

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close()

    print(f"Chart saved: {output_path}")
    return output_path
