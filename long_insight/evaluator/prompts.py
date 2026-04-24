"""Prompt templates for trajectory quality evaluation."""

STAGE1_PROMPT = """\
You are a code problem complexity analyst. Rate the difficulty of the following problem.

# Input

## Problem Description
{problem_statement}

## Metadata
- Issue count: {issue_count}
- Resolved: {resolved}
- Rounds: {rounds}
- Tokens used: {tokens}
- Test log excerpt: {test_log_summary}

# Scoring Dimensions

1. **Intrinsic complexity** — files involved, logic depth, edge cases
2. **Fix difficulty** — architecture understanding, cross-module interaction
3. **Description clarity** — how well the problem is specified
4. **Project scale** — reflected by issue count
5. **Actual resolution difficulty** — rounds, tokens, test outcomes

# Scale (0-10)

- 0-2: Simple — single file, clear logic
- 3-4: Moderate — few files, straightforward
- 5-6: Medium — multi-file coordination or complex logic
- 7-8: Hard — architecture-level understanding needed
- 9-10: Very hard — complex architecture, difficult localization

# Output

Return JSON with exactly these fields:
```json
{{
  "difficulty_score": <0-10 integer>,
  "difficulty_reasoning": "<detailed rationale>"
}}
```
"""

STAGE2_PROMPT = """\
You are a trajectory quality expert. Evaluate the improvement potential of this \
agent trajectory.

# Trajectory Info

- Instance ID: {instance_id}
- Total steps: {total_steps}
- Resolved: {resolved}

## Compressed Trajectory
{compressed_trajectory}

# Anti-Patterns to Detect

A. **Test avoidance** — skipping failed tests without investigation
B. **Missing verification** — no re-test after code changes
C. **Repetitive loops** — near-identical operations in sequence
D. **Inefficient exploration** — viewing files unrelated to the fix
E. **Ignored errors** — not responding to clear error messages
F. **Verbose thinking** — long thinking with little substance
G. **Mid-trajectory deviation** — going off-track then correcting
H. **Late-stage waste** — problem solved early, unnecessary work continues

# Scoring Dimensions

1. Test respect — seriousness about test failures
2. Verification completeness — discover → analyze → fix → verify loop
3. Localization accuracy — correct root cause identification
4. Repetition level — degree of circular behavior
5. Exploration efficiency — ratio of useful vs. wasted exploration
6. Error responsiveness — acting on error messages
7. Reasoning quality — substance in thinking blocks
8. Trajectory stability — absence of major deviations
9. Late-stage validity — useful work throughout the trajectory

# Scale (0-10)

- 9-10: Excellent — minimal anti-patterns, high training value
- 7-8: Good — minor issues, still valuable
- 5-6: Medium — some anti-patterns, moderate value
- 3-4: Poor — significant anti-patterns, limited value
- 0-2: Very poor — severe anti-patterns, not suitable for training

# Output

Return JSON with exactly these fields:
```json
{{
  "improvement_potential_score": <0-10 integer>,
  "improvement_potential_reasoning": "<detailed rationale covering detected patterns>"
}}
```
"""


def format_stage1_prompt(trajectory: dict) -> str:
    """Format the difficulty scoring prompt."""
    problem = trajectory.get("problem_statement", "No description")
    issues = trajectory.get("issue_numbers", [])
    issue_count = len(issues) if isinstance(issues, list) else 0
    resolved = trajectory.get("resolved", False)
    rounds = trajectory.get("rounds", 0)
    tokens = trajectory.get("tokens", 0)

    judge = trajectory.get("judge_result", {})
    raw_log = judge.get("raw_log_content", "")
    test_log = (raw_log[:500] + "...") if len(raw_log) > 500 else raw_log
    if not test_log:
        test_log = "No test log available"

    return STAGE1_PROMPT.format(
        problem_statement=problem,
        issue_count=issue_count,
        resolved="Yes" if resolved else "No",
        rounds=rounds,
        tokens=tokens,
        test_log_summary=test_log,
    )


def format_stage2_prompt(trajectory: dict, compressed_messages: list) -> str:
    """Format the improvement potential scoring prompt."""
    instance_id = trajectory.get("instance_id", "unknown")
    resolved = trajectory.get("resolved", False)
    total_steps = sum(1 for m in compressed_messages if m.get("role") == "assistant")

    # Build readable trajectory
    lines = []
    step = 0
    for msg in compressed_messages:
        role = msg.get("role")
        if role == "assistant":
            step += 1
            lines.append(f"\nStep {step} [Assistant]:")
            content = msg.get("content", "")
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict):
                        if item.get("type") == "thinking":
                            lines.append(f"  Thinking: {item.get('thinking', '')}")
                        elif item.get("type") == "text":
                            lines.append(f"  Text: {item.get('text', '')}")
            elif isinstance(content, str):
                lines.append(f"  Content: {content}")
        elif role == "user" and step > 0:
            lines.append(f"\nObservation [User]:")
            lines.append(f"  {msg.get('content', '')}")

    return STAGE2_PROMPT.format(
        instance_id=instance_id,
        total_steps=total_steps,
        resolved="True" if resolved else "False",
        compressed_trajectory="\n".join(lines),
    )
