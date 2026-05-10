/**
 * Typed API client for AI Reel Studio backend.
 * All requests include Authorization header via interceptor.
 * All responses are fully typed.
 *
 * Image Upload Flow:
 *   1. uploadMediaAsset(file) → { id: assetId }
 *   2. createReelProject({ ...data, source_image_id: assetId })
 *   3. Redirect to /dashboard/reels/{project.id}
 */

import axios, { AxiosError, AxiosInstance } from "axios";

// ── Shared Types ──────────────────────────────────────────────────────────────

export interface ApiError {
  code: string;
  message: string;
  request_id: string;
  details?: Record<string, unknown>;
}

export type ReelProjectStatus =
  | "draft"
  | "script_generating"
  | "script_ready"
  | "video_generating"
  | "audio_generating"
  | "rendering"
  | "rendered"
  | "ready_for_review"
  | "ready_to_publish"
  | "approved"
  | "publishing"
  | "ig_processing"
  | "published"
  | "failed"
  | "failed_script"
  | "failed_video"
  | "failed_audio"
  | "failed_render"
  | "failed_instagram_upload"
  | "failed_instagram_publish";

export interface Scene {
  scene_number: number;
  duration_seconds: number;
  visual_description: string;
  text_overlay: string | null;
  transition: string;
}

export interface SubtitleLine {
  start_seconds: number;
  end_seconds: number;
  text: string;
}

export interface ReelVersion {
  id: string;
  project_id: string;
  version_number: number;
  hook: string | null;
  script: string | null;
  scenes: Scene[] | null;
  voiceover_text: string | null;
  subtitle_lines: SubtitleLine[] | null;
  caption: string | null;
  hashtags: string[] | null;
  video_prompt: string | null;
  estimated_duration: number | null;
  moderation_flags: Record<string, unknown> | null;
  render_settings: Record<string, unknown> | null;
  edit_metadata: Record<string, unknown> | null;
  audio_asset_id: string | null;
  voiceover_asset_id: string | null;
  video_asset_id: string | null;
  rendered_asset_id: string | null;
  thumbnail_asset_id: string | null;
  rendered_video_url?: string | null;
  thumbnail_url?: string | null;
  audio_url?: string | null;
  voiceover_url?: string | null;
  voiceover_provider?: string | null;
  rendered_video_mime_type?: string | null;
  audio_mime_type?: string | null;
  status: ReelProjectStatus;
  approved_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ReelProject {
  id: string;
  workspace_id: string;
  title: string | null;
  prompt: string;
  language: string;
  tone: string | null;
  duration_seconds: number;
  cta_text: string | null;
  status: ReelProjectStatus;
  latest_version_id: string | null;
  source_image_id: string | null;
  latest_version?: ReelVersion | null;
  created_at: string;
  updated_at: string;
}

export interface MediaAsset {
  id: string;
  workspace_id: string;
  asset_type: string;
  s3_key: string;
  filename: string | null;
  mime_type: string | null;
  file_size: number | null;
  status: string;
  url: string | null;
  public_url?: string | null;
  media_url?: string | null;
  provider?: string | null;
  renderer?: string | null;
  /** Render metadata: visual_source, mock_visual_theme, generated_scene_count, etc. */
  metadata?: Record<string, unknown>;
  created_at: string;
}

export interface RenderJob {
  id: string;
  project_id: string;
  version_id: string;
  celery_task_id: string | null;
  status: "queued" | "running" | "complete" | "failed";
  renderer: string;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
  command_log: string | null;
  input_payload: Record<string, unknown> | null;
  output_payload: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface GenerationJob {
  id: string;
  project_id: string;
  version_id: string | null;
  job_type: string;
  status: "queued" | "running" | "complete" | "failed";
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
  provider: string | null;
  provider_metadata_json: Record<string, unknown> | null;
  error_code: string | null;
  retry_count: number;
  created_at: string;
  updated_at: string;
}

export interface CreateReelProjectRequest {
  workspace_id?: string;
  prompt: string;
  language?: string;
  tone?: string;
  duration_seconds?: number;
  cta_text?: string;
  title?: string;
  source_image_id?: string;
}

export interface CreateReelProjectResponse {
  project: ReelProject;
  version: ReelVersion;
  generation_job: GenerationJob;
}

export interface AIProviderStatus {
  ai_provider: "mock" | "openai" | string;
  image_analysis_provider: "mock" | "openai" | string;
  tts_provider: "mock" | "openai" | string;
  ai_model: string | null;
  image_analysis_model: string | null;
  tts_model: string | null;
  tts_voice: string | null;
  configured: boolean;
  supported: boolean;
  setup_warning: string | null;
  mock_mode: boolean;
}

export interface SocialAccount {
  id: string;
  workspace_id: string;
  connected_by_user_id: string;
  platform: string;
  username: string | null;
  account_type: string | null;
  ig_user_id: string;
  page_id: string | null;
  page_name: string | null;
  status: "connected" | "reconnect_required" | "error";
  token_expires_at: string | null;
  scopes_json: string[] | null;
  metadata_json: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
  disconnected_at: string | null;
}

export interface PublishJob {
  id: string;
  project_id: string;
  version_id: string;
  social_account_id: string;
  status: "queued" | "container_created" | "polling" | "published" | "failed" | "cancelled" | "scheduled" | "reconnect_required";
  ig_container_id: string | null;
  ig_media_id: string | null;
  scheduled_for: string | null;
  started_at: string | null;
  published_at: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreatePublishJobResponse {
  publish_job: PublishJob;
  project: ReelProject;
  version: ReelVersion;
}

export interface SchedulePublishJobRequest {
  social_account_id: string;
  caption?: string;
  share_to_feed?: boolean;
  allow_comments?: boolean;
  scheduled_at: string;
  schedule_timezone?: string;
}

export interface StoryboardSceneInput {
  scene_number?: number;
  start_time: number;
  end_time: number;
  visual_description: string;
  text_overlay?: string;
  voiceover_text?: string;
}

export interface SubtitleLineInput {
  start_seconds: number;
  end_seconds: number;
  text: string;
}

export interface RenderSettingsInput {
  duration_seconds?: number;
  resolution?: string;
  fps?: number;
  subtitle_style?: string;
  text_position?: string;
  cta_position?: string;
  include_caption_burn_in?: boolean;
}

export interface UpdateReelVersionRequest {
  hook?: string;
  script?: string;
  storyboard?: StoryboardSceneInput[];
  voiceover_text?: string;
  subtitle_lines?: SubtitleLineInput[];
  caption?: string;
  hashtags?: string[];
  video_prompt?: string;
  render_settings?: RenderSettingsInput;
}

export interface ReelVersionEditorResponse {
  project: ReelProject;
  version: ReelVersion;
  can_edit: boolean;
  can_render: boolean;
  can_publish: boolean;
  has_unrendered_edits: boolean;
}

export interface SaveEditorDraftResponse {
  project: ReelProject;
  version: ReelVersion;
  message: string;
}

export interface User {
  id: string;
  email: string;
  full_name: string | null;
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
}

export interface Workspace {
  id: string;
  name: string;
  slug: string;
  plan: string;
  is_active: boolean;
  created_at: string;
}

// ── Billing & Usage Types ──────────────────────────────────────────────────────

export type PlanKey = "FREE" | "CREATOR" | "PRO";
export type UsageEventType = "AI_GENERATION" | "RENDER" | "PUBLISH" | "SCHEDULED_PUBLISH";

export interface PlanDefinition {
  key: PlanKey;
  plan_key: PlanKey | null;
  name: string;
  ai_generations_per_month: number;
  renders_per_month: number;
  publishes_per_month: number;
  scheduled_publishes_limit: number;
  watermark_enabled: boolean;
  stripe_price_configured: boolean;
  checkout_available: boolean;
}

export interface UsageSummary {
  plan: PlanDefinition;
  current_plan: PlanKey | null;
  subscription_plan_key: PlanKey | null;
  subscription_status: string;
  provider: string;
  current_period_start: string | null;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
  billing_portal_available: boolean;
  upgrade_available: boolean;
  stripe_mode: "mock" | "live" | string;
  period_start: string;
  period_end: string;
  ai_generations_used: number;
  ai_generations_limit: number;
  renders_used: number;
  renders_limit: number;
  publishes_used: number;
  publishes_limit: number;
  active_scheduled_publishes: number;
  scheduled_publishes_limit: number;
}

export interface CheckoutSessionResponse {
  checkout_url: string;
  session_id: string;
  mode: "mock" | "live" | string;
}

export interface PortalSessionResponse {
  portal_url: string;
  mode: "mock" | "live" | string;
  message: string | null;
}

/** Error shape returned for HTTP 402 usage limit exceeded */
export interface UsageLimitError {
  code: "USAGE_LIMIT_EXCEEDED";
  message: string;
  plan_key: PlanKey;
  limit: number;
  used: number;
  upgrade_required: boolean;
  _isUsageLimitError?: true;
}

/** Type guard — check if a caught error is a usage-limit 402 error */
export function isUsageLimitError(err: unknown): err is UsageLimitError {
  return (
    typeof err === "object" &&
    err !== null &&
    (
      (("_isUsageLimitError" in err) &&
        (err as UsageLimitError)._isUsageLimitError === true) ||
      (("code" in err) && (err as UsageLimitError).code === "USAGE_LIMIT_EXCEEDED")
    )
  );
}

// ── Client ────────────────────────────────────────────────────────────────────


class ApiClient {
  private client: AxiosInstance;

  constructor(baseURL: string) {
    this.client = axios.create({
      baseURL,
      headers: { "Content-Type": "application/json" },
      timeout: 30000,
    });

    // Inject Bearer token from localStorage on every request
    this.client.interceptors.request.use((config) => {
      const token =
        typeof window !== "undefined" ? localStorage.getItem("access_token") : null;
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
      return config;
    });

    // Normalize error responses
    this.client.interceptors.response.use(
      (res) => res,
      (error: AxiosError<{ error?: ApiError; detail?: string | unknown; code?: string }>) => {
        const status = error.response?.status;
        const payload = error.response?.data;
        const detail = payload?.detail;
        const usageLimitPayload =
          detail && typeof detail === "object"
            ? detail
            : payload && typeof payload === "object" && payload.code === "USAGE_LIMIT_EXCEEDED"
            ? payload
            : null;

        // 402: Usage limit exceeded — preserve the full detail object
        if (
          status === 402 &&
          usageLimitPayload &&
          "code" in usageLimitPayload &&
          (usageLimitPayload as UsageLimitError).code === "USAGE_LIMIT_EXCEEDED"
        ) {
          return Promise.reject({ ...usageLimitPayload, _isUsageLimitError: true });
        }

        const apiError: ApiError = payload?.error ?? {
          code:
            detail && typeof detail === "object" && "code" in detail
              ? String((detail as { code?: unknown }).code)
              : "NETWORK_ERROR",
          message:
            typeof detail === "string"
              ? detail
              : detail && typeof detail === "object" && "message" in detail
              ? String((detail as { message?: unknown }).message)
              : error.message,
          request_id: "unknown",
        };
        return Promise.reject(apiError);
      }
    );
  }

  // ── Auth ───────────────────────────────────────────────────────────────────

  async login(email: string, password: string) {
    const res = await this.client.post<{ access_token: string; expires_in: number }>(
      "/api/v1/auth/login",
      { email, password }
    );
    return res.data;
  }

  async register(email: string, password: string, fullName?: string) {
    const res = await this.client.post<{
      user: User;
      workspace: Workspace;
      access_token: string;
    }>("/api/v1/auth/register", { email, password, full_name: fullName });
    return res.data;
  }

  async me(): Promise<User> {
    const res = await this.client.get<User>("/api/v1/auth/me");
    return res.data;
  }

  async logout(): Promise<void> {
    await this.client.post("/api/v1/auth/logout");
    if (typeof window !== "undefined") {
      localStorage.removeItem("access_token");
    }
  }

  // ── Media Assets ──────────────────────────────────────────────────────────

  /**
   * Upload a source image file for reel generation.
   * Returns a MediaAsset with id — use as source_image_id when creating a reel.
   */
  async uploadMediaAsset(file: File): Promise<MediaAsset> {
    const formData = new FormData();
    formData.append("file", file);
    const res = await this.client.post<MediaAsset>("/api/v1/media-assets/upload", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return res.data;
  }

  async getMediaAsset(id: string): Promise<MediaAsset> {
    const res = await this.client.get<MediaAsset>(`/api/v1/media-assets/${id}`);
    return res.data;
  }

  // ── Reel Projects ─────────────────────────────────────────────────────────

  /**
   * Create a new reel project. Returns project + version + generation_job.
   * Call uploadMediaAsset() first to get source_image_id.
   */
  async createReelProject(
    data: CreateReelProjectRequest
  ): Promise<CreateReelProjectResponse> {
    const res = await this.client.post<CreateReelProjectResponse>(
      "/api/v1/reel-projects/",
      data
    );
    return res.data;
  }

  /**
   * List all reel projects for the authenticated user's workspaces.
   */
  async listReelProjects(): Promise<ReelProject[]> {
    const res = await this.client.get<ReelProject[]>("/api/v1/reel-projects/");
    return res.data;
  }

  /**
   * Get full reel project detail including latest_version content.
   * Poll this while status === "script_generating".
   */
  async getReelProject(id: string): Promise<ReelProject> {
    const res = await this.client.get<ReelProject>(`/api/v1/reel-projects/${id}`);
    return res.data;
  }

  /**
   * Trigger regeneration — creates a new version + job.
   */
  async regenerateReelProject(
    projectId: string
  ): Promise<{ version: ReelVersion; generation_job: GenerationJob }> {
    const res = await this.client.post<{
      version: ReelVersion;
      generation_job: GenerationJob;
    }>(`/api/v1/reel-projects/${projectId}/regenerate`);
    return res.data;
  }

  /**
   * Get all generation/render/publish jobs for a project (timeline).
   */
  async getReelProjectJobs(projectId: string): Promise<GenerationJob[]> {
    const res = await this.client.get<GenerationJob[]>(
      `/api/v1/reel-projects/${projectId}/jobs`
    );
    return res.data;
  }

  async getAIProviderStatus(): Promise<AIProviderStatus> {
    const res = await this.client.get<AIProviderStatus>(
      "/api/v1/reel-projects/ai/provider-status"
    );
    return res.data;
  }

  /**
   * Trigger rendering for the specified or latest version.
   */
  async renderReelProject(
    projectId: string,
    versionId?: string
  ): Promise<{ render_job: RenderJob; project: ReelProject; version: ReelVersion }> {
    let url = `/api/v1/reel-projects/${projectId}/render`;
    if (versionId) {
      url += `?version_id=${versionId}`;
    }
    const res = await this.client.post<{
      render_job: RenderJob;
      project: ReelProject;
      version: ReelVersion;
    }>(url);
    return res.data;
  }

  /**
   * Get all render jobs for a project.
   */
  async getRenderJobs(projectId: string): Promise<RenderJob[]> {
    const res = await this.client.get<RenderJob[]>(
      `/api/v1/reel-projects/${projectId}/render-jobs`
    );
    return res.data;
  }

  // ── Editor ─────────────────────────────────────────────────────────────────

  async getReelEditorData(projectId: string): Promise<ReelVersionEditorResponse> {
    const res = await this.client.get<ReelVersionEditorResponse>(
      `/api/v1/reel-projects/${projectId}/editor`
    );
    return res.data;
  }

  async updateReelVersion(
    projectId: string,
    versionId: string,
    data: UpdateReelVersionRequest
  ): Promise<SaveEditorDraftResponse> {
    const res = await this.client.put<SaveEditorDraftResponse>(
      `/api/v1/reel-projects/${projectId}/versions/${versionId}`,
      data
    );
    return res.data;
  }

  async cloneReelVersion(projectId: string, versionId: string): Promise<ReelVersion> {
    const res = await this.client.post<ReelVersion>(
      `/api/v1/reel-projects/${projectId}/versions/${versionId}/clone`
    );
    return res.data;
  }

  // ── Reel Versions ─────────────────────────────────────────────────────────

  async updateCaption(versionId: string, caption: string): Promise<void> {
    await this.client.patch(`/api/v1/reel-versions/${versionId}/caption`, { caption });
  }

  async updateHashtags(versionId: string, hashtags: string[]): Promise<void> {
    await this.client.patch(`/api/v1/reel-versions/${versionId}/hashtags`, { hashtags });
  }

  async approveVersion(versionId: string): Promise<void> {
    await this.client.post(`/api/v1/reel-versions/${versionId}/approve`);
  }

  async rejectVersion(versionId: string, reason?: string): Promise<void> {
    await this.client.post(`/api/v1/reel-versions/${versionId}/reject`, { reason });
  }

  // ── Instagram Integrations ────────────────────────────────────────────────

  async getInstagramStatus(): Promise<{ connected: boolean; accounts: SocialAccount[] }> {
    const res = await this.client.get<{ connected: boolean; accounts: SocialAccount[] }>(
      "/api/v1/integrations/instagram/status"
    );
    return res.data;
  }

  async startInstagramConnect(): Promise<{ authorization_url: string }> {
    const res = await this.client.post<{ authorization_url: string }>(
      "/api/v1/integrations/instagram/connect"
    );
    return res.data;
  }

  async mockInstagramConnect(): Promise<{ status: string }> {
    const res = await this.client.post<{ status: string }>(
      "/api/v1/integrations/instagram/mock-connect"
    );
    return res.data;
  }

  async listInstagramAccounts(): Promise<SocialAccount[]> {
    const res = await this.client.get<SocialAccount[]>(
      "/api/v1/integrations/instagram/accounts"
    );
    return res.data;
  }

  async disconnectInstagramAccount(id: string): Promise<void> {
    await this.client.delete(`/api/v1/integrations/instagram/accounts/${id}`);
  }

  async reconnectInstagramAccount(): Promise<{ authorization_url: string }> {
    const res = await this.client.post<{ authorization_url: string }>(
      "/api/v1/integrations/instagram/reconnect"
    );
    return res.data;
  }

  // ── Publish Jobs ──────────────────────────────────────────────────────────

  async publishReelProject(
    projectId: string,
    data: { social_account_id: string; caption?: string }
  ): Promise<CreatePublishJobResponse> {
    const res = await this.client.post<CreatePublishJobResponse>(
      `/api/v1/reel-projects/${projectId}/publish`,
      data
    );
    return res.data;
  }

  async scheduleReelProject(
    projectId: string,
    data: SchedulePublishJobRequest
  ): Promise<CreatePublishJobResponse> {
    const res = await this.client.post<CreatePublishJobResponse>(
      `/api/v1/reel-projects/${projectId}/schedule`,
      data
    );
    return res.data;
  }

  async cancelScheduledPublishJob(jobId: string): Promise<PublishJob> {
    const res = await this.client.delete<PublishJob>(
      `/api/v1/reel-projects/publish-jobs/${jobId}/schedule`
    );
    return res.data;
  }

  async getPublishJobs(projectId: string): Promise<PublishJob[]> {
    const res = await this.client.get<PublishJob[]>(
      `/api/v1/reel-projects/${projectId}/publish-jobs`
    );
    return res.data;
  }

  async retryPublishJob(jobId: string): Promise<PublishJob> {
    const res = await this.client.post<PublishJob>(
      `/api/v1/reel-projects/publish-jobs/${jobId}/retry`
    );
    return res.data;
  }

  // ── Billing & Usage ───────────────────────────────────────────────────────

  /**
   * Get all available plan definitions (public — no auth needed).
   */
  async getPlans(): Promise<PlanDefinition[]> {
    const res = await this.client.get<PlanDefinition[]>("/api/v1/billing/plans");
    return res.data;
  }

  /**
   * Get current usage summary for the authenticated workspace.
   * Use this to populate usage bars and upgrade CTAs.
   */
  async getUsageSummary(): Promise<UsageSummary> {
    const res = await this.client.get<UsageSummary>("/api/v1/billing/usage");
    return res.data;
  }

  async createCheckoutSession(planKey: PlanKey): Promise<CheckoutSessionResponse> {
    const res = await this.client.post<CheckoutSessionResponse>(
      "/api/v1/billing/checkout",
      { plan_key: planKey }
    );
    return res.data;
  }

  async createBillingPortalSession(): Promise<PortalSessionResponse> {
    const res = await this.client.post<PortalSessionResponse>("/api/v1/billing/portal");
    return res.data;
  }

  async devMockCheckoutComplete(planKey: PlanKey): Promise<{ message: string }> {
    const res = await this.client.post<{ message: string }>(
      "/api/v1/billing/dev/mock-checkout-complete",
      { plan_key: planKey }
    );
    return res.data;
  }

  /**
   * DEV ONLY — Override plan for the authenticated workspace.
   * Only works when backend APP_ENV=development.
   */
  async devSetPlan(planKey: PlanKey): Promise<{ message: string; plan: PlanDefinition }> {
    const res = await this.client.post<{ message: string; plan: PlanDefinition }>(
      "/api/v1/billing/dev/set-plan",
      { plan_key: planKey }
    );
    return res.data;
  }

  /**
   * DEV ONLY — Grant artificial usage for testing limit enforcement.
   * Only works when backend APP_ENV=development.
   */
  async devGrantUsage(eventType: UsageEventType, quantity: number): Promise<{ message: string }> {
    const res = await this.client.post<{ message: string }>(
      "/api/v1/billing/dev/grant-usage",
      { event_type: eventType, quantity }
    );
    return res.data;
  }
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export const apiClient = new ApiClient(API_BASE_URL);
