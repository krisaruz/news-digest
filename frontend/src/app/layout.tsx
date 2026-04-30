import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI 科技简报 Dashboard",
  description: "每日 AI 科技简报管理后台",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN">
      <body className="min-h-screen bg-gray-50">{children}</body>
    </html>
  );
}
