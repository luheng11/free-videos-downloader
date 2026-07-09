<script setup lang="ts">
import { ref } from "vue";
import { RouterLink, useRoute } from "vue-router";

const route = useRoute();
const mobileOpen = ref(false);

const navItems = [
  { to: "/", label: "视频下载", icon: "download" },
  { to: "/batch", label: "批量下载", icon: "batch" },
  { to: "/tools", label: "AI 工具", icon: "tools" },
  { to: "/vip", label: "会员中心", icon: "vip" },
];
</script>

<template>
  <header class="sticky top-0 z-50 bg-white/80 backdrop-blur-lg border-b border-gray-100">
    <nav class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div class="flex items-center justify-between h-16">
        <!-- Logo -->
        <RouterLink to="/" class="flex items-center gap-2.5 shrink-0">
          <div class="w-9 h-9 rounded-xl bg-brand flex items-center justify-center">
            <svg class="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 3v12m0 0l-4-4m4 4l4-4M3 17v3a1 1 0 001 1h16a1 1 0 001-1v-3" />
            </svg>
          </div>
          <span class="text-xl font-bold text-brand-dark">VidPull</span>
        </RouterLink>

        <!-- Desktop Nav -->
        <div class="hidden md:flex items-center gap-1">
          <RouterLink
            v-for="item in navItems"
            :key="item.to"
            :to="item.to"
            class="px-4 py-2 rounded-full text-sm font-medium transition-all"
            :class="route.path === item.to
              ? 'bg-brand text-white shadow-md shadow-brand/30'
              : 'text-gray-600 hover:text-brand hover:bg-brand-light/50'"
          >
            {{ item.label }}
          </RouterLink>
        </div>

        <!-- CTA -->
        <div class="hidden md:flex items-center gap-3">
          <RouterLink to="/vip" class="btn-primary !py-2 !px-5 text-sm">
            <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
              <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
            </svg>
            升级会员
          </RouterLink>
        </div>

        <!-- Mobile toggle -->
        <button class="md:hidden p-2 text-gray-600" @click="mobileOpen = !mobileOpen">
          <svg class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path v-if="!mobileOpen" stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 12h16M4 18h16" />
            <path v-else stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <!-- Mobile Nav -->
      <div v-if="mobileOpen" class="md:hidden pb-4 space-y-1">
        <RouterLink
          v-for="item in navItems"
          :key="item.to"
          :to="item.to"
          class="block px-4 py-3 rounded-xl text-sm font-medium transition-all"
          :class="route.path === item.to
            ? 'bg-brand text-white'
            : 'text-gray-600 hover:bg-gray-50'"
          @click="mobileOpen = false"
        >
          {{ item.label }}
        </RouterLink>
      </div>
    </nav>
  </header>
</template>
