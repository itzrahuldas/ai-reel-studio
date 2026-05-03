"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import type { 
  ReelVersionEditorResponse, 
  StoryboardSceneInput, 
  SubtitleLineInput 
} from "@/lib/api-client";



function SectionCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="card mb-6">
      <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4 border-b border-gray-800 pb-2">
        {title}
      </h2>
      {children}
    </div>
  );
}

export default function EditorPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!localStorage.getItem("access_token")) {
      router.replace("/login");
    }
  }, [router]);

  const { data, isLoading, isError } = useQuery<ReelVersionEditorResponse>({
    queryKey: ["reel-editor", id],
    queryFn: () => apiClient.getReelEditorData(id),
    enabled: !!id,
  });

  const [hook, setHook] = useState("");
  const [script, setScript] = useState("");
  const [voiceoverText, setVoiceoverText] = useState("");
  const [caption, setCaption] = useState("");
  const [hashtags, setHashtags] = useState<string[]>([]);
  const [storyboard, setStoryboard] = useState<StoryboardSceneInput[]>([]);
  const [subtitles, setSubtitles] = useState<SubtitleLineInput[]>([]);
  const [duration, setDuration] = useState<number>(30);
  
  const [isDirty, setIsDirty] = useState(false);

  // Initialize state from data
  useEffect(() => {
    if (data?.version && !isDirty) {
      setHook(data.version.hook || "");
      setScript(data.version.script || "");
      setVoiceoverText(data.version.voiceover_text || "");
      setCaption(data.version.caption || "");
      setHashtags(data.version.hashtags || []);
      setStoryboard((data.version.scenes as unknown as StoryboardSceneInput[]) || []);
      setSubtitles((data.version.subtitle_lines as unknown as SubtitleLineInput[]) || []);
      setDuration(
        data.version.render_settings?.duration_seconds || 
        data.project.duration_seconds || 
        30
      );
    }
  }, [data, isDirty]);

  const saveMutation = useMutation({
    mutationFn: async () => {
      if (!data) return;
      return apiClient.updateReelVersion(id, data.version.id, {
        hook,
        script,
        voiceover_text: voiceoverText,
        caption,
        hashtags,
        storyboard,
        subtitle_lines: subtitles,
        render_settings: {
          duration_seconds: duration,
        }
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["reel-editor", id] });
      queryClient.invalidateQueries({ queryKey: ["reel-project", id] });
      setIsDirty(false);
      alert("Draft saved successfully!");
    },
    onError: (err: Error) => {
      alert("Failed to save: " + (err.message || "Unknown error"));
    }
  });

  const renderMutation = useMutation({
    mutationFn: async () => {
      if (!data) return;
      
      // Save first
      const saveRes = await apiClient.updateReelVersion(id, data.version.id, {
        hook,
        script,
        voiceover_text: voiceoverText,
        caption,
        hashtags,
        storyboard,
        subtitle_lines: subtitles,
        render_settings: {
          duration_seconds: duration,
        }
      });
      
      return apiClient.renderReelProject(id, saveRes.version.id);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["reel-editor", id] });
      queryClient.invalidateQueries({ queryKey: ["reel-project", id] });
      setIsDirty(false);
      router.push(`/dashboard/reels/${id}`);
    },
    onError: (err: Error) => {
      alert("Failed to render: " + (err.message || "Unknown error"));
    }
  });

  const markDirty = () => setIsDirty(true);

  if (isLoading) {
    return <div className="p-8 text-center text-gray-500 animate-pulse">Loading Editor...</div>;
  }

  if (isError || !data) {
    return (
      <div className="p-8 text-center">
        <h2 className="text-xl text-white mb-2">Editor not available</h2>
        <Link href={`/dashboard/reels/${id}`} className="text-violet-400">Back to project</Link>
      </div>
    );
  }

  if (!data.can_edit && data.version.status !== "published") {
      // Actually the backend blocks editing published ones, but allows cloning
      // I'll add a simple clone CTA if they really want to edit a published one.
      // But we handled cloning implicitly in backend during save if it has a rendered_asset_id!
      // The backend says: "Cannot edit a published or publishing version. Please clone it first."
      // Let's implement clone mutation here if needed, but our backend might just handle it if it's not published
  }

  const handleSceneChange = (index: number, field: keyof StoryboardSceneInput, value: string | number) => {
    const newStoryboard = [...storyboard];
    newStoryboard[index] = { ...newStoryboard[index], [field]: value };
    setStoryboard(newStoryboard);
    markDirty();
  };

  const handleSubtitleChange = (index: number, field: keyof SubtitleLineInput, value: string | number) => {
    const newSubtitles = [...subtitles];
    newSubtitles[index] = { ...newSubtitles[index], [field]: value };
    setSubtitles(newSubtitles);
    markDirty();
  };

  return (
    <div className="p-8 max-w-6xl mx-auto pb-32">
      <div className="flex items-start justify-between mb-6 sticky top-0 bg-gray-950/90 py-4 z-10 backdrop-blur-sm border-b border-gray-800">
        <div>
          <Link href={`/dashboard/reels/${id}`} className="text-sm text-gray-500 hover:text-gray-300 mb-2 block">
            &larr; Back to Detail
          </Link>
          <h1 className="text-2xl font-bold text-white">Editor: {data.project.title ?? "Untitled"}</h1>
          <p className="text-xs text-gray-400 mt-1">Version {data.version.version_number}</p>
        </div>
        <div className="flex gap-3">
          {data.version.status === "published" || data.version.status === "publishing" ? (
             <button
               onClick={() => {
                 apiClient.cloneReelVersion(id, data.version.id).then(() => {
                   queryClient.invalidateQueries({ queryKey: ["reel-editor", id] });
                 });
               }}
               className="btn-secondary"
             >
               Clone to Edit
             </button>
          ) : (
            <>
              <button 
                onClick={() => saveMutation.mutate()} 
                disabled={!isDirty || saveMutation.isPending}
                className="btn-secondary disabled:opacity-50"
              >
                {saveMutation.isPending ? "Saving..." : "Save Draft"}
              </button>
              <button 
                onClick={() => renderMutation.mutate()} 
                disabled={renderMutation.isPending}
                className="btn-primary disabled:opacity-50"
              >
                {renderMutation.isPending ? "Saving & Rendering..." : "Save & Render"}
              </button>
            </>
          )}
        </div>
      </div>

      {(data.version.status === "published" || data.version.status === "publishing") && (
        <div className="mb-6 p-4 rounded-xl bg-yellow-950/50 border border-yellow-800/50 text-yellow-300 text-sm">
          This version is published and cannot be edited. Clone it to make changes.
        </div>
      )}

      {data.has_unrendered_edits && (
        <div className="mb-6 p-4 rounded-xl bg-blue-950/50 border border-blue-800/50 text-blue-300 text-sm">
          You have unsaved or unrendered edits. Render again before publishing.
        </div>
      )}

      <div className="grid lg:grid-cols-12 gap-8">
        
        {/* Left Column: Script & Settings */}
        <div className="lg:col-span-4 space-y-6">
          <SectionCard title="Render Settings">
            <div className="space-y-4">
              <div>
                <label className="block text-xs text-gray-400 mb-1">Target Duration (seconds)</label>
                <input 
                  type="number" 
                  value={duration} 
                  onChange={(e) => { setDuration(Number(e.target.value)); markDirty(); }}
                  className="w-full bg-gray-900 border border-gray-700 rounded-md p-2 text-white text-sm"
                  min={5} max={60}
                />
              </div>
            </div>
          </SectionCard>

          <SectionCard title="Script & Voiceover">
            <div className="space-y-4">
              <div>
                <label className="block text-xs text-gray-400 mb-1">Hook</label>
                <textarea 
                  value={hook} 
                  onChange={(e) => { setHook(e.target.value); markDirty(); }}
                  className="w-full bg-gray-900 border border-gray-700 rounded-md p-2 text-white text-sm min-h-[60px]"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">Script</label>
                <textarea 
                  value={script} 
                  onChange={(e) => { setScript(e.target.value); markDirty(); }}
                  className="w-full bg-gray-900 border border-gray-700 rounded-md p-2 text-white text-sm min-h-[150px]"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">Voiceover Text</label>
                <textarea 
                  value={voiceoverText} 
                  onChange={(e) => { setVoiceoverText(e.target.value); markDirty(); }}
                  className="w-full bg-gray-900 border border-gray-700 rounded-md p-2 text-white text-sm min-h-[100px]"
                />
              </div>
            </div>
          </SectionCard>
          
          <SectionCard title="Post Details">
            <div className="space-y-4">
              <div>
                <label className="block text-xs text-gray-400 mb-1">Caption</label>
                <textarea 
                  value={caption} 
                  onChange={(e) => { setCaption(e.target.value); markDirty(); }}
                  className="w-full bg-gray-900 border border-gray-700 rounded-md p-2 text-white text-sm min-h-[100px]"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">Hashtags (comma separated)</label>
                <input 
                  type="text" 
                  value={hashtags.join(", ")} 
                  onChange={(e) => { 
                    setHashtags(e.target.value.split(",").map(s => s.trim()).filter(Boolean)); 
                    markDirty(); 
                  }}
                  className="w-full bg-gray-900 border border-gray-700 rounded-md p-2 text-white text-sm"
                />
              </div>
            </div>
          </SectionCard>
        </div>

        {/* Right Column: Storyboard & Subtitles */}
        <div className="lg:col-span-8 space-y-6">
          
          <SectionCard title="Storyboard">
            <div className="space-y-4">
              {storyboard.map((scene, index) => (
                <div key={index} className="p-4 bg-gray-900 rounded-lg border border-gray-700 space-y-3">
                  <div className="flex justify-between items-center">
                    <span className="text-violet-400 font-bold text-sm">Scene {scene.scene_number || index + 1}</span>
                    <div className="flex gap-2">
                       <input 
                         type="number" 
                         value={scene.start_time} 
                         onChange={(e) => handleSceneChange(index, 'start_time', Number(e.target.value))}
                         className="bg-gray-800 border border-gray-700 rounded p-1 w-16 text-xs text-white"
                         step="0.1"
                       />
                       <span className="text-gray-500 text-xs py-1">to</span>
                       <input 
                         type="number" 
                         value={scene.end_time} 
                         onChange={(e) => handleSceneChange(index, 'end_time', Number(e.target.value))}
                         className="bg-gray-800 border border-gray-700 rounded p-1 w-16 text-xs text-white"
                         step="0.1"
                       />
                    </div>
                  </div>
                  
                  <div>
                    <label className="block text-xs text-gray-500 mb-1">Visual Description</label>
                    <textarea 
                      value={scene.visual_description} 
                      onChange={(e) => handleSceneChange(index, 'visual_description', e.target.value)}
                      className="w-full bg-gray-800 border border-gray-700 rounded p-2 text-white text-sm"
                      rows={2}
                    />
                  </div>
                  
                  <div>
                    <label className="block text-xs text-gray-500 mb-1">On-Screen Text</label>
                    <input 
                      type="text" 
                      value={scene.text_overlay || ""} 
                      onChange={(e) => handleSceneChange(index, 'text_overlay', e.target.value)}
                      className="w-full bg-gray-800 border border-gray-700 rounded p-2 text-white text-sm"
                    />
                  </div>
                </div>
              ))}
            </div>
          </SectionCard>

          <SectionCard title="Subtitles">
            <div className="space-y-2">
              <div className="grid grid-cols-12 gap-2 text-xs text-gray-500 mb-2 px-2">
                <div className="col-span-2">Start (s)</div>
                <div className="col-span-2">End (s)</div>
                <div className="col-span-8">Text</div>
              </div>
              
              {subtitles.map((line, index) => (
                <div key={index} className="grid grid-cols-12 gap-2 items-start">
                  <div className="col-span-2">
                    <input 
                      type="number" 
                      value={line.start_seconds} 
                      onChange={(e) => handleSubtitleChange(index, 'start_seconds', Number(e.target.value))}
                      className="w-full bg-gray-900 border border-gray-700 rounded p-2 text-white text-xs"
                      step="0.1"
                    />
                  </div>
                  <div className="col-span-2">
                    <input 
                      type="number" 
                      value={line.end_seconds} 
                      onChange={(e) => handleSubtitleChange(index, 'end_seconds', Number(e.target.value))}
                      className="w-full bg-gray-900 border border-gray-700 rounded p-2 text-white text-xs"
                      step="0.1"
                    />
                  </div>
                  <div className="col-span-8">
                    <input 
                      type="text" 
                      value={line.text} 
                      onChange={(e) => handleSubtitleChange(index, 'text', e.target.value)}
                      className="w-full bg-gray-900 border border-gray-700 rounded p-2 text-white text-sm"
                    />
                  </div>
                </div>
              ))}
            </div>
          </SectionCard>

        </div>
      </div>
    </div>
  );
}
