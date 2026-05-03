"use client";
import { useParams } from "next/navigation";

export default function ReelDetailPage() {
  const { id } = useParams<{ id: string }>();

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-white">Reel #{id}</h1>
        <span className="text-xs font-medium px-3 py-1 rounded-full bg-yellow-900 text-yellow-300">
          Ready for Review
        </span>
      </div>
      <div className="grid lg:grid-cols-2 gap-6">
        <div className="space-y-4">
          <div className="card">
            <h2 className="font-semibold text-white mb-3">Script</h2>
            <p className="text-gray-400 text-sm leading-relaxed">
              Your generated script will appear here after AI processing completes.
            </p>
          </div>
          <div className="card">
            <h2 className="font-semibold text-white mb-3">Caption</h2>
            <textarea
              className="input resize-none w-full h-32"
              placeholder="Generated caption..."
              aria-label="Caption editor"
            />
          </div>
          <div className="card">
            <h2 className="font-semibold text-white mb-3">Hashtags</h2>
            <p className="text-gray-400 text-sm">#ai #reels #content</p>
          </div>
        </div>
        <div className="space-y-4">
          <div className="card aspect-[9/16] max-h-96 flex items-center justify-center bg-gray-800 rounded-xl">
            <p className="text-gray-500 text-sm">Video preview will appear here</p>
          </div>
          <div className="flex gap-3">
            <button
              id="approve-btn"
              className="btn-primary flex-1 justify-center"
              onClick={() => alert("TODO: POST /api/v1/reel-versions/{id}/approve")}
            >
              Approve &amp; Publish
            </button>
            <button
              id="reject-btn"
              className="btn-secondary flex-1 justify-center"
              onClick={() => alert("TODO: POST /api/v1/reel-versions/{id}/reject")}
            >
              Regenerate
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
