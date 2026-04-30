"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { listIssues, exportIssue, type Issue } from "@/lib/api";
import { useState } from "react";

export default function IssueList() {
  const queryClient = useQueryClient();
  const [exportingId, setExportingId] = useState<number | null>(null);
  const [exportFormat, setExportFormat] = useState<"markdown" | "html">("markdown");
  const [previewContent, setPreviewContent] = useState<string | null>(null);

  const { data: issues, isLoading } = useQuery<Issue[]>({
    queryKey: ["issues"],
    queryFn: listIssues,
  });

  const exportMutation = useMutation({
    mutationFn: ({ id, format }: { id: number; format: "markdown" | "html" }) =>
      exportIssue(id, format),
    onSuccess: (data) => {
      setPreviewContent(data.content);
      setExportingId(null);
    },
  });

  const handleExport = (id: number) => {
    setExportingId(id);
    exportMutation.mutate({ id, format: exportFormat });
  };

  if (isLoading) {
    return <div className="text-center py-12 text-gray-500">加载中...</div>;
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div className="text-sm text-gray-500">
          共 {issues?.length || 0} 期
        </div>
        <div className="flex gap-2 items-center">
          <span className="text-sm text-gray-600">导出格式:</span>
          <select
            value={exportFormat}
            onChange={(e) =>
              setExportFormat(e.target.value as "markdown" | "html")
            }
            className="px-3 py-1 border border-gray-300 rounded-lg text-sm"
          >
            <option value="markdown">Markdown</option>
            <option value="html">HTML (微信公众号)</option>
          </select>
        </div>
      </div>

      <div className="space-y-4">
        {issues?.map((issue) => (
          <div
            key={issue.id}
            className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm"
          >
            <div className="flex justify-between items-center">
              <div>
                <h3 className="text-lg font-semibold text-gray-900">
                  {issue.title}
                </h3>
                <div className="flex gap-2 mt-2">
                  <span className="text-sm text-gray-500">
                    创建: {new Date(issue.created_at).toLocaleString("zh-CN")}
                  </span>
                  <span
                    className={`text-xs px-2 py-1 rounded ${
                      issue.status === "published"
                        ? "bg-green-100 text-green-700"
                        : "bg-yellow-100 text-yellow-700"
                    }`}
                  >
                    {issue.status === "published" ? "已发布" : "草稿"}
                  </span>
                </div>
              </div>
              <button
                onClick={() => handleExport(issue.id)}
                disabled={exportingId === issue.id}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 text-sm"
              >
                {exportingId === issue.id ? "导出中..." : "导出"}
              </button>
            </div>
          </div>
        ))}

        {issues?.length === 0 && (
          <div className="text-center py-12 bg-white rounded-xl border border-gray-200">
            <p className="text-gray-500">暂无历史期刊</p>
          </div>
        )}
      </div>

      {/* Preview modal */}
      {previewContent && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl max-w-3xl w-full max-h-[80vh] overflow-auto p-6">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-lg font-bold">导出预览</h2>
              <button
                onClick={() => setPreviewContent(null)}
                className="text-gray-500 hover:text-gray-700"
              >
                关闭
              </button>
            </div>
            {exportFormat === "html" ? (
              <div dangerouslySetInnerHTML={{ __html: previewContent }} />
            ) : (
              <pre className="whitespace-pre-wrap text-sm font-mono bg-gray-50 p-4 rounded-lg">
                {previewContent}
              </pre>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
