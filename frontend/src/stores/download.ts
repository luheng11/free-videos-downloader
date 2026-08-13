import { defineStore } from "pinia";
import { ref } from "vue";
import type { VideoInfo, TaskInfo } from "../api";
import { parseVideo, submitTask, getTask, downloadVideo, getFileUrl as fetchFileUrl } from "../api";

export const useDownloadStore = defineStore("download", () => {
  const loading = ref(false);
  const error = ref<string | null>(null);
  const videoInfo = ref<VideoInfo | null>(null);
  const downloading = ref(false);
  const downloadProgress = ref(0);
  const currentTask = ref<TaskInfo | null>(null);
  const history = ref<HistoryItem[]>(loadHistory());

  async function parse(url: string) {
    loading.value = true;
    error.value = null;
    videoInfo.value = null;
    try {
      videoInfo.value = await parseVideo(url);
    } catch (e: any) {
      error.value = e?.response?.data?.detail || e?.message || "解析失败";
    } finally {
      loading.value = false;
    }
  }

  async function download(url: string, formatId?: string) {
    downloading.value = true;
    downloadProgress.value = 0;
    error.value = null;
    try {
      // 先尝试直链/智能下载（返回 blob）
      const blob = await downloadVideo(url, formatId);
      downloadProgress.value = 100;

      // 触发浏览器下载
      const filename = videoInfo.value
        ? `${videoInfo.value.title}.${getExt(formatId)}`
        : "video.mp4";
      triggerDownload(blob, filename);

      // 记录历史
      addHistory(
        {
          title: videoInfo.value?.title || url,
          url,
          formatId: formatId || "best",
          timestamp: Date.now(),
        },
        history,
      );
    } catch (e: any) {
      error.value = e?.response?.data?.detail || e?.message || "下载失败";
    } finally {
      downloading.value = false;
    }
  }

  async function downloadViaTask(url: string, formatId?: string) {
    downloading.value = true;
    error.value = null;
    try {
      const task = await submitTask(url, formatId);
      currentTask.value = task;

      // 轮询任务状态
      while (true) {
        await new Promise((r) => setTimeout(r, 1500));
        const t = await getTask(task.task_id);
        currentTask.value = t;
        if (t.status === "completed") {
          downloadProgress.value = 100;
          const { url: fileUrl, filename } = await fetchFileUrl(task.task_id);
          const link = document.createElement("a");
          link.href = (import.meta.env.VITE_API_BASE || "http://localhost:8000") + fileUrl;
          link.download = filename;
          link.click();
          addHistory(
            {
              title: videoInfo.value?.title || url,
              url,
              formatId: formatId || "best",
              timestamp: Date.now(),
            },
            history,
          );
          break;
        }
        if (t.status === "failed") {
          throw new Error(t.error || "下载失败");
        }
      }
    } catch (e: any) {
      error.value = e?.message || "下载失败";
    } finally {
      downloading.value = false;
    }
  }

  function reset() {
    videoInfo.value = null;
    error.value = null;
    downloadProgress.value = 0;
    currentTask.value = null;
  }

  return {
    loading,
    error,
    videoInfo,
    downloading,
    downloadProgress,
    currentTask,
    history,
    parse,
    download,
    downloadViaTask,
    reset,
  };
});

interface HistoryItem {
  title: string;
  url: string;
  formatId: string;
  timestamp: number;
}

function loadHistory(): HistoryItem[] {
  try {
    const raw = localStorage.getItem("download_history");
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function addHistory(item: HistoryItem, history: { value: HistoryItem[] }) {
  const list = loadHistory();
  list.unshift(item);
  history.value = list.slice(0, 50);
  localStorage.setItem("download_history", JSON.stringify(history.value));
}

function triggerDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 5000);
}

function getExt(formatId?: string): string {
  if (!formatId) return "mp4";
  return "mp4";
}
