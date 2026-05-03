/**
 * Typed API client for AI Reel Studio backend.
 * All requests include Authorization header.
 * All responses are typed via shared types.
 */

import axios, { AxiosError, AxiosInstance } from "axios";

// ── Types ─────────────────────────────────────────────────────────────────────

export interface ApiError {
  code: string;
  message: string;
  request_id: string;
  details?: Record<string, unknown>;
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
  latest_version?: ReelVersion;
  created_at: string;
  updated_at: string;
}

export type ReelProjectStatus =
  | "draft"
  | "script_generating"
  | "script_ready"
  | "video_generating"
  | "audio_generating"
  | "rendering"
  | "ready_for_review"
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
  estimated_duration: number | null;
  status: ReelProjectStatus;
  approved_at: string | null;
  created_at: string;
  updated_at: string;
}

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

export interface SocialAccount {
  id: string;
  platform: string;
  platform_username: string | null;
  platform_user_id: string;
  status: "connected" | "reconnect_required" | "error";
  token_expires_at: string | null;
  scopes: string[] | null;
  created_at: string;
}

export interface PublishJob {
  id: string;
  project_id: string;
  version_id: string;
  social_account_id: string;
  status: "queued" | "container_created" | "polling" | "published" | "failed" | "cancelled";
  ig_container_id: string | null;
  ig_media_id: string | null;
  scheduled_for: string | null;
  published_at: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreateReelProjectRequest {
  workspace_id: string;
  prompt: string;
  language?: string;
  tone?: string;
  duration_seconds?: number;
  cta_text?: string;
  title?: string;
}

export interface CreatePublishJobRequest {
  project_id: string;
  social_account_id: string;
  schedule_time?: string;
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

// ── Client ────────────────────────────────────────────────────────────────────

class ApiClient {
  private client: AxiosInstance;

  constructor(baseURL: string) {
    this.client = axios.create({
      baseURL,
      headers: { "Content-Type": "application/json" },
      timeout: 30000,
    });

    // Add auth token to every request
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
      (error: AxiosError<{ error?: ApiError, detail?: string | any }>) => {
        const apiError: ApiError = error.response?.data?.error ?? {
          code: "NETWORK_ERROR",
          message: typeof error.response?.data?.detail === "string" 
            ? error.response.data.detail 
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
    const res = await this.client.post<{ user: User; workspace: Workspace; access_token: string }>("/api/v1/auth/register", {
      email,
      password,
      full_name: fullName,
    });
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

  // ── Reel Projects ─────────────────────────────────────────────────────────

  async listReelProjects(workspaceId: string): Promise<ReelProject[]> {
    const res = await this.client.get<ReelProject[]>("/api/v1/reel-projects", {
      params: { workspace_id: workspaceId },
    });
    return res.data;
  }

  async createReelProject(data: CreateReelProjectRequest): Promise<ReelProject & { upload_url?: string; asset_id?: string }> {
    const res = await this.client.post<ReelProject & { upload_url?: string; asset_id?: string }>(
      "/api/v1/reel-projects",
      data
    );
    return res.data;
  }

  async getReelProject(id: string): Promise<ReelProject> {
    const res = await this.client.get<ReelProject>(`/api/v1/reel-projects/${id}`);
    return res.data;
  }

  async startGeneration(projectId: string): Promise<{ job_id: string; status: string }> {
    const res = await this.client.patch<{ job_id: string; status: string }>(
      `/api/v1/reel-projects/${projectId}/start-generation`
    );
    return res.data;
  }

  async retryGeneration(projectId: string): Promise<void> {
    await this.client.post(`/api/v1/reel-projects/${projectId}/retry`);
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

  // ── Social Accounts ───────────────────────────────────────────────────────

  async listSocialAccounts(): Promise<SocialAccount[]> {
    const res = await this.client.get<SocialAccount[]>("/api/v1/social-accounts");
    return res.data;
  }

  async connectInstagram(workspaceId: string): Promise<{ auth_url: string }> {
    const res = await this.client.post<{ auth_url: string }>(
      "/api/v1/social-accounts/instagram/connect",
      { workspace_id: workspaceId }
    );
    return res.data;
  }

  async disconnectSocialAccount(id: string): Promise<void> {
    await this.client.delete(`/api/v1/social-accounts/${id}`);
  }

  // ── Publish Jobs ──────────────────────────────────────────────────────────

  async createPublishJob(data: CreatePublishJobRequest): Promise<PublishJob> {
    const res = await this.client.post<PublishJob>("/api/v1/publish-jobs", data);
    return res.data;
  }

  async getPublishJob(id: string): Promise<PublishJob> {
    const res = await this.client.get<PublishJob>(`/api/v1/publish-jobs/${id}`);
    return res.data;
  }

  // ── Media Assets ──────────────────────────────────────────────────────────

  async getUploadUrl(data: {
    filename: string;
    mime_type: string;
    file_size: number;
    project_id?: string;
  }): Promise<{ asset_id: string; upload_url: string; expires_at: string }> {
    const res = await this.client.post("/api/v1/media-assets/upload-url", data);
    return res.data;
  }

  async confirmUpload(assetId: string): Promise<void> {
    await this.client.patch(`/api/v1/media-assets/${assetId}/confirm-upload`);
  }

  async uploadFileToS3(uploadUrl: string, file: File): Promise<void> {
    await axios.put(uploadUrl, file, {
      headers: { "Content-Type": file.type },
    });
  }
}

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export const apiClient = new ApiClient(API_BASE_URL);
