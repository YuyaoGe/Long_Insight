"""Trajectory compression utilities for reducing token usage before LLM analysis."""

import copy
from typing import Dict, List


class TrajectoryCompressor:
    """Compresses agent trajectory messages by truncating verbose content.

    Compression rules:
    - Assistant thinking blocks > 500 chars: keep first 200 + "..." + last 200
    - User content > 200 chars: keep first 100 + "..."
    - Removes signature fields from thinking blocks
    """

    @staticmethod
    def truncate_thinking(text: str, max_len: int = 500, keep: int = 200) -> str:
        """Truncate thinking content, keeping head and tail."""
        if len(text) <= max_len:
            return text
        return text[:keep] + "..." + text[-keep:]

    @staticmethod
    def truncate_user_content(content: str, max_len: int = 200, keep: int = 100) -> str:
        """Truncate user message content."""
        if len(content) <= max_len:
            return content
        return content[:keep] + "..."

    @classmethod
    def compress_messages(cls, messages: List[Dict]) -> List[Dict]:
        """Compress a message list by truncating verbose fields.

        Returns a deep copy with truncated content — the original is not modified.
        """
        compressed = copy.deepcopy(messages)

        for msg in compressed:
            role = msg.get("role")

            if role == "assistant":
                content = msg.get("content")
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and item.get("type") == "thinking":
                            if "thinking" in item:
                                item["thinking"] = cls.truncate_thinking(item["thinking"])
                            item.pop("signature", None)
                elif isinstance(content, str):
                    msg["content"] = cls.truncate_thinking(content)

            elif role == "user":
                content = msg.get("content")
                if isinstance(content, str):
                    msg["content"] = cls.truncate_user_content(content)

        return compressed
