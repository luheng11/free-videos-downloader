<script setup lang="ts">
const plans = [
  {
    name: "免费版",
    price: "0",
    period: "永久免费",
    features: [
      { text: "每日 3 次下载", included: true },
      { text: "基础清晰度", included: true },
      { text: "单视频下载", included: true },
      { text: "批量下载", included: false },
      { text: "AI 视频总结", included: false },
      { text: "字幕翻译", included: false },
    ],
    cta: "当前方案",
    highlight: false,
  },
  {
    name: "会员版",
    price: "29",
    period: "/ 月",
    features: [
      { text: "无限次下载", included: true },
      { text: "最高清晰度", included: true },
      { text: "单视频下载", included: true },
      { text: "批量下载", included: true },
      { text: "AI 视频总结", included: true },
      { text: "字幕翻译", included: true },
    ],
    cta: "立即升级",
    highlight: true,
  },
];
</script>

<template>
  <div class="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
    <div class="text-center mb-10">
      <h1 class="text-3xl font-bold text-brand-dark mb-3">选择适合你的方案</h1>
      <p class="text-gray-500">解锁全部功能，享受无限下载体验</p>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-2 gap-6 max-w-3xl mx-auto">
      <div
        v-for="plan in plans"
        :key="plan.name"
        class="card p-8 relative"
        :class="plan.highlight ? 'ring-2 ring-brand shadow-lg' : ''"
      >
        <div v-if="plan.highlight" class="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-1 rounded-full bg-brand text-white text-xs font-medium">
          推荐
        </div>

        <h3 class="text-lg font-bold text-brand-dark mb-1">{{ plan.name }}</h3>
        <div class="flex items-baseline gap-1 mb-6">
          <span class="text-3xl font-bold text-brand-dark">{{ plan.price === '0' ? '免费' : '¥' + plan.price }}</span>
          <span class="text-sm text-gray-400">{{ plan.period }}</span>
        </div>

        <ul class="space-y-3 mb-8">
          <li
            v-for="f in plan.features"
            :key="f.text"
            class="flex items-center gap-2.5 text-sm"
            :class="f.included ? 'text-gray-700' : 'text-gray-300'"
          >
            <svg v-if="f.included" class="w-5 h-5 text-brand shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
            </svg>
            <svg v-else class="w-5 h-5 text-gray-300 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
            {{ f.text }}
          </li>
        </ul>

        <button
          class="w-full py-3 rounded-full font-medium text-sm transition-all"
          :class="plan.highlight
            ? 'bg-brand text-white hover:shadow-lg hover:shadow-brand/30 active:scale-95'
            : 'bg-gray-100 text-gray-500 cursor-default'"
        >
          {{ plan.cta }}
        </button>
      </div>
    </div>

    <!-- FAQ -->
    <div class="mt-16">
      <h2 class="text-xl font-bold text-brand-dark text-center mb-6">常见问题</h2>
      <div class="max-w-2xl mx-auto space-y-4">
        <div class="card p-5">
          <h4 class="font-semibold text-gray-700 mb-1">支持哪些平台？</h4>
          <p class="text-sm text-gray-500">基于 yt-dlp，支持 YouTube、B站、抖音、Twitter 等 1800+ 平台。</p>
        </div>
        <div class="card p-5">
          <h4 class="font-semibold text-gray-700 mb-1">手机能用吗？</h4>
          <p class="text-sm text-gray-500">可以，网站响应式设计，手机浏览器直接访问即可使用。</p>
        </div>
        <div class="card p-5">
          <h4 class="font-semibold text-gray-700 mb-1">下载的文件会保存多久？</h4>
          <p class="text-sm text-gray-500">服务器代理下载的文件会在 10 分钟后自动清理，直链下载不经过服务器。</p>
        </div>
      </div>
    </div>
  </div>
</template>
