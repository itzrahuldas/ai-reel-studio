"use client";

import { useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import type { ReelProject, ReelVersion, GenerationJob } from "@/lib/api-client";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const GENERATING_STATUSES = new Set([
  "draft",
  "script_generating",
  "video_generating",
  "audio_generating",
  "rendering",
]);

const STATUS_COLORS: Record<string, string> = {
  draft: "bg-gray-700 text-gray-300",
  script_generating: "bg-blue-900 text-blue-300",
  ready_for_review: "bg-yellow-900 text-yellow-300",
  approved: "bg-green-900 text-green-300",
  published: "bg-emerald-900 text-emerald-300",
  failed: "bg-red-900 text-red-300",
  failed_script: "bg-red-900 text-red-300",
};

function StatusBadge({ status }: { status: string }) {
  const label = status.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  const color = STATUS_COLORS[status] ?? "bg-gray-700 text-gray-300";
  return <span className={"text-xs font-semibold px-3 py-1.5 rounded-full " + color}>{label}</span>;
}

function SectionCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="card">
      <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">{title}</h2>
      {children}
    </div>
  );
}

function GenerationTimeline({ jobs }: { jobs: GenerationJob[] }) {
  if (!jobs.length) return null;
  return (
    <SectionCard title="Generation Timeline">
      <div className="space-y-3">
        {jobs.map((job) => (
          <div key={job.id} className="flex items-start gap-3">
            <div
              className={
                "mt-1 w-2 h-2 rounded-full flex-shrink-0 " +
                (job.status === "complete"
                  ? "bg-green-500"
                  : job.status === "failed"
                  ? "bg-red-500"
                  : job.status === "running"
                  ? "bg-blue-400 animate-pulse"
                  : "bg-gray-600")
              }
            />
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-300 font-medium">
                  {job.job_type.replace(/_/g, " ")}
                </span>
                <StatusBadge status={job.status} />
              </div>
              {job.started_at && (
                <p className="text-xs text-gray-600 mt-0.5">
                  Started: {new Date(job.started_at).toLocaleTimeString()}
                </p>
              )}
              {job.completed_at && (
                <p className="text-xs text-gray-600">
                  Done: {new Date(job.completed_at).toLocaleTimeString()}
                </p>
              )}
              {job.error_message && (
                <p className="text-xs text-red-400 mt-1">{job.error_message}</p>
              )}
            </div>
          </div>
        ))}
      </div>
    </SectionCard>
  );
}

function VersionContent({ version }: { version: ReelVersion }) {
  return (
    <>
      {version.hook && (
        <SectionCard title="Hook">
          <p className="text-white font-medium text-lg">{version.hook}</p>
        </SectionCard>
      )}
      {version.script && (
        <SectionCard title="Script">
          <p className="text-gray-300 text-sm leading-relaxed whitespace-pre-wrap">{version.script}</p>
        </SectionCard>
      )}
      {version.scenes && version.scenes.length > 0 && (
        <SectionCard title={"Storyboard (" + version.scenes.length + " Scenes)"}>
          <div className="space-y-3">
            {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
            {(version.scenes as any[]).map((scene, idx: number) => (
              <div key={idx} className="p-3 bg-gray-800/60 rounded-lg border border-gray-700">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs font-bold text-violet-400">
                    Scene {scene.scene_number ?? idx + 1}
                  </span>
                  <span className="text-xs text-gray-500">{scene.duration_seconds}s</span>
                </div>
                <p className="text-sm text-gray-300">{scene.visual_description}</p>
                {scene.text_overlay && (
                  <p className="text-xs text-gray-500 mt-1 italic">On-screen: {scene.text_overlay}</p>
                )}
              </div>
            ))}
          </div>
        </SectionCard>
      )}
      {version.voiceover_text && (
        <SectionCard title="Voiceover">
          <p className="text-gray-300 text-sm leading-relaxed">{version.voiceover_text}</p>
        </SectionCard>
      )}
      {version.subtitle_lines && version.subtitle_lines.length > 0 && (
        <SectionCard title="Subtitle Lines">
          <div className="space-y-1 max-h-40 overflow-y-auto">
            {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
            {(version.subtitle_lines as any[]).map((line, idx: number) => (
              <div key={idx} className="flex gap-3 text-sm">
                <span className="text-gray-600 flex-shrink-0">{line.start_seconds}s</span>
                <span className="text-gray-300">{line.text}</span>
              </div>
            ))}
          </div>
        </SectionCard>
      )}
      {version.caption && (
        <SectionCard title="Caption">
          <div className="p-3 bg-gray-800/60 rounded-lg text-sm text-gray-300 whitespace-pre-wrap leading-relaxed">
            {version.caption}
          </div>
        </SectionCard>
      )}
      {version.hashtags && version.hashtags.length > 0 && (
        <SectionCard title="Hashtags">
          <div className="flex flex-wrap gap-2">
            {version.hashtags.map((tag, i) => (
              <span key={i} className="text-xs px-2 py-1 bg-violet-900/50 text-violet-300 rounded-md">
                {tag}
              </span>
            ))}
          </div>
        </SectionCard>
      )}
      {version.video_prompt && (
        <SectionCard title="Video Prompt">
          <p className="text-gray-400 text-sm italic leading-relaxed">{version.video_prompt}</p>
        </SectionCard>
      )}
    </>
  );
}

export default function ReelDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!localStorage.getItem("access_token")) {
      router.replace("/login");
    }
  }, [router]);

  const { data: project, isLoading, isError } = useQuery<ReelProject>({
    queryKey: ["reel-project", id],
    queryFn: () => apiClient.getReelProject(id),
    refetchInterval: (query) => {
      const s = query.state.data?.status;
      return s && GENERATING_STATUSES.has(s) ? 3000 : false;
    },
    enabled: !!id,
  });

  const { data: jobs } = useQuery<GenerationJob[]>({
    queryKey: ["reel-project-jobs", id],
    queryFn: () => apiClient.getReelProjectJobs(id),
    refetchInterval: () =>
      project && GENERATING_STATUSES.has(project.status) ? 3000 : false,
    enabled: !!id,
  });

  const regenerateMutation = useMutation({
    mutationFn: () => apiClient.regenerateReelProject(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["reel-project", id] });
      queryClient.invalidateQueries({ queryKey: ["reel-project-jobs", id] });
    },
  });

  if (isLoading) {
    return (
      <div className="p-8 max-w-4xl mx-auto">
        <div className="animate-pulse space-y-4">
          <div className="h-8 bg-gray-800 rounded w-1/3" />
          <div className="h-4 bg-gray-800 rounded w-1/2" />
          <div className="h-64 bg-gray-800 rounded" />
        </div>
      </div>
    );
  }

  if (isError || !project) {
    return (
      <div className="p-8 max-w-4xl mx-auto text-center py-20">
        <div className="text-6xl mb-4">404</div>
        <h2 className="text-xl font-semibold text-white mb-2">Project not found</h2>
        <p className="text-gray-400 mb-6">
          This reel does not exist or you do not have access.
        </p>
        <Link href="/dashboard" className="btn-primary">
          Back to Dashboard
        </Link>
      </div>
    );
  }

  const version = project.latest_version;
  const isGenerating = GENERATING_STATUSES.has(project.status);

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="flex items-start justify-between mb-6 gap-4">
        <div>
          <Link href="/dashboard" className="text-sm text-gray-500 hover:text-gray-300 mb-2 block">
            Back to Dashboard
          </Link>
          <h1 className="text-2xl font-bold text-white">{project.title ?? "Untitled Reel"}</h1>
          <p className="text-gray-400 text-sm mt-1 max-w-xl">{project.prompt}</p>
          <div className="flex items-center gap-3 mt-3 text-xs text-gray-500">
            <span>Lang: {project.language}</span>
            {project.tone && <span>Tone: {project.tone}</span>}
            <span>{project.duration_seconds}s</span>
            {project.cta_text && <span>CTA: {project.cta_text}</span>}
          </div>
        </div>
        <div className="flex flex-col items-end gap-3 flex-shrink-0">
          <StatusBadge status={project.status} />
          <button
            id="regenerate-btn"
            onClick={() => regenerateMutation.mutate()}
            disabled={regenerateMutation.isPending || isGenerating}
            className="btn-secondary text-sm disabled:opacity-50"
          >
            {regenerateMutation.isPending ? "Regenerating..." : "Regenerate"}
          </button>
        </div>
      </div>

      {isGenerating && (
        <div
          id="generating-banner"
          className="mb-6 p-4 rounded-xl bg-blue-950/50 border border-blue-800/50 text-blue-300 text-sm flex items-center gap-3"
        >
          <span>AI is generating your reel... This page will update automatically.</span>
        </div>
      )}

      {project.status === "failed_script" && (
        <div className="mb-6 p-4 rounded-xl bg-red-950/50 border border-red-800/50 text-red-300 text-sm">
          Generation failed. Click Regenerate to try again.
        </div>
      )}

      <div className="grid lg:grid-cols-2 gap-6">
        <div className="space-y-4">
          {project.source_image_id && (
            <SectionCard title="Reference Image">
              <img
                src={API_BASE + "/static/uploads/" + project.source_image_id}
                alt="Reference"
                className="rounded-lg w-full object-cover max-h-48"
                onError={(e) => {
                  (e.target as HTMLImageElement).style.display = "none";
                }}
              />
            </SectionCard>
          )}

          {version ? (
            <VersionContent version={version} />
          ) : (
            !isGenerating && (
              <SectionCard title="Generated Content">
                <p className="text-gray-500 text-sm">
                  No content generated yet. Click Regenerate to start.
                </p>
              </SectionCard>
            )
          )}

          {jobs && jobs.length > 0 && <GenerationTimeline jobs={jobs} />}
        </div>

        <div className="space-y-4">
          <SectionCard title="Video Preview">
            <div className="aspect-[9/16] max-h-80 flex flex-col items-center justify-center bg-gray-900 rounded-xl border-2 border-dashed border-gray-700">
              {isGenerating ? (
                <div className="text-center">
                  <div className="text-4xl mb-2 animate-pulse">🎬</div>
                  <p className="text-gray-400 text-sm">Generating...</p>
                </div>
              ) : (
                <div className="text-center">
                  <div className="text-4xl mb-2">🎬</div>
                  <p className="text-gray-500 text-sm">Video preview placeholder</p>
                  <p className="text-gray-600 text-xs mt-1">Video rendering coming in next feature</p>
                </div>
              )}
            </div>
          </SectionCard>

          <div className="card">
            <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">
              Project Info
            </h2>
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between">
                <dt className="text-gray-500">Project ID</dt>
                <dd className="text-gray-300 font-mono text-xs">{project.id.slice(0, 8)}...</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">Created</dt>
                <dd className="text-gray-300">
                  {new Date(project.created_at).toLocaleString("en-IN")}
                </dd>
              </div>
              {version && (
                <div className="flex justify-between">
                  <dt className="text-gray-500">Version</dt>
                  <dd className="text-gray-300">v{version.version_number}</dd>
                </div>
              )}
            </dl>
          </div>
        </div>
      </div>
    </div>
  );
}
