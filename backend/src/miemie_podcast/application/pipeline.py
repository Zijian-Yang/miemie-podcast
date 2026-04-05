from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

from miemie_podcast.domain.models import Citation, ModuleOutput, ModuleStatus, SearchDocument, TranscriptChunk
from miemie_podcast.utils import chunk_dict, json_dumps, new_id, now_iso, timestamp_to_mmss


@dataclass
class TranscriptSentence:
    sentence_id: int
    start_ms: int
    end_ms: int
    text: str


def normalize_asr_sentences(transcript_json: Dict[str, Any]) -> List[TranscriptSentence]:
    transcripts = transcript_json.get("transcripts") or []
    if not transcripts:
        return []
    sentences = transcripts[0].get("sentences") or []
    normalized: List[TranscriptSentence] = []
    for index, sentence in enumerate(sentences):
        normalized.append(
            TranscriptSentence(
                sentence_id=sentence.get("sentence_id", index),
                start_ms=int(sentence.get("begin_time", 0)),
                end_ms=int(sentence.get("end_time", 0)),
                text=(sentence.get("text") or "").strip(),
            )
        )
    return [item for item in normalized if item.text]


def build_transcript_chunks(workspace_id: str, episode_id: str, sentences: Sequence[TranscriptSentence]) -> List[TranscriptChunk]:
    if not sentences:
        return []
    chunks: List[TranscriptChunk] = []
    target_chars = 1600
    target_ms = 8 * 60 * 1000
    index = 0
    cursor = 0
    while cursor < len(sentences):
        start_cursor = max(cursor - 1, 0) if cursor > 0 else 0
        running: List[TranscriptSentence] = []
        total_chars = 0
        start_ms = sentences[start_cursor].start_ms
        end_ms = start_ms
        probe = start_cursor
        while probe < len(sentences):
            sentence = sentences[probe]
            running.append(sentence)
            total_chars += len(sentence.text)
            end_ms = sentence.end_ms
            duration = end_ms - start_ms
            probe += 1
            if total_chars >= target_chars or duration >= target_ms:
                break
        chunk_text = "\n".join(
            f"[{timestamp_to_mmss(sentence.start_ms)}] {sentence.text}" for sentence in running
        )
        timestamp = now_iso()
        chunks.append(
            TranscriptChunk(
                id=new_id("chunk"),
                workspace_id=workspace_id,
                episode_id=episode_id,
                chunk_index=index,
                start_ms=start_ms,
                end_ms=end_ms,
                text=chunk_text,
                metadata_json=json_dumps(
                    {
                        "sentence_ids": [sentence.sentence_id for sentence in running],
                        "sentence_count": len(running),
                    }
                ),
                created_at=timestamp,
                updated_at=timestamp,
            )
        )
        index += 1
        cursor = probe
    return chunks


def render_transcript_markdown(sentences: Sequence[TranscriptSentence]) -> str:
    lines = ["# 逐字稿", ""]
    for sentence in sentences:
        lines.append(f"- `{timestamp_to_mmss(sentence.start_ms)}` {sentence.text}")
    return "\n".join(lines)


def render_summary_markdown(data: Dict[str, Any]) -> str:
    lines = ["# 总结", ""]
    lines.append(f"## 一句话概述\n{data.get('overview', '')}\n")
    if data.get("topic"):
        lines.append(f"## 主题\n{data.get('topic')}\n")
    if data.get("core_question"):
        lines.append(f"## 核心问题\n{data.get('core_question')}\n")
    lines.append("## 核心主题")
    for item in data.get("themes", []):
        lines.append(f"- {item}")
    lines.append("\n## 论点结构")
    for item in data.get("argument_structure", []):
        lines.append(f"- {item}")
    lines.append("\n## 关键证据")
    for item in data.get("key_evidence", []):
        lines.append(f"- {item}")
    lines.append("\n## 结论")
    for item in data.get("conclusions", []):
        lines.append(f"- {item}")
    lines.append("\n## 行动启发")
    for item in data.get("actionable_insights", []):
        lines.append(f"- {item}")
    lines.append("\n## 值得继续思考")
    for item in data.get("open_questions", []):
        lines.append(f"- {item}")
    return "\n".join(lines).strip()


def render_knowledge_markdown(data: Dict[str, Any]) -> str:
    lines = ["# 知识沉淀", ""]
    lines.append("## 结论")
    for item in data.get("conclusions", []):
        lines.append(f"- {item}")
    lines.append("\n## 可复用原则")
    for item in data.get("principles", []):
        lines.append(f"- {item}")
    lines.append("\n## 金句")
    for item in data.get("quotes", []):
        lines.append(f"- {item}")
    lines.append("\n## 趋势与信号")
    for item in data.get("signals", []):
        lines.append(f"- {item}")
    lines.append("\n## 关键概念")
    for item in data.get("concepts", []):
        lines.append(f"- {item}")
    lines.append("\n## 值得继续研究")
    for item in data.get("research_questions", []):
        lines.append(f"- {item}")
    return "\n".join(lines).strip()


def render_mindmap_html(episode_title: str, mindmap_spec: Dict[str, Any]) -> str:
    def render_node(node: Dict[str, Any]) -> str:
        children = node.get("children") or []
        children_html = ""
        if children:
            children_html = "<ul>" + "".join(f"<li>{render_node(child)}</li>" for child in children) + "</ul>"
        return f"<div class='node'><span>{node.get('title', '')}</span>{children_html}</div>"

    root = mindmap_spec.get("root") or {"title": episode_title, "children": []}
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{episode_title} 脑图</title>
    <style>
      body {{
        margin: 0;
        font-family: "Space Grotesk", "Noto Sans SC", sans-serif;
        background: radial-gradient(circle at top, #fff9e8 0%, #f1f5ff 45%, #eef2f7 100%);
        color: #152033;
      }}
      .wrap {{
        padding: 48px;
      }}
      h1 {{
        font-size: 36px;
        margin: 0 0 24px;
      }}
      .map {{
        display: flex;
        justify-content: center;
        overflow: auto;
        padding-bottom: 24px;
      }}
      .node {{
        position: relative;
        display: inline-flex;
        flex-direction: column;
        align-items: center;
        gap: 16px;
        min-width: 160px;
      }}
      .node > span {{
        display: inline-flex;
        align-items: center;
        justify-content: center;
        padding: 14px 18px;
        border-radius: 18px;
        background: rgba(255,255,255,0.9);
        border: 1px solid rgba(21, 32, 51, 0.08);
        box-shadow: 0 18px 48px rgba(21, 32, 51, 0.08);
        font-weight: 600;
        text-align: center;
      }}
      ul {{
        list-style: none;
        display: flex;
        gap: 24px;
        padding: 28px 0 0;
        margin: 0;
      }}
      li {{
        position: relative;
        padding-top: 18px;
      }}
      li::before {{
        content: "";
        position: absolute;
        top: 0;
        left: 50%;
        width: 2px;
        height: 18px;
        background: rgba(21, 32, 51, 0.2);
      }}
      @media (max-width: 768px) {{
        .wrap {{
          padding: 24px;
        }}
        ul {{
          flex-direction: column;
          align-items: center;
        }}
      }}
    </style>
  </head>
  <body>
    <div class="wrap">
      <h1>{episode_title} 脑图</h1>
      <div class="map">{render_node(root)}</div>
    </div>
  </body>
</html>
"""


def build_search_documents(
    workspace_id: str,
    episode_id: str,
    episode_title: str,
    podcast_title: str,
    summary_data: Dict[str, Any],
    knowledge_data: Dict[str, Any],
    transcript_chunks: Sequence[TranscriptChunk],
) -> List[SearchDocument]:
    timestamp = now_iso()
    documents: List[SearchDocument] = []
    summary_body = "\n".join(
        [
            summary_data.get("overview", ""),
            summary_data.get("topic", ""),
            *summary_data.get("themes", []),
            *summary_data.get("argument_structure", []),
            *summary_data.get("key_evidence", []),
            *summary_data.get("conclusions", []),
            *summary_data.get("actionable_insights", []),
            *summary_data.get("open_questions", []),
        ]
    )
    documents.append(
        SearchDocument(
            id=new_id("search"),
            workspace_id=workspace_id,
            episode_id=episode_id,
            source_kind="summary",
            title=f"{podcast_title} / {episode_title} / 总结",
            body=summary_body,
            metadata_json=json_dumps(summary_data),
            created_at=timestamp,
            updated_at=timestamp,
        )
    )
    knowledge_body = "\n".join(
        knowledge_data.get("conclusions", [])
        + knowledge_data.get("principles", [])
        + knowledge_data.get("quotes", [])
        + knowledge_data.get("signals", [])
        + knowledge_data.get("concepts", [])
        + knowledge_data.get("research_questions", [])
    )
    documents.append(
        SearchDocument(
            id=new_id("search"),
            workspace_id=workspace_id,
            episode_id=episode_id,
            source_kind="knowledge",
            title=f"{podcast_title} / {episode_title} / 知识沉淀",
            body=knowledge_body,
            metadata_json=json_dumps(knowledge_data),
            created_at=timestamp,
            updated_at=timestamp,
        )
    )
    for chunk in transcript_chunks:
        documents.append(
            SearchDocument(
                id=new_id("search"),
                workspace_id=workspace_id,
                episode_id=episode_id,
                source_kind="transcript",
                title=f"{podcast_title} / {episode_title} / {timestamp_to_mmss(chunk.start_ms)}",
                body=chunk.text,
                metadata_json=chunk.metadata_json,
                created_at=timestamp,
                updated_at=timestamp,
            )
        )
    return documents


def make_module_output(
    workspace_id: str,
    episode_id: str,
    module_key: str,
    content: Dict[str, Any],
    rendered_markdown: Optional[str] = None,
    rendered_html: Optional[str] = None,
    citations: Optional[Sequence[Citation]] = None,
    version: str = "v1",
    format: str = "json",
) -> ModuleOutput:
    timestamp = now_iso()
    citation_payload = [
        {
            "source_kind": citation.source_kind,
            "chunk_id": citation.chunk_id,
            "start_ms": citation.start_ms,
            "end_ms": citation.end_ms,
            "excerpt": citation.excerpt,
        }
        for citation in (citations or [])
    ]
    return ModuleOutput(
        id=new_id("module"),
        workspace_id=workspace_id,
        episode_id=episode_id,
        module_key=module_key,
        version=version,
        format=format,
        status=ModuleStatus.READY,
        content_json=json_dumps(content),
        rendered_markdown=rendered_markdown,
        rendered_html=rendered_html,
        citations_json=json_dumps(citation_payload),
        created_at=timestamp,
        updated_at=timestamp,
    )


def make_chunk_evidence(chunks: Sequence[TranscriptChunk]) -> List[Dict[str, Any]]:
    evidence: List[Dict[str, Any]] = []
    for chunk in chunks:
        evidence.append(
            chunk_dict(
                chunk_id=chunk.id,
                start_ms=chunk.start_ms,
                end_ms=chunk.end_ms,
                text=chunk.text,
                extra={"source_kind": "transcript"},
            )
        )
    return evidence
