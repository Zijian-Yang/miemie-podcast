from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from miemie_podcast.domain.models import Episode, Job
from miemie_podcast.utils import json_loads


EPISODE_STAGE_META: Dict[str, Dict[str, Any]] = {
    "queued": {"label": "等待导入", "progress_percent": 5},
    "source_resolved": {"label": "已解析音频源", "progress_percent": 18},
    "transcribing": {"label": "正在语音转写", "progress_percent": 42},
    "transcribed": {"label": "转写完成，等待分析", "progress_percent": 58},
    "analyzing": {"label": "正在生成总结与脑图", "progress_percent": 82},
    "ready": {"label": "处理完成", "progress_percent": 100},
    "transcription_failed": {"label": "转写失败", "progress_percent": 42},
    "failed": {"label": "处理失败", "progress_percent": 100},
    "deleted": {"label": "已删除", "progress_percent": 100},
}

JOB_STAGE_META: Dict[str, Dict[str, Any]] = {
    "import_episode": {"label": "导入节目链接", "progress_percent": 10},
    "poll_transcription": {"label": "等待转写结果", "progress_percent": 48},
    "analyze_episode": {"label": "生成结构化内容", "progress_percent": 86},
}

MODULE_MANIFESTS: Dict[str, Dict[str, Any]] = {
    "summary": {
        "display_name": "总结",
        "description": "整期播客的主题、论点、关键证据与行动启发。",
        "copy_markdown": True,
        "viewable": True,
        "supports_html_view": False,
        "supports_png_export": False,
        "transcript_fidelity": None,
    },
    "knowledge": {
        "display_name": "知识沉淀",
        "description": "沉淀播客中的结论、原则、金句、趋势与关键概念。",
        "copy_markdown": True,
        "viewable": True,
        "supports_html_view": False,
        "supports_png_export": False,
        "transcript_fidelity": None,
    },
    "transcript": {
        "display_name": "逐字稿",
        "description": "完整 ASR 原文展示，允许附带时间戳，但不改写语义与顺序。",
        "copy_markdown": True,
        "viewable": True,
        "supports_html_view": False,
        "supports_png_export": False,
        "transcript_fidelity": "verbatim_asr",
    },
    "mindmap": {
        "display_name": "脑图",
        "description": "受控模板渲染的脑图预览，同时支持 HTML 与 PNG 导出。",
        "copy_markdown": False,
        "viewable": True,
        "supports_html_view": True,
        "supports_png_export": True,
        "transcript_fidelity": None,
    },
    "qa": {
        "display_name": "单集问答",
        "description": "基于当前节目内容与引用证据进行问答。",
        "copy_markdown": False,
        "viewable": True,
        "supports_html_view": False,
        "supports_png_export": False,
        "transcript_fidelity": None,
    },
}


def get_episode_progress_payload(episode: Episode) -> Dict[str, Any]:
    stage = episode.processing_stage or episode.status.value
    base = EPISODE_STAGE_META.get(stage, EPISODE_STAGE_META.get(episode.status.value, {"label": stage, "progress_percent": 0}))
    last_error = episode.failure_message or None
    return {
        "current_stage": stage,
        "current_stage_label": base["label"],
        "progress_percent": base["progress_percent"],
        "last_error": last_error,
    }


def get_job_progress_payload(job: Job) -> Dict[str, Any]:
    base = JOB_STAGE_META.get(job.stage, {"label": job.stage, "progress_percent": 0})
    error_payload = json_loads(job.error_json, None)
    retryable = False
    if job.status.value == "pending" and error_payload:
        retryable = bool(error_payload.get("retryable", True))
    if job.status.value == "completed":
        progress = 100
        label = "任务已完成"
    elif job.status.value == "failed":
        progress = min(100, max(base["progress_percent"], 1))
        label = "任务失败"
    else:
        progress = base["progress_percent"]
        label = base["label"]
    return {
        "current_stage": job.stage,
        "current_stage_label": label,
        "progress_percent": progress,
        "retryable": retryable,
        "last_error": error_payload,
    }


def get_module_manifest(module_key: str) -> Dict[str, Any]:
    manifest = MODULE_MANIFESTS.get(module_key, {
        "display_name": module_key,
        "description": "",
        "copy_markdown": False,
        "viewable": True,
        "supports_html_view": False,
        "supports_png_export": False,
        "transcript_fidelity": None,
    })
    return {"module_key": module_key, **manifest}


def module_key_for_artifact(artifact_key: str, metadata_json: str) -> Optional[str]:
    metadata = json_loads(metadata_json, {})
    explicit = metadata.get("module_key")
    if explicit:
        return explicit
    if artifact_key in {"raw_asr.json", "transcript.md"}:
        return "transcript"
    if artifact_key.startswith("summary"):
        return "summary"
    if artifact_key.startswith("knowledge"):
        return "knowledge"
    if artifact_key.startswith("mindmap"):
        return "mindmap"
    return None


def group_artifacts_by_module(artifacts: Sequence[Any]) -> Dict[str, List[Any]]:
    grouped: Dict[str, List[Any]] = {}
    for artifact in artifacts:
        module_key = module_key_for_artifact(artifact.artifact_key, artifact.metadata_json)
        if not module_key:
            continue
        grouped.setdefault(module_key, []).append(artifact)
    return grouped

