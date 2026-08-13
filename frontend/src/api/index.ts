import axios from "axios";

export const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

const api = axios.create({
  baseURL: API_BASE,
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

export interface AISummaryResult {
  title: string | null;
  summary: string;
  subtitle_lang: string;
}

export interface SubtitleSegment {
  start: number;
  end: number;
  text: string;
}

export interface AITranslateResult {
  title: string | null;
  target_lang: string;
  segments: SubtitleSegment[];
}

export async function summarizeVideo(url: string): Promise<AISummaryResult> {
  const res = await api.post("/api/ai/summary", { url }, { timeout: 180000 });
  return res.data.data;
}

export async function translateSubtitles(
  url: string,
  targetLang: string,
): Promise<AITranslateResult> {
  const res = await api.post(
    "/api/ai/translate",
    { url, target_lang: targetLang },
    { timeout: 180000 },
  );
  return res.data.data;
}



export interface ReferenceFrame {
  time: number;
  url: string;
}

export interface ManhuaCharacter {
  name: string;
  role: string;
  desc: string;
}

export interface ManhuaPanel {
  index: number;
  time: number;
  scene: string;
  dialogue: string;
  narration: string;
  emotion: string;
  visual: string;
}

export interface ManhuaResult {
  title: string;
  style: string;
  panels_count: number;
  synopsis: string;
  characters: ManhuaCharacter[];
  panels: ManhuaPanel[];
  reference_frames?: ReferenceFrame[];
  generated_at: number;
}

export async function generateManhua(
  url: string,
  style: string,
  panels: number,
): Promise<ManhuaResult> {
  const res = await api.post(
    "/api/ai/manhua",
    { url, style, panels },
    { timeout: 300000 },
  );
  return res.data.data;
}
