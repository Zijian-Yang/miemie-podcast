"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { apiRequest } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function enterWorkspace() {
    setSubmitting(true);
    setError(null);
    try {
      await apiRequest("/api/v1/auth/me");
      router.replace("/");
      return;
    } catch {
    }
    try {
      await apiRequest("/api/v1/auth/login", {
        method: "POST",
        body: JSON.stringify({}),
      });
      router.replace("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "进入工作台失败");
    } finally {
      setSubmitting(false);
    }
  }

  useEffect(() => {
    void enterWorkspace();
  }, []);

  return (
    <main className="login-shell">
      <section className="login-card">
        <p className="eyebrow">Miemie Podcast</p>
        <h1>进入 Miemie Podcast</h1>
        <p className="hero-copy">
          当前为单用户会话模式，系统会自动创建登录会话并进入工作台。
        </p>
        <div className="stack">
          <button className="primary-button" type="button" disabled={submitting} onClick={() => void enterWorkspace()}>
            {submitting ? "进入中..." : "进入工作台"}
          </button>
          {error ? <p className="helper-text error-text">{error}</p> : null}
        </div>
      </section>
    </main>
  );
}
