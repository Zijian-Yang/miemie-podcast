"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { API_BASE_URL, EpisodeDetail, apiRequest } from "@/lib/api";

type Props = {
  episodeId: string;
};

export function EpisodeDetailView({ episodeId }: Props) {
  const router = useRouter();
  const [detail, setDetail] = useState<EpisodeDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<{ answer: string; citations: Array<Record<string, unknown>> } | null>(null);
  const [asking, setAsking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadDetail() {
    const payload = await apiRequest<EpisodeDetail>(`/api/v1/episodes/${episodeId}`);
    setDetail(payload);
  }

  useEffect(() => {
    let active = true;
    async function bootstrap() {
      try {
        await apiRequest("/api/v1/auth/me");
        if (!active) {
          return;
        }
        await loadDetail();
      } catch (err) {
        router.replace("/login");
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }
    bootstrap();
    return () => {
      active = false;
    };
  }, [episodeId, router]);

  useEffect(() => {
    if (!detail) {
      return;
    }
    if (!["queued", "source_resolved", "transcribing", "transcribed", "analyzing"].includes(detail.episode.status)) {
      return;
    }
    const timer = window.setInterval(() => {
      void loadDetail();
    }, 5000);
    return () => window.clearInterval(timer);
  }, [detail]);

  const moduleMap = useMemo(() => {
    const map = new Map(detail?.modules.map((module) => [module.module_key, module]) || []);
    return map;
  }, [detail]);

  async function handleAsk(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setAsking(true);
    setError(null);
    try {
      const payload = await apiRequest<{ answer: string; citations: Array<Record<string, unknown>> }>(
        `/api/v1/episodes/${episodeId}/qa`,
        {
          method: "POST",
          body: JSON.stringify({ question }),
        },
      );
      setAnswer(payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : "问答失败");
    } finally {
      setAsking(false);
    }
  }

  async function copyText(value: string | null | undefined) {
    if (!value) {
      return;
    }
    await navigator.clipboard.writeText(value);
  }

  if (loading) {
    return <div className="page-shell"><div className="empty-state">正在加载详情...</div></div>;
  }

  if (!detail) {
    return <div className="page-shell"><div className="empty-state">未找到该记录。</div></div>;
  }

  const transcriptModule = moduleMap.get("transcript");
  const summaryModule = moduleMap.get("summary");
  const knowledgeModule = moduleMap.get("knowledge");
  const mindmapModule = moduleMap.get("mindmap");
  const mindmapDelivery = (mindmapModule?.content_json?._delivery || {}) as {
    png_render_status?: string;
  };

  return (
    <div className="page-shell detail-shell">
      <section className="hero-card">
        <div>
          <Link className="ghost-link" href="/">
            返回工作台
          </Link>
          <h1>{detail.episode.episode_title || "播客详情"}</h1>
          <p className="hero-copy">
            {detail.episode.podcast_title || "小宇宙单集"} · 状态 {detail.episode.status} · {detail.episode.current_stage_label}
            {" "}· {detail.episode.progress_percent}%
          </p>
          <div className="progress-track hero-progress" aria-hidden="true">
            <span className="progress-fill" style={{ width: `${detail.episode.progress_percent}%` }} />
          </div>
          {detail.episode.last_error ? <p className="helper-text error-text">{detail.episode.last_error}</p> : null}
        </div>
        <a className="primary-link" href={detail.episode.source_url} target="_blank" rel="noreferrer">
          打开原始页面
        </a>
      </section>

      <section className="detail-grid">
        <article className="panel wide-panel">
          <div className="panel-header">
            <div>
              <p className="eyebrow">总结模块</p>
              <h2>{summaryModule?.display_name || "总结"}</h2>
            </div>
            {summaryModule?.manifest.copy_markdown ? (
              <button className="ghost-button" onClick={() => void copyText(summaryModule?.rendered_markdown)}>
                复制 Markdown
              </button>
            ) : null}
          </div>
          <p className="helper-text">{summaryModule?.manifest.description}</p>
          <pre className="markdown-preview">{summaryModule?.rendered_markdown || "总结生成中..."}</pre>
          {summaryModule?.artifacts?.length ? (
            <div className="artifact-grid">
              {summaryModule.artifacts.map((artifact) => (
                <a
                  className="artifact-card"
                  key={artifact.artifact_key}
                  href={`${API_BASE_URL}${artifact.download_url}`}
                  target="_blank"
                  rel="noreferrer"
                >
                  <strong>{artifact.artifact_key}</strong>
                  <span>{artifact.mime_type}</span>
                </a>
              ))}
            </div>
          ) : null}
        </article>

        <article className="panel wide-panel">
          <div className="panel-header">
            <div>
              <p className="eyebrow">知识沉淀模块</p>
              <h2>{knowledgeModule?.display_name || "知识沉淀"}</h2>
            </div>
            {knowledgeModule?.manifest.copy_markdown ? (
              <button className="ghost-button" onClick={() => void copyText(knowledgeModule?.rendered_markdown)}>
                复制 Markdown
              </button>
            ) : null}
          </div>
          <p className="helper-text">{knowledgeModule?.manifest.description}</p>
          <pre className="markdown-preview">{knowledgeModule?.rendered_markdown || "知识沉淀生成中..."}</pre>
          {knowledgeModule?.artifacts?.length ? (
            <div className="artifact-grid">
              {knowledgeModule.artifacts.map((artifact) => (
                <a
                  className="artifact-card"
                  key={artifact.artifact_key}
                  href={`${API_BASE_URL}${artifact.download_url}`}
                  target="_blank"
                  rel="noreferrer"
                >
                  <strong>{artifact.artifact_key}</strong>
                  <span>{artifact.mime_type}</span>
                </a>
              ))}
            </div>
          ) : null}
        </article>

        <article className="panel">
          <div className="panel-header">
            <div>
              <p className="eyebrow">脑图模块</p>
              <h2>{mindmapModule?.display_name || "脑图与导出"}</h2>
            </div>
          </div>
          <p className="helper-text">{mindmapModule?.manifest.description}</p>
          {mindmapModule?.rendered_html ? (
            <iframe
              className="mindmap-frame"
              title="mindmap-preview"
              srcDoc={mindmapModule.rendered_html}
            />
          ) : (
            <div className="empty-state">
              脑图预览暂不可用，仍可尝试下载 HTML 或查看结构化 JSON。
            </div>
          )}
          {mindmapDelivery.png_render_status === "failed" ? (
            <p className="helper-text error-text">
              PNG 导出暂未生成，当前仍保留 HTML 预览和脑图结构 JSON 作为降级结果。
            </p>
          ) : null}
          <div className="artifact-grid">
            {(mindmapModule?.artifacts || [])
              .map((artifact) => (
                <a
                  className="artifact-card"
                  key={artifact.artifact_key}
                  href={`${API_BASE_URL}${artifact.download_url}`}
                  target="_blank"
                  rel="noreferrer"
                >
                  <strong>{artifact.artifact_key}</strong>
                  <span>{artifact.mime_type}</span>
                </a>
              ))}
          </div>
          <pre className="markdown-preview compact-preview">
            {JSON.stringify(mindmapModule?.content_json || {}, null, 2)}
          </pre>
        </article>

        <article className="panel">
          <div className="panel-header">
            <div>
              <p className="eyebrow">单集问答</p>
              <h2>对这一期继续追问</h2>
            </div>
          </div>
          <form className="stack" onSubmit={handleAsk}>
            <textarea
              className="input-area"
              rows={4}
              placeholder="例如：这期最重要的三条行业判断是什么？"
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
            />
            <button className="primary-button" type="submit" disabled={asking || !question.trim()}>
              {asking ? "问答中..." : "开始提问"}
            </button>
            {error ? <p className="helper-text error-text">{error}</p> : null}
          </form>
          {answer ? (
            <div className="qa-answer">
              <h3>回答</h3>
              <p>{answer.answer}</p>
              <h4>引用</h4>
              <ul className="citation-list">
                {answer.citations.map((citation, index) => (
                  <li key={`${citation.chunk_id || "citation"}-${index}`}>
                    <strong>{String(citation.source_kind)}</strong> {String(citation.excerpt || "")}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </article>
      </section>

      <section className="panel">
        <div className="panel-header">
            <div>
              <p className="eyebrow">逐字稿</p>
              <h2>{transcriptModule?.display_name || "逐字稿模块"}</h2>
            </div>
          {transcriptModule?.manifest.copy_markdown ? (
            <button className="ghost-button" onClick={() => void copyText(transcriptModule?.rendered_markdown)}>
              复制 Markdown
            </button>
          ) : null}
        </div>
        <p className="helper-text">
          {transcriptModule?.manifest.transcript_fidelity === "verbatim_asr"
            ? "该模块展示完整 ASR 原文，保留时间戳与顺序，不做摘要化改写。"
            : transcriptModule?.manifest.description}
        </p>
        <pre className="markdown-preview transcript-preview">
          {transcriptModule?.rendered_markdown || "逐字稿生成中..."}
        </pre>
        {transcriptModule?.artifacts?.length ? (
          <div className="artifact-grid">
            {transcriptModule.artifacts.map((artifact) => (
              <a
                className="artifact-card"
                key={artifact.artifact_key}
                href={`${API_BASE_URL}${artifact.download_url}`}
                target="_blank"
                rel="noreferrer"
              >
                <strong>{artifact.artifact_key}</strong>
                <span>{artifact.mime_type}</span>
              </a>
            ))}
          </div>
        ) : null}
      </section>
    </div>
  );
}
