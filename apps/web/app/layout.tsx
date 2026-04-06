import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "Miemie Podcast",
  description: "小宇宙播客分析与知识沉淀工作台",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN" suppressHydrationWarning>
      <body>{children}</body>
    </html>
  );
}
