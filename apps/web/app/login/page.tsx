"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { apiRequest } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await apiRequest("/api/v1/auth/login", {
        method: "POST",
        body: JSON.stringify({ password }),
      });
      router.replace("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "登录失败");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="login-shell">
      <section className="login-card">
        <p className="eyebrow">Single User Workspace</p>
        <h1>登录 Miemie Podcast</h1>
        <p className="hero-copy">
          首版采用简单管理口令保护工作台，内部数据结构已预留多用户与 Postgres / Redis 迁移接口。
        </p>
        <form className="stack" onSubmit={handleSubmit}>
          <input
            className="inline-input"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="输入管理密码"
          />
          <button className="primary-button" type="submit" disabled={submitting || !password.trim()}>
            {submitting ? "登录中..." : "进入工作台"}
          </button>
          {error ? <p className="helper-text error-text">{error}</p> : null}
        </form>
      </section>
    </main>
  );
}

