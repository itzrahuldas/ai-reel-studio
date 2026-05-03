"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import type { ReelProjectStatus } from "@/lib/api-client";

const STATUS_COLORS: Record<string, string> = {
  draft: "bg-gray-700 text-gray-300",
  script_generating: "bg-blue-900 text-blue-300",
  script_ready: "bg-cyan-900 text-cyan-300",
  video_generating: "bg-indigo-900 text-indigo-300",
  audio_generating: "bg-purple-900 text-purple-300",
  rendering: "bg-amber-900 text-amber-300",
  ready_for_review: "bg-yellow-900 text-yellow-300",
  approved: "bg-green-900 text-green-300",
  published: "bg-emerald-900 text-emerald-300",
  failed: "bg-red-900 text-red-300",
  failed_script: "bg-red-900 text-red-300",
};

const STATUS_LABELS: Record<string, string> = {
  draft: "Draft",
  script_generating: "Generating...",
  script_ready: "Script Ready",
  ready_for_review: "Ready for Review",
  approved: "Approved",
  published: "Published",
  failed: "Failed",
  failed_script: "Generation Failed",
};

function StatusBadge({ status }: { status: ReelProjectStatus }) {
  const label = STATUS_LABELS[status] ?? status.replace(/_/g, " ");
  const color = STATUS_COLORS[status] ?? "bg-gray-700 text-gray-300";
  return (
    <span className={"text-xs font-medium px-3 py-1 rounded-full " + color}>
      {label}
    </span>
  );
}

function SkeletonCard() {
  return (
    <div className="card animate-pulse">
      <div className="h-4 bg-gray-800 rounded w-1/2 mb-2" />
      <div className="h-3 bg-gray-800 rounded w-1/4" />
    </div>
  );
}

function EmptyState() {
  return (
    <div className="text-center py-20">
      <div className="text-6xl mb-4">🎬</div>
      <h2 className="text-xl font-semibold text-white mb-2">No reels yet</h2>
      <p className="text-gray-400 mb-6">Create your first AI-powered Instagram Reel in minutes.</p>
      <Link href="/dashboard/create" className="btn-primary">
        + Create Your First Reel
      </Link>
    </div>
  );
}

export default function DashboardPage() {
  const router = useRouter();

  useEffect(() => {
    if (!localStorage.getItem("access_token")) {
      router.replace("/login");
    }
  }, [router]);

  const { data: projects, isLoading, isError, error } = useQuery({
    queryKey: ["reel-projects"],
    queryFn: () => apiClient.listReelProjects(),
    staleTime: 30_000,
  });

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-white">Your Reels</h1>
          <p className="text-gray-400 mt-1">Manage and publish your AI-generated Instagram Reels</p>
        </div>
        <Link href="/dashboard/create" id="create-reel-btn" className="btn-primary">
          + Create Reel
        </Link>
      </div>

      {isLoading && (
        <div className="grid gap-4">
          {[1, 2, 3].map((i) => <SkeletonCard key={i} />)}
        </div>
      )}

      {isError && (
        <div className="p-4 rounded-xl bg-red-950/50 border border-red-800/50 text-red-300 text-sm">
          Failed to load projects: {(error as { message?: string })?.message ?? "Unknown error"}
        </div>
      )}

      {!isLoading && !isError && projects?.length === 0 && <EmptyState />}

      {!isLoading && !isError && projects && projects.length > 0 && (
        <div className="grid gap-4">
          {projects.map((project) => (
            <Link
              key={project.id}
              href={"/dashboard/reels/" + project.id}
              id={"project-card-" + project.id}
              className="card hover:border-gray-700 transition-colors flex items-center justify-between"
            >
              <div className="flex-1 min-w-0 pr-4">
                <h3 className="font-semibold text-white truncate">{project.title ?? "Untitled Reel"}</h3>
                <p className="text-sm text-gray-500 mt-1 truncate">{project.prompt}</p>
                <p className="text-xs text-gray-600 mt-1">
                  {new Date(project.created_at).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}
                </p>
              </div>
              <StatusBadge status={project.status} />
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
