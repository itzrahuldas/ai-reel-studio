"use client";
import Link from "next/link";

const STATUS_COLORS: Record<string, string> = {
  draft: "bg-gray-700 text-gray-300",
  script_generating: "bg-blue-900 text-blue-300",
  ready_for_review: "bg-yellow-900 text-yellow-300",
  approved: "bg-green-900 text-green-300",
  published: "bg-emerald-900 text-emerald-300",
  failed: "bg-red-900 text-red-300",
};

const MOCK_PROJECTS = [
  { id: "1", title: "Bakery Launch Reel", status: "ready_for_review", created_at: "2026-05-03" },
  { id: "2", title: "Product Showcase", status: "published", created_at: "2026-05-02" },
  { id: "3", title: "Brand Story", status: "script_generating", created_at: "2026-05-01" },
];

export default function DashboardPage() {
  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-white">Your Reels</h1>
          <p className="text-gray-400 mt-1">Manage and publish your AI-generated Instagram Reels</p>
        </div>
        <Link href="/dashboard/create" className="btn-primary">+ Create Reel</Link>
      </div>
      <div className="grid gap-4">
        {MOCK_PROJECTS.map((project) => (
          <Link key={project.id} href={`/dashboard/reels/${project.id}`}
            className="card hover:border-gray-700 transition-colors flex items-center justify-between">
            <div>
              <h3 className="font-semibold text-white">{project.title}</h3>
              <p className="text-sm text-gray-500 mt-1">{project.created_at}</p>
            </div>
            <span className={`text-xs font-medium px-3 py-1 rounded-full ${STATUS_COLORS[project.status] ?? "bg-gray-700 text-gray-300"}`}>
              {project.status.replace(/_/g, " ")}
            </span>
          </Link>
        ))}
      </div>
    </div>
  );
}
