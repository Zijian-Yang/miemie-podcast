export const API_BASE_URL = "/__miemie_api";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

export async function apiRequest<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
    ...init,
  });

  if (!response.ok) {
    let message = response.statusText;
    try {
      const raw = await response.text();
      if (raw) {
        try {
          const payload = JSON.parse(raw) as { detail?: string; message?: string };
          message = payload.detail || payload.message || raw || message;
        } catch {
          message = raw;
        }
      }
    } catch {
      message = response.statusText;
    }
    throw new ApiError(message, response.status);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export type EpisodeListItem = {
  id: string;
  source_url: string;
  source_type: string;
  source_episode_id: string;
  podcast_title: string;
  episode_title: string;
  cover_image_url: string;
  audio_url: string;
  published_at?: string | null;
  duration_seconds?: number | null;
  status: string;
  processing_stage: string;
  current_stage: string;
  current_stage_label: string;
  progress_percent: number;
  last_error?: string | null;
  failure_code?: string | null;
  failure_message?: string | null;
  updated_at: string;
};

export type EpisodeDetail = {
  episode: EpisodeListItem;
  modules: {
    module_key: string;
    display_name: string;
    version: string;
    format: string;
    status: string;
    content_json: Record<string, unknown>;
    rendered_markdown?: string | null;
    rendered_html?: string | null;
    manifest: {
      module_key: string;
      display_name: string;
      description: string;
      copy_markdown: boolean;
      viewable: boolean;
      supports_html_view: boolean;
      supports_png_export: boolean;
      transcript_fidelity?: string | null;
    };
    artifacts: {
      artifact_key: string;
      format: string;
      mime_type: string;
      download_url: string;
      size_bytes: number;
    }[];
    citations_json: Array<Record<string, unknown>>;
  }[];
  transcript_chunks: {
    id: string;
    chunk_index: number;
    start_ms: number;
    end_ms: number;
    text: string;
    metadata: Record<string, unknown>;
  }[];
  artifacts: {
    artifact_key: string;
    format: string;
    mime_type: string;
    download_url: string;
    size_bytes: number;
  }[];
};
