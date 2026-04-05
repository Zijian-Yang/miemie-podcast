from miemie_podcast.application.pipeline import (
    TranscriptSentence,
    build_transcript_chunks,
    normalize_asr_sentences,
    render_knowledge_markdown,
    render_summary_markdown,
    render_transcript_markdown,
)


def test_normalize_asr_sentences():
    transcript_json = {
        "transcripts": [
            {
                "sentences": [
                    {"sentence_id": 0, "begin_time": 0, "end_time": 1000, "text": "你好"},
                    {"sentence_id": 1, "begin_time": 1000, "end_time": 2000, "text": "世界"},
                ]
            }
        ]
    }
    sentences = normalize_asr_sentences(transcript_json)
    assert len(sentences) == 2
    assert sentences[0].text == "你好"


def test_build_transcript_chunks():
    sentences = [
        TranscriptSentence(sentence_id=index, start_ms=index * 1000, end_ms=(index + 1) * 1000, text="测试文本" * 80)
        for index in range(5)
    ]
    chunks = build_transcript_chunks("ws_1", "ep_1", sentences)
    assert chunks
    assert chunks[0].workspace_id == "ws_1"
    assert chunks[0].episode_id == "ep_1"


def test_render_transcript_markdown_preserves_sentence_order_and_text():
    sentences = [
        TranscriptSentence(sentence_id=0, start_ms=0, end_ms=1000, text="第一句原文"),
        TranscriptSentence(sentence_id=1, start_ms=1000, end_ms=2000, text="第二句原文"),
    ]
    markdown = render_transcript_markdown(sentences)
    assert "第一句原文" in markdown
    assert "第二句原文" in markdown
    assert markdown.index("第一句原文") < markdown.index("第二句原文")


def test_render_summary_markdown_contains_extended_sections():
    markdown = render_summary_markdown(
        {
            "overview": "这期节目讨论了 AI 产品路线。",
            "topic": "AI 产品策略",
            "core_question": "团队应该先追求速度还是壁垒？",
            "themes": ["产品定位", "组织效率"],
            "argument_structure": ["先确认用户价值，再决定工程投入。"],
            "key_evidence": ["嘉宾给出了两家公司的对比案例。"],
            "conclusions": ["中短期内应该优先验证真实需求。"],
            "actionable_insights": ["先做小范围验证，再扩大投入。"],
            "open_questions": ["长期护城河会落在模型还是分发？"],
        }
    )
    assert "## 核心问题" in markdown
    assert "## 论点结构" in markdown
    assert "## 关键证据" in markdown
    assert "## 行动启发" in markdown


def test_render_knowledge_markdown_contains_extended_sections():
    markdown = render_knowledge_markdown(
        {
            "conclusions": ["播客认为验证速度比盲目堆功能更重要。"],
            "principles": ["先缩小问题范围。"],
            "quotes": ["先别急着做大。"],
            "signals": ["团队开始更重视工作流自动化。"],
            "concepts": ["工作流产品化"],
            "research_questions": ["AI 时代的产品壁垒会如何变化？"],
        }
    )
    assert "## 关键概念" in markdown
    assert "## 值得继续研究" in markdown
