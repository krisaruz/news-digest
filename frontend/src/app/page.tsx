"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import PendingList from "@/components/PendingList";
import IssueList from "@/components/IssueList";

export default function Home() {
  const [queryClient] = useState(() => new QueryClient());
  const [activeTab, setActiveTab] = useState<"pending" | "issues">("pending");

  return (
    <QueryClientProvider client={queryClient}>
      <div className="min-h-screen bg-gray-50">
        {/* Header */}
        <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex justify-between items-center h-16">
              <h1 className="text-xl font-bold text-gray-900">AI 科技简报 Dashboard</h1>
              <div className="flex gap-2">
                <TabButton
                  active={activeTab === "pending"}
                  onClick={() => setActiveTab("pending")}
                >
                  待审核
                </TabButton>
                <TabButton
                  active={activeTab === "issues"}
                  onClick={() => setActiveTab("issues")}
                >
                  历史期刊
                </TabButton>
              </div>
            </div>
          </div>
        </header>

        {/* Content */}
        <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          {activeTab === "pending" ? <PendingList /> : <IssueList />}
        </main>
      </div>
    </QueryClientProvider>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
        active
          ? "bg-green-600 text-white"
          : "text-gray-600 hover:bg-gray-100"
      }`}
    >
      {children}
    </button>
  );
}
