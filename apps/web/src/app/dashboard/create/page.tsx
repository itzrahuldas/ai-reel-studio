"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";

const LANGUAGES = [
  { value: "en", label: "English" }, { value: "hi", label: "Hindi" },
  { value: "es", label: "Spanish" }, { value: "fr", label: "French" },
  { value: "de", label: "German" }, { value: "pt", label: "Portuguese" },
];
const TONES = ["professional", "casual", "energetic", "inspirational", "humorous", "dramatic"];

export default function CreateReelPage() {
  const router = useRouter();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [form, setForm] = useState({
    prompt: "", language: "en", tone: "energetic",
    duration_seconds: 30, cta_text: "",
  });
  const [imageFile, setImageFile] = useState<File | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!imageFile) return alert("Please upload an image.");
    setIsSubmitting(true);
    try {
      // TODO: call apiClient.createReelProject + upload image + start generation
      console.log("Creating reel:", form, imageFile.name);
      router.push("/dashboard");
    } catch (err) {
      console.error(err);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="p-8 max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold text-white mb-2">Create a Reel</h1>
      <p className="text-gray-400 mb-8">Describe your idea and upload an image. AI handles the rest.</p>
      <form onSubmit={handleSubmit} className="space-y-6">
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">Business Idea / Prompt *</label>
          <textarea id="prompt" rows={4} className="input resize-none" placeholder="e.g. Launch post for my artisan sourdough bakery. Highlight the freshness and handcrafted quality..."
            value={form.prompt} onChange={e => setForm(f => ({...f, prompt: e.target.value}))} required minLength={10} maxLength={2000} />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">Source Image *</label>
          <div className="border-2 border-dashed border-gray-700 rounded-lg p-8 text-center hover:border-violet-600 transition-colors cursor-pointer"
            onClick={() => document.getElementById("image-upload")?.click()}>
            {imageFile ? (
              <p className="text-green-400">? {imageFile.name}</p>
            ) : (
              <div>
                <p className="text-gray-400 mb-2">Click to upload or drag and drop</p>
                <p className="text-gray-600 text-sm">JPEG, PNG, WEBP — max 20MB</p>
              </div>
            )}
          </div>
          <input id="image-upload" type="file" accept="image/jpeg,image/png,image/webp" className="hidden"
            onChange={e => setImageFile(e.target.files?.[0] ?? null)} />
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">Language</label>
            <select id="language" className="input" value={form.language} onChange={e => setForm(f => ({...f, language: e.target.value}))}>
              {LANGUAGES.map(l => <option key={l.value} value={l.value}>{l.label}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">Tone</label>
            <select id="tone" className="input" value={form.tone} onChange={e => setForm(f => ({...f, tone: e.target.value}))}>
              {TONES.map(t => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">Duration</label>
            <select id="duration" className="input" value={form.duration_seconds} onChange={e => setForm(f => ({...f, duration_seconds: Number(e.target.value)}))}>
              {[15, 30, 60, 90].map(d => <option key={d} value={d}>{d}s</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">CTA Text</label>
            <input id="cta" type="text" className="input" placeholder="Shop now at..." value={form.cta_text}
              onChange={e => setForm(f => ({...f, cta_text: e.target.value}))} maxLength={500} />
          </div>
        </div>
        <button id="create-submit" type="submit" disabled={isSubmitting} className="btn-primary w-full justify-center py-3 text-base">
          {isSubmitting ? "Creating..." : "Generate Reel ?"}
        </button>
      </form>
    </div>
  );
}
