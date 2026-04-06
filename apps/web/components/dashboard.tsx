"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { API_BASE_URL, EpisodeListItem, apiRequest } from "@/lib/api";

type DashboardPayload = {
  items: EpisodeListItem[];
  total: number;
  page: number;
  page_size: number;
};

const activeStatuses = new Set(["queued", "source_resolved", "transcribing", "transcribed", "analyzing"]);

export function Dashboard() {
  const router = useRouter();
  const [episodes, setEpisodes] = useState<EpisodeListItem[]>([]);
  const [search, setSearch] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);

  async function loadEpisodes(currentQuery = search) {
    const query = new URLSearchParams();
    if (currentQuery.trim()) {
      query.set("query", currentQuery.trim());
    }
    const payload = await apiRequest<DashboardPayload>(`/api/v1/episodes?${query.toString()}`);
    setEpisodes(payload.items);
  }

  useEffect(() => {
    let active = true;
    async function bootstrap() {
      try {
        await apiRequest("/api/v1/auth/me");
        if (!active) {
          return;
        }
        await loadEpisodes("");
      } catch {
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
  }, [router]);

  useEffect(() => {
    const hasProcessing = episodes.some((item) => activeStatuses.has(item.status));
    if (!hasProcessing) {
      return;
    }
    const timer = window.setInterval(() => {
      void loadEpisodes();
    }, 5000);
    return () => window.clearInterval(timer);
  }, [episodes, search]);

  const stats = useMemo(() => {
    const ready = episodes.filter((item) => item.status === "ready").length;
    const processing = episodes.filter((item) => activeStatuses.has(item.status)).length;
    const failed = episodes.filter((item) => item.status === "failed").length;
    return { ready, processing, failed };
  }, [episodes]);

  async function handleImport(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setFeedback(null);
    try {
      const payload = await apiRequest<{ episode: EpisodeListItem; reused: boolean }>("/api/v1/episodes/import", {
        method: "POST",
        body: JSON.stringify({ source_url: sourceUrl }),
      });
      setSourceUrl("");
      setFeedback(payload.reused ? "该链接已存在，已直接返回历史记录。" : "导入任务已创建，后台开始处理。");
      await loadEpisodes();
    } catch (error) {
      setFeedback(error instanceof Error ? error.message : "导入失败");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete(id: string) {
    const confirmed = window.confirm("确认删除这条处理记录及其产物吗？");
    if (!confirmed) {
      return;
    }
    await apiRequest(`/api/v1/episodes/${id}`, { method: "DELETE" });
    await loadEpisodes();
  }

  if (loading) {
    return <div className="page-shell"><div className="empty-state">正在加载工作台...</div></div>;
  }

  return (
    <div className="page-shell">
      <section className="hero-card">
        <div>
          <p className="eyebrow">Miemie Podcast</p>
          <h1>把小宇宙播客沉淀成可搜索的第二大脑</h1>
          <p className="hero-copy">
            输入小宇宙单集链接，系统会自动提取音频、提交 Qwen ASR 转写、做分层分析，并生成总结、
            知识沉淀、逐字稿、脑图和单集问答。
          </p>
        </div>
      </section>

      <section className="stats-grid">
        <article className="stat-card">
          <span>已完成</span>
          <strong>{stats.ready}</strong>
        </article>
        <article className="stat-card">
          <span>处理中</span>
          <strong>{stats.processing}</strong>
        </article>
        <article className="stat-card">
          <span>失败</span>
          <strong>{stats.failed}</strong>
        </article>
      </section>

      <section className="content-grid">
        <article className="panel">
          <div className="panel-header">
            <div>
              <p className="eyebrow">导入</p>
              <h2>提交小宇宙单集链接</h2>
            </div>
          </div>
          <form className="stack" onSubmit={handleImport}>
            <textarea
              className="input-area"
              placeholder="https://www.xiaoyuzhoufm.com/episode/69b1645e9b893f69c739b82a"
              value={sourceUrl}
              onChange={(event) => setSourceUrl(event.target.value)}
              rows={4}
            />
            <button className="primary-button" type="submit" disabled={submitting || !sourceUrl.trim()}>
              {submitting ? "提交中..." : "开始处理"}
            </button>
            {feedback ? <p className="helper-text">{feedback}</p> : null}
          </form>
        </article>

        <article className="panel">
          <div className="panel-header">
            <div>
              <p className="eyebrow">历史</p>
              <h2>全文搜索与记录管理</h2>
            </div>
            <div className="search-bar">
              <input
                className="inline-input"
                placeholder="搜索标题、播客名"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
              />
              <button className="ghost-button" onClick={() => void loadEpisodes(search)}>
                搜索
              </button>
            </div>
          </div>
          <div className="episode-list">
            {episodes.length === 0 ? (
              <div className="empty-state">还没有处理记录，先导入一条播客试试。</div>
            ) : null}
            {episodes.map((item) => (
              <div className="episode-row" key={item.id}>
                <div className="episode-meta">
                  <span className={`status-chip status-${item.status}`}>{item.status}</span>
                  <h3>{item.episode_title || item.source_episode_id}</h3>
                  <p>{item.podcast_title || "小宇宙单集"}</p>
                  <p className="progress-text">
                    {item.current_stage_label} · {item.progress_percent}%
                  </p>
                  <div className="progress-track" aria-hidden="true">
                    <span className="progress-fill" style={{ width: `${item.progress_percent}%` }} />
                  </div>
                </div>
                <div className="episode-actions">
                  <Link className="primary-link" href={`/episodes/${item.id}`}>
                    查看详情
                  </Link>
                  <a className="ghost-link" href={item.source_url} target="_blank" rel="noreferrer">
                    原链接
                  </a>
                  <button className="danger-link" onClick={() => void handleDelete(item.id)}>
                    删除
                  </button>
                </div>
              </div>
            ))}
          </div>
        </article>
      </section>

      <section className="footer-strip">
        <div>
          <strong>支持能力:</strong> 总结、知识沉淀、逐字稿、脑图、单集问答
        </div>
        <div>
          <strong>处理范围:</strong> 小宇宙单集链接导入与历史检索
        </div>
      </section>
    </div>
  );
}
