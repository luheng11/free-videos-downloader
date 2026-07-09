<script setup lang="ts">
import { ref } from "vue";
import { useDownloadStore } from "../stores/download";

const store = useDownloadStore();
const urls = ref("");
const batchResults = ref<{ url: string; status: "pending" | "success" | "error"; message?: string }[]>([]);

async function handleBatchDownload() {
  const urlList = urls.value
    .split("\n")
    .map((u) => u.trim())
    .filter(Boolean);

  if (urlList.length === 0) return;

  batchResults.value = urlList.map((url) => ({ url, status: "pending" }));

  for (let i = 0; i < urlList.length; i++) {
    try {
      await store.parse(urlList[i]);
      if (store.videoInfo?.best_format_id) {
        await store.download(urlList[i], store.videoInfo.best_format_id);
        batchResults.value[i].status = "success";
        batchResults.value[i].message = store.videoInfo.title;
      }
    } catch (e: any) {
      batchResults.value[i].status = "error";
      batchResults.value[i].message = e?.message || "失败";
    }
  }
}
</script>

<template>
  <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
    <div class="text-center mb-10">
      <div class="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-amber-50 text-amber-600 text-xs font-medium mb-4">
        <svg class="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
          <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
        </svg>
        VIP 专享功能
      </div>
      <h1 class="text-3xl font-bold text-brand-dark mb-3">批量下载</h1>
      <p class="text-gray-500">每行一个链接，自动解析并批量下载</p>
    </div>

    <div class="card p-6">
      <textarea
        v-model="urls"
        rows="8"
        placeholder="每行粘贴一个视频链接&#10;https://www.bilibili.com/video/xxx&#10;https://www.youtube.com/watch?v=xxx"
        class="input-base resize-none font-mono text-sm"
      />

      <div class="flex items-center justify-between mt-4">
        <span class="text-sm text-gray-400">
          {{ urls.split("\n").filter((u) => u.trim()).length }} 个链接
        </span>
        <button
          class="btn-primary"
          :disabled="store.downloading || !urls.trim()"
          @click="handleBatchDownload"
        >
          {{ store.downloading ? "下载中..." : "批量下载" }}
        </button>
      </div>
    </div>

    <!-- 批量结果 -->
    <div v-if="batchResults.length > 0" class="mt-6 space-y-2">
      <div
        v-for="(item, idx) in batchResults"
        :key="idx"
        class="card p-4 flex items-center gap-3"
      >
        <div class="w-8 h-8 rounded-full flex items-center justify-center shrink-0"
          :class="item.status === 'success' ? 'bg-green-50' : item.status === 'error' ? 'bg-red-50' : 'bg-blue-50'">
          <svg v-if="item.status === 'success'" class="w-4 h-4 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
          </svg>
          <svg v-else-if="item.status === 'error'" class="w-4 h-4 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
          <svg v-else class="animate-spin w-4 h-4 text-brand" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
        </div>
        <div class="flex-1 min-w-0">
          <p class="text-sm font-medium text-gray-700 truncate">{{ item.message || item.url }}</p>
          <p class="text-xs text-gray-400 truncate">{{ item.url }}</p>
        </div>
      </div>
    </div>
  </div>
</template>
