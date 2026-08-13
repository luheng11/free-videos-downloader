<script setup lang="ts">
import { ref } from "vue";
import { summarizeVideo, translateSubtitles, generateManhua, API_BASE } from "../api";
import type {
  AISummaryResult,
  AITranslateResult,
  SubtitleSegment,
  ManhuaResult,
} from "../api";

const url = ref("");
const loading = ref(false);
const error = ref<string | null>(null);
const targetLang = ref("zh");
const style = ref("guoman");
const panels = ref(8);
const activeTab = ref<"summary" | "translate" | "manhua">("summary");
const summaryResult = ref<AISummaryResult | null>(null);
const translateResult = ref<AITranslateResult | null>(null);
const manhuaResult = ref<ManhuaResult | null>(null);

const langs = [
  { code: "zh", label: "中文" },
  { code: "en", label: "English" },
  { code: "ja", label: "日本語" },
];

const styles = [
  { code: "guoman", label: "国漫" },
  { code: "riman", label: "日漫" },
  { code: "qban", label: "Q版" },
  { code: "hanman", label: "韩漫" },
];

const panelOptions = [6, 8, 12];

async function handleSubmit() {
  const link = url.value.trim();
  if (!link) return;
  loading.value = true;
  error.value = null;
  summaryResult.value = null;
  translateResult.value = null;
  manhuaResult.value = null;
  try {
    if (activeTab.value === "summary") {
      summaryResult.value = await summarizeVideo(link);
    } else if (activeTab.value === "translate") {
      translateResult.value = await translateSubtitles(link, targetLang.value);
    } else {
      manhuaResult.value = await generateManhua(link, style.value, panels.value);
    }
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || "处理失败，请稍后重试";
  } finally {
    loading.value = false;
  }
}

function frameUrl(u: string): string {
  if (!u) return "";
  return u.startsWith("http") ? u : API_BASE + u;
}

function formatTime(sec: number): string {
  if (!isFinite(sec) || sec < 0) return "00:00";
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return String(m).padStart(2, "0") + ":" + String(s).padStart(2, "0");
}

function formatSrtTime(sec: number): string {
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = Math.floor(sec % 60);
  const ms = Math.round((sec - Math.floor(sec)) * 1000);
  return (
    String(h).padStart(2, "0") + ":" +
    String(m).padStart(2, "0") + ":" +
    String(s).padStart(2, "0") + "," +
    String(ms).padStart(3, "0")
  );
}

function buildSrt(segments: SubtitleSegment[]): string {
  return (
    segments
      .map(
        (seg, i) =>
          (i + 1) + "\n" +
          formatSrtTime(seg.start) + " --> " + formatSrtTime(seg.end) + "\n" +
          seg.text,
      )
      .join("\n\n") + "\n"
  );
}

function downloadSrt() {
  if (!translateResult.value?.segments?.length) return;
  const content = buildSrt(translateResult.value.segments);
  const blob = new Blob(["\ufeff" + content], { type: "text/plain;charset=utf-8" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = "subtitle.srt";
  link.click();
  setTimeout(() => URL.revokeObjectURL(link.href), 5000);
}

function buildManhuaMarkdown(r: ManhuaResult): string {
  const lines: string[] = [];
  lines.push("# " + r.title);
  lines.push("");
  lines.push("- 风格：" + r.style);
  lines.push("- 分镜数：" + String(r.panels_count));
  lines.push("");
  lines.push("## 剧情梗概");
  lines.push(r.synopsis || "（无）");
  lines.push("");
  lines.push("## 角色设定");
  if (r.characters?.length) {
    for (const c of r.characters) {
      lines.push("- **" + c.name + "**（" + (c.role || "角色") + "）：" + (c.desc || ""));
    }
  } else {
    lines.push("（无）");
  }
  lines.push("");
  lines.push("## 分镜");
  for (const p of r.panels || []) {
    lines.push("### 第 " + p.index + " 格（" + p.time + "s）");
    lines.push("- 场景：" + (p.scene || ""));
    lines.push("- 对白：" + (p.dialogue || ""));
    lines.push("- 旁白：" + (p.narration || ""));
    lines.push("- 情绪：" + (p.emotion || ""));
    lines.push("- 画面：" + (p.visual || ""));
    lines.push("");
  }
  return lines.join("\n");
}

function downloadManhuaMd() {
  if (!manhuaResult.value) return;
  const content = buildManhuaMarkdown(manhuaResult.value);
  const blob = new Blob(["\ufeff" + content], { type: "text/markdown;charset=utf-8" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = "manhua_script.md";
  link.click();
  setTimeout(() => URL.revokeObjectURL(link.href), 5000);
}

function buildPromptPack(r: ManhuaResult): string {
  const styleHint: Record<string, string> = {
    guoman: "国漫写实插图风，线条干净，色彩明快，角色俊美",
    riman: "日系赛璐璐/萌系二次元画风",
    qban: "大头Q版搞笑风，头身比约1:2，圆润可爱",
    hanman: "韩漫厚涂风，光影细腻，高颜值",
    国漫: "国漫写实插图风，线条干净，色彩明快，角色俊美",
    日漫: "日系赛璐璐/萌系二次元画风",
    Q版: "大头Q版搞笑风，头身比约1:2，圆润可爱",
    韩漫: "韩漫厚涂风，光影细腻，高颜值",
  };
  const hint = styleHint[r.style] || "漫画风";
  const L: string[] = [];
  L.push("# 漫剧出图提示词包：" + r.title);
  L.push("");
  L.push("画风：" + r.style + "（" + hint + "）");
  L.push("分镜：" + r.panels_count + " 格");
  L.push("");
  L.push("## 使用步骤");
  L.push("0. 先下载本页「参考帧」图片（选角色正脸最清晰的一张），作为角色参考图；");
  L.push("1. 打开 Grok（App 或网页），新建对话，上传参考帧，先输入：“把图中角色形象用" + hint + "重绘，保持人物形象一致”；");
  L.push("2. 逐格复制下方提示词粘贴给 Grok 生成（保持同一对话，角色更稳定）；");
  L.push("3. 若某格角色走样，重新上传参考帧并补一句“按参考图中的人物形象来画”；");
  L.push("4. 全部生成后，按分镜顺序把图导入剪映/CapCut，用 AI 配音读对白/旁白、加字幕和转场，导出竖屏视频。");
  L.push("");
  L.push("> 提示：让画面保持“无文字”，对白交给后期字幕/配音，避免 AI 中文文字乱码。");
  L.push("");
  L.push("## 角色外貌参考（无参考帧时的文字备选）");
  for (const c of r.characters || []) {
    L.push("- **" + c.name + "**（" + (c.role || "角色") + "）：" + (c.desc || "") + "。");
  }
  L.push("");
  L.push("## 逐格提示词");
  for (const p of r.panels || []) {
    L.push("### 第 " + p.index + " 格（约 " + p.time + "s）");
    L.push("提示词：按参考帧中的角色形象绘制：" + (p.visual || p.scene || ""));
    L.push("画风：" + hint + "，角色外貌严格按参考帧。");
    L.push("构图：竖版 9:16 漫画分镜，电影感构图，情绪氛围" + (p.emotion || "自然") + "。画面中不要出现任何文字或对白气泡。");
    L.push("");
  }
  return L.join("\n");
}

function downloadPromptPack() {
  if (!manhuaResult.value) return;
  const content = buildPromptPack(manhuaResult.value);
  const blob = new Blob(["\ufeff" + content], { type: "text/markdown;charset=utf-8" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = "manhua_prompt_pack.md";
  link.click();
  setTimeout(() => URL.revokeObjectURL(link.href), 5000);
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
      <p class="text-gray-500">视频总结、字幕翻译、漫剧创作，让 AI 帮你理解与再创作视频内容</p>
    </div>

    <!-- Tab 切换 -->
    <div class="flex gap-2 mb-6 p-1 bg-gray-100 rounded-xl">
      <button
        v-for="tab in [
          { key: 'summary', label: '视频总结' },
          { key: 'translate', label: '字幕翻译' },
          { key: 'manhua', label: '漫剧创作' },
        ]"
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

      <!-- 画风 + 分镜数（漫剧创作） -->
      <div v-if="activeTab === 'manhua'" class="mb-4 grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label class="text-sm text-gray-600 mb-2 block">画风</label>
          <div class="flex gap-2">
            <button
              v-for="s in styles"
              :key="s.code"
              class="px-4 py-2 rounded-xl text-sm font-medium transition-all"
              :class="style === s.code
                ? 'bg-brand text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'"
              @click="style = s.code"
            >
              {{ s.label }}
            </button>
          </div>
        </div>
        <div>
          <label class="text-sm text-gray-600 mb-2 block">分镜数量</label>
          <div class="flex gap-2">
            <button
              v-for="n in panelOptions"
              :key="n"
              class="px-4 py-2 rounded-xl text-sm font-medium transition-all"
              :class="panels === n
                ? 'bg-brand text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'"
              @click="panels = n"
            >
              {{ n }} 格
            </button>
          </div>
        </div>
      </div>

      <button
        class="btn-primary w-full"
        :disabled="loading || !url.trim()"
        @click="handleSubmit"
      >
        {{ loading
          ? "处理中（首次约 1-3 分钟）..."
          : activeTab === "summary"
            ? "生成总结"
            : activeTab === "translate"
              ? "翻译字幕"
              : "生成漫剧" }}
      </button>

      <div v-if="error" class="mt-4 px-4 py-3 rounded-xl bg-red-50 text-red-600 text-sm">
        {{ error }}
      </div>

      <!-- 视频总结结果 -->
      <div v-if="summaryResult" class="mt-4 px-4 py-4 rounded-xl bg-brand-light/30 text-sm text-gray-700 leading-relaxed">
        <div v-if="summaryResult.title" class="font-semibold text-brand-dark mb-2">
          {{ summaryResult.title }}
        </div>
        <div class="whitespace-pre-wrap">{{ summaryResult.summary }}</div>
        <div v-if="summaryResult.subtitle_lang" class="mt-3 text-xs text-gray-400">
          字幕语言：{{ summaryResult.subtitle_lang }}
        </div>
      </div>

      <!-- 字幕翻译结果 -->
      <div v-if="translateResult" class="mt-4 rounded-xl bg-brand-light/30 text-sm text-gray-700">
        <div class="flex items-center justify-between px-4 py-3 border-b border-brand-light/60">
          <span class="font-semibold text-brand-dark">
            {{ translateResult.title || "翻译字幕" }}
          </span>
          <button
            class="px-3 py-1.5 rounded-full bg-brand text-white text-xs font-medium hover:shadow-md transition-all"
            @click="downloadSrt"
          >
            下载 SRT
          </button>
        </div>
        <div class="max-h-96 overflow-y-auto px-4 py-3 space-y-2">
          <div
            v-for="(seg, i) in translateResult.segments"
            :key="i"
            class="flex gap-3"
          >
            <span class="text-gray-400 shrink-0 w-14 tabular-nums">{{ formatTime(seg.start) }}</span>
            <span class="leading-relaxed">{{ seg.text }}</span>
          </div>
        </div>
        <div class="px-4 py-2 text-xs text-gray-400">
          共 {{ translateResult.segments.length }} 条字幕
        </div>
      </div>

      <!-- 漫剧创作结果 -->
      <div v-if="manhuaResult" class="mt-4 rounded-xl bg-brand-light/30 text-sm text-gray-700">
        <div class="flex items-center justify-between px-4 py-3 border-b border-brand-light/60">
          <span class="font-semibold text-brand-dark">{{ manhuaResult.title || "漫剧脚本" }}</span>
          <div class="flex items-center gap-2">
            <button
              class="px-3 py-1.5 rounded-full bg-brand text-white text-xs font-medium hover:shadow-md transition-all"
              @click="downloadManhuaMd"
            >
              下载 Markdown
            </button>
            <button
              class="px-3 py-1.5 rounded-full bg-white border border-brand/30 text-brand text-xs font-medium hover:shadow-md transition-all"
              @click="downloadPromptPack"
            >
              下载出图提示词包
            </button>
          </div>
        </div>
        <div class="px-4 py-4 space-y-4">
          <div>
            <div class="text-xs text-gray-400 mb-1">画风：{{ manhuaResult.style }} · 分镜：{{ manhuaResult.panels_count }} 格</div>
            <div class="leading-relaxed">{{ manhuaResult.synopsis }}</div>
          </div>

          <div v-if="manhuaResult.reference_frames?.length">
            <div class="text-xs font-semibold text-brand-dark mb-2">参考帧（上传到 Grok 保持角色一致）</div>
            <div class="grid grid-cols-3 gap-2">
              <a
                v-for="(f, i) in manhuaResult.reference_frames"
                :key="i"
                :href="frameUrl(f.url)"
                target="_blank"
                rel="noopener"
              >
                <img
                  :src="frameUrl(f.url)"
                  :alt="'参考帧 ' + f.time + 's'"
                  class="w-full aspect-[9/16] object-cover rounded-lg border border-brand-light"
                  loading="lazy"
                />
              </a>
            </div>
            <div class="text-xs text-gray-400 mt-1">点击查看原图，选角色正脸最清晰的一张上传到 Grok 作参考。</div>
          </div>
          <div v-if="manhuaResult.characters?.length">
            <div class="text-xs font-semibold text-brand-dark mb-2">角色设定</div>
            <div class="space-y-2">
              <div
                v-for="(c, i) in manhuaResult.characters"
                :key="i"
                class="rounded-xl bg-white/70 px-3 py-2"
              >
                <span class="font-semibold text-brand-dark">{{ c.name }}</span>
                <span v-if="c.role" class="ml-2 text-xs text-gray-400">{{ c.role }}</span>
                <div class="text-xs text-gray-500 mt-0.5">{{ c.desc }}</div>
              </div>
            </div>
          </div>
          <div>
            <div class="text-xs font-semibold text-brand-dark mb-2">分镜表</div>
            <div class="space-y-3">
              <div
                v-for="p in manhuaResult.panels"
                :key="p.index"
                class="rounded-xl bg-white/70 px-3 py-3"
              >
                <div class="flex items-center justify-between mb-1">
                  <span class="font-semibold text-brand-dark">第 {{ p.index }} 格</span>
                  <span class="text-xs text-gray-400 tabular-nums">{{ formatTime(p.time) }}</span>
                </div>
                <div class="grid grid-cols-1 gap-1 text-xs">
                  <div><span class="text-gray-400">场景：</span>{{ p.scene || "—" }}</div>
                  <div v-if="p.dialogue"><span class="text-gray-400">对白：</span>{{ p.dialogue }}</div>
                  <div v-if="p.narration"><span class="text-gray-400">旁白：</span>{{ p.narration }}</div>
                  <div><span class="text-gray-400">情绪：</span>{{ p.emotion || "—" }}</div>
                  <div><span class="text-gray-400">画面：</span>{{ p.visual || "—" }}</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
