from __future__ import annotations

import shlex
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import httpx

from miemie_podcast.application.prompts import get_task_system_prompt
from miemie_podcast.config import Settings
from miemie_podcast.domain.models import Citation, QAAnswer
from miemie_podcast.ports.services import LanguageModelProvider, SpeechToTextProvider
from miemie_podcast.utils import json_loads


class QwenAsrFlashFiletransProvider(SpeechToTextProvider):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = httpx.Client(
            timeout=60.0,
            headers={
                "Authorization": f"Bearer {self.settings.dashscope_api_key}",
                "Content-Type": "application/json",
            },
        )

    def submit_file(self, url: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        if not self.settings.dashscope_api_key:
            raise RuntimeError("DASHSCOPE_API_KEY is not configured.")
        payload = {
            "model": "qwen3-asr-flash-filetrans",
            "input": {"file_url": url},
            "parameters": {
                "channel_id": [0],
                "enable_itn": False,
                "language": metadata.get("language", "zh"),
            },
        }
        response = self.client.post(
            f"{self.settings.dashscope_base_url}/api/v1/services/audio/asr/transcription",
            headers={"X-DashScope-Async": "enable"},
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        output = data.get("output") or {}
        return {
            "task_id": output.get("task_id"),
            "task_status": output.get("task_status", "PENDING"),
            "raw": data,
        }

    def get_result(self, task_id: str) -> Dict[str, Any]:
        if not self.settings.dashscope_api_key:
            raise RuntimeError("DASHSCOPE_API_KEY is not configured.")
        response = self.client.get(
            f"{self.settings.dashscope_base_url}/api/v1/tasks/{task_id}",
            headers={"X-DashScope-Async": "enable"},
        )
        response.raise_for_status()
        data = response.json()
        output = data.get("output") or {}
        status = output.get("task_status", "UNKNOWN")
        if status != "SUCCEEDED":
            return {
                "task_id": task_id,
                "status": status,
                "raw": data,
                "message": output.get("message"),
                "code": output.get("code"),
            }
        result = output.get("result") or {}
        transcript_url = result.get("transcription_url")
        transcript_response = self.client.get(transcript_url)
        transcript_response.raise_for_status()
        transcript_json = transcript_response.json()
        return {
            "task_id": task_id,
            "status": status,
            "usage": data.get("usage"),
            "transcript_json": transcript_json,
            "raw": data,
        }


class Qwen35PlusProvider(LanguageModelProvider):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = httpx.Client(
            timeout=120.0,
            headers={
                "Authorization": f"Bearer {self.settings.dashscope_api_key}",
                "Content-Type": "application/json",
            },
        )

    def generate_json(
        self,
        task: str,
        schema: Dict[str, Any],
        input_parts: Sequence[Dict[str, Any]],
        cache_strategy: Optional[Dict[str, Any]] = None,
        temperature: float = 0.2,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not self.settings.dashscope_api_key:
            raise RuntimeError("DASHSCOPE_API_KEY is not configured.")
        system_prompt = get_task_system_prompt(task, schema)
        messages: List[Dict[str, Any]] = [
            {
                "role": "system",
                "content": system_prompt,
            }
        ]
        for part in input_parts:
            if cache_strategy and part.get("cacheable"):
                messages.append(
                    {
                        "role": part.get("role", "user"),
                        "content": [
                            {
                                "type": "text",
                                "text": part["text"],
                                "cache_control": {"type": "ephemeral"},
                            }
                        ],
                    }
                )
            else:
                messages.append({"role": part.get("role", "user"), "content": part["text"]})
        payload = {
            "model": model or "qwen3.5-plus",
            "messages": messages,
            "temperature": temperature,
            "response_format": {"type": "json_object"},
        }
        response = self.client.post(
            f"{self.settings.dashscope_compatible_base_url}/chat/completions",
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        return json_loads(content, {})

    def answer_with_citations(
        self,
        question: str,
        evidence_set: Sequence[Dict[str, Any]],
        output_schema: Dict[str, Any],
        cache_strategy: Optional[Dict[str, Any]] = None,
    ) -> QAAnswer:
        prompt = (
            "Use only the supplied evidence to answer the user's question. "
            "Return JSON with keys: answer, citations. "
            "Each citation must include source_kind, chunk_id, start_ms, end_ms, excerpt."
        )
        payload = self.generate_json(
            task="episode_qa",
            schema=output_schema,
            input_parts=[
                {"role": "system", "text": prompt, "cacheable": bool(cache_strategy)},
                {
                    "role": "user",
                    "text": f"Question: {question}\nEvidence JSON: {evidence_set}",
                },
            ],
            cache_strategy=cache_strategy,
        )
        citations = [
            Citation(
                source_kind=item.get("source_kind", "unknown"),
                chunk_id=item.get("chunk_id"),
                start_ms=item.get("start_ms"),
                end_ms=item.get("end_ms"),
                excerpt=item.get("excerpt", ""),
            )
            for item in payload.get("citations", [])
        ]
        return QAAnswer(answer=payload.get("answer", ""), citations=citations, metadata={"raw": payload})


def render_mindmap_png(command: str, html_path: Path, png_path: Path) -> bool:
    parts = shlex.split(command)
    if not parts:
        return False
    completed = subprocess.run(
        [*parts, str(html_path), str(png_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.returncode == 0 and png_path.exists()
