"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { apiClient } from "@/lib/api-client";
import type { ApiError } from "@/lib/api-client";

// ── Schema ────────────────────────────────────────────────────────────────────

const createReelSchema = z.object({
  prompt: z.string().min(10, "Prompt must be at least 10 characters").max(2000),
  language: z.enum(["en", "hi", "hinglish"]),
  tone: z.enum(["professional", "funny", "luxury", "educational", "dramatic"]),
  duration_seconds: z.number().int().min(10).max(60),
  cta_text: z.string().max(500).optional(),
});

type CreateReelFormData = z.infer<typeof createReelSchema>;

const LANGUAGE_OPTIONS = [
  { value: "en" as const, label: "English" },
  { value: "hi" as const, label: "Hindi" },
  { value: "hinglish" as const, label: "Hinglish" },
];

const TONE_OPTIONS = [
  { value: "professional" as const, label: "Professional" },
  { value: "funny" as const, label: "Funny" },
  { value: "luxury" as const, label: "Luxury" },
  { value: "educational" as const, label: "Educational" },
  { value: "dramatic" as const, label: "Dramatic" },
];

const DURATION_OPTIONS = [10, 15, 20, 30] as const;

// ── Page ──────────────────────────────────────────────────────────────────────

export default function CreateReelPage() {
  const router = useRouter();

  // ALL hooks declared unconditionally first
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    formState: { errors },
  } = useForm<CreateReelFormData>({
    resolver: zodResolver(createReelSchema),
    defaultValues: { language: "en", tone: "professional", duration_seconds: 15 },
  });

  const watchedLanguage = watch("language");
  const watchedTone = watch("tone");
  const watchedDuration = watch("duration_seconds");

  // Auth guard via useEffect (safe — hooks called unconditionally above)
  useEffect(() => {
    if (!localStorage.getItem("access_token")) {
      router.replace("/login");
    }
  }, [router]);

  const handleImageSelect = useCallback(
    (file: File) => {
      const allowed = ["image/jpeg", "image/png", "image/webp"];
      if (!allowed.includes(file.type)) {
        setApiError("Only JPEG, PNG, and WebP images are supported.");
        return;
      }
      if (file.size > 20 * 1024 * 1024) {
        setApiError("Image must be under 20 MB.");
        return;
      }
      setApiError(null);
      setImageFile(file);
      const reader = new FileReader();
      reader.onload = (e) => setImagePreview(e.target?.result as string);
      reader.readAsDataURL(file);
    },
    []
  );

  const onSubmit = async (formData: CreateReelFormData) => {
    setSubmitting(true);
    setApiError(null);
    try {
      let sourceImageId: string | undefined;
      if (imageFile) {
        setUploading(true);
        const asset = await apiClient.uploadMediaAsset(imageFile);
        sourceImageId = asset.id;
        setUploading(false);
      }
      const response = await apiClient.createReelProject({
        prompt: formData.prompt,
        language: formData.language,
        tone: formData.tone,
        duration_seconds: formData.duration_seconds,
        cta_text: formData.cta_text || undefined,
        source_image_id: sourceImageId,
      });
      router.push("/dashboard/reels/" + response.project.id);
    } catch (err) {
      const apiErr = err as ApiError;
      setApiError(apiErr?.message ?? "An unexpected error occurred.");
      setUploading(false);
      setSubmitting(false);
    }
  };

  const isLoading = uploading || submitting;

  return (
    <div className="p-8 max-w-2xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-white">Create a Reel</h1>
        <p className="text-gray-400 mt-1">
          Describe your idea. AI will generate script, storyboard and caption.
        </p>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
        {/* Image Upload */}
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">
            Reference Image <span className="text-gray-500">(optional)</span>
          </label>
          <div
            id="image-upload-zone"
            className={
              "relative border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-colors " +
              (dragOver
                ? "border-violet-500 bg-violet-950/30"
                : "border-gray-700 hover:border-gray-600 bg-gray-900/50")
            }
            onClick={() => fileInputRef.current?.click()}
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragOver(false);
              const f = e.dataTransfer.files[0];
              if (f) handleImageSelect(f);
            }}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) handleImageSelect(f);
              }}
              aria-label="Upload reference image"
            />
            {imagePreview ? (
              <div className="flex flex-col items-center gap-3">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={imagePreview}
                  alt="Preview"
                  className="max-h-40 rounded-lg object-contain"
                />
                <p className="text-sm text-gray-400">{imageFile?.name}</p>
                <button
                  type="button"
                  className="text-xs text-red-400 hover:text-red-300"
                  onClick={(e) => {
                    e.stopPropagation();
                    setImageFile(null);
                    setImagePreview(null);
                  }}
                >
                  Remove
                </button>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-2 py-4">
                <span className="text-4xl">🖼️</span>
                <p className="text-gray-300 font-medium">Drop image here or click to browse</p>
                <p className="text-xs text-gray-500">JPEG, PNG, WebP — Max 20 MB</p>
              </div>
            )}
          </div>
        </div>

        {/* Prompt */}
        <div>
          <label htmlFor="prompt" className="block text-sm font-medium text-gray-300 mb-2">
            Reel Idea Prompt <span className="text-violet-400">*</span>
          </label>
          <textarea
            id="prompt"
            {...register("prompt")}
            rows={4}
            placeholder="E.g. Morning coffee routine at our cozy cafe — warm, aesthetic, premium feel"
            className="input w-full resize-none"
            disabled={isLoading}
          />
          {errors.prompt && (
            <p className="mt-1 text-sm text-red-400">{errors.prompt.message}</p>
          )}
        </div>

        {/* Language + Duration */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">Language</label>
            <div className="flex flex-wrap gap-2">
              {LANGUAGE_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  id={"lang-" + opt.value}
                  onClick={() => setValue("language", opt.value)}
                  className={
                    "px-3 py-1.5 rounded-lg text-sm font-medium transition-colors " +
                    (watchedLanguage === opt.value
                      ? "bg-violet-600 text-white"
                      : "bg-gray-800 text-gray-400 hover:bg-gray-700 hover:text-white")
                  }
                  disabled={isLoading}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">Duration</label>
            <div className="flex flex-wrap gap-2">
              {DURATION_OPTIONS.map((val) => (
                <button
                  key={val}
                  type="button"
                  id={"dur-" + val}
                  onClick={() => setValue("duration_seconds", val)}
                  className={
                    "px-3 py-1.5 rounded-lg text-sm font-medium transition-colors " +
                    (watchedDuration === val
                      ? "bg-violet-600 text-white"
                      : "bg-gray-800 text-gray-400 hover:bg-gray-700 hover:text-white")
                  }
                  disabled={isLoading}
                >
                  {val}s
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Tone */}
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">Tone</label>
          <div className="flex flex-wrap gap-2">
            {TONE_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                id={"tone-" + opt.value}
                onClick={() => setValue("tone", opt.value)}
                className={
                  "px-4 py-2 rounded-lg text-sm font-medium transition-colors " +
                  (watchedTone === opt.value
                    ? "bg-violet-600 text-white"
                    : "bg-gray-800 text-gray-400 hover:bg-gray-700 hover:text-white")
                }
                disabled={isLoading}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        {/* CTA */}
        <div>
          <label htmlFor="cta_text" className="block text-sm font-medium text-gray-300 mb-2">
            Call to Action <span className="text-gray-500">(optional)</span>
          </label>
          <input
            id="cta_text"
            type="text"
            {...register("cta_text")}
            placeholder="E.g. Visit our menu at link in bio"
            className="input w-full"
            disabled={isLoading}
          />
        </div>

        {/* API Error */}
        {apiError && (
          <div
            id="api-error-banner"
            className="p-4 rounded-xl bg-red-950/50 border border-red-800/50 text-red-300 text-sm"
          >
            {apiError}
          </div>
        )}

        {/* Submit */}
        <button
          id="submit-create-reel"
          type="submit"
          disabled={isLoading}
          className="btn-primary w-full justify-center text-base py-3 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {uploading
            ? "Uploading image..."
            : submitting
            ? "Creating your reel..."
            : "Generate Reel"}
        </button>

        <p className="text-center text-xs text-gray-600">
          Generation takes a few seconds. You will be redirected automatically.
        </p>
      </form>
    </div>
  );
}
