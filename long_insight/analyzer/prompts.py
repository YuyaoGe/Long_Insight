"""Prompt templates for trajectory step decomposition."""

# JSON Schema for structured LLM output
ANALYSIS_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "behavior_type": {
            "type": "string",
            "enum": ["new_step", "continuation"],
            "description": "Whether this turn starts a new step or continues the previous one",
        },
        "step_type": {
            "type": "string",
            "enum": [
                "task_understanding",
                "project_exploration",
                "environment_setup",
                "code_implementation",
                "test_verification",
                "debugging",
                "documentation",
                "planning",
            ],
            "description": "Category of the current step",
        },
        "step_title": {
            "type": "string",
            "description": "Brief title for the step (5-15 words)",
        },
        "step_summary": {
            "type": "string",
            "description": "1-2 sentence summary of what this step accomplishes",
        },
        "step_detail": {
            "type": "string",
            "description": "Detailed causal narrative of operations performed",
        },
        "parent_step_ids": {
            "type": "array",
            "items": {"type": "integer"},
            "description": "IDs of parent steps this step depends on. [-1] for root step.",
        },
    },
    "required": [
        "behavior_type",
        "step_type",
        "step_title",
        "step_summary",
        "step_detail",
        "parent_step_ids",
    ],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """\
You are a professional software development task analyst. Your job is to analyze \
agent conversation trajectories and decompose them into meaningful, hierarchical steps.

## Concepts

### Turn
A turn is the basic unit of conversation. Each message exchange is one turn:
- **user**: System feedback — command output, error messages, file content
- **assistant**: Agent response — reasoning, tool calls, code edits

### Step
A step is a logical grouping of consecutive turns that accomplish a sub-task:
- Step 1 (turns 1-3): Understand the task requirements
- Step 2 (turns 4-8): Explore relevant source files
- Step 3 (turns 9-15): Implement the fix
- Step 4 (turns 16-20): Run tests to verify

### Step Types
1. **task_understanding** — Analyzing requirements, reading issue descriptions
2. **project_exploration** — Browsing directories, reading source files, searching code
3. **environment_setup** — Installing dependencies, creating directories, configuring
4. **code_implementation** — Writing or modifying code
5. **test_verification** — Running tests, checking correctness
6. **debugging** — Analyzing errors, fixing bugs
7. **documentation** — Writing docs, notes, summaries
8. **planning** — Making plans, strategizing next steps

### Parent-Child Relationships
Steps form a DAG (directed acyclic graph). Each step lists its parent step IDs — \
the steps it logically depends on.

Rules:
- Exactly ONE root step with parent_step_ids = [-1]
- A step cannot be its own parent
- No forward references (parents must already exist)
- A step can have multiple parents: [2, 3] means it depends on both

## Your Task
For each turn, determine:
1. Is this a **new_step** or **continuation** of the current step?
2. What **step_type** best describes the activity?
3. Provide a concise **step_title**
4. Write a **step_summary** (1-2 sentences)
5. Write a **step_detail** (causal narrative)
6. Identify **parent_step_ids**
"""

ANALYSIS_PROMPT = """\
Analyze the following turn from an agent's software development trajectory.

Given the existing steps and the current turn content, determine whether this turn \
starts a new step or continues the previous one, and provide the step metadata.

Output a JSON object with the required fields.
"""
