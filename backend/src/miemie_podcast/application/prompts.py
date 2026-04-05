from __future__ import annotations

from typing import Any, Dict, Sequence

from miemie_podcast.utils import json_dumps


TASK_SYSTEM_PROMPTS: Dict[str, str] = {
    "chunk_extract": (
        "You are Miemie Podcast's chunk analysis engine.\n"
        "Extract factual and analytical structure from exactly one transcript chunk.\n"
        "Do not use outside knowledge.\n"
        "Preserve uncertainty when speakers are speculative."
    ),
    "section_merge": (
        "You are Miemie Podcast's section synthesis engine.\n"
        "Merge several chunk-level analyses into one coherent section-level abstraction.\n"
        "Remove repetition while keeping the main argument flow and evidence."
    ),
    "episode_summary": (
        "You are Miemie Podcast's long-form episode summarizer.\n"
        "Synthesize the episode from section evidence instead of rewriting transcript fragments.\n"
        "Prefer specificity, argument structure, and evidence over filler language."
    ),
    "episode_knowledge": (
        "You are Miemie Podcast's knowledge distillation engine.\n"
        "Extract reusable conclusions, principles, concepts, signals, and research directions.\n"
        "Prefer durable knowledge over generic summary sentences."
    ),
    "mindmap_spec_build": (
        "You are Miemie Podcast's mind map planner.\n"
        "Convert episode structure into a clean tree spec for a controlled renderer.\n"
        "Do not emit free-form HTML, JavaScript, or CSS."
    ),
    "episode_qa": (
        "You are Miemie Podcast's episode QA engine.\n"
        "Answer only from the supplied evidence and cite the evidence used.\n"
        "If evidence is insufficient, say so explicitly."
    ),
}


def get_task_system_prompt(task: str, schema: Dict[str, Any]) -> str:
    base = TASK_SYSTEM_PROMPTS.get(
        task,
        "You are Miemie Podcast's analysis engine. Return valid JSON only.",
    )
    return f"{base}\nReturn valid JSON only.\nSchema guidance: {json_dumps(schema)}"


def build_chunk_extract_prompt(chunk_text: str) -> str:
    return (
        "任务：chunk_extract\n"
        "目标：从单个播客逐字稿片段中提取结构化信息。\n\n"
        "输出字段：\n"
        "- summary: 本片段的简洁概括\n"
        "- facts: 本片段明确说出的事实、判断或例证\n"
        "- insights: 值得沉淀的观点或洞察\n"
        "- quotes: 原文中值得保留的短句\n"
        "- outline_nodes: 适合脑图或大纲的节点\n"
        "- open_questions: 本片段留下的疑问或未决问题\n\n"
        "要求：\n"
        "- 只基于输入片段\n"
        "- 不补充外部信息\n"
        "- 用中文输出\n"
        "- 返回 JSON\n\n"
        "输入片段：\n"
        f"{chunk_text}"
    )


def build_section_merge_prompt(chunk_extracts: Sequence[Dict[str, Any]]) -> str:
    return (
        "任务：section_merge\n"
        "将以下 chunk_extract 结果合并为一个 section 级摘要。\n\n"
        "输出字段：\n"
        "- section_title\n"
        "- summary\n"
        "- takeaways\n"
        "- evidence_points\n"
        "- open_questions\n\n"
        "要求：\n"
        "- 保留这一段讨论的主线\n"
        "- 避免重复 chunk 级细节\n"
        "- 结论必须能被输入证据支撑\n"
        "- 返回 JSON\n\n"
        "输入：\n"
        f"{json_dumps(list(chunk_extracts))}"
    )


def build_episode_summary_prompt(
    episode_metadata: Dict[str, Any],
    sections: Sequence[Dict[str, Any]],
) -> str:
    return (
        "任务：episode_summary\n"
        "请基于节目 metadata 与 section summaries，为整期播客生成高质量中文总结。\n\n"
        "必须覆盖：\n"
        "- 主题\n"
        "- 核心问题\n"
        "- 论点结构\n"
        "- 关键证据\n"
        "- 结论\n"
        "- 行动启发\n"
        "- 未决问题\n\n"
        "输出字段：\n"
        "- overview\n"
        "- topic\n"
        "- core_question\n"
        "- themes\n"
        "- argument_structure\n"
        "- key_evidence\n"
        "- conclusions\n"
        "- actionable_insights\n"
        "- open_questions\n\n"
        "质量要求：\n"
        "- 不能只写泛泛的鼓励性语言\n"
        "- 至少覆盖节目最重要的 3 个信息簇\n"
        "- 结论必须和输入证据一致\n"
        "- 返回 JSON\n\n"
        "节目 metadata：\n"
        f"{json_dumps(episode_metadata)}\n\n"
        "section summaries：\n"
        f"{json_dumps(list(sections))}"
    )


def build_episode_knowledge_prompt(
    episode_metadata: Dict[str, Any],
    sections: Sequence[Dict[str, Any]],
    chunk_extracts: Sequence[Dict[str, Any]],
) -> str:
    return (
        "任务：episode_knowledge\n"
        "请从这期播客中提炼适合长期沉淀的知识内容。\n\n"
        "必须覆盖：\n"
        "- 结论\n"
        "- 原则\n"
        "- 金句\n"
        "- 趋势/信号\n"
        "- 关键概念\n"
        "- 值得继续研究的问题\n\n"
        "输出字段：\n"
        "- conclusions\n"
        "- principles\n"
        "- quotes\n"
        "- signals\n"
        "- concepts\n"
        "- research_questions\n\n"
        "要求：\n"
        "- 优先抽取可复用的认识，而不是普通摘要句\n"
        "- quotes 只保留短句，不要长段复制\n"
        "- trends/signals 必须是值得持续追踪的内容\n"
        "- 返回 JSON\n\n"
        "metadata：\n"
        f"{json_dumps(episode_metadata)}\n\n"
        "sections：\n"
        f"{json_dumps(list(sections))}\n\n"
        "chunk_extracts：\n"
        f"{json_dumps(list(chunk_extracts))}"
    )


def build_mindmap_prompt(
    episode_title: str,
    summary_data: Dict[str, Any],
    knowledge_data: Dict[str, Any],
) -> str:
    return (
        "任务：mindmap_spec_build\n"
        "请把这期播客整理成适合脑图展示的树状结构。\n\n"
        "输出格式：\n"
        "- root.title\n"
        "- root.children[].title\n"
        "- root.children[].children\n\n"
        "要求：\n"
        "- 顶层节点代表这期播客的几个核心板块\n"
        "- 子节点代表关键论点、结论和例证\n"
        "- 结构清晰，避免过深\n"
        "- 返回 JSON\n\n"
        f"标题：{episode_title}\n"
        f"summary={json_dumps(summary_data)}\n"
        f"knowledge={json_dumps(knowledge_data)}"
    )
