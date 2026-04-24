"""Centralized configuration for Long-Insight."""

import os


# LLM provider: "openai" or "anthropic"
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")

# API settings
API_BASE_URL = os.getenv("API_BASE_URL", "")
API_KEY = (
    os.getenv("OPENAI_API_KEY")
    or os.getenv("ANTHROPIC_API_KEY")
    or os.getenv("QIANXUN_API_KEY")
    or ""
)

# Model settings
DEFAULT_MODEL = os.getenv("LLM_MODEL", "claude-sonnet-4")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.7"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "4096"))

# Retry settings
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "5"))
LLM_RETRY_DELAY = int(os.getenv("LLM_RETRY_DELAY", "3"))
JSON_MAX_RETRIES = int(os.getenv("JSON_MAX_RETRIES", "3"))

# Concurrency
DEFAULT_CONCURRENCY = int(os.getenv("DEFAULT_CONCURRENCY", "32"))

# Analysis settings
MAX_TURNS_TO_ANALYZE = int(os.getenv("MAX_TURNS_TO_ANALYZE", "100"))
SAVE_INTERVAL = int(os.getenv("SAVE_INTERVAL", "1"))

# Debug
DEBUG = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")
