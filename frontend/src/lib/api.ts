const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000";

export interface Article {
  id: string;
  title: string;
  url: string;
  source: string;
  content: string;
  summary: string;
  keywords: string;
  score: number;
  category: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface Issue {
  id: number;
  title: string;
  created_at: string;
  published_at: string | null;
  status: string;
  content: string;
}

// Collector
export async function triggerCollect() {
  const res = await fetch(`${API_BASE}/api/collect/trigger`, { method: "POST" });
  return res.json();
}

export async function getCollectStats() {
  const res = await fetch(`${API_BASE}/api/collect/stats`);
  return res.json();
}

// Processor
export async function runPipeline() {
  const res = await fetch(`${API_BASE}/api/process/run`, { method: "POST" });
  return res.json();
}

// Articles
export async function getPendingArticles(): Promise<Article[]> {
  const res = await fetch(`${API_BASE}/api/articles/pending`);
  return res.json();
}

export async function getArticle(id: string): Promise<Article> {
  const res = await fetch(`${API_BASE}/api/articles/${id}`);
  return res.json();
}

export async function updateArticle(
  id: string,
  updates: Partial<Pick<Article, "title" | "summary" | "category" | "status" | "content">>
) {
  const res = await fetch(`${API_BASE}/api/articles/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(updates),
  });
  return res.json();
}

// Issues
export async function generateIssue(title?: string) {
  const res = await fetch(`${API_BASE}/api/issue/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title: title || "" }),
  });
  return res.json();
}

export async function getIssue(id: number): Promise<Issue> {
  const res = await fetch(`${API_BASE}/api/issue/${id}`);
  return res.json();
}

export async function listIssues(): Promise<Issue[]> {
  const res = await fetch(`${API_BASE}/api/issues`);
  return res.json();
}

export async function exportIssue(id: number, format: "markdown" | "html" = "markdown") {
  const res = await fetch(`${API_BASE}/api/issue/${id}/export?format=${format}`, {
    method: "POST",
  });
  return res.json();
}

// Pipeline
export async function runFullPipeline() {
  const res = await fetch(`${API_BASE}/api/pipeline/run`, { method: "POST" });
  return res.json();
}
