<script setup lang="ts">
import { computed } from "vue";
import type { VideoInfo, VideoFormat } from "../api";

const props = defineProps<{
  info: VideoInfo;
  selectedFormatId: string | null;
  downloading: boolean;
}>();

const emit = defineEmits<{
  "select-format": [formatId: string];
  download: [];
}>();

const durationText = computed(() => {
  if (!props.info.duration) return "";
  const m = Math.floor(props.info.duration / 60);
  const s = props.info.duration % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
});

// 按清晰度分组，只展示有视频流的格式
const videoFormats = computed(() => {
  return props.info.formats.filter(
    (f: VideoFormat) => f.vcodec && f.vcodec !== "none",
  );
});

const audioFormats = computed(() => {
  return props.info.formats.filter(
    (f: VideoFormat) => (!f.vcodec || f.vcodec === "none") && f.acodec && f.acodec !== "none",
  );
});

function formatSize(bytes: number | null): string {
  if (!bytes) return "";
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)}KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)}MB`;
  return `${(bytes / 1024 / 1024 / 1024).toFixed(2)}GB`;
}

function selectBest() {
  if (props.info.best_format_id) {
    emit("select-format", props.info.best_format_id);
  } else if (videoFormats.value.length > 0) {
    emit("select-format", videoFormats.value[0].format_id);
  }
}
</script>

<template>
  <div class="card overflow-hidden">
    <!-- 封面图 -->
    <div class="relative aspect-video bg-gray-100">
      <img
        v-if="info.thumbnail"
        :src="info.thumbnail"
        :alt="info.title"
        class="w-full h-full object-cover"
        referrerpolicy="no-referrer"
      />
      <div class="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent" />
      <!-- 时长标签 -->
      <span v-if="durationText" class="absolute bottom-3 right-3 px-2 py-1 rounded-md bg-black/70 text-white text-xs font-medium">
        {{ durationText }}
      </span>
      <!-- 平台标签 -->
      <span class="absolute top-3 left-3 px-3 py-1 rounded-full bg-brand/90 text-white text-xs font-medium backdrop-blur-sm">
        {{ info.extractor }}
      </span>
    </div>

    <!-- 视频信息 -->
    <div class="p-5">
      <h3 class="text-lg font-bold text-brand-dark line-clamp-2 mb-2">{{ info.title }}</h3>

      <div class="flex items-center gap-4 text-sm text-gray-500 mb-4">
        <span v-if="info.uploader" class="flex items-center gap-1">
          <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
          </svg>
          {{ info.uploader }}
        </span>
        <span v-if="info.view_count" class="flex items-center gap-1">
          <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            <path stroke-linecap="round" stroke-linejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
          </svg>
          {{ info.view_count.toLocaleString() }}
        </span>
      </div>

      <!-- 格式选择 -->
      <div class="space-y-3">
        <div class="flex items-center justify-between">
          <span class="text-sm font-semibold text-gray-700">选择清晰度</span>
          <button
            v-if="!selectedFormatId"
            class="text-xs text-brand font-medium hover:underline"
            @click="selectBest"
          >
            自动选择最佳
          </button>
        </div>

        <div class="grid grid-cols-2 sm:grid-cols-3 gap-2">
          <button
            v-for="f in videoFormats.slice(0, 9)"
            :key="f.format_id"
            class="px-3 py-2.5 rounded-xl border text-sm font-medium transition-all text-left"
            :class="selectedFormatId === f.format_id
              ? 'border-brand bg-brand-light/50 text-brand ring-2 ring-brand/20'
              : 'border-gray-200 text-gray-600 hover:border-brand/40 hover:bg-gray-50'"
            @click="emit('select-format', f.format_id)"
          >
            <div class="font-semibold">{{ f.resolution }}</div>
            <div class="text-xs text-gray-400 mt-0.5">
              {{ f.ext }}<span v-if="formatSize(f.filesize)"> · {{ formatSize(f.filesize) }}</span>
            </div>
          </button>
        </div>

        <!-- 仅音频 -->
        <details v-if="audioFormats.length > 0" class="mt-2">
          <summary class="text-sm text-gray-500 cursor-pointer hover:text-brand">仅提取音频</summary>
          <div class="grid grid-cols-2 sm:grid-cols-3 gap-2 mt-2">
            <button
              v-for="f in audioFormats.slice(0, 3)"
              :key="f.format_id"
              class="px-3 py-2 rounded-xl border text-sm transition-all"
              :class="selectedFormatId === f.format_id
                ? 'border-brand bg-brand-light/50 text-brand'
                : 'border-gray-200 text-gray-600 hover:border-brand/40'"
              @click="emit('select-format', f.format_id)"
            >
              音频 {{ f.ext }}
            </button>
          </div>
        </details>
      </div>

      <!-- 下载按钮 -->
      <button
        class="btn-primary w-full mt-5"
        :disabled="downloading || !selectedFormatId"
        @click="emit('download')"
      >
        <svg v-if="downloading" class="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
        <svg v-else class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 3v12m0 0l-4-4m4 4l4-4M3 17v3a1 1 0 001 1h16a1 1 0 001-1v-3" />
        </svg>
        {{ downloading ? "下载中..." : "立即下载" }}
      </button>
    </div>
  </div>
</template>
