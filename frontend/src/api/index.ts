import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || "http://localhost:8000",
  timeout: 120000,
});

export interface VideoFormat {
  format_id: string;
  ext: string;
  resolution: string;
  fps: number | null;
  vcodec: string | null;
  acodec: string | null;
  filesize: number | null;
  url: string | null;
  tbr: number | null;
}

export interface VideoInfo {
  id: string;
  title: string;
  thumbnail: string | null;
  duration: number | null;
  uploader: string | null;
  uploader_url: string | null;
  webpage_url: string;
  extractor: string;
  extractor_key: string;
  view_count: number | null;
  like_count: number | null;
  description: string;
  formats: VideoFormat[];
  best_format_id: string | null;
  subtitles: string[];
  automatic_captions: string[];
}

export interface TaskInfo {
  task_id: string;
  url: string;
  status: "pending" | "downloading" | "completed" | "failed";
  progress: number;
  filename: string | null;
  error: string | null;
  created_at: number;
  completed_at: number | null;
}

export async function parseVideo(url: string): Promise<VideoInfo> {
  const res = await api.post("/api/parse", { url });
  return res.data.data;
}

export async function downloadVideo(url: string, formatId?: string): Promise<Blob> {
  const res = await api.post(
    "/api/download",
    { url, format_id: formatId || null },
    { responseType: "blob", timeout: 600000 },
  );
  return res.data;
}

export async function submitTask(url: string, formatId?: string): Promise<TaskInfo> {
  const res = await api.post("/api/task", { url, format_id: formatId || null });
  return res.data.data;
}

export async function getTask(taskId: string): Promise<TaskInfo> {
  const res = await api.get(`/api/task/${taskId}`);
  return res.data.data;
}

export async function listTasks(): Promise<TaskInfo[]> {
  const res = await api.get("/api/tasks");
  return res.data.data;
}

export async function getFileUrl(taskId: string): Promise<{ url: string; filename: string }> {
  const res = await api.get(`/api/file/${taskId}`);
  return res.data.data;
}
