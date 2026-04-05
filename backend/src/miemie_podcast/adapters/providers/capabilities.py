from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class ModelCapability:
    provider: str
    model: str
    purpose: str
    input_constraints: List[str]
    structured_output: bool
    context_cache: bool
    timeout_seconds: int
    retry_policy: str
    cost_tier: str


MODEL_CAPABILITIES: Dict[str, ModelCapability] = {
    "qwen3-asr-flash-filetrans": ModelCapability(
        provider="dashscope",
        model="qwen3-asr-flash-filetrans",
        purpose="Long-form speech-to-text for full podcast episodes",
        input_constraints=[
            "Accepts public file_url input",
            "Uses async task polling",
            "Preferred for large podcast audio files",
        ],
        structured_output=False,
        context_cache=False,
        timeout_seconds=60,
        retry_policy="Retry polling on transient task states or provider timeouts",
        cost_tier="medium",
    ),
    "qwen3.5-plus": ModelCapability(
        provider="dashscope",
        model="qwen3.5-plus",
        purpose="Structured JSON extraction, synthesis, and episode Q&A",
        input_constraints=[
            "Use JSON mode for intermediate and final structured outputs",
            "Use chunked and section-merged inputs for long transcripts",
        ],
        structured_output=True,
        context_cache=True,
        timeout_seconds=120,
        retry_policy="Retry on invalid JSON or transient upstream failures; validate schema before accepting output",
        cost_tier="medium",
    ),
}

