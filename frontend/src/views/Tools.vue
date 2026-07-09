<script setup lang="ts">
import { ref } from "vue";

const url = ref("");
const loading = ref(false);
const result = ref<string | null>(null);
const error = ref<string | null>(null);
const targetLang = ref("zh");
const activeTab = ref<"summary" | "translate">("summary");

const langs = [
  { code: "zh", label: "中文" },
  { code: "en", label: "English" },
  { code: "ja", label: "日本語" },
];

async function handleSubmit() {
  if (!url.value.trim()) return;
  loading.value = true;
  error.value = null;
  result.value = null;
  // TODO: 阶段 5 对接后端 AI 接口
  await new Promise((r) => setTimeout(r, 1500));
  result.value = "AI 功能将在阶段 5 上线，敬请期待！";
  loading.value = false;
}
</script>

<template>
  <div class="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
    <div class="text-center mb-10">
      <div class="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-amber-50 text-amber-600 text-xs font-medium mb-4">
        <svg class="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
          <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
        </svg>
        VIP 专享功能
      </div>
      <h1 class="text-3xl font-bold text-brand-dark mb-3">AI 智能工具</h1>
      <p class="text-gray-500">视频总结、字幕翻译，让 AI 帮你理解视频内容</p>
    </div>

    <!-- Tab 切换 -->
    <div class="flex gap-2 mb-6 p-1 bg-gray-100 rounded-xl">
      <button
        v-for="tab in [{ key: 'summary', label: '视频总结' }, { key: 'translate', label: '字幕翻译' }]"
        :key="tab.key"
        class="flex-1 py-2.5 rounded-lg text-sm font-medium transition-all"
        :class="activeTab === tab.key ? 'bg-white text-brand shadow-sm' : 'text-gray-500'"
        @click="activeTab = tab.key as any"
      >
        {{ tab.label }}
      </button>
    </div>

    <div class="card p-6">
      <input
        v-model="url"
        type="text"
        placeholder="粘贴视频链接"
        class="input-base mb-4"
      />

      <!-- 语言选择（字幕翻译） -->
      <div v-if="activeTab === 'translate'" class="mb-4">
        <label class="text-sm text-gray-600 mb-2 block">翻译为</label>
        <div class="flex gap-2">
          <button
            v-for="lang in langs"
            :key="lang.code"
            class="px-4 py-2 rounded-xl text-sm font-medium transition-all"
            :class="targetLang === lang.code
              ? 'bg-brand text-white'
              : 'bg-gray-100 text-gray-600 hover:bg-gray-200'"
            @click="targetLang = lang.code"
          >
            {{ lang.label }}
          </button>
        </div>
      </div>

      <button
        class="btn-primary w-full"
        :disabled="loading || !url.trim()"
        @click="handleSubmit"
      >
        {{ loading ? "处理中..." : activeTab === "summary" ? "生成总结" : "翻译字幕" }}
      </button>

      <div v-if="error" class="mt-4 px-4 py-3 rounded-xl bg-red-50 text-red-600 text-sm">
        {{ error }}
      </div>

      <div v-if="result" class="mt-4 px-4 py-4 rounded-xl bg-brand-light/30 text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">
        {{ result }}
      </div>
    </div>
  </div>
</template>
