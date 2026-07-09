<script setup lang="ts">
import { ref } from "vue";
import { useDownloadStore } from "../stores/download";
import DownloadCard from "../components/DownloadCard.vue";

const store = useDownloadStore();
const url = ref("");
const selectedFormatId = ref<string | null>(null);

const platforms = [
  { name: "YouTube", color: "#FF0000" },
  { name: "B站", color: "#00A1D6" },
  { name: "抖音", color: "#000000" },
  { name: "Twitter/X", color: "#1DA1F2" },
  { name: "Instagram", color: "#E4405F" },
  { name: "TikTok", color: "#000000" },
  { name: "小红书", color: "#FF2442" },
  { name: "快手", color: "#FF6600" },
];

async function handleParse() {
  if (!url.value.trim()) return;
  selectedFormatId.value = null;
  await store.parse(url.value.trim());
  // 自动选中最佳格式
  if (store.videoInfo?.best_format_id) {
    selectedFormatId.value = store.videoInfo.best_format_id;
  }
}

async function handleDownload() {
  if (!store.videoInfo || !selectedFormatId.value) return;
  await store.download(store.videoInfo.webpage_url, selectedFormatId.value);
}

function handlePaste() {
  navigator.clipboard.readText().then((text) => {
    url.value = text.trim();
  });
}
</script>

<template>
  <div>
    <!-- Hero 区 -->
    <section class="relative overflow-hidden">
      <div class="absolute inset-0 bg-gradient-to-br from-brand-light/40 via-white to-brand-light/20" />
      <div class="absolute top-0 left-1/2 -translate-x-1/2 w-[600px] h-[600px] bg-brand/5 rounded-full blur-3xl" />

      <div class="relative max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 pt-16 pb-12 text-center">
        <!-- Badge -->
        <div class="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-brand-light/60 text-brand text-sm font-medium mb-6">
          <span class="flex h-2 w-2">
            <span class="animate-ping absolute inline-flex h-2 w-2 rounded-full bg-brand opacity-75" />
            <span class="relative inline-flex rounded-full h-2 w-2 bg-brand" />
          </span>
          支持 1800+ 平台 · 基于 yt-dlp
        </div>

        <h1 class="text-4xl sm:text-5xl font-bold text-brand-dark leading-tight mb-4">
          万能视频下载
          <span class="text-brand">随时随地保存</span>
        </h1>
        <p class="text-lg text-gray-500 max-w-2xl mx-auto mb-8">
          粘贴视频链接，一键解析下载。支持 YouTube、B站、抖音、Twitter 等主流平台，手机也能用。
        </p>

        <!-- URL 输入 -->
        <div class="max-w-2xl mx-auto">
          <div class="flex flex-col sm:flex-row gap-3">
            <div class="relative flex-1">
              <input
                v-model="url"
                type="text"
                placeholder="粘贴视频链接，如 https://www.bilibili.com/video/..."
                class="input-base !py-4 !text-base pr-24"
                @keyup.enter="handleParse"
              />
              <button
                class="absolute right-3 top-1/2 -translate-y-1/2 text-sm text-gray-400 hover:text-brand transition-colors"
                @click="handlePaste"
              >
                粘贴
              </button>
            </div>
            <button
              class="btn-primary !py-4 !px-8 text-base whitespace-nowrap"
              :disabled="store.loading || !url.trim()"
              @click="handleParse"
            >
              <svg v-if="store.loading" class="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              <svg v-else class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              {{ store.loading ? "解析中..." : "解析视频" }}
            </button>
          </div>

          <!-- 错误提示 -->
          <div v-if="store.error" class="mt-4 px-4 py-3 rounded-xl bg-red-50 text-red-600 text-sm flex items-center gap-2">
            <svg class="w-5 h-5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            {{ store.error }}
          </div>
        </div>

        <!-- 平台展示 -->
        <div class="mt-10">
          <p class="text-sm text-gray-400 mb-4">已支持以下平台</p>
          <div class="flex flex-wrap justify-center gap-2.5">
            <span
              v-for="p in platforms"
              :key="p.name"
              class="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full bg-white border border-gray-100 text-sm font-medium text-gray-600 shadow-sm hover:shadow-md transition-shadow"
            >
              <span class="w-2 h-2 rounded-full" :style="{ backgroundColor: p.color }" />
              {{ p.name }}
            </span>
          </div>
        </div>
      </div>
    </section>

    <!-- 解析结果 -->
    <section v-if="store.videoInfo" class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 pb-16">
      <div class="flex items-center gap-2 mb-5">
        <div class="w-1 h-6 rounded-full bg-brand" />
        <h2 class="text-xl font-bold text-brand-dark">解析结果</h2>
      </div>

      <DownloadCard
        :info="store.videoInfo"
        :selected-format-id="selectedFormatId"
        :downloading="store.downloading"
        @select-format="selectedFormatId = $event"
        @download="handleDownload"
      />

      <!-- 下载错误 -->
      <div v-if="store.error && store.downloading === false" class="mt-4 px-4 py-3 rounded-xl bg-red-50 text-red-600 text-sm">
        下载失败：{{ store.error }}
      </div>
    </section>

    <!-- 功能特性（无解析结果时展示） -->
    <section v-else class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 pb-16">
      <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div class="card p-6 text-center">
          <div class="w-12 h-12 rounded-2xl bg-brand-light flex items-center justify-center mx-auto mb-4">
            <svg class="w-6 h-6 text-brand" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
          </div>
          <h3 class="font-semibold text-brand-dark mb-2">极速下载</h3>
          <p class="text-sm text-gray-500">智能选择最快下载路径，直链优先，自动回退代理</p>
        </div>
        <div class="card p-6 text-center">
          <div class="w-12 h-12 rounded-2xl bg-brand-light flex items-center justify-center mx-auto mb-4">
            <svg class="w-6 h-6 text-brand" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" />
            </svg>
          </div>
          <h3 class="font-semibold text-brand-dark mb-2">多格式选择</h3>
          <p class="text-sm text-gray-500">支持多种清晰度和格式，包括仅提取音频</p>
        </div>
        <div class="card p-6 text-center">
          <div class="w-12 h-12 rounded-2xl bg-brand-light flex items-center justify-center mx-auto mb-4">
            <svg class="w-6 h-6 text-brand" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2H5a2 2 0 00-2-2z" />
              <path stroke-linecap="round" stroke-linejoin="round" d="M18 7V5a2 2 0 00-2-2H8a2 2 0 00-2 2v2" />
            </svg>
          </div>
          <h3 class="font-semibold text-brand-dark mb-2">手机可用</h3>
          <p class="text-sm text-gray-500">响应式设计，手机浏览器直接访问，随时下载</p>
        </div>
      </div>
    </section>
  </div>
</template>
