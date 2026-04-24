"""Step decomposition: breaks long agent trajectories into a DAG of logical steps."""

import json
import os
from textwrap import dedent
from typing import Any, Dict, List, Optional

from long_insight import config
from long_insight.llm.client import LLMClient
from long_insight.analyzer.prompts import ANALYSIS_JSON_SCHEMA, ANALYSIS_PROMPT, SYSTEM_PROMPT


class StepDecomposer:
    """Decomposes a multi-turn agent trajectory into hierarchical steps.

    Each step is a logical sub-task with:
    - Type classification (8 categories)
    - Title, summary, and detailed narrative
    - Parent step IDs forming a DAG
    """

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or LLMClient()
        self.steps: List[Dict[str, Any]] = []
        self.current_turn = 0

    def load_trajectory(self, file_path: str) -> List[Dict]:
        """Load turns from a JSONL trajectory file.

        Reads the last line of the JSONL file and extracts the messages array.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Trajectory file not found: {file_path}")

        last_line = None
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    last_line = line.strip()

        if not last_line:
            raise ValueError(f"Empty trajectory file: {file_path}")

        data = json.loads(last_line)
        messages = data.get("messages", [])
        return messages

    def load_existing_steps(self, output_path: str) -> None:
        """Resume from a previously saved analysis."""
        if os.path.exists(output_path):
            with open(output_path, "r", encoding="utf-8") as f:
                self.steps = json.load(f)

    def save_steps(self, output_path: str) -> None:
        """Persist current steps to JSON."""
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(self.steps, f, ensure_ascii=False, indent=2)

    def analyze(
        self,
        trajectory_path: str,
        output_path: str,
        max_turns: Optional[int] = None,
    ) -> List[Dict]:
        """Run the full decomposition pipeline.

        Args:
            trajectory_path: Path to JSONL trajectory file.
            output_path: Path to save step analysis JSON.
            max_turns: Maximum number of turns to analyze (-1 or None for all).

        Returns:
            List of decomposed steps.
        """
        turns = self.load_trajectory(trajectory_path)
        self.load_existing_steps(output_path)

        max_turns = max_turns if max_turns and max_turns > 0 else len(turns)

        # Determine start point
        if self.steps:
            start = self.steps[-1].get("end_turn", 0) + 1
        else:
            start = 1

        end = min(start + max_turns - 1, len(turns))

        if end < start:
            print(f"All turns already analyzed (up to turn {len(turns)})")
            return self.steps

        print(f"Analyzing turns {start}–{end} ({end - start + 1} turns)")

        for i, turn in enumerate(turns[start - 1 :], start):
            if i > end:
                break

            self.current_turn = i

            if i % 10 == 0:
                print(f"  Turn {i}/{end} — role: {turn.get('role', '?')}")

            try:
                result = self._analyze_turn(turn, i)
                self._update_steps(result)
                self.save_steps(output_path)
            except KeyboardInterrupt:
                self.save_steps(output_path)
                print(f"\nInterrupted — saved {len(self.steps)} steps")
                raise
            except Exception as e:
                print(f"  Warning: turn {i} failed: {e}")
                self.save_steps(output_path)
                continue

        print(f"Decomposition complete: {len(self.steps)} steps")
        return self.steps

    def _analyze_turn(self, turn: Dict, turn_number: int) -> Dict:
        """Call LLM to classify a single turn."""
        context = self._format_context(turn, turn_number)

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": ANALYSIS_PROMPT},
            {"role": "user", "content": f"Context:\n{context}"},
        ]

        has_root = any(s.get("parent_ids") == [-1] for s in self.steps)

        for attempt in range(config.JSON_MAX_RETRIES):
            try:
                if self.llm_client.provider == "anthropic":
                    result = self.llm_client.chat_json(
                        messages, json_schema=ANALYSIS_JSON_SCHEMA
                    )
                else:
                    text = self.llm_client.chat_with_retry(messages)
                    result = LLMClient._parse_json(text)

                # Validate parent IDs
                parent_ids = result.get("parent_step_ids", [])
                if not isinstance(parent_ids, list):
                    parent_ids = [parent_ids] if parent_ids is not None else []

                parent_ids = [int(p) for p in parent_ids if isinstance(p, (int, str))]

                if not parent_ids:
                    parent_ids = [-1] if not self.steps else [self.steps[-1]["id"]]

                result["parent_step_ids"] = parent_ids

                # Validation
                is_new = result.get("behavior_type") == "new_step"
                current_id = len(self.steps) + 1 if is_new else (
                    self.steps[-1]["id"] if self.steps else 1
                )

                errors = []
                if current_id in parent_ids:
                    errors.append(f"Step {current_id} cannot be its own parent")
                if is_new and -1 in parent_ids and has_root:
                    errors.append("Root step already exists, cannot create another")

                invalid = [p for p in parent_ids if p != -1 and p > len(self.steps)]
                if invalid:
                    errors.append(f"Parent IDs {invalid} exceed existing step range")

                if errors:
                    if attempt < config.JSON_MAX_RETRIES - 1:
                        messages.append({
                            "role": "user",
                            "content": f"Validation errors: {errors}. Please fix.",
                        })
                        continue
                    else:
                        raise ValueError(f"Validation failed: {errors}")

                return result

            except Exception as e:
                if attempt >= config.JSON_MAX_RETRIES - 1:
                    # Return safe default
                    default_parent = [-1] if not self.steps else [self.steps[-1]["id"]]
                    return {
                        "behavior_type": "continuation",
                        "step_type": "project_exploration",
                        "step_title": f"Turn {turn_number}",
                        "step_summary": f"Processing turn {turn_number}",
                        "step_detail": str(turn.get("content", ""))[:200],
                        "parent_step_ids": default_parent,
                    }

    def _update_steps(self, result: Dict) -> None:
        """Integrate LLM result into the step list."""
        behavior = result.get("behavior_type", "continuation")
        parent_ids = result.get("parent_step_ids", [-1])

        if behavior == "new_step":
            # Prevent duplicate root
            if parent_ids == [-1] and any(s.get("parent_ids") == [-1] for s in self.steps):
                parent_ids = [1]

            step_id = len(self.steps) + 1
            self.steps.append({
                "id": step_id,
                "type": result.get("step_type", "project_exploration"),
                "title": result.get("step_title", f"Step {step_id}"),
                "start_turn": self.current_turn,
                "end_turn": self.current_turn,
                "summary": result.get("step_summary", ""),
                "detail": result.get("step_detail", ""),
                "parent_ids": parent_ids,
            })
        elif self.steps:
            last = self.steps[-1]
            last["end_turn"] = self.current_turn
            last["summary"] = result.get("step_summary", last["summary"])
            last["detail"] = result.get("step_detail", last["detail"])
            if result.get("step_type"):
                last["type"] = result["step_type"]
            if result.get("step_title"):
                last["title"] = result["step_title"]
        else:
            # No steps yet — force create root
            result["behavior_type"] = "new_step"
            result["parent_step_ids"] = [-1]
            self._update_steps(result)

    def _format_context(self, turn: Dict, turn_number: int) -> str:
        """Build context string for LLM from existing steps + current turn."""
        if not self.steps:
            ctx = '{\n  "existing_steps": []'
        else:
            ctx = '{\n  "existing_steps": ['
            for step in self.steps[-3:]:
                ctx += f"""
    {{
      "id": {step["id"]},
      "type": "{step["type"]}",
      "title": "{step["title"]}",
      "summary": "{step["summary"][:100]}",
      "parent_ids": {step["parent_ids"]}
    }},"""

        content_preview = str(turn.get("content", ""))[:200]
        if len(str(turn.get("content", ""))) > 200:
            content_preview += "..."

        ctx += f"""
  ],
  "current_turn_number": {turn_number},
  "current_turn": {{
    "role": "{turn.get("role", "")}",
    "content": "{repr(content_preview)[1:-1]}"
  }}
}}"""
        return dedent(ctx).strip()
