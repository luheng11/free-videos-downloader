<script setup lang="ts">
const platforms = ["YouTube", "B站", "抖音", "Twitter/X", "Instagram", "TikTok", "小红书", "快手"];
</script>

<template>
  <footer class="border-t border-gray-100 bg-brand-dark text-gray-400">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
      <div class="grid grid-cols-1 md:grid-cols-4 gap-8">
        <div class="md:col-span-2">
          <div class="flex items-center gap-2.5 mb-4">
            <div class="w-9 h-9 rounded-xl bg-brand flex items-center justify-center">
              <svg class="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
                <path stroke-linecap="round" stroke-linejoin="round" d="M12 3v12m0 0l-4-4m4 4l4-4M3 17v3a1 1 0 001 1h16a1 1 0 001-1v-3" />
              </svg>
            </div>
            <span class="text-xl font-bold text-white">VidPull</span>
          </div>
          <p class="text-sm leading-relaxed max-w-md">
            万能视频下载工具，支持 1800+ 平台，随时随地快速下载你喜欢的视频。手机也能用。
          </p>
        </div>
        <div>
          <h4 class="text-white font-semibold mb-3 text-sm">支持平台</h4>
          <div class="flex flex-wrap gap-2">
            <span v-for="p in platforms" :key="p" class="text-xs px-2.5 py-1 rounded-full bg-white/10">
              {{ p }}
            </span>
          </div>
        </div>
        <div>
          <h4 class="text-white font-semibold mb-3 text-sm">快速链接</h4>
          <ul class="space-y-2 text-sm">
            <li><RouterLink to="/" class="hover:text-brand transition-colors">视频下载</RouterLink></li>
            <li><RouterLink to="/batch" class="hover:text-brand transition-colors">批量下载</RouterLink></li>
            <li><RouterLink to="/vip" class="hover:text-brand transition-colors">会员中心</RouterLink></li>
          </ul>
        </div>
      </div>
      <div class="mt-10 pt-6 border-t border-white/10 text-xs text-center">
        <p>Powered by yt-dlp | 仅供个人学习使用，请遵守各平台版权政策</p>
      </div>
    </div>
  </footer>
</template>
