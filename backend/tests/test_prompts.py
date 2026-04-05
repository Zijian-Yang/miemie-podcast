import pytest

from miemie_podcast.application.pipeline import render_knowledge_markdown, render_summary_markdown
from miemie_podcast.application.prompts import (
    build_episode_knowledge_prompt,
    build_episode_summary_prompt,
)


def test_summary_prompt_includes_required_contract_terms():
    prompt = build_episode_summary_prompt(
        {"episode_title": "测试节目", "podcast_title": "测试播客"},
        [{"section_title": "开场", "summary": "讨论问题背景", "takeaways": ["需要先定义问题"]}],
    )
    assert "核心问题" in prompt
    assert "论点结构" in prompt
    assert "关键证据" in prompt
    assert "行动启发" in prompt


def test_knowledge_prompt_includes_required_contract_terms():
    prompt = build_episode_knowledge_prompt(
        {"episode_title": "测试节目", "podcast_title": "测试播客"},
        [{"section_title": "趋势", "summary": "谈趋势", "takeaways": ["AI 会改变分工"]}],
        [{"summary": "chunk", "insights": ["先缩小范围"], "quotes": ["不要一步到位"]}],
    )
    assert "趋势/信号" in prompt
    assert "关键概念" in prompt
    assert "值得继续研究的问题" in prompt


@pytest.mark.parametrize(
    "payload",
    [
        {
            "overview": "节目讨论创业节奏。",
            "topic": "创业策略",
            "core_question": "先速度还是先利润？",
            "themes": ["节奏控制"],
            "argument_structure": ["先验证需求。"],
            "key_evidence": ["嘉宾分享项目复盘。"],
            "conclusions": ["盲目扩张风险更大。"],
            "actionable_insights": ["用更短周期做复盘。"],
            "open_questions": ["市场窗口会持续多久？"],
        },
        {
            "overview": "节目讨论组织管理。",
            "topic": "团队协同",
            "core_question": "如何降低沟通损耗？",
            "themes": ["职责边界", "反馈机制"],
            "argument_structure": ["先统一目标，再拆职责。"],
            "key_evidence": ["给出了具体团队案例。"],
            "conclusions": ["目标对齐优先于流程复杂度。"],
            "actionable_insights": ["建立固定复盘节奏。"],
            "open_questions": ["何时需要更正式的流程？"],
        },
        {
            "overview": "节目讨论 AI 工作流。",
            "topic": "自动化实践",
            "core_question": "哪些环节最适合自动化？",
            "themes": ["工作流拆解"],
            "argument_structure": ["先找重复劳动，再定义接口。"],
            "key_evidence": ["对比了人工流程和自动化流程。"],
            "conclusions": ["接口清晰比工具数量更重要。"],
            "actionable_insights": ["先把输入输出标准化。"],
            "open_questions": ["自动化的维护成本如何控制？"],
        },
    ],
)
def test_summary_markdown_golden_cases(payload):
    markdown = render_summary_markdown(payload)
    for heading in ["## 主题", "## 核心问题", "## 论点结构", "## 关键证据", "## 结论", "## 行动启发"]:
        assert heading in markdown


@pytest.mark.parametrize(
    "payload",
    [
        {
            "conclusions": ["先验证真实需求。"],
            "principles": ["缩小问题范围。"],
            "quotes": ["先别急着做大。"],
            "signals": ["团队开始重视自动化。"],
            "concepts": ["需求验证"],
            "research_questions": ["什么场景最适合自动化？"],
        },
        {
            "conclusions": ["组织清晰度决定效率上限。"],
            "principles": ["目标先于流程。"],
            "quotes": ["目标不清，流程只会更乱。"],
            "signals": ["跨职能协同需求上升。"],
            "concepts": ["职责设计"],
            "research_questions": ["不同规模团队如何设计反馈机制？"],
        },
        {
            "conclusions": ["内容产品需要更强检索能力。"],
            "principles": ["结构化先于美化。"],
            "quotes": ["先把骨架搭起来。"],
            "signals": ["长文本工程方案越来越重要。"],
            "concepts": ["分层总结"],
            "research_questions": ["检索和总结应该如何配合？"],
        },
    ],
)
def test_knowledge_markdown_golden_cases(payload):
    markdown = render_knowledge_markdown(payload)
    for heading in ["## 结论", "## 可复用原则", "## 金句", "## 趋势与信号", "## 关键概念", "## 值得继续研究"]:
        assert heading in markdown
