"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getPendingArticles, updateArticle, triggerCollect, runPipeline, generateIssue, type Article } from "@/lib/api";
import { useState } from "react";

const CATEGORIES = ["科技动态", "AI 相关", "工具", "文章推荐", "资源", "言论"];

export default function PendingList() {
  const queryClient = useQueryClient();
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<Partial<Article>>({});

  const { data: articles, isLoading } = useQuery<Article[]>({
    queryKey: ["pending-articles"],
    queryFn: getPendingArticles,
    refetchInterval: 30000,
  });

  const approveMutation = useMutation({
    mutationFn: (id: string) => updateArticle(id, { status: "approved" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["pending-articles"] }),
  });

  const rejectMutation = useMutation({
    mutationFn: (id: string) => updateArticle(id, { status: "rejected" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["pending-articles"] }),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<Article> }) =>
      updateArticle(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["pending-articles"] });
      setEditingId(null);
    },
  });

  const collectMutation = useMutation({
    mutationFn: triggerCollect,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["pending-articles"] }),
  });

  const pipelineMutation = useMutation({
    mutationFn: runPipeline,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["pending-articles"] }),
  });

  const issueMutation = useMutation({
    mutationFn: (title?: string) => generateIssue(title),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["pending-articles"] }),
  });

  const handleSave = (id: string) => {
    updateMutation.mutate({ id, data: editForm });
  };

  const handleStartEdit = (article: Article) => {
    setEditingId(article.id);
    setEditForm({
      title: article.title,
      summary: article.summary,
      category: article.category || "",
    });
  };

  if (isLoading) {
    return <div className="text-center py-12 text-gray-500">加载中...</div>;
  }

  return (
    <div>
      {/* Actions */}
      <div className="flex gap-3 mb-6">
        <button
          onClick={() => collectMutation.mutate()}
          disabled={collectMutation.isPending}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
        >
          {collectMutation.isPending ? "采集中..." : "采集 RSS"}
        </button>
        <button
          onClick={() => pipelineMutation.mutate()}
          disabled={pipelineMutation.isPending}
          className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50"
        >
          {pipelineMutation.isPending ? "处理中..." : "AI 处理"}
        </button>
        <button
          onClick={() => issueMutation.mutate()}
          disabled={issueMutation.isPending}
          className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50"
        >
          生成简报
        </button>
      </div>

      {/* Article count */}
      <div className="mb-4 text-sm text-gray-500">
        共 {articles?.length || 0} 篇待审核文章
      </div>

      {/* Article list */}
      <div className="space-y-4">
        {articles?.map((article) => (
          <div
            key={article.id}
            className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm"
          >
            {editingId === article.id ? (
              /* Edit form */
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    标题
                  </label>
                  <input
                    type="text"
                    value={editForm.title || ""}
                    onChange={(e) =>
                      setEditForm({ ...editForm, title: e.target.value })
                    }
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    摘要
                  </label>
                  <textarea
                    value={editForm.summary || ""}
                    onChange={(e) =>
                      setEditForm({ ...editForm, summary: e.target.value })
                    }
                    rows={3}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    分类
                  </label>
                  <select
                    value={editForm.category || ""}
                    onChange={(e) =>
                      setEditForm({ ...editForm, category: e.target.value })
                    }
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                  >
                    <option value="">未分类</option>
                    {CATEGORIES.map((cat) => (
                      <option key={cat} value={cat}>
                        {cat}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => handleSave(article.id)}
                    className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700"
                  >
                    保存
                  </button>
                  <button
                    onClick={() => setEditingId(null)}
                    className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300"
                  >
                    取消
                  </button>
                </div>
              </div>
            ) : (
              /* Display */
              <>
                <div className="flex justify-between items-start">
                  <div className="flex-1">
                    <h3 className="text-lg font-semibold text-gray-900">
                      {article.title}
                    </h3>
                    <div className="flex gap-2 mt-2 flex-wrap">
                      <span className="text-xs px-2 py-1 bg-gray-100 text-gray-600 rounded">
                        {article.source}
                      </span>
                      {article.score > 0 && (
                        <span
                          className={`text-xs px-2 py-1 rounded ${
                            article.score >= 0.8
                              ? "bg-green-100 text-green-700"
                              : article.score >= 0.6
                              ? "bg-yellow-100 text-yellow-700"
                              : "bg-red-100 text-red-700"
                          }`}
                        >
                          评分: {(article.score * 100).toFixed(0)}
                        </span>
                      )}
                      {article.category && (
                        <span className="text-xs px-2 py-1 bg-blue-100 text-blue-700 rounded">
                          {article.category}
                        </span>
                      )}
                      <span
                        className={`text-xs px-2 py-1 rounded ${
                          article.status === "screened"
                            ? "bg-green-100 text-green-700"
                            : "bg-orange-100 text-orange-700"
                        }`}
                      >
                        {article.status === "screened" ? "已筛选" : "新"}
                      </span>
                    </div>
                  </div>
                </div>

                {article.summary && (
                  <p className="mt-3 text-gray-600 text-sm">{article.summary}</p>
                )}

                <div className="flex gap-2 mt-4">
                  {article.url && (
                    <a
                      href={article.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm text-blue-600 hover:underline"
                    >
                      原文链接
                    </a>
                  )}
                  <button
                    onClick={() => handleStartEdit(article)}
                    className="text-sm text-gray-600 hover:text-gray-900"
                  >
                    编辑
                  </button>
                  <button
                    onClick={() => approveMutation.mutate(article.id)}
                    className="text-sm text-green-600 hover:text-green-800"
                  >
                    通过
                  </button>
                  <button
                    onClick={() => rejectMutation.mutate(article.id)}
                    className="text-sm text-red-600 hover:text-red-800"
                  >
                    排除
                  </button>
                </div>
              </>
            )}
          </div>
        ))}

        {articles?.length === 0 && (
          <div className="text-center py-12 bg-white rounded-xl border border-gray-200">
            <p className="text-gray-500">暂无待审核文章，请先点击"采集 RSS"</p>
          </div>
        )}
      </div>
    </div>
  );
}
